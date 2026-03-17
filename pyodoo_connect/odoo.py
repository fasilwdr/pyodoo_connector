from typing import Optional, Any, List, Dict, Union, Tuple
import httpx
import warnings

_sorted = sorted  # preserve built-in before OdooRecordset.sorted shadows the name


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class OdooException(Exception):
    """Base exception class for Odoo API errors"""
    pass


class OdooConnectionError(OdooException):
    """Raised when connection to Odoo server fails"""
    pass


class OdooAuthenticationError(OdooException):
    """Raised when authentication fails"""
    pass


class OdooRequestError(OdooException):
    """Raised when an API request fails"""

    def __init__(self, message: str, response: Optional[dict] = None):
        super().__init__(message)
        self.response = response


class OdooValidationError(OdooException):
    """Raised when data validation fails"""
    pass


# ---------------------------------------------------------------------------
# _FieldProxy – dual field-value / method-call proxy
# ---------------------------------------------------------------------------

class _FieldProxy:
    """
    Proxy returned by ``OdooRecord.__getattr__`` for unknown attribute names.

    * **Calling** the proxy makes a JSON-RPC method call on the record::

          partner.message_post(body="Hello")

    * **Using** the proxy as a plain value (``str()``, ``bool()``, comparison,
      iteration, …) fetches the field value from Odoo (with local caching)::

          print(partner.name)          # prints the partner name
          if partner.active: ...       # truthy check on the active field
    """

    __slots__ = ('_record', '_name')

    def __init__(self, record: 'OdooRecord', name: str):
        object.__setattr__(self, '_record', record)
        object.__setattr__(self, '_name', name)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_value(self) -> Any:
        record = object.__getattribute__(self, '_record')
        name = object.__getattribute__(self, '_name')
        return record._get_field(name)

    # ------------------------------------------------------------------
    # Method-call path
    # ------------------------------------------------------------------

    def __call__(self, *args, **kwargs) -> Any:
        record = object.__getattribute__(self, '_record')
        name = object.__getattribute__(self, '_name')
        return record._call_method(name, *args, **kwargs)

    # ------------------------------------------------------------------
    # Value path – delegate to the fetched field value
    # ------------------------------------------------------------------

    def __str__(self) -> str:
        v = self._get_value()
        return str(v) if v is not None and v is not False else ''

    def __repr__(self) -> str:
        return repr(self._get_value())

    def __bool__(self) -> bool:
        return bool(self._get_value())

    def __eq__(self, other) -> bool:
        if isinstance(other, _FieldProxy):
            return self._get_value() == other._get_value()
        return self._get_value() == other

    def __ne__(self, other) -> bool:
        return not self.__eq__(other)

    def __hash__(self) -> int:
        return hash(self._get_value())

    def __int__(self) -> int:
        return int(self._get_value())

    def __float__(self) -> float:
        return float(self._get_value())

    def __len__(self) -> int:
        return len(self._get_value())

    def __iter__(self):
        return iter(self._get_value())

    def __contains__(self, item) -> bool:
        return item in self._get_value()

    def __getitem__(self, key):
        return self._get_value()[key]

    def __lt__(self, other) -> bool:
        return self._get_value() < other

    def __le__(self, other) -> bool:
        return self._get_value() <= other

    def __gt__(self, other) -> bool:
        return self._get_value() > other

    def __ge__(self, other) -> bool:
        return self._get_value() >= other

    def __add__(self, other):
        v = self._get_value()
        return v + (other._get_value() if isinstance(other, _FieldProxy) else other)

    def __radd__(self, other):
        return other + self._get_value()

    def __getattr__(self, name: str):
        if name.startswith('_'):
            raise AttributeError(name)
        return getattr(self._get_value(), name)


# ---------------------------------------------------------------------------
# OdooRecord
# ---------------------------------------------------------------------------

