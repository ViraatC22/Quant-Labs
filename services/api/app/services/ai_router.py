import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.vault import AiProviderStatus, StrategyInfo

logger = get_logger("app.ai_router")


@dataclass(frozen=True)
class AiProvider:
    id: str
    label: str
    key: str
    model: str
    endpoint: str
    protocol: str


@dataclass(frozen=True)
class AiExtraction:
    title: str | None
    strategy_info: StrategyInfo | None
    tags: list[str]
    provider_id: str
    model: str


def _providers() -> dict[str, AiProvider]:
    return {
        "openrouter": AiProvider(
            id="openrouter",
            label="OpenRouter",
            key=settings.openrouter_api_key,
            model=settings.openrouter_model,
            endpoint="https://openrouter.ai/api/v1/chat/completions",
            protocol="openai_chat",
        ),
        "groq": AiProvider(
            id="groq",
            label="Groq",
            key=settings.groq_api_key,
            model=settings.groq_model,
            endpoint="https://api.groq.com/openai/v1/chat/completions",
            protocol="openai_chat",
        ),
        "gemini": AiProvider(
            id="gemini",
            label="Google Gemini",
            key=settings.gemini_api_key,
            model=settings.gemini_model,
            # Base for the REST generateContent call; the model is appended per
            # request as `{base}/{model}:generateContent`.
            endpoint="https://generativelanguage.googleapis.com/v1beta/models",
            protocol="gemini_generate",
        ),
        "cerebras": AiProvider(
            id="cerebras",
            label="Cerebras",
            key=settings.cerebras_api_key,
            model=settings.cerebras_model,
            endpoint="https://api.cerebras.ai/v1/chat/completions",
            protocol="openai_chat",
        ),
    }


def provider_status() -> list[AiProviderStatus]:
    providers = _providers()
    statuses: list[AiProviderStatus] = []
    for index, provider_id in enumerate(settings.ai_provider_order):
        provider = providers.get(provider_id)
        if not provider:
            continue
        statuses.append(
            AiProviderStatus(
                id=provider.id,
                label=provider.label,
                configured=bool(provider.key),
                model=provider.model,
                priority=index + 1,
                protocol=provider.protocol,
            )
        )
    return statuses


def router_mode() -> str:
    if settings.ai_enrichment_mode not in {"auto", "local", "off"}:
        return "local"
    return settings.ai_enrichment_mode


def active_provider_status() -> AiProviderStatus | None:
    if router_mode() != "auto":
        return None
    return next((provider for provider in provider_status() if provider.configured), None)


def extract_strategy_with_ai(
    *,
    title: str,
    kind: str,
    source: str,
    body: str,
) -> AiExtraction | None:
    if router_mode() != "auto" or not body.strip():
        return None

    providers = _providers()
    for provider_id in settings.ai_provider_order:
        provider = providers.get(provider_id)
        if not provider or not provider.key:
            continue
        start = time.perf_counter()
        try:
            extraction = _extract_with_provider(
                provider,
                title=title,
                kind=kind,
                source=source,
                body=body,
            )
            logger.info(
                "ai_extract provider=%s model=%s status=ok latency_ms=%.0f",
                provider.id,
                provider.model,
                (time.perf_counter() - start) * 1000,
            )
            return extraction
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            logger.warning(
                "ai_extract provider=%s model=%s status=failed latency_ms=%.0f error=%s: %s",
                provider.id,
                provider.model,
                (time.perf_counter() - start) * 1000,
                type(exc).__name__,
                exc,
            )
            continue
    return None


