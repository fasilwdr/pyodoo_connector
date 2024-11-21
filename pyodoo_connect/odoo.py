# -*- coding: utf-8 -*-
#############################################################################
# Author: Fasil
# Email: fasilwdr@hotmail.com
# WhatsApp: https://wa.me/966538952934
# Facebook: https://www.facebook.com/fasilwdr
# Instagram: https://www.instagram.com/fasilwdr
#############################################################################

import json
import random
import logging
import httpx
from .proxies import ModelProxy


class Environment:
    def __init__(self, odoo_instance):
        self.odoo = odoo_instance
        self._model_cache = {}
        self.context = {}  # Initializes an empty context
        self.user_info = {}
        self.settings = {}

    def update_context(self, result):
        """Update the environment with new context and other relevant data."""
        self.context = result.get('user_context', {})
        self.user_info = {
            'uid': result.get('uid'),
            'is_admin': result.get('is_admin'),
            'name': result.get('name'),
            'username': result.get('username'),
            'partner_id': result.get('partner_id'),
        }
        self.settings = {
            'web_base_url': result.get('web.base.url'),
            'localization': {
                'lang': self.context.get('lang'),
                'tz': self.context.get('tz')
            },
            'company_details': result.get('user_companies', {})
        }

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
        self.client = httpx.Client()  # Create persistent client
        self.uid = None
        self.version = None
        self.env = Environment(self)
        self.login()  # Automatically login on initialization

    def __del__(self):
        """Ensure the client is closed when the instance is destroyed"""
        self.client.close()

    def json_rpc(self, method, params):
        """ Perform a JSON-RPC to the given URL with the specified method and parameters. """
        if self.uid is None:
            raise Exception("User is not authenticated. Please log in first.")

        data = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": random.randint(0, 1000000000)
        }

        headers = {"Content-Type": "application/json"}

        try:
            response = self.client.post(
                self.jsonrpc_url,
                json=data,
                headers=headers,
                timeout=30.0  # Add reasonable timeout
            )
            response.raise_for_status()
            reply = response.json()

            if "error" in reply:
                logging.error(f"JSON RPC Error: {reply['error']}")
                raise ValueError("JSON RPC Error", reply["error"])

            if "result" not in reply:
                if "error" not in reply:
                    logging.info(f"Operation completed successfully, no result to return. Full reply: {reply}")
                    return None
                logging.error(f"No 'result' in response, full reply: {reply}")
                return None

            return reply["result"]

        except httpx.TimeoutException as e:
            logging.error(f"Timeout Error: {e}")
            raise ConnectionError("Request timed out", e)
        except httpx.HTTPError as e:
            logging.error(f"HTTP Error: {e}")
            raise ConnectionError("HTTP Error", e)
        except httpx.RequestError as e:
            logging.error(f"Request Error: {e}")
            raise ConnectionError("Request Error", e)

    def login(self):
        """ Authenticate and establish a session with the Odoo server. """
        login_url = f"{self.url}/web/session/authenticate"

        data = {
            "jsonrpc": "2.0",
            "params": {
                "db": self.db,
                "login": self.username,
                "password": self.password
            }
        }

        headers = {'Content-Type': 'application/json'}

        try:
            response = self.client.post(
                login_url,
                json=data,
                headers=headers,
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()

            if result.get('result'):
                self.uid = result.get('result').get('uid')
                self.version = result.get('result').get('server_version')
                if self.uid is None:
                    raise Exception("Failed to obtain user ID.")
                # Update context
                self.env.update_context(result.get('result'))
            else:
                raise Exception("Login failed: " + str(result.get('error')))

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise Exception("Unauthorized")
            else:
                raise ConnectionError(f"HTTP Error during login: {e}")
        except httpx.RequestError as e:
            raise ConnectionError(f"Request Error during login: {e}")

    def call(self, service, method, *args):
        params = {
            "service": service,
            "method": method,
            "args": [self.db, self.uid, self.password] + list(args),
        }
        return self.json_rpc("call", params)

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

    def download_report(self, report_name: str, record_ids: list, file_name: str = None):
        """ Download a PDF report from Odoo. """
        report_url = f"{self.url}/report/pdf/{report_name}/{','.join(map(str, record_ids))}"

        try:
            response = self.client.get(report_url)
            response.raise_for_status()

            if file_name is None:
                file_name = 'Report.pdf'
            else:
                file_name += '.pdf'

            with open(file_name, 'wb') as f:
                f.write(response.content)
            print("Report downloaded successfully.")

        except httpx.HTTPError as e:
            print(f"Failed to download report: {e}")
        except httpx.RequestError as e:
            print(f"Failed to download report: {e}")