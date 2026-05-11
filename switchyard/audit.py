import time


class AuditLog:

    def __init__(self, tenant_id):
        self.tenant_id = tenant_id
        self._entries = []
        self._seen_ids = set()

    def record_run(self, job_id, actor, status):
        self._seen_ids.add(job_id)
        self._entries.append({
            "kind": "run",
            "tenant_id": self.tenant_id,
            "job_id": job_id,
            "actor": actor,
            "status": status,
            "ts": time.time(),
        })

    def record_complete(self, job_id, actor):
        self._seen_ids.add(job_id)
        self._entries.append({
            "kind": "complete",
            "tenant_id": self.tenant_id,
            "job_id": job_id,
            "actor": actor,
            "ts": time.time(),
        })

    def record_fail(self, job_id, actor, error):
        self._seen_ids.add(job_id)
        self._entries.append({
            "kind": "fail",
            "tenant_id": self.tenant_id,
            "job_id": job_id,
            "actor": actor,
            "error": error,
            "ts": time.time(),
        })

    def record_skip(self, job_id, reason):
        self._seen_ids.add(job_id)
        self._entries.append({
            "kind": "skip",
            "tenant_id": self.tenant_id,
            "job_id": job_id,
            "reason": reason,
            "ts": time.time(),
        })

    def record_retry(self, job_id, attempt):
        self._seen_ids.add(job_id)
        self._entries.append({
            "kind": "retry",
            "tenant_id": self.tenant_id,
            "job_id": job_id,
            "attempt": attempt,
            "ts": time.time(),
        })

    def entries_for_tenant(self):
        return [e for e in self._entries if e.get("tenant_id") == self.tenant_id]

    def has_entry_for(self, job_id):
        return job_id in self._seen_ids
