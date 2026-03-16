# PyOdoo Connect

A powerful Python package for interacting with Odoo platforms via JSON-RPC.
This library provides a seamless, **Odoo-style** interface for performing
CRUD operations, calling model methods, and managing context — all from
outside an Odoo environment.

## Features

- 🔐 Simple session-based authentication
- 🌐 `OdooSession` — mirrors `self.env` in Odoo
- 📋 `OdooRecordset` — Odoo-style recordsets with `ids`, `mapped`, `filtered`, `sorted`, `ensure_one`, set operations
- 📝 Direct access to all Odoo model methods
- 🔍 `search`, `search_read`, `search_count`, `read`, `browse`
- ✏️ `create`, `write`, `unlink`
- 🧩 `sudo()`, `with_user()`, `with_context()` for API compatibility
- 📦 Lazy field loading with local caching on `OdooRecord`
- 🛡️ Comprehensive error handling with typed exceptions
- 🔗 Shared `httpx` client for efficient connection reuse
- 🚀 Lightweight and fast

## Installation

```bash
pip install pyodoo_connect --upgrade
```

### Requirements
- Python 3.8+
- `httpx >= 0.24.0`
- Access to an Odoo instance with JSON-RPC enabled

---

## Quick Start

### 1. Authenticate

```python
from pyodoo_connect import connect_odoo, OdooSession

session_id = connect_odoo(
    url="https://your-odoo-instance.com",
    db="your_database",
    username="your_username",
    password="your_password",
)
```

### 2. Create a session environment

```python
env = OdooSession(url="https://your-odoo-instance.com", session_id=session_id)
```

### 3. Access models (like `self.env` in Odoo)

```python
Partner = env('res.partner')
# or equivalently:
Partner = env['res.partner']
```

---

## Usage Examples

### Search for records

```python
# Returns an OdooRecordset — iterate, index, check len, etc.
partners = Partner.search([('is_company', '=', True)], limit=10)

for partner in partners:
    print(partner.name)   # field values are fetched lazily and cached
    print(partner.email)

# Singleton field delegation — access fields directly on a single-record set
partner = Partner.search([('name', '=', 'John')], limit=1)
if partner:               # falsy when empty
    print(partner.name)   # field delegation on single-record set
```

### Search and read (returns dicts)

```python
results = Partner.search_read(
    domain=[('customer_rank', '>', 0)],
    fields=['name', 'email', 'phone'],
    limit=5,
    order='name ASC',
)
for row in results:
    print(row['name'], row['email'])
```

### Count records

```python
count = Partner.search_count([('is_company', '=', True)])
print(count)
```

### Create a record

```python
new_partner = Partner.create({'name': 'ACME Corp', 'is_company': True})
print(new_partner.id)     # integer database ID
print(new_partner)        # res.partner(42,)
```

### Write (update)

```python
# On a record instance
new_partner.write({'phone': '+1 800 555 0100'})

# On the model (multiple IDs at once)
Partner.write([1, 2, 3], {'active': False})
```

### Unlink (delete)

```python
# On a record instance
new_partner.unlink()

# On the model
Partner.unlink([4, 5, 6])
```

### Browse by ID

```python
partner = Partner.browse(1)          # single-record OdooRecordset
partners = Partner.browse([1, 2, 3]) # multi-record OdooRecordset
print(partners.ids)                  # [1, 2, 3]
```

### Recordset helpers

```python
# mapped — collect field values across all records
names = partners.mapped('name')      # ['Alice', 'Bob', 'Charlie']

# filtered — keep records matching a condition
companies = partners.filtered(lambda r: r.is_company)

# sorted — sort by field or key
by_name = partners.sorted('name')
by_id_desc = partners.sorted(reverse=True)

# ensure_one — raise ValueError if not exactly one record
partner = partners.filtered(lambda r: r.id == 1).ensure_one()

# set operations
all_partners = partners1 | partners2   # union (deduplicated)
common = partners1 & partners2         # intersection
diff = partners1 - partners2           # difference
```

### Read raw data

```python
data = Partner.read([1, 2], fields=['name', 'email'])
# [{'id': 1, 'name': '...', 'email': '...'}, ...]
```

### Call arbitrary Odoo methods on records

```python
order = env('sale.order').browse(10)
order.action_confirm()                        # no extra args
order.message_post(body="Confirmed by bot!")  # keyword args
```

### Environment variables (`env.user`, `env.company`, …)

These mirror the properties available on `self.env` in Odoo and are fetched
lazily from the server on first access (result is cached for the session
lifetime).

