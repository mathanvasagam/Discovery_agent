from __future__ import annotations

import logging
from typing import Any, Dict, List

from core.gemini_provider import call_llm as call_gemini_llm
from core.gemini_provider import get_status as get_gemini_status
from core.gemini_provider import verify_connection as verify_gemini_connection
from core.llm import call_llm as call_groq_llm
from core.llm import get_llm_status as get_groq_status
from core.llm import verify_llm_connection as verify_groq_connection
from settings import settings

logger = logging.getLogger(__name__)
SUPPORTED_PROVIDERS = ("groq", "gemini")


def provider_order() -> List[str]:
    requested = [item.strip().lower() for item in settings.llm_provider_order.split(",") if item.strip()]
    ordered = [provider for provider in requested if provider in SUPPORTED_PROVIDERS]
    for provider in SUPPORTED_PROVIDERS:
        if provider not in ordered:
            ordered.append(provider)
    return ordered


def get_llm_status() -> Dict[str, Any]:
    groq = get_groq_status()
    gemini = get_gemini_status()
    providers = {
        "groq": {"configured": bool(groq.get("configured")), "model": groq.get("model")},
        "gemini": {"configured": bool(gemini.get("configured")), "model": gemini.get("model")},
    }
    active = next((provider for provider in provider_order() if providers[provider]["configured"]), None)
    return {
        "provider": active or "none",
        "configured": active is not None,
        "model": providers[active]["model"] if active else None,
        "providers": providers,
        "failover_order": provider_order(),
    }


def verify_provider_connection(provider: str) -> Dict[str, Any]:
    normalized = provider.strip().lower()
    if normalized == "groq":
        return verify_groq_connection()
    if normalized == "gemini":
        return verify_gemini_connection()
    return {
        "provider": normalized or "unknown",
        "configured": False,
        "connected": False,
        "model": None,
        "message": f"Unsupported LLM provider: {provider}",
    }


def verify_llm_connection() -> Dict[str, Any]:
    attempts = []
    for provider in provider_order():
        result = verify_provider_connection(provider)
        if not result.get("configured"):
            continue
        attempts.append(result)
        if result.get("connected"):
            result["failover_order"] = provider_order()
            result["attempted_providers"] = [attempt["provider"] for attempt in attempts]
            return result
    return {
        "provider": "none",
        "configured": bool(attempts),
        "connected": False,
        "model": None,
        "message": "No configured LLM provider could establish a connection.",
        "failover_order": provider_order(),
        "attempted_providers": [attempt["provider"] for attempt in attempts],
    }


def call_llm(prompt: str, response_mime_type: str = "application/json") -> Any:
    configured_any = False
    for provider in provider_order():
        if provider == "groq":
            if not get_groq_status().get("configured"):
                continue
            configured_any = True
            result = call_groq_llm(prompt, response_mime_type)
        else:
            if not get_gemini_status().get("configured"):
                continue
            configured_any = True
            result = call_gemini_llm(prompt, response_mime_type)

        if result is not None:
            logger.info("LLM request completed with provider %s", provider)
            return result

    if configured_any:
        logger.warning("All configured LLM providers failed; deterministic fallback will be used.")
    else:
        logger.warning("No LLM providers are configured; deterministic fallback will be used.")
    return None