def self_test_providers() -> list[dict[str, Any]]:
    """Fire a tiny canary at each configured provider and report the result.

    Makes silent misconfiguration (wrong key, wrong endpoint, wrong model)
    visible instead of a provider failing forever unnoticed.
    """
    providers = _providers()
    results: list[dict[str, Any]] = []
    for provider_id in settings.ai_provider_order:
        provider = providers.get(provider_id)
        if not provider:
            continue
        if not provider.key:
            results.append(
                {
                    "id": provider.id,
                    "label": provider.label,
                    "configured": False,
                    "ok": False,
                    "latency_ms": None,
                    "error": "no API key configured",
                }
            )
            continue
        start = time.perf_counter()
        try:
            extraction = _extract_with_provider(
                provider,
                title="Self-test",
                kind="note",
                source="selftest://canary",
                body="VWAP pullback long entry on the opening range breakout with a stop below VWAP.",
            )
            results.append(
                {
                    "id": provider.id,
                    "label": provider.label,
                    "configured": True,
                    "ok": extraction is not None,
                    "latency_ms": round((time.perf_counter() - start) * 1000),
                    "error": None,
                }
            )
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            results.append(
                {
                    "id": provider.id,
                    "label": provider.label,
                    "configured": True,
                    "ok": False,
                    "latency_ms": round((time.perf_counter() - start) * 1000),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    return results


def _extract_with_provider(
    provider: AiProvider,
    *,
    title: str,
    kind: str,
    source: str,
    body: str,
) -> AiExtraction:
    prompt = _extraction_prompt(title=title, kind=kind, source=source, body=body)
    if provider.protocol == "gemini_generate":
        raw = _post_json(
            f"{provider.endpoint}/{provider.model}:generateContent",
            headers={"x-goog-api-key": provider.key},
            payload={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.1,
                    "responseMimeType": "application/json",
                },
            },
        )
        content = _gemini_text(raw)
    else:
        raw = _post_json(
            provider.endpoint,
            headers={"Authorization": f"Bearer {provider.key}"},
            payload={
                "model": provider.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "Extract trading strategy metadata. Return only valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 900,
                "response_format": {"type": "json_object"},
            },
        )
        content = _chat_text(raw)

    payload = _parse_json_object(content)
    extracted_title = payload.get("title")
    strategy = payload.get("strategy_info")
    tags = payload.get("tags")
    return AiExtraction(
        title=extracted_title.strip()[:240]
        if isinstance(extracted_title, str) and extracted_title.strip()
        else None,
        strategy_info=StrategyInfo.model_validate(strategy) if isinstance(strategy, dict) else None,
        tags=sorted({str(tag).strip().lower() for tag in tags if str(tag).strip()})
        if isinstance(tags, list)
        else [],
        provider_id=provider.id,
        model=provider.model,
    )


def _post_json(url: str, *, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    with urlopen(request, timeout=settings.ai_request_timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def _chat_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("AI response did not include choices.")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str):
        raise ValueError("AI response did not include text content.")
    return content


def _gemini_text(payload: dict[str, Any]) -> str:
    # Response shape: candidates[].content.parts[].text
    candidates = payload.get("candidates")
    if isinstance(candidates, list):
        parts: list[str] = []
        for candidate in candidates:
            content = candidate.get("content") if isinstance(candidate, dict) else None
            for item in (content or {}).get("parts", []) if isinstance(content, dict) else []:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
        if parts:
            return "\n".join(parts)
    raise ValueError("Gemini response did not include text content.")


def _parse_json_object(content: str) -> dict[str, Any]:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        stripped = stripped.removeprefix("json").strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("AI response was not JSON.")
    parsed = json.loads(stripped[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("AI response JSON root must be an object.")
    return parsed


def _extraction_prompt(*, title: str, kind: str, source: str, body: str) -> str:
    excerpt = body[:9000]
    return f"""
Extract structured trading strategy metadata from this source.

Return one JSON object with:
- title: best human-readable source or strategy title
- tags: lowercase short strings, especially trading technical tags
- strategy_info: object with keys name, summary, setup, entry_rules, exit_rules,
  risk_rules, timeframe, indicators, market, technical_tags, technical_profile,
  confidence

technical_tags should include compact tags such as vwap, fair-value-gap,
liquidity-sweep, support, resistance, order-block, opening-range-breakout,
risk-reward, position-sizing, trendline, volume-profile.

technical_profile should group labels under keys like indicators, price_action,
market_structure, setups, risk, sessions, markets, timeframes.

Use null or empty lists when a field is not supported by the evidence. Do not
invent a profitable strategy. Keep rules short and evidence-grounded.

Title: {title}
Kind: {kind}
Source: {source}
Body:
{excerpt}
""".strip()
