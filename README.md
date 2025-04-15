# PyOdoo Connector

A powerful Python package for interacting with Odoo platforms via JSON-RPC. This library provides a seamless interface for performing operations and executing custom methods on your Odoo instance.

## Features

- 🔐 Simple session-based authentication
- 📝 Direct access to all Odoo methods
- 🎯 Clean and intuitive API design
- 🔍 Easy record browsing
- 📊 Support for Odoo's standard context-based behavior
- 🛡️ Comprehensive error handling
- 🚀 Lightweight and fast

## Installation

```bash
pip install pyodoo_connect --upgrade
```

### Requirements
- Python 3.6+
- httpx>=0.24.0
- Access to an Odoo instance with JSON-RPC enabled

## Quick Start

### Connect to Odoo

```python
from pyodoo_connect import connect_odoo

# Get session ID from Odoo
session_id = connect_odoo(
    url="https://your-odoo-instance.com",
    db="your_database",
    username="your_username",
    password="your_password"
)
```

### Connect to a Model

```python
from pyodoo_connect import connect_model

# Connect to a specific model
partner_model = connect_model(
    session_id=session_id,
    url="https://your-odoo-instance.com",
    model="res.partner"
)
```

## Usage Examples

### Create Records

```python
# Create a single partner
vals = {'name': 'John Doe', 'email': 'john@example.com'}
partner = partner_model.create(vals)

# Use the returned record object directly
partner.write({'phone': '+1234567890'})
```

### Call Any Odoo Method

```python
# Call methods directly on records
partner.any_function()

# Use the with_context method to change context
translated_partner = partner.with_context(lang='es_ES')
spanish_name = translated_partner.read('name')

# Call methods with arguments
partner.message_post(body="Hello world!")

# Call methods with keyword arguments
partner.message_post(body="Hello", message_type="comment")

# Call methods with dictionary context
partner.with_context({"active_test": False}).unlink()
```

### Working with Model Methods

```python
# Search for records
partners = partner_model.search([('is_company', '=', True)])

# Browse existing records
company = partner_model.browse(1)

# Call custom model methods
count = partner_model.search_count([])
```

### Using Command for Relational Fields

```python
from pyodoo_connect import Command

# Creating a sales order with order lines
order = order_model.create({
    'partner_id': 1,
    'order_line': [
        Command.create({
            'product_id': 1,
            'product_uom_qty': 2,
            'price_unit': 100
        })
    ]
})
```

## Error Handling

The library provides specific exceptions for different error scenarios:

```python
from pyodoo_connect import (
    OdooException,
    OdooConnectionError,
    OdooAuthenticationError,
    OdooRequestError,
    OdooValidationError
)

try:
    partner = partner_model.create({'name': 'Test', 'email': 'invalid_email'})
except OdooValidationError as e:
    print(f"Validation Error: {str(e)}")
except OdooConnectionError as e:
    print(f"Connection Error: {str(e)}")
except OdooException as e:
    print(f"General Odoo Error: {str(e)}")
```

## What's New in Version 0.2.0

- Completely redesigned API with simplified session handling
- Direct access to all Odoo model methods with proper return types
- Automatic passing of record IDs for method calls
- Enhanced context management with both dictionary and keyword argument support
- Improved error handling with specific exception types
- Streamlined record creation and management

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author

- **Name:** Fasil
- **Email:** fasilwdr@hotmail.com