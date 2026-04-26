"""纯函数式的 verification helper：给 (evidence, claim) 出 pass/fail 判决。

设计约束（PLAN §6）：
- 无 session、无 tools、无 system prompt 注入——调用尽可能干净，避免
  verdict 被上下文污染。
- 低温度（0.0）最大化同一输入的判决一致性。
- 解析失败 → 判 fail 而不是默认 pass：verdict 本来就只是 LLM 自省信号
  （非硬 gate），"fail closed" 更符合 simulate→verify 的心智模型。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from nanobot.providers.base import LLMProvider


@dataclass(frozen=True)
class Verdict:
    """一次 verify 的结果。detail 通常只在 fail 时有值。"""
    passed: bool
    detail: str | None = None


_VERIFY_PROMPT = """You are a strict verifier. Given EVIDENCE and a CLAIM, \
decide whether EVIDENCE clearly satisfies CLAIM.

Reply with ONE JSON object, no markdown, no prose:
{{"passed": true, "detail": null}}
or
{{"passed": false, "detail": "<one short sentence pinpointing what violates the claim>"}}

Rules:
- "passed" MUST be a boolean.
- "detail" MUST be null when passed, and a non-empty string when failed.
- Do not hedge. Do not explain beyond the detail field.

EVIDENCE:
{evidence}

CLAIM:
{claim}
"""


_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _try_parse_json(raw: str) -> dict | None:
    """容忍常见的包装：纯 JSON / ```json fence / 前后有少量散文。"""
    text = raw.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 某些模型会包 markdown fence 或前后加一句解释——抓第一个 {...}
    match = _JSON_OBJECT_RE.search(text)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


async def verify(
    evidence: str,
    claim: str,
    *,
    provider: "LLMProvider",
    model: str,
) -> Verdict:
    """单次 LLM 调用判决 evidence 是否满足 claim。

    Failure 模式：
    - provider 抛异常 → Verdict(False, "verifier call failed: ...")
    - 空响应 / JSON 解析失败 / 字段缺失 → Verdict(False, "verifier ...")

    这些都**不**重试、不 fallback 到 pass：verify 是 LLM 的自省信号，
    静默通过会废掉整条 simulate→verify 链路。
    """
    prompt = _VERIFY_PROMPT.format(evidence=evidence, claim=claim)
    try:
        response = await provider.chat(
            messages=[{"role": "user", "content": prompt}],
            tools=None,
            model=model,
            max_tokens=256,
            temperature=0.0,
        )
    except Exception as exc:  # noqa: BLE001 — 所有 provider 错误统一落回 Verdict
        logger.warning("verify: provider call failed: {}", exc)
        return Verdict(False, f"verifier call failed: {type(exc).__name__}: {exc}")

    raw = (response.content or "").strip()
    if not raw:
        return Verdict(False, "verifier returned empty response")

    parsed = _try_parse_json(raw)
    if not isinstance(parsed, dict) or "passed" not in parsed:
        snippet = raw[:200]
        return Verdict(False, f"verifier returned unparseable response: {snippet!r}")

    passed = bool(parsed.get("passed"))
    detail = parsed.get("detail")
    if detail is not None and not isinstance(detail, str):
        detail = str(detail)
    # 约束 detail 语义：passed=True 的 detail 无意义，丢掉保持字段干净
    if passed:
        detail = None
    return Verdict(passed=passed, detail=detail)