class OdooRecord:
    """
    Represents a single Odoo record.

    Field values are fetched lazily on first access and cached locally.
    Arbitrary Odoo methods can be called directly::

        partner = env('res.partner').browse(1)
        print(partner.name)          # lazy field read
        partner.write({'name': 'X'}) # explicit write helper
        partner.message_post(body="Hi")  # arbitrary method call
    """

    def __init__(
        self,
        session_id: str,
        url: str,
        model: str,
        record_id: int,
        context: Optional[dict] = None,
        client: Optional[httpx.Client] = None,
    ):
        self._session_id = session_id
        self._url = url
        self._model = model
        self._id = record_id
        self._context: dict = context if context is not None else {"lang": "en_US", "tz": "UTC"}
        self._own_client: bool = client is None
        self._client: httpx.Client = client if client is not None else httpx.Client()
        self._cache: Dict[str, Any] = {}
        self._fields_info: Optional[Dict[str, Any]] = None

    def __del__(self):
        if self._own_client:
            try:
                self._client.close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Identity / dunder
    # ------------------------------------------------------------------

    @property
    def id(self) -> int:
        """The integer database ID of this record."""
        return self._id

    def __repr__(self) -> str:
        return f"{self._model}({self._id},)"

    def __bool__(self) -> bool:
        return bool(self._id)

    def __eq__(self, other) -> bool:
        if isinstance(other, OdooRecord):
            return self._model == other._model and self._id == other._id
        return NotImplemented

    def __hash__(self) -> int:
        return hash((self._model, self._id))

    # ------------------------------------------------------------------
    # Low-level request
    # ------------------------------------------------------------------

    def _make_request(self, method: str, args: Optional[list] = None, kwargs: Optional[dict] = None) -> Any:
        """Send a JSON-RPC call_kw request and return the result."""
        method_kwargs: dict = dict(kwargs) if kwargs else {}
        if 'context' in method_kwargs:
            ctx = self._context.copy()
            ctx.update(method_kwargs['context'])
            method_kwargs['context'] = ctx
        else:
            method_kwargs['context'] = self._context

        payload = {
            "jsonrpc": "2.0",
            "params": {
                "model": self._model,
                "method": method,
                "args": args or [],
                "kwargs": method_kwargs,
            },
        }
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Cookie': f'session_id={self._session_id}',
        }
        try:
            response = self._client.post(
                f"{self._url}/web/dataset/call_kw/{self._model}/{method}",
                headers=headers,
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            result = response.json()
            if 'error' in result:
                error_data = result['error']
                error_msg = error_data.get('data', {}).get('message', str(error_data))
                raise OdooRequestError(f"Odoo server error: {error_msg}", error_data)
            return result.get("result", False)
        except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.PoolTimeout):
            raise OdooConnectionError("Request timed out")
        except httpx.HTTPError as e:
            raise OdooConnectionError(f"HTTP error occurred: {str(e)}")
        except OdooException:
            raise
        except Exception as e:
            raise OdooRequestError(f"Unexpected error: {str(e)}")

    # ------------------------------------------------------------------
    # Field access helpers (used by _FieldProxy)
    # ------------------------------------------------------------------

    def _get_fields_info(self) -> Dict[str, Any]:
        """Fetch and cache fields_get metadata (type and relation) for this model."""
        if self._fields_info is None:
            result = self._make_request(
                "fields_get", [], {"attributes": ["type", "relation"]}
            )
            self._fields_info = result if isinstance(result, dict) else {}
        return self._fields_info

    def _coerce_relational(self, field_name: str, value: Any) -> Any:
        """
        Convert a raw many2one value ``[id, display_name]`` to an
        :class:`OdooRecordset`, matching Odoo's native related-field behaviour.

        Any other value is returned unchanged.
        """
        if not (
            isinstance(value, (list, tuple))
            and len(value) == 2
            and isinstance(value[0], int)
            and isinstance(value[1], str)
        ):
            return value
        fields_info = self._get_fields_info()
        field_meta = fields_info.get(field_name, {})
        if field_meta.get("type") == "many2one" and field_meta.get("relation"):
            comodel = field_meta["relation"]
            rec = OdooRecord(
                self._session_id, self._url, comodel,
                value[0], self._context.copy(), self._client,
            )
            return OdooRecordset(
                (rec,), comodel, self._session_id,
                self._url, self._context.copy(), self._client,
            )
        return value

    def _get_field(self, name: str) -> Any:
        """Return a field value, fetching from Odoo on first access."""
        if name not in self._cache:
            result = self._make_request("read", [[self._id], [name]])
            if result and isinstance(result, list):
                for k, v in result[0].items():
                    self._cache[k] = v
        value = self._cache.get(name, False)
        return self._coerce_relational(name, value)

    def _call_method(self, name: str, *args, **kwargs) -> Any:
        """Call an arbitrary Odoo method on this record."""
        return self._make_request(name, [[self._id]] + list(args), kwargs)

    # ------------------------------------------------------------------
    # Explicit record helpers
    # ------------------------------------------------------------------

    def write(self, values: Dict) -> bool:
        """Update fields of this record."""
        result = self._make_request("write", [[self._id], values])
        self._cache.clear()
        return bool(result)

    def unlink(self) -> bool:
        """Delete this record from the database."""
        return bool(self._make_request("unlink", [[self._id]]))

    def refresh(self) -> None:
        """Invalidate the local field cache, forcing a re-fetch on next access."""
        self._cache.clear()

    def sudo(self) -> 'OdooRecord':
        """
        Return a new record proxy.

        Note: For external JSON-RPC sessions the authenticated user cannot be
        elevated server-side; this method is provided for API compatibility.
        """
        return OdooRecord(
            self._session_id, self._url, self._model,
            self._id, self._context.copy(), self._client,
        )

    def with_user(self, user_id: int) -> 'OdooRecord':
        """
        Return a new record proxy.

        Note: For external JSON-RPC sessions user switching is not enforced
        server-side; this method is provided for API compatibility.
        """
        return OdooRecord(
            self._session_id, self._url, self._model,
            self._id, self._context.copy(), self._client,
        )

    def with_context(self, *args, **kwargs) -> 'OdooRecord':
        """Return a new record with an updated evaluation context."""
        context = self._context.copy()
        if args and isinstance(args[0], dict):
            context.update(args[0])
        context.update(kwargs)
        return OdooRecord(
            self._session_id, self._url, self._model,
            self._id, context, self._client,
        )

    # ------------------------------------------------------------------
    # Dynamic attribute access
    # ------------------------------------------------------------------

    def __getattr__(self, name: str) -> '_FieldProxy':
        """Return a _FieldProxy that can act as a field value or a method call."""
        if name.startswith('_'):
            raise AttributeError(name)
        return _FieldProxy(self, name)


