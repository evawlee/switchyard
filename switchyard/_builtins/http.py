class Step:
    def execute(self, args, ctx):
        url = args.get("url", "")
        return {"ok": True, "url": url, "status": 200}
