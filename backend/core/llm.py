import json
import logging
from typing import Any, Dict, List, Optional
from settings import settings

logger = logging.getLogger(__name__)

def get_llm_client():
    """Return the configured Groq client without exposing its secret."""
    groq_key = settings.groq_api_key
    if groq_key:
        try:
            from groq import Groq
            return Groq(api_key=groq_key, timeout=settings.llm_timeout_seconds), "groq"
        except ImportError:
            logger.warning("Groq library not installed.")
    
    return None, None

def get_llm_status() -> Dict[str, Any]:
    """Provide safe, UI-ready provider status; never return the API key."""
    client, provider = get_llm_client()
    return {
        "provider": provider or "none",
        "configured": client is not None,
        "model": settings.groq_model if provider == "groq" else None,
    }


def verify_llm_connection() -> Dict[str, Any]:
    """Make a minimal real request to validate the configured Groq key/model."""
    client, provider = get_llm_client()
    if not client or provider != "groq":
        return {
            "provider": provider or "groq",
            "configured": False,
            "connected": False,
            "model": settings.groq_model,
            "message": "DISCOVERY_GROQ_API_KEY is not configured.",
        }

    try:
        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[{"role": "user", "content": "Reply with OK."}],
            max_tokens=5,
            temperature=0,
        )
        reply = (response.choices[0].message.content or "").strip()
        return {
            "provider": provider,
            "configured": True,
            "connected": True,
            "model": settings.groq_model,
            "message": "Groq is connected and ready.",
            "reply": reply[:40],
        }
    except Exception as exc:
        logger.warning("Groq verification failed: %s", exc)
        return {
            "provider": provider,
            "configured": True,
            "connected": False,
            "model": settings.groq_model,
            "message": "Groq could not be reached. Check the API key and model name.",
        }


def call_llm(prompt: str, response_mime_type: str = "application/json") -> Any:
    client, provider = get_llm_client()
    if not client:
        logger.warning("No LLM client configured. Agent is in deterministic fallback mode.")
        return None

    try:
        if provider == "groq":
            # client is groq.Groq
            response = client.chat.completions.create(
                model=settings.groq_model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"} if response_mime_type == "application/json" else None
            )
            content = response.choices[0].message.content
            logger.debug(f"Groq response: {content}")
            if response_mime_type == "application/json":
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    # Robust cleaning for LLM-generated JSON
                    import re
                    # 1. Strip potential Markdown code block wrappers
                    clean_content = re.sub(r"```[a-zA-Z0-9_+-]*\n?(.*?)\n?```", r"\1", content, flags=re.DOTALL).strip()
                    # 2. Find the first [ or { and the last ] or }
                    match = re.search(r"(\[.*\]|\{.*\})", clean_content, re.DOTALL)
                    if match:
                        try:
                            return json.loads(match.group(1))
                        except json.JSONDecodeError:
                            # Last resort: remove non-printable control characters and parse again.
                            sanitized = "".join(
                                ch for ch in match.group(1) if ch.isprintable() or ch in "\n\r\t"
                            )
                            try:
                                return json.loads(sanitized)
                            except json.JSONDecodeError:
                                pass
                        raise
            return content
            
    except Exception as exc:
        logger.error("Error calling %s: %s", provider, exc)
        return None
    
    return None


# Kept for imports in older extensions while the app transitions to provider-neutral naming.
call_gemini = call_llm
