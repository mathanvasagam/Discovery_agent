import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from main import app
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool
from models import DocumentRecord, InventorySystem, UseCase

@pytest.fixture(name="test_engine")
def test_engine_fixture():
    # Set up in-memory sqlite with StaticPool for connection sharing
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    return engine

@pytest.fixture(name="client")
def client_fixture(test_engine):
    # Patch the global engine in main.py to use the test database across namespaces
    with patch("main.engine", test_engine), patch("backend.main.engine", test_engine, create=True):
        with TestClient(app) as client:
            yield client

def test_create_use_case_returns_created_payload(client):
    response = client.post(
        "/use-cases",
        json={
            "title": "Invoice Sync",
            "description": "Sync opportunities to invoices.",
            "business_goal": "Automate invoicing.",
            "target_systems": ["Salesforce", "NetSuite"],
            "data_flows": [],
            "frequency": "Daily",
            "criticality": "High",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["id"] is not None
    assert payload["title"] == "Invoice Sync"
    assert payload["target_systems"] == ["Salesforce", "NetSuite"]


def test_health_reports_safe_llm_configuration(client):
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert "llm" in payload
    assert "configured" in payload["llm"]
    assert "api_key" not in payload["llm"]


def test_liveness_is_database_independent(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_readiness_reports_database_ready(client):
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_cors_allows_local_vite_loopback_origin(client):
    response = client.get(
        "/health",
        headers={"Origin": "http://127.0.0.1:5173"},
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"


def test_discover_goals_endpoint_fallback(client):
    # Test discovery when no documents or inventory exist (should return default use cases)
    response = client.post("/use-cases/discover")
    assert response.status_code == 200
    data = response.json()
    assert "use_cases" in data
    assert len(data["use_cases"]) >= 2

    titles = [uc["title"] for uc in data["use_cases"]]
    assert "Invoice Automation" in titles
    assert "Customer Profile Sync" in titles

def test_discover_goals_endpoint_with_inventory(client, test_engine):
    # Setup some test inventory systems in the patched db
    with Session(test_engine) as session:
        session.add(InventorySystem(
            name="Salesforce",
            category="CRM",
            auth_method="OAuth2",
            criticality="High",
            confidence_score=0.98,
            evidence="Uses Salesforce CRM.",
            source_reference="docs.txt"
        ))
        session.add(InventorySystem(
            name="NetSuite",
            category="ERP",
            auth_method="Token",
            criticality="High",
            confidence_score=0.95,
            evidence="Uses NetSuite ERP.",
            source_reference="docs.txt"
        ))
        session.commit()
        
        # Verify they exist in this session
        assert len(session.exec(select(InventorySystem)).all()) == 2

    # Call endpoint - should auto-discover based on CRM + ERP rule
    response = client.post("/use-cases/discover")
    assert response.status_code == 200
    data = response.json()
    assert "use_cases" in data
    
    titles = [uc["title"] for uc in data["use_cases"]]
    assert "Invoice & Billing Automation" in titles
