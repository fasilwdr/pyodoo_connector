import json
import pytest
from unittest.mock import patch, MagicMock
from pyodoo_connect.odoo import Odoo


class TestOdoo:
    @patch('pyodoo_connect.odoo.urllib.request.build_opener')
    def test_login_successful(self, mock_build_opener):
        # Mock response and its read().decode() method to return JSON
        mock_response = MagicMock()
        mock_response.read.return_value.decode.return_value = json.dumps({"jsonrpc": "2.0", "result": {"uid": 1}})

        # Mock opener to return the mock response
        mock_opener = MagicMock()
        mock_opener.open.return_value.__enter__.return_value = mock_response
        mock_build_opener.return_value = mock_opener

        # Create an instance of the Odoo class
        odoo = Odoo('http://fake-url.com', 'db', 'user', 'pass')

        # Check if the UID is set correctly
        assert odoo.uid == 1, "UID should be set to 1 after successful login"

    @patch('pyodoo_connect.odoo.urllib.request.build_opener')
    def test_login_failure(self, mock_build_opener):
        # Setup the mock response to simulate a login failure
        mock_response = MagicMock()
        mock_response.read.return_value.decode.return_value = json.dumps(
            {"jsonrpc": "2.0", "error": "Invalid credentials"})

        mock_opener = MagicMock()
        mock_opener.open.return_value.__enter__.return_value = mock_response
        mock_build_opener.return_value = mock_opener

        # Attempt to create an instance of the Odoo class and catch the expected exception
        with pytest.raises(Exception) as excinfo:
            odoo = Odoo('http://fake-url.com', 'db', 'user', 'pass')

        assert "Invalid credentials" in str(excinfo.value), "Should raise an exception for invalid credentials"

    @patch('pyodoo_connect.odoo.urllib.request.build_opener')
    def test_execute_function(self, mock_build_opener):
        # Setup the mock response for executing a function
        mock_response = MagicMock()
        mock_response.read.return_value.decode.return_value = json.dumps({"jsonrpc": "2.0", "result": {"status": "Success", "uid": 1}})

        # Mock opener to return the mock response
        mock_opener = MagicMock()
        mock_opener.open.return_value.__enter__.return_value = mock_response
        mock_build_opener.return_value = mock_opener

        # Create an instance of the Odoo class and perform a function execution
        odoo = Odoo('http://fake-url.com', 'db', 'user', 'pass')
        result = odoo.execute_function('res.partner', [1], 'action_archive')

        # Check if the function executes successfully
        assert result.get("status") == "Success", "Function execution should return 'Success'"