# ---------------------------------------------------------------------------
# OdooRecordset
# ---------------------------------------------------------------------------

class OdooRecordset:
    """
    An ordered collection of :class:`OdooRecord` objects for the same model.

    Mirrors the Odoo recordset API: supports iteration, indexing, boolean
    checks (falsy when empty), field delegation on singletons, and common
    helpers like ``mapped``, ``filtered``, ``sorted``, and ``ensure_one``.

    Obtain a recordset via :class:`OdooModel`::

        partners = env('res.partner').search([('is_company', '=', True)])
        for p in partners:
            print(p.name)

        single = env('res.partner').browse(42)
        print(single.name)  # field delegation on singleton
    """

    __slots__ = ('_records', '_model', '_session_id', '_url', '_context', '_client')

    def __init__(
        self,
        records: Tuple[OdooRecord, ...],
        model: str,
        session_id: str,
        url: str,
        context: Optional[dict] = None,
        client: Optional[httpx.Client] = None,
    ):
        self._records: tuple = tuple(records)
        self._model: str = model
        self._session_id: str = session_id
        self._url: str = url
        self._context: dict = context if context is not None else {"lang": "en_US", "tz": "UTC"}
        self._client: Optional[httpx.Client] = client

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------

    def _new(self, records) -> 'OdooRecordset':
        """Build a new recordset from *records*, reusing model metadata."""
        return OdooRecordset(
            tuple(records), self._model, self._session_id,
            self._url, self._context.copy(), self._client,
        )

    # ------------------------------------------------------------------
    # Identity / dunder
    # ------------------------------------------------------------------

    @property
    def ids(self) -> List[int]:
        """Return a list of integer database IDs for all records."""
        return [r._id for r in self._records]

    @property
    def id(self) -> int:
        """The database ID of the singleton record. Raises ValueError if not singleton."""
        self.ensure_one()
        return self._records[0]._id

    def __iter__(self):
        """Iterate over records in the set."""
        return iter(self._records)

    def __len__(self) -> int:
        """Return the number of records."""
        return len(self._records)

    def __bool__(self) -> bool:
        """True if the recordset is non-empty."""
        return len(self._records) > 0

    def __getitem__(self, index):
        """Integer index returns an OdooRecord, slice returns a new OdooRecordset."""
        if isinstance(index, slice):
            return self._new(self._records[index])
        return self._records[index]

    def __contains__(self, item) -> bool:
        """Check if a record is in the set."""
        return item in self._records

    def __repr__(self) -> str:
        ids_str = ", ".join(str(r._id) for r in self._records)
        return f"{self._model}({ids_str})"

    def __str__(self) -> str:
        return self.__repr__()

    def __eq__(self, other) -> bool:
        if isinstance(other, OdooRecordset):
            return self._model == other._model and self._records == other._records
        return NotImplemented

    def __hash__(self) -> int:
        return hash((self._model, self._records))

    # ------------------------------------------------------------------
    # Singleton field / method delegation
    # ------------------------------------------------------------------

    def __getattr__(self, name: str):
        """
        For singleton recordsets, delegate attribute access to the single record.
        For multi-record or empty recordsets, raise ValueError.
        """
        if name.startswith('_'):
            raise AttributeError(name)
        if len(self._records) == 1:
            return getattr(self._records[0], name)
        raise ValueError(
            f"Expected singleton: {self._model} recordset contains "
            f"{len(self._records)} records"
        )

    # ------------------------------------------------------------------
    # Recordset helpers
    # ------------------------------------------------------------------

    def mapped(self, field_name: str) -> list:
        """
        Return a list of field values for the given *field_name* across all records.

        Uses the internal ``_get_field`` method for consistency with lazy caching.
        """
        return [record._get_field(field_name) for record in self._records]

    def filtered(self, func) -> 'OdooRecordset':
        """
        Return a new recordset containing only records for which *func(record)*
        is truthy.
        """
        return self._new(r for r in self._records if func(r))

    def sorted(self, key=None, reverse: bool = False) -> 'OdooRecordset':
        """
        Return a new recordset sorted by *key*.

        If *key* is ``None``, records are sorted by database ID.
        If *key* is a string, it is treated as a field name.
        If *key* is callable, it receives each record.
        """
        if key is None:
            sort_key = lambda r: r._id
        elif isinstance(key, str):
            field_name = key
            sort_key = lambda r: r._get_field(field_name)
        else:
            sort_key = key
        return self._new(_sorted(self._records, key=sort_key, reverse=reverse))

    def ensure_one(self) -> 'OdooRecordset':
        """
        Raise :class:`ValueError` if this recordset does not contain exactly
        one record.  Returns ``self`` for chaining.
        """
        if len(self._records) != 1:
            raise ValueError(
                f"Expected singleton: {self._model} recordset contains "
                f"{len(self._records)} records"
            )
        return self

    # ------------------------------------------------------------------
    # Batch CRUD
    # ------------------------------------------------------------------

    def write(self, values: Dict) -> bool:
        """Write *values* to all records in the set in a single RPC call."""
        if not self._records:
            return True
        ids = self.ids
        result = self._records[0]._make_request("write", [ids, values])
        for record in self._records:
            record._cache.clear()
        return bool(result)

    def unlink(self) -> bool:
        """Delete all records in the set in a single RPC call."""
        if not self._records:
            return True
        ids = self.ids
        return bool(self._records[0]._make_request("unlink", [ids]))

    # ------------------------------------------------------------------
    # Set operations
    # ------------------------------------------------------------------

    def __add__(self, other: 'OdooRecordset') -> 'OdooRecordset':
        """Concatenation (preserves order, may contain duplicates)."""
        if not isinstance(other, OdooRecordset):
            return NotImplemented
        return self._new(self._records + other._records)

    def __or__(self, other: 'OdooRecordset') -> 'OdooRecordset':
        """Union (preserves order, removes duplicates)."""
        if not isinstance(other, OdooRecordset):
            return NotImplemented
        seen: set = set()
        result: list = []
        for r in self._records + other._records:
            key = (r._model, r._id)
            if key not in seen:
                seen.add(key)
                result.append(r)
        return self._new(result)

    def __sub__(self, other: 'OdooRecordset') -> 'OdooRecordset':
        """Difference (records in self but not in other)."""
        if not isinstance(other, OdooRecordset):
            return NotImplemented
        other_keys = {(r._model, r._id) for r in other._records}
        return self._new(r for r in self._records if (r._model, r._id) not in other_keys)

    def __and__(self, other: 'OdooRecordset') -> 'OdooRecordset':
        """Intersection (records in both self and other, order from self)."""
        if not isinstance(other, OdooRecordset):
            return NotImplemented
        other_keys = {(r._model, r._id) for r in other._records}
        return self._new(r for r in self._records if (r._model, r._id) in other_keys)

    # ------------------------------------------------------------------
    # Context / user modifiers
    # ------------------------------------------------------------------

    def sudo(self) -> 'OdooRecordset':
        """Return a new recordset with sudo-modified records."""
        return self._new(r.sudo() for r in self._records)

    def with_user(self, user_id: int) -> 'OdooRecordset':
        """Return a new recordset with user-modified records."""
        return self._new(r.with_user(user_id) for r in self._records)

    def with_context(self, *args, **kwargs) -> 'OdooRecordset':
        """Return a new recordset with context-modified records."""
        new_records = tuple(r.with_context(*args, **kwargs) for r in self._records)
        context = self._context.copy()
        if args and isinstance(args[0], dict):
            context.update(args[0])
        context.update(kwargs)
        return OdooRecordset(
            new_records, self._model, self._session_id,
            self._url, context, self._client,
        )

    def refresh(self) -> None:
        """Invalidate the local field cache on all records."""
        for record in self._records:
            record.refresh()


