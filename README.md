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
- 🔗 **Related field behaviour** — many2one fields return an `OdooRecordset` of the target model, exactly as in Odoo's native ORM (e.g. `product_template_id.ceteg_id` → `product.category(231)`)
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

# On a recordsetpartners = env["res.partner"].browse([2,4,5])
partners.write({"phone": "+162382732"})
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

### Related field (many2one) behaviour

Many2one fields return an `OdooRecordset` pointing to the linked record,
matching Odoo's native ORM behaviour:

```python
product_tmpl = env('product.template').search(
    [('default_code', '=', '1234567')], limit=1
)

# product_variant_id is a many2one field → returns an OdooRecordset
product_id = product_tmpl.product_variant_id
print(product_id)          # product.product(591579)

# Field access on the related record works naturally
print("product name", product_id.name)   # product name Awesome Widget
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
