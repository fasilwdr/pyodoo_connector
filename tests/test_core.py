import unittest
from unittest.mock import patch, MagicMock
from odoo_connector.core import Odoo


class TestOdoo(unittest.TestCase):
    def setUp(self):
        # Setup a mock for the Odoo instance that does not perform actual HTTP requests
        self.odoo = Odoo('https://62234807-17-0-all.runbot161.odoo.com/', '62234807-17-0-all', 'admin', 'admin')
        self.odoo.uid = 1  # Simulate a successful login by setting a user ID

    @patch('odoo_connector.core.urllib.request.Request')
    @patch('odoo_connector.core.urllib.request.build_opener')
    def test_login(self, mock_build_opener, mock_request):
        # Prepare the mock response object to simulate the server's response
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"result": {"uid": 1}}'

        # Setup the mock opener to use our mock response
        mock_opener = MagicMock()
        mock_opener.open.return_value = mock_response
        mock_build_opener.return_value = mock_opener

        self.odoo.login()
        self.assertEqual(self.odoo.uid, 1)

    @patch('odoo_connector.core.urllib.request.Request')
    @patch('odoo_connector.core.urllib.request.build_opener')
    def test_read(self, mock_build_opener, mock_request):
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"result": 10}'
        mock_opener = MagicMock()
        mock_opener.open.return_value = mock_response
        mock_build_opener.return_value = mock_opener

        result = self.odoo.read('res.partner', [1], ['name', 'title'])
        self.assertEqual(result, 10)

    @patch('odoo_connector.core.urllib.request.Request')
    @patch('odoo_connector.core.urllib.request.build_opener')
    def test_search(self, mock_build_opener, mock_request):
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"result": [1, 2, 3]}'
        mock_opener = MagicMock()
        mock_opener.open.return_value = mock_response
        mock_build_opener.return_value = mock_opener

        result = self.odoo.search('res.partner', [('name', '=', 'Partner')])
        self.assertEqual(result, [1, 2, 3])


if __name__ == '__main__':
    unittest.main()
