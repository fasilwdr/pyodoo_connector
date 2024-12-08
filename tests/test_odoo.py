# -*- coding: utf-8 -*-
#############################################################################
# Author: Fasil
# Email: fasilwdr@hotmail.com
# WhatsApp: https://wa.me/966538952934
# Facebook: https://www.facebook.com/fasilwdr
# Instagram: https://www.instagram.com/fasilwdr
#############################################################################
import pytest
from pyodoo_connect import connect_odoo, Command


# Configuration for test environment
@pytest.fixture
def odoo_config():
    return {
        'url': 'https://test.odoo.com',
        'db': 'test_db',
        'username': 'admin',
        'password': 'admin'
    }


# Fixture for Odoo API connection
@pytest.fixture
def odoo_api(odoo_config):
    api, session_id = connect_odoo(
        url=odoo_config['url'],
        db=odoo_config['db'],
        username=odoo_config['username'],
        password=odoo_config['password']
    )
    if not api:
        pytest.skip("Could not connect to Odoo server")
    return api


# Fixture for creating a test partner
@pytest.fixture
def test_partner(odoo_api):
    partner_data = {
        'name': 'Test Partner',
        'email': 'test@example.com',
        'phone': '1234567890'
    }
    partner_id = odoo_api.env('res.partner').create(partner_data)
    yield partner_id
    # Cleanup after test
    try:
        odoo_api.env('res.partner').unlink([partner_id])
    except Exception as e:
        print(f"Cleanup failed: {e}")


def test_connection(odoo_api):
    """Test if connection is successful"""
    assert odoo_api is not None
    assert odoo_api.context.get('uid') is not None


def test_partner_create(odoo_api):
    """Test partner creation"""
    partner_data = {
        'name': 'Create Test Partner',
        'email': 'create_test@example.com'
    }
    partner_id = odoo_api.env('res.partner').create(partner_data)
    assert partner_id > 0

    # Cleanup
    odoo_api.env('res.partner').unlink([partner_id])


def test_partner_read(odoo_api, test_partner):
    """Test reading partner data"""
    partner = odoo_api.env('res.partner').browse(test_partner)
    assert partner.name == 'Test Partner'
    assert partner.email == 'test@example.com'


def test_partner_update(odoo_api, test_partner):
    """Test updating partner data"""
    partner = odoo_api.env('res.partner').browse(test_partner)
    new_phone = '0987654321'

    updated = partner.write({'phone': new_phone})
    assert updated is True

    # Verify update
    partner = odoo_api.env('res.partner').browse(test_partner)
    assert partner.phone == new_phone


def test_partner_search(odoo_api):
    """Test search functionality"""
    # Search for partners
    domain = [('name', 'ilike', 'Test Partner')]
    partners = odoo_api.env('res.partner').search(domain, limit=5)
    assert isinstance(partners, list)


def test_partner_search_read(odoo_api):
    """Test search_read functionality"""
    domain = [('customer_rank', '>', 0)]
    fields = ['name', 'email', 'phone']
    results = odoo_api.env('res.partner').search_read(
        domain=domain,
        fields=fields,
        limit=5
    )
    assert isinstance(results, list)
    if results:
        assert all(field in results[0] for field in fields)


def test_command_operations(odoo_api):
    """Test Command operations for relational fields"""
    # Create a partner with tags
    partner_data = {
        'name': 'Command Test Partner',
        'category_id': [
            Command.create({'name': 'Test Tag'})
        ]
    }

    partner_id = odoo_api.env('res.partner').create(partner_data)
    assert partner_id > 0

    partner = odoo_api.env('res.partner').browse(partner_id)
    assert len(partner.category_id) > 0

    # Test updating tags using Command
    partner.write({
        'category_id': [
            Command.clear()  # Clear existing tags
        ]
    })

    partner = odoo_api.env('res.partner').browse(partner_id)
    assert len(partner.category_id) == 0

    # Cleanup
    odoo_api.env('res.partner').unlink([partner_id])


def test_error_handling(odoo_api):
    """Test error handling for invalid operations"""
    with pytest.raises(Exception):
        # Try to create a partner with invalid data
        odoo_api.env('res.partner').create({
            'name': 'Error Test Partner',
            'email': 'invalid_email'  # This should raise a validation error
        })


if __name__ == '__main__':
    pytest.main([__file__, '-v'])