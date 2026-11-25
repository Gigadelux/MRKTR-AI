"""Offline fakes for the channel, TTS, tool log and LLM."""

from __future__ import annotations

from types import SimpleNamespace


class FakeChat:
    def __init__(self) -> None:
        self.sent: list[tuple[str, int, object]] = []

    async def send_text(self, chat_id, text):
        self.sent.append(("text", chat_id, text))
        return [len(self.sent)]

    async def send_sticker(self, chat_id, file_id):
        self.sent.append(("sticker", chat_id, file_id))
        return len(self.sent)

    async def send_voice(self, chat_id, audio, seconds=None):
        self.sent.append(("voice", chat_id, audio))
        return len(self.sent)


class FakeTTS:
    def __init__(self, fail: bool = False) -> None:
        self.calls: list[str] = []
        self.fail = fail

    async def speak(self, text):
        self.calls.append(text)
        if self.fail:
            raise RuntimeError("boom")
        return b"OggS-fake"


class FakeLog:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def log_tool_call(self, user_id, tool, args, result, refused_reason):
        self.calls.append({"tool": tool, "args": args, "refused_reason": refused_reason})


def tool_call(call_id: str, name: str, arguments: str):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=arguments))


class FakeMessage(SimpleNamespace):
    def model_dump(self, exclude_none: bool = False):
        return {"role": "assistant", "content": self.content, "tool_calls": "..."}


class FakeLLM:
    """Replies with the scripted messages in order and records every request."""

    def __init__(self, script: list[FakeMessage]) -> None:
        self.script = list(script)
        self.requests: list[dict] = []
        self.model = "fake-model"
        self.client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=self._create))
        )

    async def _create(self, **kwargs):
        self.requests.append(kwargs)
        msg = self.script.pop(0)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def reply(content: str | None = None, tool_calls: list | None = None) -> FakeMessage:
    return FakeMessage(content=content, tool_calls=tool_calls)
