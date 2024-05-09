# -*- coding: utf-8 -*-
#############################################################################
# Author: Fasil
# Email: fasilwdr@hotmail.com
# WhatsApp: https://wa.me/966538952934
# Facebook: https://www.facebook.com/fasilwdr
# Instagram: https://www.instagram.com/fasilwdr
#############################################################################

class MethodCaller:
    def __init__(self, model_proxy, record_id, method_name):
        self.model_proxy = model_proxy
        self.record_id = record_id
        self.method_name = method_name

    def __call__(self, *args, **kwargs):
        # If there are positional arguments, assume the first is a dictionary and reformat as needed
        if args and isinstance(args[0], dict):
            kwargs = {'values': args[0]}  # Override kwargs with values from args
        elif args:
            # If args are not a dictionary, raise an error or handle appropriately
            raise ValueError(
                "Positional arguments must be a single dictionary containing the parameters for the method.")
        return self.model_proxy.odoo.execute_function(
            self.model_proxy.model_name,
            [self.record_id],
            self.method_name,
            **kwargs
        )


class RecordProxy:
    def __init__(self, model_proxy, record_id):
        self.model_proxy = model_proxy
        self.record_id = record_id
        self.values = {}
        self.loaded_fields = set()

    def __getattr__(self, name):
        if name in self.values:
            return self.values[name]
        elif name not in self.loaded_fields:
            # Attempt to fetch the field first. If not present, treat as method
            try:
                self.fetch_field(name)
                return self.values.get(name, None)
            except KeyError:
                pass
        # If it's not a field, treat it as a method call
        return MethodCaller(self.model_proxy, self.record_id, name)

    def fetch_field(self, field_name):
        # Fetch single field and check if it exists
        fields_info = self.model_proxy.fields_get([field_name], ['name', 'type'])
        if field_name not in fields_info:
            raise KeyError(f"No such field '{field_name}' on model.")
        result = self.model_proxy.read([self.record_id], [field_name])
        if result:
            self.values.update(result[0])
            self.loaded_fields.add(field_name)

    def __setattr__(self, name, value):
        if name in ['model_proxy', 'record_id', 'values', 'loaded_fields'] or name.startswith('_'):
            super().__setattr__(name, value)
        else:
            self.model_proxy.write(ids=[self.record_id], values={name: value})
            self.values[name] = value  # Update the local cache after the write operation

    def _fetch_all(self):
        # Optional: Method to manually fetch all fields if needed
        fields = self.model_proxy.fields_get([], ['name'])
        self.values = self.model_proxy.read([self.record_id], list(fields.keys()))[0]
        self.loaded_fields.update(fields.keys())



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
        print(values)
        return self.odoo.call("object", "execute", self.model_name, 'write', ids, values)

    def unlink(self, ids: list):
        return self.odoo.call("object", "execute", self.model_name, 'unlink', ids)