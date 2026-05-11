import re


class AuthError(Exception):
    pass


class RunResult:
    def __init__(self, job_id, status, steps_run, error=None):
        self.job_id = job_id
        self.status = status
        self.steps_run = steps_run
        self.error = error

    def to_dict(self):
        return {
            "job_id": self.job_id,
            "status": self.status,
            "steps_run": list(self.steps_run),
            "error": self.error,
        }


_REF_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")


class WorkflowRunner:

    _compiled_cache = {}

    def __init__(self, tenant_id, registry, audit, plugins, secrets, pool, artifacts, router=None, role_resolver=None):
        self.tenant_id = tenant_id
        self.registry = registry
        self.audit = audit
        self.plugins = plugins
        self.secrets = secrets
        self.pool = pool
        self.artifacts = artifacts
        self.router = router
        self._role_resolver = role_resolver if role_resolver is not None else _default_role_resolver

    def run_now(self, workflow_def, ctx, actor):
        self._authorize(actor, "run")
        job = self.registry.create(
            workflow_name=workflow_def.get("name", "anon"),
            owner=actor,
            payload={"ctx": dict(ctx), "steps": list(workflow_def.get("steps", []))},
        )
        if not self.pool.acquire(job.job_id):
            self.registry.set_status(job.job_id, "skipped")
            self.audit.record_skip(job.job_id, "no slot")
            return RunResult(job.job_id, "skipped", [])
        steps_run = []
        try:
            self.registry.set_status(job.job_id, "running")
            self.audit.record_run(job.job_id, actor, "running")
            for step in workflow_def.get("steps", []):
                cond = step.get("if")
                if cond is not None and not self.evaluate_expression(cond, ctx):
                    continue
                self._run_step(job.job_id, step, ctx)
                steps_run.append(step.get("id", "?"))
            self.registry.set_status(job.job_id, "succeeded")
            self.audit.record_complete(job.job_id, actor)
            return RunResult(job.job_id, "succeeded", steps_run)
        except Exception as e:
            self.registry.set_status(job.job_id, "failed")
            self.audit.record_fail(job.job_id, actor, str(e))
            return RunResult(job.job_id, "failed", steps_run, error=str(e))
        finally:
            self.pool.release(job.job_id)

    def retry_failed(self, job_id, actor):
        self._authorize(actor, "retry")
        job = self.registry.get(job_id)
        if job is None:
            return RunResult(job_id, "missing", [])
        if job.status != "failed":
            return RunResult(job_id, "not_failed", [])
        n = self.registry.increment_attempts(job_id)
        self.audit.record_retry(job_id, n)
        if not self.pool.acquire(job_id):
            self.registry.set_status(job_id, "skipped")
            return RunResult(job_id, "skipped", [])
        steps_run = []
        try:
            self.registry.set_status(job_id, "running")
            ctx = job.payload.get("ctx", {})
            for step in job.payload.get("steps", []):
                cond = step.get("if")
                if cond is not None and not self.evaluate_expression(cond, ctx):
                    continue
                self._run_step(job_id, step, ctx)
                steps_run.append(step.get("id", "?"))
            self.registry.set_status(job_id, "succeeded")
            self.audit.record_complete(job_id, actor)
            return RunResult(job_id, "succeeded", steps_run)
        except Exception as e:
            self.registry.set_status(job_id, "failed")
            self.audit.record_fail(job_id, actor, str(e))
            return RunResult(job_id, "failed", steps_run, error=str(e))
        finally:
            self.pool.release(job_id)

    def cancel(self, job_id, actor):
        self._authorize(actor, "cancel")
        job = self.registry.get(job_id)
        if job is None:
            return False
        if job.status in ("succeeded", "failed", "cancelled"):
            return False
        self.pool.release(job_id)
        self.registry.set_status(job_id, "cancelled")
        return True

    def pause(self, job_id, actor):
        self._authorize(actor, "pause")
        job = self.registry.get(job_id)
        if job is None:
            return False
        if job.status not in ("pending", "running"):
            return False
        self.pool.release(job_id)
        self.registry.set_status(job_id, "paused")
        return True

    def evaluate_expression(self, expr_text, ctx):
        rendered = self._substitute(expr_text, ctx)
        if rendered in self._compiled_cache:
            code = self._compiled_cache[rendered]
        else:
            try:
                code = compile(rendered, "<expr>", "eval")
            except Exception:
                return False
            self._compiled_cache[rendered] = code
        try:
            return bool(eval(code, {"__builtins__": {}}, {}))
        except Exception:
            return False

    def _substitute(self, expr_text, ctx):
        def repl(m):
            ref = m.group(1)
            parts = ref.split(".")
            if parts[0] == "ctx":
                cur = ctx
                for p in parts[1:]:
                    if isinstance(cur, dict):
                        cur = cur.get(p)
                    else:
                        cur = getattr(cur, p, None)
                    if cur is None:
                        return "None"
                if isinstance(cur, str):
                    return repr(cur)
                return str(cur)
            return "None"
        return _REF_RE.sub(repl, expr_text)

    def _run_step(self, job_id, step, ctx):
        step_type = step.get("type", "noop")
        cls = self.plugins.load_step(step_type)
        instance = cls()
        args = dict(step.get("args", {}))
        if self.router is not None:
            target_route = self.router.resolve(step, ctx)
            args["_route"] = target_route
        return instance.execute(args, ctx)

    def _authorize(self, actor, op):
        if not actor:
            raise AuthError("actor required")
        roles = self._role_resolver(self.tenant_id, actor)
        if op == "run":
            if "operator" not in roles and "admin" not in roles:
                raise AuthError("not authorized for run: " + actor)
        elif op == "retry":
            if "operator" not in roles and "admin" not in roles:
                raise AuthError("not authorized for retry: " + actor)
        elif op == "cancel":
            if "operator" not in roles and "admin" not in roles:
                raise AuthError("not authorized for cancel: " + actor)
        elif op == "pause":
            if "operator" not in roles and "admin" not in roles:
                raise AuthError("not authorized for pause: " + actor)


_DEFAULT_ROLES = {}


def _default_role_resolver(tenant_id, actor):
    return _DEFAULT_ROLES.get((tenant_id, actor), set())


def grant_role(tenant_id, actor, role):
    key = (tenant_id, actor)
    cur = _DEFAULT_ROLES.get(key, set())
    cur = set(cur)
    cur.add(role)
    _DEFAULT_ROLES[key] = cur


def revoke_role(tenant_id, actor, role):
    key = (tenant_id, actor)
    cur = _DEFAULT_ROLES.get(key, set())
    if role in cur:
        cur = set(cur)
        cur.discard(role)
        _DEFAULT_ROLES[key] = cur


def reset_roles():
    _DEFAULT_ROLES.clear()
