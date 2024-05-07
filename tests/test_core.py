import unittest
from unittest.mock import patch, MagicMock
from odoo_connector.core import Odoo

class TestOdoo(unittest.TestCase):
    def setUp(self):
        # Setup a mock for the Odoo instance that does not perform actual HTTP requests
        self.odoo = Odoo('http://fake-url.com', 'db', 'user', 'pass')
        self.odoo.uid = 1  # Simulate a successful login by setting a user ID

    @patch('odoo_connector.core.urllib.request')
    def test_login(self, mock_urllib):
        # Test the login function to make sure it sets the uid correctly
        mock_response = MagicMock()
        mock_response.read.return_value = '{"result": {"uid": 1}}'.encode('utf-8')
        mock_urllib.build_opener().open.return_value = mock_response

        self.odoo.login()
        self.assertEqual(self.odoo.uid, 1)

    @patch('odoo_connector.core.urllib.request')
    def test_create(self, mock_urllib):
        # Test the create function to make sure it can handle a creation operation
        mock_response = MagicMock()
        mock_response.read.return_value = '{"result": 10}'.encode('utf-8')
        mock_urllib.build_opener().open.return_value = mock_response

        result = self.odoo.create('res.partner', {'name': 'New Partner'})
        self.assertEqual(result, 10)

    @patch('odoo_connector.core.urllib.request')
    def test_search(self, mock_urllib):
        # Test the search function to simulate a search operation
        mock_response = MagicMock()
        mock_response.read.return_value = '{"result": [1, 2, 3]}'.encode('utf-8')
        mock_urllib.build_opener().open.return_value = mock_response

        result = self.odoo.search('res.partner', [('name', '=', 'Partner')])
        self.assertEqual(result, [1, 2, 3])

if __name__ == '__main__':
    unittest.main()
