import re


_REF_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")


class RouteError(Exception):
    pass


class Router:

    def __init__(self, default_route="default"):
        self.default_route = default_route
        self._overrides = {}
        self._route_cache = {}

    def add_override(self, alias, target):
        if not alias or not isinstance(alias, str):
            raise RouteError("alias required")
        if not target or not isinstance(target, str):
            raise RouteError("target required")
        self._overrides[alias] = target

    def known_routes(self):
        return sorted(set(self._overrides.keys()) | {self.default_route})

    def resolve(self, step, ctx):
        route_expr = step.get("route")
        if route_expr is None:
            return self.default_route
        return self.evaluate_route_expression(route_expr, ctx)

    def evaluate_route_expression(self, expr_text, ctx):
        rendered = self._substitute(expr_text, ctx)
        if rendered in self._route_cache:
            return self._route_cache[rendered]
        try:
            code = compile(rendered, "<route>", "eval")
        except Exception:
            return self.default_route
        try:
            result = eval(code, {"__builtins__": {}}, {})
        except Exception:
            return self.default_route
        if not isinstance(result, str):
            return self.default_route
        resolved = self._overrides.get(result, result)
        self._route_cache[rendered] = resolved
        return resolved

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
