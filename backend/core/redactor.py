from __future__ import annotations

import re
from typing import Any, Dict, List

EMAIL_REGEX = r"\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b"
PHONE_REGEX = r"(?:(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4})"
IP_REGEX = r"\b(?:\d{1,3}\.){3}\d{1,3}\b"

# Two-word person names are redacted conservatively to avoid replacing product names.
NAME_REGEX = r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b"

SYSTEM_NAME_GUARD = {
    "Salesforce",
    "NetSuite",
    "Workday",
    "HubSpot",
    "ServiceNow",
    "Jira",
    "Slack",
    "Okta",
    "Mailchimp",
    "PostgreSQL",
    "Stripe",
    "SAP",
    "Oracle",
    "Dynamics",
}


def _redact_name_match(match: re.Match[str]) -> str:
    candidate = match.group(0)
    # If the candidate contains any of our guarded system names, don't redact it
    if any(system.lower() in candidate.lower() for system in SYSTEM_NAME_GUARD):
        return candidate
    return "[PERSON]"


def redact_text(text: str) -> str:
    """
    Redact ONLY critical sensitive data (Email, Phone, IP).
    """
    if not text:
        return ""

    redacted = re.sub(EMAIL_REGEX, "[EMAIL]", text)
    redacted = re.sub(PHONE_REGEX, "[PHONE]", redacted)
    redacted = re.sub(IP_REGEX, "[IP_ADDRESS]", redacted)
    return redacted


def redact_chunks(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Apply redaction to a list of chunk dictionaries while preserving metadata.
    """
    redacted_chunks: List[Dict[str, Any]] = []
    for chunk in chunks:
        new_chunk = dict(chunk)
        new_chunk["content"] = redact_text(chunk.get("content", ""))
        redacted_chunks.append(new_chunk)
    return redacted_chunks
