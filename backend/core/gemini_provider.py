from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict

from settings import settings

logger = logging.getLogger(__name__)


def get_client():
    """Create the official Gemini SDK client using its environment-based configuration."""
    try:
        from google import genai

        return genai.Client()
    except (ImportError, ValueError) as exc:
        logger.debug("Gemini client unavailable: %s", exc)
        return None


def get_status() -> Dict[str, Any]:
    client = get_client()
    return {
        "provider": "gemini",
        "configured": client is not None,
        "model": settings.gemini_model,
    }


def verify_connection() -> Dict[str, Any]:
    client = get_client()
    if client is None:
        return {
            "provider": "gemini",
            "configured": False,
            "connected": False,
            "model": settings.gemini_model,
            "message": "Gemini environment configuration was not found.",
        }
    try:
        response = client.models.generate_content(model=settings.gemini_model, contents="Reply with OK.")
        reply = (response.text or "").strip()
        return {
            "provider": "gemini",
            "configured": True,
            "connected": True,
            "model": settings.gemini_model,
            "message": "Gemini is connected and ready.",
            "reply": reply[:40],
        }
    except Exception as exc:
        logger.warning("Gemini verification failed: %s", exc)
        return {
            "provider": "gemini",
            "configured": True,
            "connected": False,
            "model": settings.gemini_model,
            "message": "Gemini could not be reached. Check quota, model availability, and environment configuration.",
        }


def _parse_json(content: str) -> Any:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        clean = re.sub(r"```[a-zA-Z0-9_+-]*\n?(.*?)\n?```", r"\1", content, flags=re.DOTALL).strip()
        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            match = re.search(r"(\[.*\]|\{.*\})", clean, re.DOTALL)
            if not match:
                raise
            sanitized = "".join(ch for ch in match.group(1) if ch.isprintable() or ch in "\n\r\t")
            return json.loads(sanitized)


def call_llm(prompt: str, response_mime_type: str = "application/json") -> Any:
    client = get_client()
    if client is None:
        return None
    try:
        response = client.models.generate_content(model=settings.gemini_model, contents=prompt)
        content = (response.text or "").strip()
        if not content:
            return None
        return _parse_json(content) if response_mime_type == "application/json" else content
    except Exception as exc:
        logger.warning("Gemini request failed: %s", exc)
        return None
