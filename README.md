
# Odoo Connector

Odoo Connector is a Python package providing a convenient way to interact with Odoo platforms via JSON-RPC. It simplifies operations like logging in, executing commands, and managing records in an Odoo database.

## Features

- **Session Management**: Handles login and session management automatically.
- **CRUD Operations**: Easy-to-use functions for creating, reading, updating, and deleting records.
- **Method Execution**: Supports calling custom methods defined in Odoo models.
- **Error Handling**: Implements error handling for HTTP and URL request errors.
- **Report Downloading**: Allows downloading reports from Odoo in PDF form.

## Installation

Install Odoo Connector using pip:

```bash
pip install pyodoo_connect
```

### Prerequisites

- Python 3.6 or higher.
- Access to an Odoo instance with the JSON-RPC interface enabled.

Ensure you have the necessary permissions to interact with the Odoo server as some operations might require administrative access.

## Configuration

Before using this module, configure the connection parameters to match your Odoo instance settings:

1. **URL**: The URL of your Odoo server.
2. **Database**: The database name.
3. **Username**: Your Odoo username.
4. **Password**: Your Odoo password.

## Usage

Here is a simple example to show how you can use Odoo Connector to interact with an Odoo instance:
### Initializing the Connection
```python
from pyodoo_connect import Odoo
odoo = Odoo('https://example-odoo.com/', 'your-db', 'your-username', 'your-password')
```
### Basic Operations
- Get a Partner Record
```python
partner = odoo.env['res.partner'].browse(9)
partner.name = 'New Partner Name'
```

- Execute a Method on a Record
```python
partner.action_archive()
partner.update({'mobile': '12345678'})
```
- Search for Records
```python
partner_ids = odoo.env['res.partner'].search(domain=[('name', '=', 'Abigail Peterson')])
print(partner_ids)
```
- Read Records
```python
print(partner.name)
records = odoo.env['res.partner'].read(ids=search_check, fields=['name', 'email'])
print(records)
```
- Create a New Record
```python
new_partner_id = odoo.env['res.partner'].create({'name': 'New Partner', 'email': 'new@partner.com', 'is_company': True})
print(new_partner_id)
```
- Update Records
```python
odoo.env['res.partner'].write(ids=new_partner_id, values={'phone': '1234567890'})
```
- Delete Records
```python
odoo.env['res.partner'].unlink(ids=new_partner_id)
```
- Download a QWeb Report
```python
odoo.download_report(report_name='sale.report_saleorder', record_ids=[52], file_name='Sales Report')
```

## Contributing
Contributions are welcome! Please feel free to submit pull requests, report bugs, or suggest features.

## License
This project is licensed under the MIT License - see the LICENSE file for details.