```python
# Current user ID (integer)
print(env.uid)               # e.g. 2

# Current user as an OdooRecord (res.users)
user = env.user
print(user.name)             # 'Administrator'

# Current company as an OdooRecord (res.company)
company = env.company
print(company.name)          # 'My Company'

# All allowed companies (list of OdooRecord)
for comp in env.companies:
    print(comp.id, comp.name)

# Active language code (from context)
print(env.lang)              # 'en_US'

# Full context dict (copy)
print(env.context)           # {'lang': 'en_US', 'tz': 'UTC'}
```

### Context management

```python
# Session level
env_fr = env.with_context(lang='fr_FR')
Partner_fr = env_fr('res.partner')

# Model level
Partner_es = Partner.with_context({'lang': 'es_ES'})

# Record level
translated = new_partner.with_context(lang='de_DE')
print(translated.name)
```

### `sudo()` and `with_user()` (API compatibility)

```python
# These methods return a new proxy and are provided so that
# code written for Odoo's internal API can run outside Odoo unchanged.
# Note: external JSON-RPC sessions run as the authenticated user;
# privilege escalation is not enforced server-side.
admin_partner = Partner.sudo()
user_partner = Partner.with_user(3)
```

### Refresh cached field values

```python
partner = Partner.browse(1)
print(partner.name)   # fetches from Odoo, caches locally
partner.write({'name': 'New Name'})
partner.refresh()     # clear cache
print(partner.name)   # fetches fresh value
```

---

## Using Command for relational fields

```python
from pyodoo_connect import Command

order = env('sale.order').create({
    'partner_id': 1,
    'order_line': [
        Command.create({
            'product_id': 1,
            'product_uom_qty': 2,
            'price_unit': 100.0,
        })
    ],
})

# Link / unlink tags
partner = Partner.browse(1)
partner.write({
    'category_id': [
        Command.link(5),      # link existing tag id=5
        Command.create({'name': 'VIP'}),
        Command.clear(),      # remove all existing
    ]
})
```

---

## Legacy API (still supported)

```python
from pyodoo_connect import connect_model

Partner = connect_model(
    session_id=session_id,
    url="https://your-odoo-instance.com",
    model="res.partner",
)
```

---

## Error Handling

```python
from pyodoo_connect import (
    OdooException,
    OdooConnectionError,
    OdooAuthenticationError,
    OdooRequestError,
    OdooValidationError,
)

try:
    partner = Partner.create({'name': 'Test'})
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

---

## What's New in Version 0.3.1

- **`OdooRecordset`** — new class mirroring Odoo's native recordset API;
  `search()`, `browse()`, and `create()` now return `OdooRecordset` instead
  of plain lists or single `OdooRecord`
- **Iteration, indexing, `len()`, `bool()`** — recordsets support all
  standard collection operations; empty recordsets are falsy
- **`.ids`** property — returns a list of integer IDs for all records
- **`.mapped(field_name)`** — collect field values across all records
- **`.filtered(func)`** — return a new recordset with matching records
- **`.sorted(key, reverse)`** — sort by ID, field name, or callable
- **`.ensure_one()`** — raise `ValueError` if not exactly one record
- **Singleton field delegation** — access fields directly on single-record
  recordsets: `partner.name` works when the recordset has exactly one record
- **Set operations** — `|` (union), `&` (intersection), `-` (difference),
  `+` (concatenation) on recordsets
- **Batch `write()` / `unlink()`** on recordsets — single RPC call for all IDs
- **`sudo()`, `with_user()`, `with_context()`, `refresh()`** on recordsets

## What's New in Version 0.3.0

- **`OdooSession`** — Odoo-style `env` gateway; supports `env('model')` and
  `env['model']` syntax
- **Environment variables** — `env.uid`, `env.user`, `env.company`,
  `env.companies`, `env.lang`, `env.context`; fetched lazily from
  `/web/session/get_session_info` and cached for the session lifetime
- **Explicit model methods** — `search`, `search_read`, `search_count`,
  `read`, `write`, `unlink`, `browse`, `create` with typed signatures
- **Lazy field access on `OdooRecord`** — `partner.name` transparently
  fetches field values and caches them; first field access per record
  populates all returned fields in the cache
- **Dual field/method proxy (`_FieldProxy`)** — unknown attributes on a
  record can be used as field values *or* called as Odoo methods
- **`sudo()`, `with_user()`, `with_context()`** on both models and records
- **`OdooRecord.id`** property, `__repr__`, `__bool__`, `__eq__`, `__hash__`
- **Shared `httpx.Client`** — all models/records from a session reuse a
  single HTTP connection pool
- **All exceptions exported** from the top-level package
- **`Command` parameter rename** — `id` → `record_id` in `update`, `delete`,
  `unlink`, `link`
- **Python ≥ 3.8** minimum; updated classifiers
- **Comprehensive mock-based unit test suite**

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For
major changes, please open an issue first to discuss what you would like to
change.

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE)
file for details.

## Author

- **Name:** Fasil
- **Email:** fasilwdr@hotmail.com
