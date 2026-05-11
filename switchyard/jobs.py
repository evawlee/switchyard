class Job:
    def __init__(self, job_id, tenant_id, workflow_name, owner, payload, status="pending"):
        self.job_id = job_id
        self.tenant_id = tenant_id
        self.workflow_name = workflow_name
        self.owner = owner
        self.payload = payload
        self.status = status
        self.attempts = 0


class JobRegistry:

    def __init__(self, tenant_id):
        self.tenant_id = tenant_id
        self._jobs = {}
        self._by_tenant = {}
        self._next_id = 1

    def create(self, workflow_name, owner, payload):
        job_id = "job-" + str(self._next_id)
        self._next_id += 1
        job = Job(job_id, self.tenant_id, workflow_name, owner, payload, status="pending")
        self._jobs[job_id] = job
        self._by_tenant.setdefault(self.tenant_id, []).append(job_id)
        return job

    def get(self, job_id):
        job = self._jobs.get(job_id)
        if job is None or job.tenant_id != self.tenant_id:
            return None
        return job

    def set_status(self, job_id, status):
        job = self.get(job_id)
        if job is not None:
            job.status = status

    def increment_attempts(self, job_id):
        job = self.get(job_id)
        if job is None:
            return 0
        job.attempts += 1
        return job.attempts

    def list_for_tenant(self):
        return list(self._by_tenant.get(self.tenant_id, []))
