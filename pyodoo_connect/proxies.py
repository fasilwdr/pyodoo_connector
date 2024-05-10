# -*- coding: utf-8 -*-
#############################################################################
# Author: Fasil
# Email: fasilwdr@hotmail.com
# WhatsApp: https://wa.me/966538952934
# Facebook: https://www.facebook.com/fasilwdr
# Instagram: https://www.instagram.com/fasilwdr
#############################################################################
from typing import Dict, Any


class RecordProxy:
    def __init__(self, model_proxy, record_id, context=None):
        self.model_proxy = model_proxy
        self.record_id = record_id
        self.context = context if context is not None else {}
        self.values = {}
        self.loaded_fields = set()

    def with_context(self, *args, **kwargs):
        if args and isinstance(args[0], dict):
            kwargs = args[0]
        # Return a new instance of RecordProxy with the updated context
        new_context = self.context.copy()
        new_context.update(kwargs)
        return RecordProxy(self.model_proxy, self.record_id, new_context)

    def __getattr__(self, name):
        if name in self.values:
            return self.values[name]
        elif name not in self.loaded_fields:
            try:
                self.fetch_field(name)
                return self.values.get(name, None)
            except KeyError:
                pass
        return MethodCaller(self.model_proxy, self.record_id, name, self.context)

    def fetch_field(self, field_name):
        fields_info = self.model_proxy.fields_get([field_name], ['name', 'type'])
        if field_name not in fields_info:
            raise KeyError(f"No such field '{field_name}' on model.")
        result = self.model_proxy.read([self.record_id], [field_name])
        if result:
            self.values.update(result[0])
            self.loaded_fields.add(field_name)

    def __setattr__(self, name, value):
        if name in ['model_proxy', 'record_id', 'values', 'loaded_fields', 'context'] or name.startswith('_'):
            super().__setattr__(name, value)
        else:
            self.model_proxy.write(ids=[self.record_id], values={name: value})
            self.values[name] = value


# MethodCaller class modification to include context in RPC calls
class MethodCaller:
    def __init__(self, model_proxy, record_id, method_name, context=None):
        self.model_proxy = model_proxy
        self.record_id = record_id
        self.method_name = method_name
        self.context = context if context is not None else {}

    def __call__(self, *args, **kwargs):
        if self.method_name == 'write':
            self.method_name = 'update'
        if args and isinstance(args[0], dict):
            kwargs = {'values': args[0]}
        elif args:
            raise ValueError(
                "Positional arguments must be a single dictionary containing the parameters for the method.")

        # Merging context into kwargs for RPC call
        if self.context:
            kwargs['context'] = self.context

        return self.model_proxy.odoo.execute_function(
            self.model_proxy.model_name,
            [self.record_id],
            self.method_name,
            **kwargs
        )


class ModelProxy:
    def __init__(self, odoo_instance, model_name):
        self.odoo = odoo_instance
        self.model_name = model_name

    def browse(self, record_id):
        return RecordProxy(self, record_id)

    def search(self, domain, limit=100, order=''):
        return self.odoo.call("object", "execute", self.model_name, 'search', domain, 0, limit, order)

    def search_count(self, domain: list):
        return self.odoo.call("object", "execute", self.model_name, 'search_count', domain)

    def fields_get(self, fields: list, attributes: list):
        return self.odoo.call("object", "execute", self.model_name, 'fields_get', fields, attributes)

    def create(self, values: dict):
        return self.odoo.call("object", "execute", self.model_name, 'create', values)

    def read(self, ids: list, fields: list):
        return self.odoo.call("object", "execute", self.model_name, 'read', ids, fields)

    def search_read(self, domain: list, fields: list):
        return self.odoo.call("object", "execute", self.model_name, 'search_read', domain, fields)

    def write(self, ids: list, values: dict):
        return self.odoo.call("object", "execute", self.model_name, 'write', ids, values)

    def unlink(self, ids: list):
        return self.odoo.call("object", "execute", self.model_name, 'unlink', ids)