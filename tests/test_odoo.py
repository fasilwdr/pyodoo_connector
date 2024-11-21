# -*- coding: utf-8 -*-
#############################################################################
# Author: Fasil
# Email: fasilwdr@hotmail.com
# WhatsApp: https://wa.me/966538952934
# Facebook: https://www.facebook.com/fasilwdr
# Instagram: https://www.instagram.com/fasilwdr
#############################################################################
import json
import pytest
from unittest.mock import patch, MagicMock
from pyodoo_connect.odoo import Odoo


class TestOdoo:
    @patch('httpx.Client')
    def test_login_successful(self, mock_client):
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "result": {
                "uid": 1,
                "server_version": "15.0",
                "user_context": {"lang": "en_US", "tz": "UTC"},
                "user_companies": False
            }
        }
        mock_response.raise_for_status.return_value = None

        # Setup mock client
        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_response
        mock_client.return_value = mock_client_instance

        # Create an instance of the Odoo class
        odoo = Odoo('http://fake-url.com', 'db', 'user', 'pass')

        # Check if the UID is set correctly
        assert odoo.uid == 1, "UID should be set to 1 after successful login"
        assert odoo.version == "15.0", "Version should be set correctly"

    @patch('httpx.Client')
    def test_login_failure(self, mock_client):
        # Mock response for failed login
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "error": "Invalid credentials"
        }
        mock_response.raise_for_status.return_value = None

        # Setup mock client
        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_response
        mock_client.return_value = mock_client_instance

        # Attempt to create an instance of the Odoo class and catch the expected exception
        with pytest.raises(Exception) as excinfo:
            Odoo('http://fake-url.com', 'db', 'user', 'pass')

        assert "Login failed: Invalid credentials" in str(excinfo.value)

    @patch('httpx.Client')
    def test_execute_function(self, mock_client):
        # Mock login response
        mock_login_response = MagicMock()
        mock_login_response.json.return_value = {
            "jsonrpc": "2.0",
            "result": {
                "uid": 1,
                "server_version": "15.0",
                "user_context": {"lang": "en_US", "tz": "UTC"},
                "user_companies": False
            }
        }

        # Mock execute function response
        mock_execute_response = MagicMock()
        mock_execute_response.json.return_value = {
            "jsonrpc": "2.0",
            "result": {"status": "Success"}
        }

        # Setup mock client
        mock_client_instance = MagicMock()
        mock_client_instance.post.side_effect = [mock_login_response, mock_execute_response]
        mock_client.return_value = mock_client_instance

        # Create an instance and execute function
        odoo = Odoo('http://fake-url.com', 'db', 'user', 'pass')
        result = odoo.execute_function('res.partner', [1], 'action_archive')

        # Verify the result
        assert result == {"status": "Success"}, "Function execution should return success status"

    @patch('httpx.Client')
    def test_client_cleanup(self, mock_client):
        """Test that the client is properly closed when the Odoo instance is destroyed"""
        # Setup mock client
        mock_client_instance = MagicMock()
        mock_login_response = MagicMock()
        mock_login_response.json.return_value = {
            "jsonrpc": "2.0",
            "result": {
                "uid": 1,
                "server_version": "15.0",
                "user_context": {"lang": "en_US", "tz": "UTC"},
                "user_companies": False
            }
        }
        mock_client_instance.post.return_value = mock_login_response
        mock_client.return_value = mock_client_instance

        # Create and explicitly close an Odoo instance
        odoo = Odoo('http://fake-url.com', 'db', 'user', 'pass')
        odoo.__del__()  # Explicitly call the destructor

        # Verify the client was closed
        mock_client_instance.close.assert_called_once()