# ---------------------------------------------------------------------------
# OdooModel
# ---------------------------------------------------------------------------

class OdooModel:
    """
    Represents an Odoo model and exposes the standard record-set API.

    Obtain an instance via :class:`OdooSession`::

        env = OdooSession(url=url, session_id=session_id)
        Partner = env('res.partner')

    or the legacy helper::

        Partner = connect_model(session_id, url, 'res.partner')
    """

    def __init__(
        self,
        session_id: str,
        url: str,
        model: str,
        context: Optional[dict] = None,
        client: Optional[httpx.Client] = None,
    ):
        self._session_id = session_id
        self._url = url
        self._model = model
        self._context: dict = context if context is not None else {"lang": "en_US", "tz": "UTC"}
        self._own_client: bool = client is None
        self._client: httpx.Client = client if client is not None else httpx.Client()

    def __del__(self):
        if self._own_client:
            try:
                self._client.close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Low-level request
    # ------------------------------------------------------------------

    def _make_request(self, method: str, args: Optional[list] = None, kwargs: Optional[dict] = None) -> Any:
        """Send a JSON-RPC call_kw request and return the result."""
        method_kwargs: dict = dict(kwargs) if kwargs else {}
        if 'context' in method_kwargs:
            ctx = self._context.copy()
            ctx.update(method_kwargs['context'])
            method_kwargs['context'] = ctx
        else:
            method_kwargs['context'] = self._context

        payload = {
            "jsonrpc": "2.0",
            "params": {
                "model": self._model,
                "method": method,
                "args": args or [],
                "kwargs": method_kwargs,
            },
        }
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Cookie': f'session_id={self._session_id}',
        }
        try:
            response = self._client.post(
                f"{self._url}/web/dataset/call_kw/{self._model}/{method}",
                headers=headers,
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            result = response.json()
            if 'error' in result:
                error_data = result['error']
                error_msg = error_data.get('data', {}).get('message', str(error_data))
                raise OdooRequestError(f"Odoo server error: {error_msg}", error_data)
            return result.get("result", False)
        except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.PoolTimeout):
            raise OdooConnectionError("Request timed out")
        except httpx.HTTPError as e:
            raise OdooConnectionError(f"HTTP error occurred: {str(e)}")
        except OdooException:
            raise
        except Exception as e:
            raise OdooRequestError(f"Unexpected error: {str(e)}")

    def _make_record(self, record_id: int) -> OdooRecord:
        """Construct an :class:`OdooRecord` sharing the same client."""
        return OdooRecord(
            self._session_id, self._url, self._model,
            record_id, self._context.copy(), self._client,
        )

    def _make_recordset(self, record_ids: List[int]) -> OdooRecordset:
        """Construct an :class:`OdooRecordset` from a list of IDs."""
        records = tuple(self._make_record(rid) for rid in record_ids)
        return OdooRecordset(
            records, self._model, self._session_id,
            self._url, self._context.copy(), self._client,
        )

    # ------------------------------------------------------------------
    # Standard model methods
    # ------------------------------------------------------------------

    def search(
        self,
        domain: Optional[List] = None,
        limit: Optional[int] = None,
        offset: int = 0,
        order: Optional[str] = None,
    ) -> OdooRecordset:
        """Search for records and return an :class:`OdooRecordset`."""
        kw: Dict = {'offset': offset}
        if limit is not None:
            kw['limit'] = limit
        if order:
            kw['order'] = order
        result = self._make_request("search", [domain or []], kw)
        if not result:
            return self._make_recordset([])
        return self._make_recordset(result)

    def search_read(
        self,
        domain: Optional[List] = None,
        fields: Optional[List[str]] = None,
        limit: Optional[int] = None,
        offset: int = 0,
        order: Optional[str] = None,
    ) -> List[Dict]:
        """Search and read records, returning a list of field-value dicts."""
        kw: Dict = {'offset': offset}
        if fields:
            kw['fields'] = fields
        if limit is not None:
            kw['limit'] = limit
        if order:
            kw['order'] = order
        return self._make_request("search_read", [domain or []], kw) or []

    def search_count(self, domain: Optional[List] = None) -> int:
        """Return the number of records matching *domain*."""
        return self._make_request("search_count", [domain or []]) or 0

    def create(self, values: Dict) -> OdooRecordset:
        """Create a new record and return an :class:`OdooRecordset` for it."""
        result = self._make_request("create", [values])
        if result:
            return self._make_recordset([result])
        raise OdooValidationError("Create operation returned no ID")

    def write(self, ids: Union[int, List[int]], values: Dict) -> bool:
        """Write *values* to the records identified by *ids*."""
        if isinstance(ids, int):
            ids = [ids]
        return bool(self._make_request("write", [ids, values]))

    def unlink(self, ids: Union[int, List[int]]) -> bool:
        """Delete the records identified by *ids*."""
        if isinstance(ids, int):
            ids = [ids]
        return bool(self._make_request("unlink", [ids]))

    def read(
        self,
        ids: Union[int, List[int]],
        fields: Optional[List[str]] = None,
    ) -> List[Dict]:
        """Read records by ID and return a list of field-value dicts."""
        if isinstance(ids, int):
            ids = [ids]
        kw: Dict = {}
        if fields:
            kw['fields'] = fields
        return self._make_request("read", [ids], kw) or []

    def browse(self, ids: Union[int, List[int]]) -> OdooRecordset:
        """Return an :class:`OdooRecordset` for the given *ids*."""
        if isinstance(ids, int):
            return self._make_recordset([ids])
        return self._make_recordset(ids)

    # ------------------------------------------------------------------
    # Context / user modifiers
    # ------------------------------------------------------------------

    def sudo(self) -> 'OdooModel':
        """
        Return a new model proxy.

        Note: For external JSON-RPC sessions the authenticated user cannot be
        elevated server-side; this method is provided for API compatibility.
        """
        return OdooModel(
            self._session_id, self._url, self._model,
            self._context.copy(), self._client,
        )

    def with_user(self, user_id: int) -> 'OdooModel':
        """
        Return a new model proxy.

        Note: For external JSON-RPC sessions user switching is not enforced
        server-side; this method is provided for API compatibility.
        """
        return OdooModel(
            self._session_id, self._url, self._model,
            self._context.copy(), self._client,
        )

    def with_context(self, *args, **kwargs) -> 'OdooModel':
        """Return a new model with an updated evaluation context."""
        context = self._context.copy()
        if args and isinstance(args[0], dict):
            context.update(args[0])
        context.update(kwargs)
        return OdooModel(
            self._session_id, self._url, self._model,
            context, self._client,
        )

    # ------------------------------------------------------------------
    # Dynamic method calls
    # ------------------------------------------------------------------

    def __getattr__(self, name: str):
        """Forward unknown attribute access as a JSON-RPC method call."""
        if name.startswith('_'):
            raise AttributeError(name)

        def method_call(*args, **kwargs):
            return self._make_request(name, list(args), kwargs)

        return method_call


