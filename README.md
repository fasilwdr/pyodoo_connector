
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
partner.update(values={'mobile': '12345678'})
```
- Search for Records
```python
search_check = odoo.env['res.partner'].search(domain=[('name', '=', 'Abigail Peterson')])
print("search_check", search_check)
```
- Read Records
```python
read_check = odoo.env['res.partner'].read(ids=search_check, fields=['name', 'email'])
print("read_check", read_check)
```
- Create a New Record
```python
create_check = odoo.env['res.partner'].create({'name': 'New Partner', 'email': 'new@partner.com', 'is_company': True})
print("create_check", create_check)
```
- Update Records
```python
write_check = odoo.env['res.partner'].write(ids=[create_check], values={'phone': '1234567890'})
print("write_check", write_check)
```
- Delete Records
```python
unlink_check = odoo.env['res.partner'].unlink(ids=[create_check])
print("unlink_check", unlink_check)
```
- Download a QWeb Report
```python
odoo.download_report(report_name='sale.report_saleorder', record_ids=[52], file_name='Sales Report')
```

## Contributing
Contributions are welcome! Please feel free to submit pull requests, report bugs, or suggest features.

## License
This project is licensed under the MIT License - see the LICENSE file for details.
