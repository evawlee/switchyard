import pytest

from switchyard.plugins import PluginLoader
from switchyard.runner import WorkflowRunner, reset_roles


@pytest.fixture(autouse=True)
def _wipe_class_body_state():
    PluginLoader._resolved = {}
    WorkflowRunner._compiled_cache = {}
    reset_roles()
    yield
    PluginLoader._resolved = {}
    WorkflowRunner._compiled_cache = {}
    reset_roles()
