from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from core.discovery_catalog import PROFILE_BY_ALIAS, iter_profiles
from core.provider_router import call_llm as call_provider_llm


logger = logging.getLogger(__name__)

GENERIC_SYSTEM_PATTERNS = [
    ("mainframe", "Other", "Unknown", "High"),
    ("database", "Database", "Unknown", "High"),
    ("erp system", "ERP", "Unknown", "High"),
    ("crm tool", "CRM", "Unknown", "Medium"),
    ("legacy app", "Other", "Unknown", "Low"),
    ("cloud storage", "Storage", "Unknown", "Medium"),
]


def call_llm(prompt: str) -> Any:
    """Hook for provider-backed extraction."""
    return call_provider_llm(prompt)


def _sentence_candidates(text: str) -> List[str]:
    return [segment.strip() for segment in re.split(r"(?<=[.!?])\s+|\n+", text) if segment.strip()]


def _find_evidence_sentence(content: str, alias: str) -> str:
    sentences = _sentence_candidates(content)
    lowered_alias = alias.lower()
    for sentence in sentences:
        if lowered_alias in sentence.lower():
            return sentence
    return content[:240].strip()


def _profile_result(content: str, alias: str, source_ref: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    profile = PROFILE_BY_ALIAS[alias]
    evidence = _find_evidence_sentence(content, alias)
    lowered_evidence = evidence.lower()
    
    # Explicit if canonical name or alias is found
    # Since we are iterating known aliases, if it's found, we consider it a confident match (0.98)
    # This prevents 'Jira' getting 85% just because the word 'system' isn't nearby.
    confidence_score = 0.98 
    
    return {
        "name": profile.canonical_name,
        "category": profile.category,
        "auth_method": profile.auth_method,
        "key_entities": profile.key_entities,
        "business_processes": profile.business_processes,
        "criticality": profile.criticality,
        "confidence_score": confidence_score,
        "inference_note": "",
        "human_review_required": False,
        "evidence": evidence,
        "source_reference": source_ref,
        "page_number": metadata.get("page_number"),
        "line_number": metadata.get("line_number"),
    }


def _generic_result(content: str, term: str, category: str, auth_method: str, criticality: str, source_ref: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    evidence = _find_evidence_sentence(content, term)
    return {
        "name": term.title(),
        "category": category,
        "auth_method": auth_method,
        "key_entities": [],
        "business_processes": [],
        "criticality": criticality,
        "confidence_score": 0.6,
        "inference_note": f"Inferred from mention of '{term}'. Exact product name was not stated.",
        "human_review_required": True,
        "evidence": evidence,
        "source_reference": source_ref,
        "page_number": metadata.get("page_number"),
        "line_number": metadata.get("line_number"),
    }


def _deduplicate(systems: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}
    for system in systems:
        key = system["name"].strip().lower()
        existing = merged.get(key)
        if existing is None or system["confidence_score"] > existing["confidence_score"]:
            merged[key] = system
        elif system.get("evidence") and system["evidence"] not in existing.get("evidence", ""):
            existing["evidence"] = f"{existing['evidence']} | {system['evidence']}"
    return list(merged.values())


def _deterministic_extract(content: str, source_ref: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    lowered = content.lower()

    for profile in iter_profiles():
        for alias in profile.aliases:
            if alias.lower() in lowered:
                findings.append(_profile_result(content, alias.lower(), source_ref, metadata))
                break

    for term, category, auth_method, criticality in GENERIC_SYSTEM_PATTERNS:
        if term in lowered:
            findings.append(_generic_result(content, term, category, auth_method, criticality, source_ref, metadata))

    return _deduplicate(findings)


def _normalize_llm_result(system: Dict[str, Any], source_ref: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    confidence_score = float(system.get("confidence_score", 0.0))
    raw_text = system.get("raw_text", "")
    evidence = system.get("evidence") or _find_evidence_sentence(raw_text or source_ref, system.get("name", ""))
    
    # Enforce stricter confidence criteria from PDF page 10
    # 95%+ for explicit mentions, 70-90% for inferred, below 70% flagged for human review
    
    # If explicit mention found in evidence, clamp min confidence to 0.95
    if system.get("name", "").lower() in evidence.lower():
        confidence_score = max(confidence_score, 0.95)
    
    return {
        "name": str(system.get("name", "Unknown")),
        "category": str(system.get("category", "Other")),
        "auth_method": str(system.get("auth_method", "Unknown")),
        "key_entities": list(system.get("key_entities", [])),
        "business_processes": list(system.get("business_processes", [])),
        "criticality": str(system.get("criticality", "Medium")),
        "confidence_score": confidence_score,
        "inference_note": str(system.get("inference_note", "")),
        "human_review_required": confidence_score < 0.7,
        "evidence": str(system.get("evidence", evidence)),
        "source_reference": source_ref,
        "page_number": metadata.get("page_number"),
        "line_number": metadata.get("line_number"),
    }


def extract_inventory(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Extract a structured system inventory from document chunks.
    """
    all_systems: List[Dict[str, Any]] = []

    for chunk in chunks:
        content = chunk.get("content", "")
        metadata = chunk.get("metadata", {})
        source_ref = metadata.get("source_document", "Unknown")

        prompt = f"""
        Role: Enterprise Architect Discovery Agent
        Task: Extract EVERY software system mentioned in the following text.

        Text:
        \"\"\"{content}\"\"\"

        Requirements:
        1. Extract: name, category, auth_method, key_entities, business_processes, criticality.
        2. Assign a confidence_score between 0.0 and 1.0 based on explicit presence:
           - 0.95+ for EXPLICIT mentions (system name is directly stated).
           - 0.70-0.90 for INFERRED mentions (inferred from context/processes, not directly stated).
           - Below 0.70 for uncertain mentions.
        3. If confidence_score < 0.95, include an inference_note explaining what was inferred and what evidence was missing.
        4. ZERO HALLUCINATION: if no systems are present, return [].
        5. Include the specific evidence sentence from the text.

        Output: Return ONLY a valid JSON list of objects.
        """

        extracted_systems: Optional[List[Dict[str, Any]]] = None
        try:
            llm_result = call_llm(prompt)
            systems_list = []
            if isinstance(llm_result, list):
                systems_list = llm_result
            elif isinstance(llm_result, dict):
                # Look for common keys like "systems", "findings", "software_systems"
                for key in ["systems", "findings", "software_systems", "results"]:
                    if isinstance(llm_result.get(key), list):
                        systems_list = llm_result[key]
                        break
                if not systems_list and len(llm_result) == 1:
                    # If there's only one key and it's a list, use it
                    val = list(llm_result.values())[0]
                    if isinstance(val, list):
                        systems_list = val
            
            if systems_list:
                validated_systems = []
                lowered_content = content.lower()
                for system in systems_list:
                    sys_name = system.get("name", "")
                    if sys_name:
                        sys_lower = sys_name.lower()
                        in_text = sys_lower in lowered_content
                        if not in_text:
                            words = [w.strip(".,()\"';:") for w in sys_lower.split()]
                            words = [w for w in words if len(w) > 3]
                            if words and any(word in lowered_content for word in words):
                                in_text = True
                        if in_text:
                            validated_systems.append(system)
                        else:
                            logger.warning(f"Hallucination rejected: System '{sys_name}' not found in source text.")
                extracted_systems = [_normalize_llm_result(system, source_ref, metadata) for system in validated_systems]
        except Exception as exc:
            logger.warning("LLM extraction hook failed for %s: %s", source_ref, exc)

        if extracted_systems is None:
            extracted_systems = _deterministic_extract(content, source_ref, metadata)

        all_systems.extend(extracted_systems)

    return _deduplicate(all_systems)
