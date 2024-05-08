import json
import random
import logging
import urllib.request
from urllib.error import URLError, HTTPError

class MethodCaller:
    def __init__(self, model_proxy, record_id, method_name):
        self.model_proxy = model_proxy
        self.record_id = record_id
        self.method_name = method_name

    def __call__(self, *args, **kwargs):
        return self.model_proxy.odoo.execute_function(
            self.model_proxy.model_name,
            [self.record_id],
            self.method_name,
            **kwargs
        )

class RecordProxy:
    def __init__(self, model_proxy, record_id):
        self.model_proxy = model_proxy
        self.record_id = record_id
        self.data = {}
        self._fetch()

    def _fetch(self):
        fields = self.model_proxy.fields_get([], ['name'])  # Fetch all fields with their names
        self.data = self.model_proxy.read([self.record_id], list(fields.keys()))[0]

    def __getattr__(self, name):
        if name in self.data:
            return self.data[name]
        else:
            # Treat any unknown attribute as a method call
            return MethodCaller(self.model_proxy, self.record_id, name)

    def __setattr__(self, name, value):
        if name in ['model_proxy', 'record_id', 'data'] or name.startswith('_'):
            super(RecordProxy, self).__setattr__(name, value)
        else:
            self.model_proxy.write([self.record_id], {name: value})
            self.data[name] = value  # Update the local cache after the write operation

class ModelProxy:
    def __init__(self, odoo_instance, model_name):
        self.odoo = odoo_instance
        self.model_name = model_name

    def browse(self, record_id):
        return RecordProxy(self, record_id)

    def search(self, domain, limit=100):
        return self.odoo.call("object", "execute", self.model_name, 'search', domain, 0, limit)

    def search_count(self, domain: list):
        return self.odoo.call("object", "execute", self.model_name, 'search_count', domain)

    def fields_get(self, fields: list, attributes: list):
        return self.odoo.call("object", "execute", self.model_name, 'fields_get', fields, attributes)

    def create(self, data: dict):
        return self.odoo.call("object", "execute", self.model_name, 'create', data)

    def read(self, ids: list, fields: list):
        return self.odoo.call("object", "execute", self.model_name, 'read', ids, fields)

    def search_read(self, domain: list, fields: list):
        return self.odoo.call("object", "execute", self.model_name, 'search_read', domain, fields)

    def write(self, ids: list, data: dict):
        return self.odoo.call("object", "execute", self.model_name, 'write', ids, data)

    def unlink(self, ids: list):
        return self.odoo.call("object", "execute", self.model_name, 'unlink', ids)

class Environment:
    def __init__(self, odoo_instance):
        self.odoo = odoo_instance
        self._model_cache = {}

    def __getitem__(self, model_name):
        if model_name not in self._model_cache:
            self._model_cache[model_name] = ModelProxy(self.odoo, model_name)
        return self._model_cache[model_name]


