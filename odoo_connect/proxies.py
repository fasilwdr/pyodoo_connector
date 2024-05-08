

class MethodCaller:
    def __init__(self, model_proxy, record_id, method_name):
        self.model_proxy = model_proxy
        self.record_id = record_id
        self.method_name = method_name

    def __call__(self, *args, **kwargs):
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
        self._fetch()

    def _fetch(self):
        fields = self.model_proxy.fields_get([], ['name'])  # Fetch all fields with their names
        self.values = self.model_proxy.read([self.record_id], list(fields.keys()))[0]

    def __getattr__(self, name):
        if name in self.values:
            return self.values[name]
        else:
            # Treat any unknown attribute as a method call
            return MethodCaller(self.model_proxy, self.record_id, name)

    def __setattr__(self, name, value):
        if name in ['model_proxy', 'record_id', 'values'] or name.startswith('_'):
            super(RecordProxy, self).__setattr__(name, value)
        else:
            self.model_proxy.write(ids=[self.record_id], values={name: value})
            self.values[name] = value  # Update the local cache after the write operation


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