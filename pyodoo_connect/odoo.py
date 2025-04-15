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
    def __init__(self, session_id: str, url: str, model: str, record_id: int, context: dict = None):
        self._session_id = session_id
        self._url = url
        self._model = model
        self._id = record_id
        self._context = context or {"lang": "en_US", "tz": "UTC"}
        self._client = httpx.Client(verify=False)

    def __del__(self):
        try:
            self._client.close()
        except Exception:
            pass

    def with_context(self, *args, **kwargs) -> 'OdooRecord':
        """Return a new record with updated context"""
        context = self._context.copy()

        # Handle dictionary argument
        if args and isinstance(args[0], dict):
            context.update(args[0])

        # Handle keyword arguments
        context.update(kwargs)

        return OdooRecord(self._session_id, self._url, self._model, self._id, context)

    def __getattr__(self, name):
        """Handle dynamic method calls to Odoo"""

        def method_call(*args, **kwargs):
            endpoint = f"/web/dataset/call_kw/{self._model}/{name}"

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
            except Exception as e:
                raise OdooRequestError(f"Unexpected error: {str(e)}")

        return method_call


class OdooModel:
    def __init__(self, session_id: str, url: str, model: str, context: dict = None):
        self._session_id = session_id
        self._url = url
        self._model = model
        self._context = context or {"lang": "en_US", "tz": "UTC"}
        self._client = httpx.Client(verify=False)

    def __del__(self):
        try:
            self._client.close()
        except Exception:
            pass

    def with_context(self, *args, **kwargs) -> 'OdooModel':
        """Return a new model with updated context"""
        context = self._context.copy()

        # Handle dictionary argument
        if args and isinstance(args[0], dict):
            context.update(args[0])

        # Handle keyword arguments
        context.update(kwargs)

        return OdooModel(self._session_id, self._url, self._model, context)

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
        except Exception as e:
            raise OdooRequestError(f"Unexpected error: {str(e)}")

    def __getattr__(self, name):
        """Handle dynamic method calls to Odoo"""

        def method_call(*args, **kwargs):
            return self._make_request(name, args, kwargs)

        return method_call

    def create(self, values: Dict) -> int:
        """Create a new record and return its ID"""
        result = self._make_request("create", [values])
        if result:
            return OdooRecord(self._session_id, self._url, self._model, result)
        raise OdooValidationError("Create operation returned no ID")

    def browse(self, ids: Union[int, List[int]]) -> Union[OdooRecord, List[OdooRecord]]:
        """Browse records by ID"""
        if isinstance(ids, int):
            return OdooRecord(self._session_id, self._url, self._model, ids, self._context)
        return [OdooRecord(self._session_id, self._url, self._model, id_, self._context) for id_ in ids]


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

    try:
        client = httpx.Client(verify=False)

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


def connect_model(session_id: str, url: str, model: str) -> OdooModel:
    """
    Connect to an Odoo model using an existing session ID.

    Args:
        session_id: Odoo session ID string
        url: Odoo instance URL
        model: Model name (e.g. 'res.partner')

    Returns:
        OdooModel: Model instance for interacting with Odoo
    """
    if not session_id or not url or not model:
        raise OdooValidationError("Session ID, URL and model name must be provided")

    url = url.rstrip('/')
    return OdooModel(session_id, url, model)