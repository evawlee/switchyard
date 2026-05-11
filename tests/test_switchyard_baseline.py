from switchyard import (
    WorkflowRunner, AuthError, RunResult, grant_role,
    JobRegistry, SecretStore, PluginLoader, PluginError, AuditLog, RunnerPool, ArtifactCache,
    Router, RouteError,
)


def _build_runner(tenant_id="tenant-a", actor="alice", role="operator"):
    grant_role(tenant_id, actor, role)
    registry = JobRegistry(tenant_id)
    audit = AuditLog(tenant_id)
    plugins = PluginLoader()
    secrets = SecretStore(tenant_id)
    pool = RunnerPool(capacity=4)
    artifacts = ArtifactCache(tenant_id)
    router = Router(default_route="default")
    return WorkflowRunner(tenant_id, registry, audit, plugins, secrets, pool, artifacts, router=router)


class TestExpressionEvaluator:

    def test_literal_true_evaluates_to_true(self):
        runner = _build_runner()
        assert runner.evaluate_expression("True", {}) is True

    def test_literal_false_evaluates_to_false(self):
        runner = _build_runner()
        assert runner.evaluate_expression("False", {}) is False

    def test_ctx_string_compare_main_branch(self):
        runner = _build_runner()
        assert runner.evaluate_expression("{{ ctx.branch }} == 'main'", {"branch": "main"}) is True

    def test_ctx_string_compare_other_branch(self):
        runner = _build_runner()
        assert runner.evaluate_expression("{{ ctx.branch }} == 'main'", {"branch": "dev"}) is False

    def test_malformed_expression_returns_false(self):
        runner = _build_runner()
        assert runner.evaluate_expression("not a valid {{{ expression", {}) is False

    def test_boolean_and_passes(self):
        runner = _build_runner()
        assert runner.evaluate_expression("True and True", {}) is True

    def test_boolean_or_passes(self):
        runner = _build_runner()
        assert runner.evaluate_expression("False or True", {}) is True

    def test_numeric_compare_passes(self):
        runner = _build_runner()
        assert runner.evaluate_expression("1 < 2", {}) is True


class TestPluginLoader:

    def test_load_builtin_noop(self):
        loader = PluginLoader()
        cls = loader.load_step("noop")
        assert cls is not None
        assert cls.__name__ == "Step"

    def test_load_builtin_shell(self):
        loader = PluginLoader()
        cls = loader.load_step("shell")
        assert cls is not None
        assert cls.__name__ == "Step"

    def test_load_builtin_http(self):
        loader = PluginLoader()
        cls = loader.load_step("http")
        assert cls is not None

    def test_register_resolves_via_extra(self):
        loader = PluginLoader()
        loader.register("my_noop", "switchyard._builtins.noop")
        cls = loader.load_step("my_noop")
        assert cls is not None

    def test_known_aliases_lists_builtins(self):
        loader = PluginLoader()
        aliases = loader.known_aliases()
        assert "noop" in aliases
        assert "shell" in aliases
        assert "http" in aliases


class TestWorkflowRunner:

    def test_run_now_happy_path(self):
        runner = _build_runner()
        result = runner.run_now({"name": "deploy", "steps": [{"id": "s1", "type": "noop"}]}, {}, "alice")
        assert result.status == "succeeded"
        assert result.steps_run == ["s1"]

    def test_run_now_authorizes_run(self):
        registry = JobRegistry("tenant-a")
        audit = AuditLog("tenant-a")
        plugins = PluginLoader()
        secrets = SecretStore("tenant-a")
        pool = RunnerPool()
        artifacts = ArtifactCache("tenant-a")
        router = Router(default_route="default")
        runner = WorkflowRunner("tenant-a", registry, audit, plugins, secrets, pool, artifacts, router=router)
        try:
            runner.run_now({"steps": []}, {}, "no_role_actor")
            assert False, "expected AuthError"
        except AuthError:
            pass

    def test_run_now_no_steps_succeeds(self):
        runner = _build_runner()
        result = runner.run_now({"steps": []}, {}, "alice")
        assert result.status == "succeeded"
        assert result.steps_run == []

    def test_if_false_skips_step(self):
        runner = _build_runner()
        result = runner.run_now({"steps": [{"id": "s1", "type": "noop", "if": "False"}]}, {}, "alice")
        assert result.steps_run == []


