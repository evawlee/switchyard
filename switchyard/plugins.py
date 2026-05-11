import importlib


class PluginError(Exception):
    pass


_REGISTERED_BUILTIN = {
    "shell": "switchyard._builtins.shell",
    "http": "switchyard._builtins.http",
    "noop": "switchyard._builtins.noop",
}


class PluginLoader:

    _resolved = {}

    def __init__(self):
        self._extra = {}

    def register(self, alias, module_path):
        if not alias or not isinstance(alias, str):
            raise PluginError("alias required")
        if not module_path or not isinstance(module_path, str):
            raise PluginError("module_path required")
        self._extra[alias] = module_path

    def load_step(self, step_type):
        if not step_type or not isinstance(step_type, str):
            raise PluginError("step_type required")
        if step_type in self._resolved:
            return self._resolved[step_type]
        target = self._extra.get(step_type) or _REGISTERED_BUILTIN.get(step_type) or step_type
        try:
            module = importlib.import_module(target)
        except ImportError as e:
            raise PluginError("could not load: " + target + " (" + str(e) + ")")
        cls = getattr(module, "Step", None)
        if cls is None:
            raise PluginError("module has no Step class: " + target)
        self._resolved[step_type] = cls
        return cls

    def known_aliases(self):
        return sorted(set(_REGISTERED_BUILTIN.keys()) | set(self._extra.keys()))

    def clear_cache(self):
        self._resolved.clear()
