import time
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
    _field_cache = {}  # Class-level cache for fields

    def __init__(self, api, model: str, record_id: int, values: dict = None, context: dict = None):
        self._api = api
        self._model = model
        self._id = record_id
        self._values = values or {}
        self._context = context or api.context.copy()

        # Initialize model's field cache if not already present
        if self._model not in self._field_cache:
            try:
                self._field_cache[self._model] = set(
                    self._api.env(self._model).fields_get().keys()
                )
            except OdooException as e:
                self._field_cache[self._model] = set()
                raise OdooValidationError(f"Failed to fetch fields for model {self._model}: {str(e)}")

    def with_context(self, *args, **kwargs) -> 'OdooRecord':
        """Return a new record with updated context"""
        context = self._context.copy()

        # Handle dictionary argument
        if args and isinstance(args[0], dict):
            context.update(args[0])

        # Handle keyword arguments
        context.update(kwargs)

        return OdooRecord(self._api, self._model, self._id, self._values.copy(), context)

    def __getattr__(self, name):
        if name in self._values:
            return self._values[name]

        # Check if it's a known field using the cache
        if name in self._field_cache.get(self._model, set()):
            try:
                record = self._api.env(self._model).search_read(
                    domain=[('id', '=', self._id)],
                    fields=[name]
                )
                if record and name in record[0]:
                    self._values.update(record[0])
                    return self._values.get(name)
            except OdooException as e:
                raise OdooRequestError(f"Failed to fetch field {name}: {str(e)}")

        # If not a field, treat it as a method
        def method_call(*args, **kwargs):
            try:
                endpoint = f"/web/dataset/call_kw/{self._model}/{name}"
                kwargs = kwargs.copy()

                if 'context' in kwargs:
                    ctx = self._context.copy()
                    ctx.update(kwargs['context'])
                    kwargs['context'] = ctx
                else:
                    kwargs['context'] = self._context

                payload = {
                    "params": {
                        "model": self._model,
                        "method": name,
                        "args": [[self._id]] + list(args),
                        "kwargs": kwargs
                    }
                }
                response = self._api._make_request(endpoint, payload)
                if not response:
                    raise OdooRequestError(f"Method call failed: {name}")
                return response.get("result", False)
            except OdooException as e:
                raise OdooRequestError(f"Method call failed: {name} - {str(e)}")

        return method_call

    def __setattr__(self, name, value):
        if name.startswith('_'):
            super().__setattr__(name, value)
        else:
            try:
                if self._api.env(self._model).write([self._id], {name: value}):
                    self._values[name] = value
                else:
                    raise OdooValidationError(f"Failed to write value for field: {name}")
            except OdooException as e:
                raise OdooRequestError(f"Failed to set attribute {name}: {str(e)}")

    def write(self, values: dict) -> bool:
        result = self._api.env(self._model).write([self._id], values)
        if result:
            self._values.update(values)
        return result

    def unlink(self) -> bool:
        return self._api.env(self._model).unlink([self._id])


