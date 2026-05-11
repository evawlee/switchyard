class Step:
    def execute(self, args, ctx):
        return {"ok": True, "args": dict(args)}
