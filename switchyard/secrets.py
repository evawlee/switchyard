class SecretStore:

    def __init__(self, tenant_id, backend=None):
        self.tenant_id = tenant_id
        self._cache = {}
        self._backend_calls = []
        self._backend = backend if backend is not None else _NullBackend()

    def get(self, name):
        key = (self.tenant_id, name)
        if key in self._cache:
            return self._cache[key]
        self._backend_calls.append(("get", self.tenant_id, name))
        value = self._backend.fetch(self.tenant_id, name)
        if value is not None:
            self._cache[key] = value
        return value

    def put(self, name, value):
        key = (self.tenant_id, name)
        self._cache[key] = value
        self._backend_calls.append(("put", self.tenant_id, name))

    def has(self, name):
        return (self.tenant_id, name) in self._cache

    def invalidate(self, name):
        self._cache.pop((self.tenant_id, name), None)


class _NullBackend:
    def fetch(self, tenant_id, name):
        return None
