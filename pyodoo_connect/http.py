import httpx
import json
from typing import Dict, Any, Optional, Union, List, Tuple
from .odoo import OdooException, OdooConnectionError, OdooRequestError, OdooAuthenticationError


class OdooHttpClient:
    """Client for accessing Odoo HTTP routes"""

    def __init__(self, url: str, session_id: Optional[str] = None):
        """
        Initialize the HTTP client.

        Args:
            url: Base URL of the Odoo instance
            session_id: Optional session ID for authenticated routes
        """
        self._url = url.rstrip('/')
        self._session_id = session_id
        self._client = httpx.Client(verify=False)

    def __del__(self):
        try:
            self._client.close()
        except Exception:
            pass

    def get(self, route: str, params: Dict = None, headers: Dict = None,
            accept_html: bool = True) -> Any:
        """
        Send a GET request to an Odoo HTTP route.

        Args:
            route: The route path (e.g., '/web/session/get_session_info')
            params: Optional query parameters
            headers: Optional additional headers
            accept_html: If True, accept HTML responses; if False, raise error for non-JSON

        Returns:
            Response data (parsed JSON or HTML text depending on response)
        """
        return self._request('GET', route, params=params, headers=headers, accept_html=accept_html)

    def post(self, route: str, json_data: Dict = None, data: Dict = None,
             headers: Dict = None, accept_html: bool = True) -> Any:
        """
        Send a POST request to an Odoo HTTP route.

        Args:
            route: The route path
            json_data: Optional JSON data
            data: Optional form data
            headers: Optional additional headers
            accept_html: If True, accept HTML responses; if False, raise error for non-JSON

        Returns:
            Response data (parsed JSON or HTML text depending on response)
        """
        return self._request('POST', route, json_data=json_data,
                             data=data, headers=headers, accept_html=accept_html)

    def json_rpc(self, endpoint: str, method: str, params: Dict = None) -> Any:
        """
        Make a JSON-RPC request to Odoo.

        Args:
            endpoint: The JSON-RPC endpoint (e.g., '/web/dataset/call_kw')
            method: The RPC method to call
            params: Parameters for the method

        Returns:
            JSON-RPC result
        """
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint

        payload = {
            'jsonrpc': '2.0',
            'method': method,
            'params': params or {},
            'id': self._generate_request_id()
        }

        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        if self._session_id:
            headers['Cookie'] = f'session_id={self._session_id}'

        response = self._client.post(
            f"{self._url}{endpoint}",
            json=payload,
            headers=headers,
            timeout=30
        )

        response.raise_for_status()
        result = response.json()

        if 'error' in result:
            error_data = result['error']
            error_msg = error_data.get('data', {}).get('message', str(error_data))
            raise OdooRequestError(f"Odoo server error: {error_msg}", error_data)

        return result.get('result')

    def call_kw(self, model: str, method: str, args: List = None, kwargs: Dict = None) -> Any:
        """
        Call a method on an Odoo model using JSON-RPC.

        Args:
            model: The model name (e.g., 'res.partner')
            method: The method to call (e.g., 'search_read')
            args: Positional arguments for the method
            kwargs: Keyword arguments for the method

        Returns:
            Method result
        """
        params = {
            'model': model,
            'method': method,
            'args': args or [],
            'kwargs': kwargs or {}
        }

        return self.json_rpc('/web/dataset/call_kw', 'call', params)

    def search_read(self, model: str, domain: List = None, fields: List = None,
                    limit: int = None, offset: int = 0, order: str = None) -> List[Dict]:
        """
        Search and read records from a model.

        Args:
            model: The model name (e.g., 'res.partner')
            domain: Search domain (e.g., [('is_company', '=', True)])
            fields: Fields to fetch (e.g., ['name', 'email'])
            limit: Maximum number of records
            offset: Record offset for pagination
            order: Sorting order (e.g., 'name ASC')

        Returns:
            List of records
        """
        kwargs = {'offset': offset}
        if fields:
            kwargs['fields'] = fields
        if limit:
            kwargs['limit'] = limit
        if order:
            kwargs['order'] = order

        return self.call_kw(model, 'search_read', [domain or []], kwargs)

    def _generate_request_id(self) -> int:
        """Generate a unique request ID for JSON-RPC calls"""
        import time
        import random
        return int(time.time() * 1000) + random.randint(1, 1000)

    def _request(self, method: str, route: str, params: Dict = None,
                 json_data: Dict = None, data: Dict = None, headers: Dict = None,
                 accept_html: bool = True) -> Any:
        """
        Make a request to an Odoo HTTP route.

        Args:
            method: HTTP method (GET, POST, etc.)
            route: The route path
            params: Optional query parameters
            json_data: Optional JSON data for POST requests
            data: Optional form data for POST requests
            headers: Optional additional headers
            accept_html: If True, accept HTML responses; if False, raise error for non-JSON

        Returns:
            Response data (parsed JSON if applicable, or text if HTML and accept_html=True)
        """
        # Ensure route starts with a slash
        if not route.startswith('/'):
            route = '/' + route

        # Prepare headers
        request_headers = {
            'Accept': 'application/json, text/plain, */*'
        }

        # Add session cookie for authenticated requests
        if self._session_id:
            request_headers['Cookie'] = f'session_id={self._session_id}'

        # Add content type header if sending JSON data
        if json_data:
            request_headers['Content-Type'] = 'application/json'

        # Add custom headers if provided
        if headers:
            request_headers.update(headers)

        url = f"{self._url}{route}"

        try:
            response = None
            if method.upper() == 'GET':
                response = self._client.get(url, params=params, headers=request_headers, timeout=30)
            elif method.upper() == 'POST':
                response = self._client.post(url, params=params, json=json_data,
                                             data=data, headers=request_headers, timeout=30)
            else:
                # For other methods like PUT, DELETE, etc.
                response = self._client.request(method, url, params=params, json=json_data,
                                                data=data, headers=request_headers, timeout=30)

            response.raise_for_status()

            # Try to parse as JSON
            try:
                result = response.json()
                # Handle Odoo error responses
                if isinstance(result, dict) and 'error' in result:
                    error_data = result['error']
                    error_msg = error_data.get('data', {}).get('message', str(error_data))
                    raise OdooRequestError(f"Odoo server error: {error_msg}", error_data)
                return result
            except ValueError:
                # If JSON parsing fails but HTML is acceptable
                if accept_html:
                    return response.text
                else:
                    raise OdooRequestError("Expected JSON response but received HTML or text")

        except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.PoolTimeout):
            raise OdooConnectionError("Request timed out")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401 or e.response.status_code == 403:
                raise OdooAuthenticationError(f"Authentication error: {str(e)}")
            raise OdooConnectionError(f"HTTP error {e.response.status_code}: {str(e)}")
        except httpx.HTTPError as e:
            raise OdooConnectionError(f"HTTP error occurred: {str(e)}")
        except Exception as e:
            raise OdooRequestError(f"Unexpected error: {str(e)}")


def connect_http(url: str, session_id: Optional[str] = None) -> OdooHttpClient:
    """
    Create an HTTP client for accessing Odoo routes.

    Args:
        url: Odoo instance URL
        session_id: Optional session ID for authenticated routes

    Returns:
        OdooHttpClient instance
    """
    if not url:
        raise ValueError("URL must be provided")

    url = url.rstrip('/')
    return OdooHttpClient(url, session_id)