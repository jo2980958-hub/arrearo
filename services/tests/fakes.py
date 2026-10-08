"""A fake bedrock-runtime client: returns queued tool inputs / texts."""


class FakeBedrock:
    def __init__(self, tool_inputs=(), texts=()):
        self.tool_inputs, self.texts, self.calls = list(tool_inputs), list(texts), []

    def converse(self, **kw):
        self.calls.append(kw)
        if "toolConfig" in kw:
            name = kw["toolConfig"]["tools"][0]["toolSpec"]["name"]
            return {"output": {"message": {"content": [{"toolUse": {"name": name, "input": self.tool_inputs.pop(0)}}]}},
                    "stopReason": "tool_use"}
        return {"output": {"message": {"content": [{"text": self.texts.pop(0)}]}}, "stopReason": "end_turn"}
