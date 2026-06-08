import pytest
from unittest.mock import patch
from backend.core.ingestor import ingest_document
from backend.core.redactor import redact_text
from backend.core.extractor import extract_inventory, _deterministic_extract

def test_pii_redaction():
    text = "Contact Mathan at mathan@example.com or call +1-555-555-0199. Server IP is 192.168.1.10. We use Salesforce."
    redacted = redact_text(text)
    assert "[EMAIL]" in redacted
    assert "[PHONE]" in redacted
    assert "[IP_ADDRESS]" in redacted
    assert "Salesforce" in redacted
    assert "Mathan" in redacted  # Person name should be kept to avoid breaking system names

def test_deterministic_extraction():
    text = "We use Salesforce for customer relationship management. We also have Oracle NetSuite for ERP processes."
    findings = _deterministic_extract(text, "test_doc.txt", {"page_number": 1})
    
    names = [f["name"] for f in findings]
    assert "Salesforce" in names
    assert "NetSuite" in names
    
    sf = [f for f in findings if f["name"] == "Salesforce"][0]
    assert sf["category"] == "CRM"
    assert sf["auth_method"] == "OAuth2"
    assert sf["confidence_score"] == 0.98
    assert sf["human_review_required"] is False
    
    # Generic inferred system test
    text_generic = "Our legacy database is slow. We need to move it to a cloud erp system."
    findings_generic = _deterministic_extract(text_generic, "test_doc.txt", {"line_number": 5})
    names_generic = [f["name"] for f in findings_generic]
    assert "Database" in names_generic
    assert "Erp System" in names_generic
    
    db_finding = [f for f in findings_generic if f["name"] == "Database"][0]
    assert db_finding["confidence_score"] == 0.6
    assert db_finding["human_review_required"] is True
    assert "Inferred" in db_finding["inference_note"]

@patch("backend.core.extractor.call_llm")
def test_llm_extraction_success(mock_call_llm):
    mock_call_llm.return_value = [
        {
            "name": "Salesforce",
            "category": "CRM",
            "auth_method": "OAuth2",
            "key_entities": ["Account", "Contact"],
            "business_processes": ["Lead Management"],
            "criticality": "High",
            "confidence_score": 0.96,
            "evidence": "We use Salesforce.",
        },
        {
            "name": "HallucinatedSystem",
            "category": "Analytics",
            "auth_method": "Unknown",
            "key_entities": [],
            "business_processes": [],
            "criticality": "Low",
            "confidence_score": 0.9,
            "evidence": "This was not in the text.",
        }
    ]
    
    chunks = [
        {
            "content": "We use Salesforce for client tracking.",
            "metadata": {"source_document": "source.txt"}
        }
    ]
    
    results = extract_inventory(chunks)
    
    names = [r["name"] for r in results]
    assert "Salesforce" in names
    assert "HallucinatedSystem" not in names  # Should be rejected as hallucination!
    
    sf = [r for r in results if r["name"] == "Salesforce"][0]
    assert sf["confidence_score"] == 0.96
    assert sf["human_review_required"] is False

@patch("backend.core.extractor.call_llm")
def test_llm_extraction_inferred(mock_call_llm):
    mock_call_llm.return_value = [
        {
            "name": "Billing Processor",
            "category": "Finance",
            "auth_method": "API Key",
            "key_entities": ["Invoice"],
            "business_processes": ["Billing"],
            "criticality": "High",
            "confidence_score": 0.8,
            "inference_note": "Inferred from invoice processing reference.",
            "evidence": "We process payments via the billing API.",
        }
    ]
    
    chunks = [
        {
            "content": "We process payments via the billing API.",
            "metadata": {"source_document": "source.txt"}
        }
    ]
    
    results = extract_inventory(chunks)
    assert len(results) == 1
    item = results[0]
    assert item["name"] == "Billing Processor"
    assert item["confidence_score"] == 0.8
    assert item["human_review_required"] is False  # Confidence score is >= 0.7
    assert item["inference_note"] == "Inferred from invoice processing reference."