class OdooModel:
    def __init__(self, api, model: str, context: dict = None):
        self._api = api
        self._model = model
        self._context = context or api.context.copy()

    def _handle_response(self, response: Optional[dict], error_msg: str) -> Any:
        """Helper method to handle API responses"""
        if not response:
            raise OdooRequestError(error_msg)
        if 'error' in response:
            raise OdooRequestError(error_msg, response['error'])
        return response.get('result', False)

    def with_context(self, *args, **kwargs) -> 'OdooModel':
        context = self._context.copy()
        if args and isinstance(args[0], dict):
            context.update(args[0])
        context.update(kwargs)
        return OdooModel(self._api, self._model, context)

    def __getattr__(self, name):
        def method_call(*args, **kwargs):
            endpoint = f"/web/dataset/call_kw/{self._model}/{name}"
            kwargs = kwargs.copy()

            if 'context' in kwargs:
                ctx = self._context.copy()
                ctx.update(kwargs['context'])
                kwargs['context'] = ctx
            else:
                kwargs['context'] = self._context

            payload = {
                "params": {
                    "model": self._model,
                    "method": name,
                    "args": list(args),
                    "kwargs": kwargs
                }
            }
            response = self._api._make_request(endpoint, payload)
            return response.get("result", False) if response else False

        return method_call

    def browse(self, ids: Union[int, List[int]]) -> Union[OdooRecord, List[OdooRecord]]:
        if isinstance(ids, int):
            return OdooRecord(self._api, self._model, ids, context=self._context)
        return [OdooRecord(self._api, self._model, id_, context=self._context) for id_ in ids]

    def search(self, domain: List = None, offset: int = 0, limit: Optional[int] = None,
               order: Optional[str] = None) -> List[int]:
        try:
            endpoint = "/web/dataset/call_kw/" + self._model + "/search"
            payload = {
                "params": {
                    "model": self._model,
                    "method": "search",
                    "args": [domain or []],
                    "kwargs": {
                        "offset": offset,
                        "limit": limit,
                        "order": order,
                    }
                }
            }
            response = self._api._make_request(endpoint, payload)
            return self._handle_response(response, f"Search failed for model {self._model}")
        except OdooException as e:
            raise OdooRequestError(f"Search operation failed: {str(e)}")

    def search_read(self, domain: List = None, fields: List[str] = None,
                    offset: int = 0, limit: Optional[int] = None,
                    order: Optional[str] = None) -> List[Dict]:
        endpoint = "/web/dataset/call_kw/" + self._model + "/search_read"
        payload = {
            "params": {
                "model": self._model,
                "method": "search_read",
                "args": [domain or []],
                "kwargs": {
                    "fields": fields or ['name'],
                    "offset": offset,
                    "limit": limit,
                    "order": order,
                }
            }
        }
        response = self._api._make_request(endpoint, payload)
        return response.get("result", []) if response else []

    def create(self, values: Dict) -> int:
        try:
            endpoint = "/web/dataset/call_kw/" + self._model + "/create"
            payload = {
                "params": {
                    "model": self._model,
                    "method": "create",
                    "args": [values],
                    "kwargs": {}
                }
            }
            response = self._api._make_request(endpoint, payload)
            result = self._handle_response(response, f"Create failed for model {self._model}")
            if not result:
                raise OdooValidationError("Create operation returned no ID")
            return result
        except OdooException as e:
            raise OdooRequestError(f"Create operation failed: {str(e)}")

    def write(self, ids: List[int], values: Dict) -> bool:
        endpoint = "/web/dataset/call_kw/" + self._model + "/write"
        payload = {
            "params": {
                "model": self._model,
                "method": "write",
                "args": [ids, values],
                "kwargs": {}
            }
        }
        response = self._api._make_request(endpoint, payload)
        return response.get("result", False) if response else False

    def unlink(self, ids: List[int]) -> bool:
        endpoint = "/web/dataset/call_kw/" + self._model + "/unlink"
        payload = {
            "params": {
                "model": self._model,
                "method": "unlink",
                "args": [ids],
                "kwargs": {}
            }
        }
        response = self._api._make_request(endpoint, payload)
        return response.get("result", False) if response else False

    def read(self, ids: List[int], fields: List[str] = None) -> List[Dict]:
        endpoint = "/web/dataset/call_kw/" + self._model + "/read"
        payload = {
            "params": {
                "model": self._model,
                "method": "read",
                "args": [ids],
                "kwargs": {
                    "fields": fields or ['name']
                }
            }
        }
        response = self._api._make_request(endpoint, payload)
        return response.get("result", []) if response else []