# ---------------------------------------------------------------------------
# OdooSession
# ---------------------------------------------------------------------------

class OdooSession:
    """
    Session-based gateway to an Odoo instance, mirroring ``self.env`` in Odoo.

    Usage::

        session_id = connect_odoo(url, db, username, password)
        env = OdooSession(url=url, session_id=session_id)

        # Three equivalent ways to get a model proxy:
        Partner = env('res.partner')
        Partner = env['res.partner']

        partners = Partner.search([('is_company', '=', True)], limit=5)
        for partner in partners:
            print(partner.name)

        # Environment variables (fetched lazily from the server):
        print(env.uid)          # current user's integer ID
        print(env.user)         # OdooRecord for res.users
        print(env.company)      # OdooRecord for the current res.company
        print(env.companies)    # list of OdooRecord for all allowed companies
        print(env.lang)         # language code, e.g. 'en_US'
        print(env.context)      # current context dict
    """

    def __init__(
        self,
        url: str,
        session_id: str,
        context: Optional[dict] = None,
        verify: bool = True,
    ):
        if not url:
            raise OdooValidationError("URL must be provided")
        if not session_id:
            raise OdooValidationError("Session ID must be provided")
        self._url = url.rstrip('/')
        self._session_id = session_id
        self._context: dict = context if context is not None else {"lang": "en_US", "tz": "UTC"}
        self._client = httpx.Client(verify=verify)
        self._session_info: Optional[dict] = None

    def __del__(self):
        try:
            self._client.close()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Session info (lazy, cached)
    # ------------------------------------------------------------------

    def _get_session_info(self) -> dict:
        """
        Fetch and cache the Odoo session info from ``/web/session/get_session_info``.

        The result is cached after the first call so subsequent property
        accesses do not make additional HTTP requests.
        """
        if self._session_info is not None:
            return self._session_info

        payload = {
            "jsonrpc": "2.0",
            "params": {},
        }
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Cookie': f'session_id={self._session_id}',
        }
        try:
            response = self._client.post(
                f"{self._url}/web/session/get_session_info",
                headers=headers,
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            result = response.json()
            if 'error' in result:
                error_data = result['error']
                error_msg = error_data.get('data', {}).get('message', str(error_data))
                raise OdooRequestError(f"Odoo server error: {error_msg}", error_data)
            self._session_info = result.get('result') or {}
        except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.PoolTimeout):
            raise OdooConnectionError("Request timed out")
        except httpx.HTTPError as e:
            raise OdooConnectionError(f"HTTP error occurred: {str(e)}")
        except OdooException:
            raise
        except Exception as e:
            raise OdooRequestError(f"Unexpected error: {str(e)}")

        return self._session_info

    # ------------------------------------------------------------------
    # Environment properties (mirror self.env.* in Odoo)
    # ------------------------------------------------------------------

    @property
    def uid(self) -> int:
        """The integer ID of the currently authenticated user."""
        return self._get_session_info().get('uid', 0)

    @property
    def user(self) -> OdooRecord:
        """
        An :class:`OdooRecord` representing the currently authenticated
        ``res.users`` record — equivalent to ``self.env.user`` in Odoo.
        """
        return OdooRecord(
            self._session_id, self._url, 'res.users',
            self.uid, self._context.copy(), self._client,
        )

    @property
    def company(self) -> OdooRecord:
        """
        An :class:`OdooRecord` representing the current ``res.company`` —
        equivalent to ``self.env.company`` in Odoo.
        """
        info = self._get_session_info()
        # company_id is the primary key; fall back to the first element of
        # current_company when it is returned as a [id, name] pair.
        company_id = info.get('company_id')
        if not company_id:
            current = info.get('current_company')
            if isinstance(current, (list, tuple)) and current:
                company_id = int(current[0])
        if not company_id:
            raise OdooRequestError("Could not determine current company from session info")
        return OdooRecord(
            self._session_id, self._url, 'res.company',
            company_id, self._context.copy(), self._client,
        )

    @property
    def companies(self) -> List[OdooRecord]:
        """
        A list of :class:`OdooRecord` objects for all companies the current
        user is allowed to access — equivalent to ``self.env.companies`` in
        Odoo.
        """
        info = self._get_session_info()
        # Odoo may return allowed companies as a list of IDs or a list of
        # [id, name] pairs depending on the version.
        raw = (
            info.get('allowed_company_ids')
            or info.get('user_companies', {}).get('allowed_companies')
            or []
        )
        ids: List[int] = []
        for item in raw:
            if isinstance(item, int):
                ids.append(item)
            elif isinstance(item, (list, tuple)) and item:
                ids.append(int(item[0]))
        return [
            OdooRecord(
                self._session_id, self._url, 'res.company',
                cid, self._context.copy(), self._client,
            )
            for cid in ids
        ]

    @property
    def lang(self) -> str:
        """
        The active language code (e.g. ``'en_US'``) — taken from the current
        context, equivalent to ``self.env.lang`` in Odoo.
        """
        return self._context.get('lang', 'en_US')

    @property
    def context(self) -> dict:
        """
        A copy of the current evaluation context dict — equivalent to
        ``self.env.context`` in Odoo.
        """
        return self._context.copy()

    # ------------------------------------------------------------------
    # Model access
    # ------------------------------------------------------------------

    def __call__(self, model: str) -> OdooModel:
        """Return an :class:`OdooModel` for *model*."""
        if not model:
            raise OdooValidationError("Model name must be provided")
        return OdooModel(
            self._session_id, self._url, model,
            self._context.copy(), self._client,
        )

    def __getitem__(self, model: str) -> OdooModel:
        """Return an :class:`OdooModel` for *model* (dict-style access)."""
        return self(model)

    def with_context(self, *args, **kwargs) -> 'OdooSession':
        """Return a new session with an updated evaluation context."""
        context = self._context.copy()
        if args and isinstance(args[0], dict):
            context.update(args[0])
        context.update(kwargs)
        # Create a new session object that reuses the existing client and
        # cached session info, changing only the context.
        new_session = object.__new__(OdooSession)
        new_session.__dict__ = self.__dict__.copy()
        new_session._context = context
        return new_session


