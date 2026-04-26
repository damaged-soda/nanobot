"""Phase 1 Step 6 — verify() 单测。

覆盖矩阵（PLAN §6）：
- pass / fail 干净 JSON
- 容忍常见包装（markdown fence / JSON 前后有散文）
- malformed / 空响应 / 字段缺失 → 一律判 fail，而不是静默 pass
- provider 抛异常 → 判 fail，detail 带错误类别
- 调用参数：无 tools / 无 system message / temperature=0
"""

from __future__ import annotations

from typing import Any

from nanobot.providers.base import LLMProvider, LLMResponse
from nanobot.verification import Verdict, verify


class _Scripted(LLMProvider):
    """按列表顺序吐响应的假 provider，同时记录最后一次调用参数。"""

    def __init__(self, responses: list[LLMResponse]) -> None:
        super().__init__()
        self._responses = list(responses)
        self.last_kwargs: dict[str, Any] | None = None

    async def chat(self, *args: Any, **kwargs: Any) -> LLMResponse:
        self.last_kwargs = kwargs
        if not self._responses:
            return LLMResponse(content="", tool_calls=[])
        return self._responses.pop(0)

    def get_default_model(self) -> str:
        return "test-model"


def _resp(content: str) -> LLMResponse:
    return LLMResponse(content=content, tool_calls=[])


async def test_verify_pass_clean_json():
    provider = _Scripted([_resp('{"passed": true, "detail": null}')])
    v = await verify("neutral briefing text", "avoid neuroscience", provider=provider, model="m")
    assert v == Verdict(passed=True, detail=None)


async def test_verify_fail_with_detail():
    provider = _Scripted([_resp('{"passed": false, "detail": "mentions neuroscience"}')])
    v = await verify("... neuroscience ...", "avoid neuroscience", provider=provider, model="m")
    assert v.passed is False
    assert v.detail == "mentions neuroscience"


async def test_verify_tolerates_markdown_fence():
    raw = "```json\n{\"passed\": true, \"detail\": null}\n```"
    provider = _Scripted([_resp(raw)])
    v = await verify("ok", "rule", provider=provider, model="m")
    assert v.passed is True


async def test_verify_tolerates_leading_prose():
    """有些模型会在 JSON 前加一句解释——抓第一个 {...}。"""
    raw = 'Sure, here is the verdict:\n{"passed": false, "detail": "oops"}'
    provider = _Scripted([_resp(raw)])
    v = await verify("x", "y", provider=provider, model="m")
    assert v.passed is False
    assert v.detail == "oops"


async def test_verify_passed_drops_any_detail():
    """passed=True 时 detail 应被归一成 None，避免调用方误读。"""
    provider = _Scripted([_resp('{"passed": true, "detail": "looks fine"}')])
    v = await verify("x", "y", provider=provider, model="m")
    assert v == Verdict(passed=True, detail=None)


async def test_verify_malformed_response_fails_closed():
    provider = _Scripted([_resp("I think it's fine, trust me.")])
    v = await verify("x", "y", provider=provider, model="m")
    assert v.passed is False
    assert v.detail is not None
    assert "unparseable" in v.detail


async def test_verify_empty_response_fails_closed():
    provider = _Scripted([_resp("")])
    v = await verify("x", "y", provider=provider, model="m")
    assert v.passed is False
    assert v.detail == "verifier returned empty response"


async def test_verify_missing_passed_field_fails_closed():
    provider = _Scripted([_resp('{"detail": "forgot the flag"}')])
    v = await verify("x", "y", provider=provider, model="m")
    assert v.passed is False
    assert v.detail is not None
    assert "unparseable" in v.detail


async def test_verify_provider_exception_fails_closed():
    class _Boom(LLMProvider):
        async def chat(self, *args: Any, **kwargs: Any) -> LLMResponse:
            raise RuntimeError("provider down")

        def get_default_model(self) -> str:
            return "m"

    v = await verify("x", "y", provider=_Boom(), model="m")
    assert v.passed is False
    assert v.detail is not None
    assert "RuntimeError" in v.detail
    assert "provider down" in v.detail


async def test_verify_call_is_clean():
    """verify 的承诺：不带 tools、不注入 system、低温度。"""
    provider = _Scripted([_resp('{"passed": true, "detail": null}')])
    await verify("evidence text", "claim text", provider=provider, model="m1")

    kw = provider.last_kwargs
    assert kw is not None
    assert kw["tools"] is None
    assert kw["model"] == "m1"
    assert kw["temperature"] == 0.0
    # 单条 user message，不 system prompt 污染
    messages = kw["messages"]
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    # evidence / claim 都进了 prompt（防止占位变量漏填）
    assert "evidence text" in messages[0]["content"]
    assert "claim text" in messages[0]["content"]


async def test_verify_coerces_non_string_detail():
    """LLM 偶尔会把 detail 写成数字等——不崩，str() 一下。"""
    provider = _Scripted([_resp('{"passed": false, "detail": 42}')])
    v = await verify("x", "y", provider=provider, model="m")
    assert v.passed is False
    assert v.detail == "42"
