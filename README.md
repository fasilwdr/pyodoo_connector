# PyOdoo Connector

A powerful Python package for interacting with Odoo platforms via JSON-RPC. This library provides a seamless interface for performing operations and executing custom methods on your Odoo instance.

## Features

- 🔐 Simple session-based authentication
- 🚀 Unified `OdooSession` entry point (new in 0.3.0)
- 📝 Direct access to all Odoo methods
- 🎯 Clean and intuitive API design
- 🔍 Easy record browsing
- 📊 Support for Odoo's standard context-based behavior
- 🛡️ Comprehensive error handling with exportable exception types
- ⚡ Lightweight and fast — single shared HTTP connection pool per session

## Installation

```bash
pip install pyodoo_connect --upgrade
```

### Requirements
- Python 3.8+
- httpx>=0.24.0
- Access to an Odoo instance with JSON-RPC enabled

## Quick Start

### Recommended: OdooSession (v0.3.0+)

`OdooSession` authenticates once and reuses a single HTTP connection pool for all
model and record operations — no need to juggle session IDs manually.

```python
from pyodoo_connect import OdooSession

session = OdooSession(
    url="https://your-odoo-instance.com",
    db="your_database",
    username="your_username",
    password="your_password",
)

# Access any model (Odoo-style syntax supported)
partner_model = session["res.partner"]  # equivalent to session.env("res.partner")
partners_admin = partner_model.sudo()
partners_for_user_5 = partner_model.with_user(5)
partners_ar = partner_model.with_context(lang="ar_001")
```

If you already have a session ID:

```python
from pyodoo_connect import connect_odoo, OdooSession

session_id = connect_odoo(
    url="https://your-odoo-instance.com",
    db="your_database",
    username="your_username",
    password="your_password",
)
session = OdooSession(url="https://your-odoo-instance.com", session_id=session_id)
partner_model = session["res.partner"]
```

### Legacy: separate connect functions

```python
from pyodoo_connect import connect_odoo, connect_model

# Step 1 – authenticate
session_id = connect_odoo(
    url="https://your-odoo-instance.com",
    db="your_database",
    username="your_username",
    password="your_password",
)

# Step 2 – connect to a model
partner_model = connect_model(
    session_id=session_id,
    url="https://your-odoo-instance.com",
    model="res.partner",
)
```

## Usage Examples

### Create Records

```python
# Create a partner and get back an OdooRecord
partner = partner_model.create({"name": "John Doe", "email": "john@example.com"})
print(partner.id)   # record ID

# Call methods on the returned record directly
partner.write({"phone": "+1234567890"})
```

### Search, Count and Read

```python
# Search – returns list of IDs
ids = partner_model.search([("is_company", "=", True)], limit=10, order="name ASC")

# Count matching records
total = partner_model.search_count([("customer_rank", ">", 0)])

# Search and read fields in one call
rows = partner_model.search_read(
    domain=[("is_company", "=", True)],
    fields=["name", "email", "phone"],
    limit=5,
)

# Read specific fields for known IDs
records = partner_model.read([1, 2, 3], fields=["name", "email"])
```

### Update and Delete

```python
# Update records via OdooModel (accepts single ID or list)
partner_model.write(1, {"phone": "+1234567890"})
partner_model.write([1, 2, 3], {"active": False})

# Delete records
partner_model.unlink(1)
partner_model.unlink([1, 2, 3])
```

### Browse Existing Records

```python
# Browse a single record
company = partner_model.browse(1)
print(company.id)

# Browse multiple records
partners = partner_model.browse([1, 2, 3])
```

### Call Any Odoo Method

```python
# Call any method on a record
partner = partner_model.browse(1)
partner.action_archive()

# Pass positional and keyword arguments
partner.message_post(body="Hello world!", message_type="comment")
```

### Context Management

```python
# Apply a context override for a single call chain
translated = partner_model.with_context(lang="es_ES")
rows = translated.search_read(fields=["name"])

# Keyword syntax also works
partner.with_context(active_test=False).unlink()
```

### Using Command for Relational Fields

```python
from pyodoo_connect import Command

order = order_model.create({
    "partner_id": 1,
    "order_line": [
        Command.create({"product_id": 1, "product_uom_qty": 2, "price_unit": 100})
    ],
})
```

### HTTP Client for Custom Routes

```python
from pyodoo_connect import connect_http

http = connect_http("https://your-odoo-instance.com", session_id=session_id)

# GET / POST any Odoo route
info = http.get("/web/session/get_session_info")

# Convenience: search_read via JSON-RPC
rows = http.search_read("res.partner", domain=[], fields=["name"], limit=5)
```

## Error Handling

All exceptions are importable directly from `pyodoo_connect`:

```python
from pyodoo_connect import (
    OdooException,
    OdooConnectionError,
    OdooAuthenticationError,
    OdooRequestError,
    OdooValidationError,
)

try:
    partner = partner_model.create({"name": "Test"})
except OdooValidationError as e:
    print(f"Validation Error: {e}")
except OdooAuthenticationError as e:
    print(f"Auth Error: {e}")
except OdooConnectionError as e:
    print(f"Connection Error: {e}")
except OdooRequestError as e:
    print(f"Request Error: {e}")
    print(f"Server response: {e.response}")
except OdooException as e:
    print(f"General Odoo Error: {e}")
```

## What's New in Version 0.3.0

- **`OdooSession`** — unified entry point that authenticates once and shares a single HTTP connection pool across all model and record operations
- **Explicit model methods** — `search`, `search_count`, `search_read`, `write`, `unlink`, and `read` are now first-class methods on `OdooModel` (no longer only accessible via `__getattr__`)
- **`OdooRecord.id` property** — clean programmatic access to the record ID
- **`__repr__`/`__str__`** on `OdooRecord` and `OdooModel` for easier debugging
- **`__bool__` on `OdooRecord`** — evaluates to `True` for valid records
- **Shared HTTP client** — `OdooSession`, `OdooModel` and `OdooRecord` share one `httpx.Client`
- **Exceptions exported** — all exception types are now importable from `pyodoo_connect` directly
- **`connect_model` accepts `context`** — pass an initial context when connecting to a model
- **`tools.Command` parameter rename** — `id` → `record_id` (avoids shadowing Python builtin)
- **Updated classifiers** — Python 3.8–3.12; status promoted to *Beta*
- **Comprehensive test suite** — 58 unit tests using mocks, no real server required

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author

- **Name:** Fasil
- **Email:** fasilwdr@hotmail.com
