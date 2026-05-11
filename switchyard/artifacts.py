class ArtifactCache:

    def __init__(self, tenant_id):
        self.tenant_id = tenant_id
        self._store = {}

    def put(self, key, value):
        self._store[(self.tenant_id, key)] = value

    def get(self, key):
        return self._store.get((self.tenant_id, key))

    def has(self, key):
        return (self.tenant_id, key) in self._store

    def keys(self):
        return [k for (t, k) in self._store.keys() if t == self.tenant_id]
