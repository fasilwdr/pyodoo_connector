# Odoo Connector

Odoo Connector is a Python package providing a convenient way to interact with Odoo platforms via JSON-RPC. It simplifies operations like logging in, executing commands, and managing records in an Odoo database.

## Installation

Install Odoo Connector using pip:

```bash
pip install odoo_connector
```
## Usage

Here is a simple example to show how you can use Odoo Connector to interact with an Odoo instance:

```python
from odoo_connector.core import Odoo

# Initialize the connection
odoo = Odoo(url='https://your-odoo-instance.com', db='odoo_db', username='user', password='pass')

# Example: Create a new partner
partner_id = odoo.create('res.partner', {'name': 'New Partner', 'email': 'email@example.com'})
print(f'Created new partner with ID: {partner_id}')

# Example: Search for partners
partners = odoo.search('res.partner', [('name', 'ilike', 'New Partner')])
print(f'Partners found: {partners}')

# Example: Read partner details
partner_details = odoo.read('res.partner', partners, ['name', 'email'])
print(f'Partner details: {partner_details}')

```
## Contributing
Contributions are welcome! Please feel free to submit pull requests, report bugs, or suggest features.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