class TestJobRegistry:

    def test_create_returns_job(self):
        reg = JobRegistry("tenant-a")
        job = reg.create("workflow1", "alice", {"steps": []})
        assert job.tenant_id == "tenant-a"
        assert job.workflow_name == "workflow1"
        assert job.status == "pending"

    def test_get_returns_created_job(self):
        reg = JobRegistry("tenant-a")
        job = reg.create("w", "alice", {})
        assert reg.get(job.job_id).job_id == job.job_id

    def test_set_status_updates_job(self):
        reg = JobRegistry("tenant-a")
        job = reg.create("w", "alice", {})
        reg.set_status(job.job_id, "running")
        assert reg.get(job.job_id).status == "running"


class TestSecretStore:

    def test_put_and_get(self):
        s = SecretStore("tenant-a")
        s.put("KEY", "value-a")
        assert s.get("KEY") == "value-a"

    def test_get_unknown_returns_none(self):
        s = SecretStore("tenant-a")
        assert s.get("MISSING") is None

    def test_has(self):
        s = SecretStore("tenant-a")
        s.put("KEY", "v")
        assert s.has("KEY") is True
        assert s.has("OTHER") is False


class TestAuditLog:

    def test_record_run_appends_entry(self):
        log = AuditLog("tenant-a")
        log.record_run("job-1", "alice", "running")
        entries = log.entries_for_tenant()
        assert len(entries) == 1
        assert entries[0]["kind"] == "run"

    def test_record_complete_appends_entry(self):
        log = AuditLog("tenant-a")
        log.record_complete("job-1", "alice")
        assert len(log.entries_for_tenant()) == 1

    def test_entries_for_tenant_filters(self):
        log = AuditLog("tenant-a")
        log.record_run("job-1", "alice", "running")
        log.record_complete("job-1", "alice")
        assert len(log.entries_for_tenant()) == 2


class TestRunnerPool:

    def test_acquire_succeeds(self):
        pool = RunnerPool(capacity=2)
        assert pool.acquire("job-1") is True

    def test_acquire_at_capacity_returns_false(self):
        pool = RunnerPool(capacity=1)
        pool.acquire("job-1")
        assert pool.acquire("job-2") is False

    def test_release_frees_slot(self):
        pool = RunnerPool(capacity=1)
        pool.acquire("job-1")
        pool.release("job-1")
        assert pool.acquire("job-2") is True


class TestArtifactCache:

    def test_put_and_get(self):
        c = ArtifactCache("tenant-a")
        c.put("key1", b"data")
        assert c.get("key1") == b"data"

    def test_has(self):
        c = ArtifactCache("tenant-a")
        c.put("key1", b"data")
        assert c.has("key1") is True
        assert c.has("missing") is False


class TestRouter:

    def test_default_route_when_no_expression(self):
        r = Router(default_route="cpu-pool")
        assert r.resolve({"id": "s1", "type": "noop"}, {}) == "cpu-pool"

    def test_route_expression_returns_string(self):
        r = Router(default_route="cpu-pool")
        result = r.resolve({"id": "s1", "type": "shell", "route": "'gpu-pool'"}, {})
        assert result == "gpu-pool"

    def test_route_override_substitution(self):
        r = Router(default_route="default")
        r.add_override("alias-a", "actual-pool")
        result = r.resolve({"id": "s1", "type": "shell", "route": "'alias-a'"}, {})
        assert result == "actual-pool"

    def test_route_known_routes_lists_default_and_overrides(self):
        r = Router(default_route="cpu-pool")
        r.add_override("a", "pool-x")
        r.add_override("b", "pool-y")
        routes = r.known_routes()
        assert "cpu-pool" in routes
        assert "a" in routes
        assert "b" in routes