class Odoo:
    """ A Python class to interact with Odoo via JSON-RPC. """

    def __init__(self, url, db, username, password):
        """ Initialize the Odoo instance with the necessary credentials and urls. """
        self.db = db
        self.username = username
        self.password = password
        self.url = url
        self.jsonrpc_url = f"{url}jsonrpc" if url[-1] == '/' else f"{url}/jsonrpc"
        self.session = None
        self.uid = None
        self.env = Environment(self)
        self.login()  # Automatically login on initialization

    # def json_rpc(self, method, params):
    #     """ Perform a JSON-RPC to the given URL with the specified method and parameters. """
    #     if self.uid is None:
    #         raise Exception("User is not authenticated. Please log in first.")
    #     data = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": random.randint(0, 1000000000)}).encode('utf-8')
    #     headers = {"Content-Type": "application/json"}
    #     req = urllib.request.Request(self.jsonrpc_url, data=data, headers=headers)
    #     try:
    #         with self.session.open(req) as response:
    #             reply = json.loads(response.read().decode())
    #             if "error" in reply:
    #                 logging.error(f"JSON RPC Error: {reply['error']}")
    #                 raise ValueError("JSON RPC Error", reply["error"])
    #             return reply["result"]
    #     except HTTPError as e:
    #         logging.error(f"HTTP Error: {e}")
    #         raise ConnectionError("HTTP Error", e)
    #     except URLError as e:
    #         logging.error(f"Request Error: {e}")
    #         raise ConnectionError("Request Error", e)

    def json_rpc(self, method, params):
        """ Perform a JSON-RPC to the given URL with the specified method and parameters. """
        if self.uid is None:
            raise Exception("User is not authenticated. Please log in first.")
        data = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": random.randint(0, 1000000000)}).encode('utf-8')
        headers = {"Content-Type": "application/json"}
        req = urllib.request.Request(self.jsonrpc_url, data=data, headers=headers)
        try:
            with self.session.open(req) as response:
                reply = json.loads(response.read().decode())
                if "error" in reply:
                    logging.error(f"JSON RPC Error: {reply['error']}")
                    raise ValueError("JSON RPC Error", reply["error"])
                if "result" not in reply:
                    # Log success if no result is returned but also no error is present
                    if "error" not in reply:
                        logging.info(f"Operation completed successfully, no result to return. Full reply: {reply}")
                        return None
                    logging.error(f"No 'result' in response, full reply: {reply}")
                    return None  # Handle cases where 'result' might not be present
                return reply["result"]
        except HTTPError as e:
            logging.error(f"HTTP Error: {e}")
            raise ConnectionError("HTTP Error", e)
        except URLError as e:
            logging.error(f"Request Error: {e}")
            raise ConnectionError("Request Error", e)

    def login(self):
        """ Authenticate and establish a session with the Odoo server. """
        login_url = f"{self.url}/web/session/authenticate"
        headers = {'Content-Type': 'application/json'}
        data = json.dumps({"jsonrpc": "2.0", "params": {"db": self.db, "login": self.username, "password": self.password}}).encode('utf-8')
        req = urllib.request.Request(login_url, data=data, headers=headers)
        self.session = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
        try:
            with self.session.open(req) as response:
                result = json.loads(response.read().decode())
                if result.get('result'):
                    self.uid = result.get('result').get('uid')
                    if self.uid is None:
                        raise Exception("Failed to obtain user ID.")
                else:
                    raise Exception("Login failed: " + str(result.get('error')))
        except HTTPError as e:
            if e.code == 401:
                raise Exception("Unauthorized")
            else:
                raise ConnectionError(f"HTTP Error during login: {e}")
        except URLError as e:
            raise ConnectionError(f"Request Error during login: {e}")

    def call(self, service, method, *args):
        params = {
            "service": service,
            "method": method,
            "args": [self.db, self.uid, self.password] + list(args),
        }
        return self.json_rpc("call", params)

    def create(self, model: str, data: dict):
        return self.call("object", "execute", model, 'create', data)

    def search(self, model: str, domain: list, limit: int = 100):
        return self.call("object", "execute", model, 'search', domain, 0, limit)

    def read(self, model: str, ids: list, fields: list):
        return self.call("object", "execute", model, 'read', ids, fields)

    def write(self, model: str, ids: list, data: dict):
        return self.call("object", "execute", model, 'write', ids, data)

    def unlink(self, model: str, ids: list):
        return self.call("object", "execute", model, 'unlink', ids)

    def execute_function(self, model, ids, function_name, **kwargs):
        """
        Executes a custom function on a model for given IDs.

        Args:
        - model (str): The model on which the function needs to be executed.
        - ids (list): List of record IDs for which the function should be applied.
        - function_name (str): The name of the function to execute.
        - kwargs (dict): Keyword arguments to pass to the function.

        Returns:
        - The result of the function execution.
        """
        params = {
            "service": "object",
            "method": "execute_kw",
            "args": [self.db, self.uid, self.password, model, function_name, [ids], kwargs],
        }
        return self.json_rpc("call", params)

    def download_report(self, report_name: str, record_ids: list, file_name: str=None):
        """ Download a PDF report from Odoo. """
        report_url = f"{self.url}/report/pdf/{report_name}/{','.join(map(str, record_ids))}"
        req = urllib.request.Request(report_url)
        if file_name is None:
            file_name = 'Report.pdf'
        else:
            file_name += '.pdf'
        try:
            with self.session.open(req) as response:
                with open(file_name, 'wb') as f:
                    f.write(response.read())
                print("Report downloaded successfully.")
        except HTTPError as e:
            print(f"Failed to download report: {e.code}, {e.read().decode()}")
        except URLError as e:
            print(f"Failed to download report: {e}")