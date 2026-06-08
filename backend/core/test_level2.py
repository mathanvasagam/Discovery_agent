import pytest
from unittest.mock import patch
from backend.core.mapping_engine import map_use_case_to_inventory

# Mock inventory representing discovered systems
MOCK_INVENTORY = [
    {
        "id": 1,
        "name": "Salesforce",
        "category": "CRM",
        "auth_method": "OAuth2",
        "criticality": "High",
        "confidence_score": 0.98,
        "evidence": "We use Salesforce CRM."
    },
    {
        "id": 2,
        "name": "NetSuite",
        "category": "ERP",
        "auth_method": "Token Based",
        "criticality": "High",
        "confidence_score": 0.95,
        "evidence": "Oracle NetSuite manages invoice ledger."
    },
    {
        "id": 3,
        "name": "Coupa",
        "category": "Procurement",
        "auth_method": "OAuth2",
        "criticality": "Medium",
        "confidence_score": 0.90,
        "evidence": "We log purchase orders in Coupa."
    },
    {
        "id": 4,
        "name": "HubSpot",
        "category": "Marketing",
        "auth_method": "API Key",
        "criticality": "Medium",
        "confidence_score": 0.88,
        "evidence": "HubSpot tracks incoming leads."
    },
    {
        "id": 5,
        "name": "ServiceNow",
        "category": "ITSM",
        "auth_method": "Basic Auth",
        "criticality": "Low",
        "confidence_score": 0.80,
        "evidence": "ServiceNow manages tickets."
    }
]

# Define 5 distinct use cases representing business automation goals
USE_CASES = [
    {
        "id": 101,
        "title": "Opportunity to Invoice Sync",
        "description": "Sync opportunities from Salesforce to NetSuite invoices.",
        "business_goal": "Automate billing updates.",
        "target_systems": ["Salesforce", "NetSuite"],
        "frequency": "Daily",
        "criticality": "High",
        "data_flows": [
            {"source": "Salesforce", "destination": "NetSuite", "entity_type": "Invoice", "trigger": "Opportunity Closed Won"}
        ]
    },
    {
        "id": 102,
        "title": "Procurement Pipeline Sync",
        "description": "Log new purchase orders from ServiceNow to Coupa.",
        "business_goal": "Automate purchase orders.",
        "target_systems": ["ServiceNow", "Coupa"],
        "frequency": "Weekly",
        "criticality": "Medium",
        "data_flows": [
            {"source": "ServiceNow", "destination": "Coupa", "entity_type": "Purchase Order", "trigger": "Ticket Approved"}
        ]
    },
    {
        "id": 103,
        "title": "Payment Settlement Integration",
        "description": "Settle payments between NetSuite and Stripe.",
        "business_goal": "Automate payments.",
        "target_systems": ["NetSuite", "Stripe"],
        "frequency": "Daily",
        "criticality": "High",
        "data_flows": [
            {"source": "NetSuite", "destination": "Stripe", "entity_type": "Payment", "trigger": "Invoice Finalized"}
        ]
    },
    {
        "id": 104,
        "title": "Marketing Contact Sync",
        "description": "Sync marketing contacts from HubSpot to Salesforce CRM.",
        "business_goal": "Enrich contacts.",
        "target_systems": ["HubSpot", "Salesforce"],
        "frequency": "Daily",
        "criticality": "Low",
        "data_flows": [
            {"source": "HubSpot", "destination": "Salesforce", "entity_type": "Contact", "trigger": "Form Submitted"}
        ]
    },
    {
        "id": 105,
        "title": "Employee Onboarding Provisioning",
        "description": "Sync new hires from Workday to ServiceNow IT tickets.",
        "business_goal": "Provision resources.",
        "target_systems": ["Workday", "ServiceNow"],
        "frequency": "Weekly",
        "criticality": "Medium",
        "data_flows": [
            {"source": "Workday", "destination": "ServiceNow", "entity_type": "User Account", "trigger": "Employee Contract Signed"}
        ]
    }
]

@patch("backend.core.mapping_engine.call_llm_mapping")
def test_use_case_mapping_and_gap_analysis(mock_llm_mapping):
    # Force fallback to rule-based engine to verify local, deterministic calculations
    mock_llm_mapping.return_value = None

    reports = []
    for uc in USE_CASES:
        report = map_use_case_to_inventory(uc, MOCK_INVENTORY)
        reports.append(report)
        
        # Verify JSON/Dictionary output structure
        assert isinstance(report, dict)
        assert "use_case_id" in report
        assert "use_case_title" in report
        assert "required_systems" in report
        assert "gaps" in report
        assert "data_flow_analysis" in report
        assert "dependency_mapping" in report
        assert "dependency_graph" in report
        assert "business_impact" in report
        assert "priority_score" in report

    # 1. Verify we mapped 5 use cases successfully
    assert len(reports) == 5

    # 2. Check Use Case 1: Salesforce to NetSuite (Both available)
    uc1 = reports[0]
    assert uc1["use_case_title"] == "Opportunity to Invoice Sync"
    assert "Salesforce" in uc1["available_systems"]
    assert "NetSuite" in uc1["available_systems"]
    assert len(uc1["missing_systems"]) == 0
    assert len(uc1["integration_gaps"]) == 0
    # Trace data flow: source, destination, entity, trigger
    assert len(uc1["data_flow_analysis"]) == 1
    flow1 = uc1["data_flow_analysis"][0]
    assert flow1["source"] == "Salesforce"
    assert flow1["destination"] == "NetSuite"
    assert flow1["entity_type"] == "Invoice"
    assert flow1["trigger"] == "Opportunity Closed Won"
    assert flow1["is_blocked"] is False

    # 3. Check Use Case 3: NetSuite to Stripe (Stripe is missing!)
    uc3 = reports[2]
    assert uc3["use_case_title"] == "Payment Settlement Integration"
    assert "NetSuite" in uc3["available_systems"]
    assert "Stripe" in uc3["missing_systems"]
    assert len(uc3["integration_gaps"]) == 1
    # Check effort estimation for missing integration (should be Large)
    gap3 = uc3["integration_gaps"][0]
    assert gap3["system_name"] == "Stripe"
    assert gap3["status"] == "missing"
    assert gap3["effort_estimate"] == "Large"
    # Check dependency mapping output format
    assert len(uc3["dependency_mapping"]) == 1
    assert "Integration with Stripe must exist before Payment Settlement Integration can be automated." in uc3["dependency_mapping"]
    # Verify business impact prioritization
    assert uc3["priority_score"] > 0
    assert uc3["business_impact"] in ["Low", "Medium", "High", "Critical"]

    # 4. Check Use Case 5: Workday to ServiceNow (Workday is missing!)
    uc5 = reports[4]
    assert uc5["use_case_title"] == "Employee Onboarding Provisioning"
    assert "ServiceNow" in uc5["available_systems"]
    assert "Workday" in uc5["missing_systems"]
    assert len(uc5["integration_gaps"]) == 1
    gap5 = uc5["integration_gaps"][0]
    assert gap5["system_name"] == "Workday"
    assert gap5["status"] == "missing"
    assert gap5["effort_estimate"] == "Large"
    assert "Integration with Workday must exist before Employee Onboarding Provisioning can be automated." in uc5["dependency_mapping"]
