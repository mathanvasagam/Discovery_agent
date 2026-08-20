import os
import json
import logging
from typing import Any, Dict, List, Optional
from settings import settings

logger = logging.getLogger(__name__)

def get_llm_client():
    # Try Groq first (Preferred)
    groq_key = settings.groq_api_key or os.getenv("GROQ_API_KEY")
    if groq_key:
        try:
            from groq import Groq
            return Groq(api_key=groq_key), "groq"
        except ImportError:
            logger.warning("Groq library not installed.")
    
    return None, None

def call_gemini(prompt: str, response_mime_type: str = "application/json") -> Any:
    client, provider = get_llm_client()
    if not client:
        logger.warning("No LLM client configured. Agent is in deterministic fallback mode.")
        return None

    try:
        if provider == "groq":
            # client is groq.Groq
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
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

