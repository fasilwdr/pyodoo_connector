from typing import Optional, Any, List, Dict, Union
import httpx


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


class OdooRecord:
    def __init__(self, session_id: str, url: str, model: str, record_id: int,
                 context: dict = None, client: httpx.Client = None):
        self._session_id = session_id
        self._url = url
        self._model = model
        self._id = record_id
        self._context = context or {"lang": "en_US", "tz": "UTC"}
        self._owns_client = client is None
        self._client = client if client is not None else httpx.Client(verify=False)

    def __del__(self):
        if self._owns_client:
            try:
                self._client.close()
            except Exception:
                pass

    @property
    def id(self) -> int:
        """Return the record ID"""
        return self._id

    def __repr__(self) -> str:
        return f"OdooRecord({self._model}, id={self._id})"

    def __str__(self) -> str:
        return f"{self._model}({self._id})"

    def __bool__(self) -> bool:
        return self._id is not None and self._id > 0

    def with_context(self, *args, **kwargs) -> 'OdooRecord':
        """Return a new record with updated context"""
        context = self._context.copy()

        # Handle dictionary argument
        if args and isinstance(args[0], dict):
            context.update(args[0])

        # Handle keyword arguments
        context.update(kwargs)

        return OdooRecord(self._session_id, self._url, self._model, self._id,
                          context, self._client)

    def with_user(self, user_id: int) -> 'OdooRecord':
        """Return a new record with a user override in context"""
        if not user_id:
            raise OdooValidationError("User ID must be provided")
        return self.with_context(uid=user_id)

    def sudo(self, user_id: Optional[int] = None) -> 'OdooRecord':
        """Return a record with sudo context enabled"""
        record = self.with_context(sudo=True)
        if user_id is not None:
            record = record.with_user(user_id)
        return record

    def __getattr__(self, name):
        """Handle dynamic method calls to Odoo"""

        def method_call(*args, **kwargs):
            # Handle context in kwargs
            method_kwargs = kwargs.copy()
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
                    "method": name,
                    "args": [[self._id]] + list(args),
                    "kwargs": method_kwargs
                }
            }

            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Cookie': f'session_id={self._session_id}'
            }

            try:
                response = self._client.post(
                    f"{self._url}/web/dataset/call_kw/{self._model}/{name}",
                    headers=headers,
                    json=payload,
                    timeout=30
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

        return method_call


class OdooModel:
    def __init__(self, session_id: str, url: str, model: str, context: dict = None,
                 client: httpx.Client = None):
        self._session_id = session_id
        self._url = url
        self._model = model
        self._context = context or {"lang": "en_US", "tz": "UTC"}
        self._owns_client = client is None
        self._client = client if client is not None else httpx.Client(verify=False)

    def __del__(self):
        if self._owns_client:
            try:
                self._client.close()
            except Exception:
                pass

    def __repr__(self) -> str:
        return f"OdooModel({self._model})"

    def __str__(self) -> str:
        return self._model

    def with_context(self, *args, **kwargs) -> 'OdooModel':
        """Return a new model with updated context"""
        context = self._context.copy()

        # Handle dictionary argument
        if args and isinstance(args[0], dict):
            context.update(args[0])

        # Handle keyword arguments
        context.update(kwargs)

        return OdooModel(self._session_id, self._url, self._model, context, self._client)

    def with_user(self, user_id: int) -> 'OdooModel':
        """Return a new model with a user override in context"""
        if not user_id:
            raise OdooValidationError("User ID must be provided")
        return self.with_context(uid=user_id)

    def sudo(self, user_id: Optional[int] = None) -> 'OdooModel':
        """Return a model with sudo context enabled"""
        model = self.with_context(sudo=True)
        if user_id is not None:
            model = model.with_user(user_id)
        return model

    def _make_request(self, method: str, args: list = None, kwargs: dict = None) -> Any:
        """Make a request to the Odoo server"""
        endpoint = f"/web/dataset/call_kw/{self._model}/{method}"

        method_kwargs = kwargs or {}
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
                "kwargs": method_kwargs
            }
        }

        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Cookie': f'session_id={self._session_id}'
        }

        try:
            response = self._client.post(
                f"{self._url}{endpoint}",
                headers=headers,
                json=payload,
                timeout=30
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

    def __getattr__(self, name):
        """Handle dynamic method calls to Odoo"""

        def method_call(*args, **kwargs):
            return self._make_request(name, args, kwargs)

        return method_call

    def create(self, values: Dict) -> 'OdooRecord':
        """Create a new record and return an OdooRecord instance"""
        result = self._make_request("create", [values])
        if result:
            return OdooRecord(self._session_id, self._url, self._model, result,
                              self._context, self._client)
        raise OdooValidationError("Create operation returned no ID")

    def browse(self, ids: Union[int, List[int]]) -> Union['OdooRecord', List['OdooRecord']]:
        """Browse records by ID"""
        if isinstance(ids, int):
            return OdooRecord(self._session_id, self._url, self._model, ids,
                              self._context, self._client)
        return [OdooRecord(self._session_id, self._url, self._model, id_,
                           self._context, self._client) for id_ in ids]

    def search(self, domain: List = None, limit: int = None, offset: int = 0,
               order: str = None) -> List[int]:
        """
        Search for records matching domain and return their IDs.

        Args:
            domain: Search domain (e.g. [('is_company', '=', True)])
            limit: Maximum number of records to return
            offset: Number of records to skip
            order: Sorting order (e.g. 'name ASC')

        Returns:
            List of record IDs
        """
        kwargs: Dict[str, Any] = {'offset': offset}
        if limit is not None:
            kwargs['limit'] = limit
        if order is not None:
            kwargs['order'] = order
        return self._make_request("search", [domain or []], kwargs) or []

    def search_count(self, domain: List = None) -> int:
        """
        Count records matching domain.

        Args:
            domain: Search domain

        Returns:
            Number of matching records
        """
        return self._make_request("search_count", [domain or []]) or 0

    def search_read(self, domain: List = None, fields: List[str] = None,
                    limit: int = None, offset: int = 0,
                    order: str = None) -> List[Dict]:
        """
        Search for records and return their field values.

        Args:
            domain: Search domain
            fields: Fields to fetch; fetches all fields if omitted
            limit: Maximum number of records to return
            offset: Number of records to skip
            order: Sorting order (e.g. 'name ASC')

        Returns:
            List of record dicts
        """
        kwargs: Dict[str, Any] = {'offset': offset}
        if fields is not None:
            kwargs['fields'] = fields
        if limit is not None:
            kwargs['limit'] = limit
        if order is not None:
            kwargs['order'] = order
        return self._make_request("search_read", [domain or []], kwargs) or []

    def write(self, ids: Union[int, List[int]], values: Dict) -> bool:
        """
        Update records.

        Args:
            ids: Record ID or list of IDs to update
            values: Field values to write

        Returns:
            True if successful
        """
        if isinstance(ids, int):
            ids = [ids]
        return self._make_request("write", [ids, values]) or False

    def unlink(self, ids: Union[int, List[int]]) -> bool:
        """
        Delete records.

        Args:
            ids: Record ID or list of IDs to delete

        Returns:
            True if successful
        """
        if isinstance(ids, int):
            ids = [ids]
        return self._make_request("unlink", [ids]) or False

    def read(self, ids: Union[int, List[int]], fields: List[str] = None) -> List[Dict]:
        """
        Read field values for the given record IDs.

        Args:
            ids: Record ID or list of IDs to read
            fields: Fields to fetch; fetches all fields if omitted

        Returns:
            List of record dicts
        """
        if isinstance(ids, int):
            ids = [ids]
        kwargs: Dict[str, Any] = {}
        if fields is not None:
            kwargs['fields'] = fields
        return self._make_request("read", [ids], kwargs) or []


class OdooSession:
    """
    Unified session that handles authentication and provides access to Odoo models.

    This is the recommended entry point for version 0.3.0+. It authenticates
    once and reuses a single HTTP connection pool across all model and record
    operations.

    Example::

        session = OdooSession(
            url="https://my-odoo.example.com",
            db="my_db",
            username="admin",
            password="admin",
        )
        partner_model = session.env("res.partner")
        partner = partner_model.create({"name": "Alice"})
        partner.write({"phone": "+1234567890"})
    """

    def __init__(self, url: str, db: str = None, username: str = None,
                 password: str = None, session_id: str = None,
                 context: dict = None):
        """
        Create an Odoo session and open a persistent HTTP session.

        Args:
            url: Odoo instance URL
            db: Database name (required if session_id is not provided)
            username: Username (required if session_id is not provided)
            password: Password (required if session_id is not provided)
            session_id: Existing Odoo session ID to reuse without authentication
            context: Default context passed to models created from this session

        Raises:
            OdooValidationError: If any parameter is missing
            OdooAuthenticationError: If credentials are invalid
            OdooConnectionError: If the server cannot be reached
        """
        if not url:
            raise OdooValidationError("URL must be provided")

        self._url = url.rstrip('/')
        self._db = db
        self._username = username
        self._client = httpx.Client(verify=False)
        self._default_context = context or {"lang": "en_US", "tz": "UTC"}

        if session_id:
            self._session_id = session_id
        else:
            if not db or not username or not password:
                raise OdooValidationError(
                    "Provide session_id or provide db, username and password"
                )
            self._session_id = self._authenticate(password)

    def __repr__(self) -> str:
        return f"OdooSession(url={self._url!r}, db={self._db!r}, user={self._username!r})"

    def __del__(self):
        try:
            self._client.close()
        except Exception:
            pass

    def _authenticate(self, password: str) -> str:
        """Perform the authentication request and return the session ID."""
        payload = {
            "jsonrpc": "2.0",
            "params": {
                "db": self._db,
                "login": self._username,
                "password": password,
            }
        }
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        try:
            response = self._client.post(
                self._url + "/web/session/authenticate",
                headers=headers,
                json=payload,
            )
        except httpx.HTTPError as e:
            raise OdooConnectionError(f"Connection error: {str(e)}")

        if response.status_code == 200:
            result = response.json()
            if result.get('result'):
                session_id = response.cookies.get('session_id')
                if session_id:
                    return session_id

        raise OdooAuthenticationError("Authentication failed")

    @property
    def session_id(self) -> str:
        """The active session ID."""
        return self._session_id

    def __getitem__(self, model: str) -> OdooModel:
        """Allow Odoo-style access: session['res.partner']"""
        return self.env(model)

    def env(self, model: str, context: dict = None) -> OdooModel:
        """
        Return an OdooModel for the given model name.

        Args:
            model: Odoo model name (e.g. 'res.partner')
            context: Optional context overrides

        Returns:
            OdooModel sharing this session's HTTP client
        """
        if not model:
            raise OdooValidationError("Model name must be provided")
        model_context = self._default_context.copy()
        if context:
            model_context.update(context)
        return OdooModel(self._session_id, self._url, model, model_context, self._client)


def connect_odoo(url: str, db: str, username: str, password: str) -> str:
    """
    Connect to Odoo and return the session ID.

    Args:
        url: Odoo instance URL
        db: Database name
        username: Username
        password: Password

    Returns:
        str: Session ID if successful, raises exception otherwise
    """
    if not url or not db or not username or not password:
        raise OdooValidationError("All connection parameters must be provided")

    url = url.rstrip('/')

    client = httpx.Client(verify=False)
    try:
        login_endpoint = "/web/session/authenticate"
        payload = {
            "jsonrpc": "2.0",
            "params": {
                "db": db,
                "login": username,
                "password": password
            }
        }

        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        response = client.post(
            url + login_endpoint,
            headers=headers,
            json=payload
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


def connect_model(session_id: str, url: str, model: str,
                  context: dict = None) -> OdooModel:
    """
    Connect to an Odoo model using an existing session ID.

    Args:
        session_id: Odoo session ID string
        url: Odoo instance URL
        model: Model name (e.g. 'res.partner')
        context: Optional context overrides

    Returns:
        OdooModel: Model instance for interacting with Odoo
    """
    if not session_id or not url or not model:
        raise OdooValidationError("Session ID, URL and model name must be provided")

    url = url.rstrip('/')
    return OdooModel(session_id, url, model, context)