class OdooAPI:
    def __init__(self, url: str, db: str = None, username: str = None, password: str = None, session_id: str = None):
        if not url:
            raise OdooValidationError("URL cannot be empty")
        if not any([session_id, all([db, username, password])]):
            raise OdooValidationError("Either session_id or (db, username, password) must be provided")

        self.url = url.rstrip('/')
        self.db = db
        self.username = username
        self.password = password
        self.session_id = session_id
        self.context = {
            "lang": "en_US",
            "tz": "Asia/Riyadh",
            "uid": None
        }
        self._last_validation = 0
        self._validation_interval = 60
        try:
            self._client = httpx.Client(verify=False)
        except Exception as e:
            raise OdooConnectionError(f"Failed to initialize HTTP client: {str(e)}")

    def __del__(self):
        try:
            self._client.close()
        except Exception:
            pass

    def env(self, model: str) -> OdooModel:
        return OdooModel(self, model)

    def validate_session(self) -> bool:
        current_time = time.time()

        if (current_time - self._last_validation) < self._validation_interval:
            return bool(self.session_id)

        if not self.session_id:
            return False

        endpoint = "/web/session/get_session_info"
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Cookie': f'session_id={self.session_id}'
        }
        payload = {
            "jsonrpc": "2.0",
            "params": {}
        }

        try:
            response = self._client.post(
                self.url + endpoint,
                headers=headers,
                json=payload
            )

            if response.status_code == 200:
                result = response.json()
                if result.get('result', {}).get('uid'):
                    self.context['uid'] = result['result']['uid']
                    self._last_validation = current_time
                    return True
            return False

        except httpx.HTTPError as e:
            print(f"Session validation error: {str(e)}")
            return False

    def connect(self) -> bool:
        if self.session_id and self.validate_session():
            return True

        login_endpoint = "/web/session/authenticate"
        payload = {
            "jsonrpc": "2.0",
            "params": {
                "db": self.db,
                "login": self.username,
                "password": self.password
            }
        }

        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        try:
            response = self._client.post(
                self.url + login_endpoint,
                headers=headers,
                json=payload
            )

            if response.status_code == 200:
                result = response.json()
                if result.get('result'):
                    self.session_id = response.cookies.get('session_id')
                    self.context['uid'] = result['result'].get('uid')
                    return True
            return False

        except httpx.HTTPError as e:
            print(f"Connection error: {str(e)}")
            return False

    def _make_request(self, endpoint: str, payload: dict) -> Optional[dict]:
        if not self.session_id or not self.validate_session():
            if not self.connect():
                raise OdooAuthenticationError("Failed to establish or validate session")

        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Cookie': f'session_id={self.session_id}'
        }

        payload["jsonrpc"] = "2.0"
        if "params" in payload and "kwargs" in payload["params"]:
            payload["params"]["kwargs"]["context"] = self.context

        try:
            response = self._client.post(
                self.url + endpoint,
                headers=headers,
                json=payload,
                timeout=30  # Add timeout
            )

            response.raise_for_status()  # Raise exception for bad HTTP status codes

            if response.status_code == 200:
                json_response = response.json()
                if 'error' in json_response:
                    error_data = json_response['error']
                    error_msg = error_data.get('data', {}).get('message', str(error_data))
                    raise OdooRequestError(f"Odoo server error: {error_msg}", error_data)
                return json_response

            # Attempt to reconnect once
            if self.connect():
                headers['Cookie'] = f'session_id={self.session_id}'
                response = self._client.post(
                    self.url + endpoint,
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                if response.status_code == 200:
                    return response.json()

            raise OdooRequestError(f"Request failed with status code: {response.status_code}")

        except httpx.TimeoutError:
            raise OdooConnectionError("Request timed out")
        except httpx.HTTPError as e:
            raise OdooConnectionError(f"HTTP error occurred: {str(e)}")
        except Exception as e:
            raise OdooRequestError(f"Unexpected error: {str(e)}")


def connect_odoo(url: str, db: str = None, username: str = None, password: str = None,
                 session_id: str = None) -> tuple[Optional[OdooAPI], Optional[str]]:
    """
    Connect to Odoo using either credentials or session ID.

    Args:
        url: Odoo instance URL
        db: Database name (optional if session_id is provided)
        username: Username (optional if session_id is provided)
        password: Password (optional if session_id is provided)
        session_id: Existing session ID (optional if credentials are provided)

    Returns:
        tuple: (OdooAPI instance, session_id) or (None, None) if connection fails
    """
    try:
        api = OdooAPI(url=url, db=db, username=username, password=password, session_id=session_id)
        if api.connect():
            return api, api.session_id
        raise OdooAuthenticationError("Failed to connect to Odoo server")
    except OdooException as e:
        print(f"Connection failed: {str(e)}")
        return None, None