class RunnerPool:

    def __init__(self, capacity=4):
        self._capacity = capacity
        self._slots = set()

    def acquire(self, job_id):
        if len(self._slots) >= self._capacity:
            return False
        self._slots.add(job_id)
        return True

    def release(self, job_id):
        self._slots.discard(job_id)

    def in_use(self):
        return len(self._slots)

    def capacity(self):
        return self._capacity