# ---------------------------------------------------------------------------
# Public helper functions
# ---------------------------------------------------------------------------

def connect_odoo(url: str, db: str, username: str, password: str) -> str:
    """
    Authenticate against Odoo and return the session ID.

    Args:
        url:      Odoo instance URL (e.g. ``https://mycompany.odoo.com``)
        db:       Database name
        username: Login (usually an e-mail address)
        password: Password

    Returns:
        str: The ``session_id`` cookie value on success.

    Raises:
        :class:`OdooValidationError`:     if any parameter is missing.
        :class:`OdooAuthenticationError`: if the credentials are rejected.
        :class:`OdooConnectionError`:     on network / HTTP errors.
    """
    if not url or not db or not username or not password:
        raise OdooValidationError("All connection parameters must be provided")

    url = url.rstrip('/')
    client = httpx.Client()
    try:
        payload = {
            "jsonrpc": "2.0",
            "params": {"db": db, "login": username, "password": password},
        }
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        response = client.post(
            f"{url}/web/session/authenticate",
            headers=headers,
            json=payload,
        )
        if response.status_code == 200:
            result = response.json()
            if result.get('result'):
                session_id = response.cookies.get('session_id')
                if session_id:
                    return session_id
        raise OdooAuthenticationError("Authentication failed")
    except httpx.HTTPError as e:
        raise OdooConnectionError(f"Connection error: {str(e)}")
    finally:
        client.close()


def connect_model(session_id: str, url: str, model: str) -> OdooModel:
    """
    Create an :class:`OdooModel` from an existing session ID (legacy helper).

    .. deprecated:: 0.3.0
        ``connect_model`` is deprecated and will be removed in version 0.4.0.
        Use :class:`OdooSession` instead::

            env = OdooSession(url=url, session_id=session_id)
            Partner = env['res.partner']

    Args:
        session_id: Odoo session ID string
        url:        Odoo instance URL
        model:      Model name (e.g. ``'res.partner'``)

    Returns:
        :class:`OdooModel`
    """
    warnings.warn(
        "connect_model() is deprecated and will be removed in version 0.4.0. "
        "Use OdooSession instead: env = OdooSession(url=url, session_id=session_id); "
        "model = env['model.name']",
        DeprecationWarning,
        stacklevel=2,
    )
    if not session_id or not url or not model:
        raise OdooValidationError("Session ID, URL and model name must be provided")
    return OdooModel(session_id, url.rstrip('/'), model)