class Step:
    def execute(self, args, ctx):
        cmd = args.get("cmd", "")
        return {"ok": True, "cmd": cmd, "exit": 0}
