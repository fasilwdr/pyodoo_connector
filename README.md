# PyOdoo Connector

A powerful Python package for interacting with Odoo platforms via JSON-RPC. This library provides a seamless interface for performing CRUD operations, managing sessions, and executing custom methods on your Odoo instance.

## Features

- 🔐 Secure session management and authentication
- 📝 Complete CRUD operations support
- 🔄 Automatic session renewal
- 🎯 Custom method execution
- 🛡️ Comprehensive error handling
- 🔍 Smart record browsing and caching
- 📊 Efficient batch operations
- 🌐 Context management

## Installation

```bash
pip install pyodoo_connect
```

### Requirements
- Python 3.6+
- httpx>=0.24.0
- Access to an Odoo instance with JSON-RPC enabled

## Quick Start

### Basic Connection

```python
from pyodoo_connect import connect_odoo

# Connect to Odoo
odoo, session_id = connect_odoo(
    url="https://your-odoo-instance.com",
    db="your_database",
    username="your_username",
    password="your_password"
)

# Check connection
if odoo:
    print("Successfully connected!")
    print(f"Session ID: {session_id}")
```

## Usage Examples

### 1. Record Operations

#### Create Records
```python
# Create a single partner
partner_id = odoo.env('res.partner').create({
    'name': 'John Doe',
    'email': 'john@example.com',
    'phone': '+1234567890',
    'is_company': True
})

# Create with related records
from pyodoo_connect import Command

sales_order = odoo.env('sale.order').create({
    'partner_id': partner_id,
    'order_line': [Command.create({
        'product_id': 1,
        'product_uom_qty': 2,
        'price_unit': 100
    })]
})
```

#### Read Records
```python
# Browse a single record
partner = odoo.env('res.partner').browse(partner_id)
print(f"Partner Name: {partner.name}")
print(f"Email: {partner.email}")

# Search and read multiple records
partners = odoo.env('res.partner').search_read(
    domain=[('is_company', '=', True)],
    fields=['name', 'email', 'phone'],
    limit=5
)
for partner in partners:
    print(f"Company: {partner['name']}")
```

#### Update Records
```python
# Update using write method
odoo.env('res.partner').write([partner_id], {
    'name': 'John Smith',
    'email': 'john.smith@example.com'
})

# Update using record attribute
partner = odoo.env('res.partner').browse(partner_id)
partner.phone = '+9876543210'
```

#### Delete Records
```python
# Delete a single record
odoo.env('res.partner').unlink([partner_id])

# Delete multiple records
partner_ids = odoo.env('res.partner').search([
    ('name', 'like', 'Test%')
])
odoo.env('res.partner').unlink(partner_ids)
```

### 2. Relational Fields Operations

Using Command class for managing relations:

```python
from pyodoo_connect import Command

# Link existing records
partner.category_id = [Command.set([1, 2, 3])]  # Set specific tags

# Create and link new record
partner.child_ids = [
    Command.create({
        'name': 'Contact Person',
        'email': 'contact@example.com'
    })
]

# Update linked record
partner.child_ids = [
    Command.update(child_id, {
        'name': 'New Name'
    })
]

# Unlink records
partner.category_id = [Command.unlink(tag_id)]

# Clear all relations
partner.category_id = [Command.clear()]
```

### 3. Search Operations

```python
# Basic search
customer_ids = odoo.env('res.partner').search([
    ('customer_rank', '>', 0),
    ('is_company', '=', True)
])

# Search with additional parameters
products = odoo.env('product.product').search_read(
    domain=[('type', '=', 'product')],
    fields=['name', 'list_price', 'qty_available'],
    offset=0,
    limit=10,
    order='name ASC'
)
```

### 4. Context Management

```python
# Set context for specific operations
order = odoo.env('sale.order').browse(order_id)
order.with_context(force_company=2).action_confirm()

# Multiple context values
result = order.with_context({
    'lang': 'es_ES',
    'tz': 'Europe/Madrid',
    'force_company': 2
}).action_invoice_create()
```

### 5. Custom Method Execution

```python
# Execute custom methods on records
sale_order = odoo.env('sale.order').browse(order_id)
sale_order.action_confirm()  # Confirm sale order

# Execute with parameters
invoice = sale_order.with_context(default_type='out_invoice')._create_invoices()
```

### 6. Error Handling

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
    odoo.env('res.partner').create({
        'name': 'Test',
        'email': 'invalid_email'  # This will raise a validation error
    })
except OdooValidationError as e:
    print(f"Validation Error: {str(e)}")
except OdooConnectionError as e:
    print(f"Connection Error: {str(e)}")
except OdooException as e:
    print(f"General Odoo Error: {str(e)}")
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author

- **Name:** Fasil
- **Email:** fasilwdr@hotmail.com
- **WhatsApp:** [Contact](https://wa.me/966538952934)
- **Facebook:** [Profile](https://www.facebook.com/fasilwdr)
- **Instagram:** [Profile](https://www.instagram.com/fasilwdr)