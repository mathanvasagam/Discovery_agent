from __future__ import annotations
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

import csv
import json
import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlmodel import Session, SQLModel, create_engine, select

from core.code_gen import generate_agent_definition, generate_connector
from core.extractor import extract_inventory
from core.ingestor import ingest_document
from core.mapping_engine import map_use_case_to_inventory
from models import (
    ConnectorGenerationRequest,
    DocumentRecord,
    GapAnalysisRequest,
    GapReportRecord,
    GeneratedArtifact,
    InventorySystem,
    UseCase,
    UseCaseCreate,
    ValidationRequest,
    ValidationRun,
)
from core.redactor import redact_chunks
from core.sandbox import validate_code_in_sandbox
from settings import settings


settings.ensure_directories()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, echo=False, connect_args=connect_args)


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv("DISCOVERY_CORS_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def _slugify(name: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in name.lower()).strip("_") or "artifact"


def _persist_inventory(
    session: Session,
    systems: List[Dict[str, Any]],
    document_id: Optional[int] = None,
) -> List[InventorySystem]:
    stored: List[InventorySystem] = []
    for system in systems:
        # Check for existing system
        existing = session.exec(
            select(InventorySystem).where(InventorySystem.name.ilike(system["name"]))
        ).first()

        new_evidence = system.get("evidence", "")
        new_source = system.get("source_reference", "")
        
        if existing:
            # Deduplicate: Update existing record
            if new_evidence and new_evidence not in existing.all_evidence:
                # Need to create a new list and reassign to trigger SQLAlchemy JSON update
                all_ev = list(existing.all_evidence)
                all_ev.append(new_evidence)
                existing.all_evidence = all_ev
            if new_source and new_source not in existing.all_sources:
                all_src = list(existing.all_sources)
                all_src.append(new_source)
                existing.all_sources = all_src
            
            # Update confidence if the new one is higher
            new_conf = float(system.get("confidence_score", 0.0))
            if new_conf > existing.confidence_score:
                existing.confidence_score = new_conf
                existing.evidence = new_evidence
                existing.source_reference = new_source
                existing.human_review_required = bool(system.get("human_review_required", False))
                existing.inference_note = system.get("inference_note", "")

            # Merge entities and processes
            current_entities = set(existing.key_entities)
            for entity in system.get("key_entities", []):
                if entity not in current_entities:
                    current_entities.add(entity)
            existing.key_entities = list(current_entities)

            current_processes = set(existing.business_processes)
            for process in system.get("business_processes", []):
                if process not in current_processes:
                    current_processes.add(process)
            existing.business_processes = list(current_processes)

            session.add(existing)
            stored.append(existing)
        else:
            # Create new record
            record = InventorySystem(
                name=system["name"],
                category=system["category"],
                auth_method=system["auth_method"],
                key_entities=system.get("key_entities", []),
                business_processes=system.get("business_processes", []),
                criticality=system.get("criticality", "Medium"),
                confidence_score=float(system.get("confidence_score", 0.0)),
                evidence=new_evidence,
                all_evidence=[new_evidence] if new_evidence else [],
                inference_note=system.get("inference_note", ""),
                human_review_required=bool(system.get("human_review_required", False)),
                source_reference=new_source,
                all_sources=[new_source] if new_source else [],
                page_number=system.get("page_number"),
                line_number=system.get("line_number"),
            )
            session.add(record)
            stored.append(record)
            
    session.commit()
    for record in stored:
        session.refresh(record)
    return stored


def _inventory_payload(record: InventorySystem) -> Dict[str, Any]:
    return {
        "id": record.id,
        "name": record.name,
        "category": record.category,
        "auth_method": record.auth_method,
        "key_entities": record.key_entities,
        "business_processes": record.business_processes,
        "criticality": record.criticality,
        "confidence_score": record.confidence_score,
        "evidence": record.evidence,
        "all_evidence": record.all_evidence,
        "inference_note": record.inference_note,
        "human_review_required": record.human_review_required,
        "source_reference": record.source_reference,
        "all_sources": record.all_sources,
        "page_number": record.page_number,
        "line_number": record.line_number,
    }


def _use_case_payload(use_case: UseCase) -> Dict[str, Any]:
    return {
        "id": use_case.id,
        "title": use_case.title,
        "description": use_case.description,
        "business_goal": use_case.business_goal,
        "target_systems": use_case.target_systems,
        "data_flows": use_case.data_flows,
        "frequency": use_case.frequency,
        "criticality": use_case.criticality,
        "created_at": use_case.created_at.isoformat(),
    }


def discover_systems_from_file(file_path: str, content_type: Optional[str] = None) -> List[Dict[str, Any]]:
    chunks = ingest_document(file_path, content_type=content_type)
    if not chunks:
        return []
    redacted = redact_chunks(chunks)
    return extract_inventory(redacted)


def get_gap_report(use_case_id: int, inventory: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    with Session(engine) as session:
        use_case = session.get(UseCase, use_case_id)
        if not use_case:
            raise HTTPException(status_code=404, detail="Use case not found")
        inventory_rows = inventory if inventory is not None else [_inventory_payload(row) for row in session.exec(select(InventorySystem)).all()]
        report = map_use_case_to_inventory(_use_case_payload(use_case), inventory_rows)
        session.add(GapReportRecord(use_case_id=use_case_id, report_json=report))
        session.commit()
        return report


def _artifact_output_paths(artifact_dir: Path, connector: Dict[str, Any]) -> Dict[str, Path]:
    code_path = artifact_dir / connector["filename"]
    tests_filename = connector.get("test_filename") or ("test_generated.py" if connector["language"] == "python" else "generated.test.js")
    tests_path = artifact_dir / tests_filename
    readme_path = artifact_dir / "README.md"
    return {"code": code_path, "tests": tests_path, "readme": readme_path}


def _write_generated_artifact(connector: Dict[str, Any]) -> Path:
    artifact_dir = settings.generated_dir / f"{_slugify(connector['filename'])}"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    output_paths = _artifact_output_paths(artifact_dir, connector)
    output_paths["code"].write_text(connector["code"], encoding="utf-8")
    output_paths["tests"].write_text(connector.get("tests", ""), encoding="utf-8")
    output_paths["readme"].write_text(connector.get("readme", ""), encoding="utf-8")
    for filename, content in connector.get("config_files", {}).items():
        (artifact_dir / filename).write_text(content, encoding="utf-8")
    return artifact_dir


def generate_automation_package(gap_entry: Dict[str, Any], language: str = "python") -> Dict[str, Any]:
    connector = generate_connector(gap_entry, language=language)
    artifact_dir = _write_generated_artifact(connector)
    agent_definition = generate_agent_definition(gap_entry)
    validation = validate_code_in_sandbox(connector)

    with Session(engine) as session:
        artifact_record = GeneratedArtifact(
            system_name=gap_entry.get("system_name", "Unknown"),
            language=connector["language"],
            filename=connector["filename"],
            artifact_dir=str(artifact_dir),
            artifact_json={
                "connector": connector,
                "agent_definition": agent_definition,
                "validation": validation,
            },
        )
        session.add(artifact_record)
        session.commit()
        session.refresh(artifact_record)
        session.add(
            ValidationRun(
                artifact_id=artifact_record.id,
                filename=connector["filename"],
                language=connector["language"],
                status=validation["status"],
                result_json=validation,
            )
        )
        session.commit()

    return {
        "connector": connector,
        "agent_definition": agent_definition,
        "validation": validation,
        "artifact_dir": str(artifact_dir),
    }


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "healthy"}


@app.get("/dashboard")
async def dashboard() -> Dict[str, Any]:
    with Session(engine) as session:
        documents = session.exec(select(DocumentRecord)).all()
        systems = session.exec(select(InventorySystem)).all()
        use_cases = session.exec(select(UseCase)).all()
        artifacts = session.exec(select(GeneratedArtifact)).all()
        validations = session.exec(select(ValidationRun)).all()
        gap_reports = session.exec(select(GapReportRecord)).all()

        total_gaps = sum(len([g for g in r.report_json.get("gaps", []) if g.get("status") == "missing"]) for r in gap_reports)
        avg_conf = sum(s.confidence_score for s in systems) / len(systems) if systems else 0.0

        return {
            "documents": len(documents),
            "systems": len(systems),
            "use_cases": len(use_cases),
            "artifacts": len(artifacts),
            "validations": len(validations),
            "latest_systems": [_inventory_payload(system) for system in systems[-5:]],
            "integration_gaps": total_gaps,
            "average_confidence": round(avg_conf * 100),
        }


@app.post("/documents/upload", status_code=201)
async def upload_document(file: UploadFile = File(...)) -> Dict[str, Any]:
    safe_filename = Path((file.filename or "upload.bin").replace("\\", "/")).name
    suffix = Path(safe_filename).suffix.lower()
    allowed_extensions = {
        ".pdf", ".txt", ".md", ".markdown", ".csv", ".docx", ".xlsx",
        ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp",
    }
    if safe_filename in {"", ".", ".."} or suffix not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Unsupported or invalid upload filename")

    destination = settings.uploads_dir / safe_filename
    if destination.exists():
        destination = settings.uploads_dir / f"{Path(safe_filename).stem}_{uuid4().hex[:8]}{suffix}"

    max_upload_bytes = int(os.getenv("DISCOVERY_MAX_UPLOAD_BYTES", str(20 * 1024 * 1024)))
    size_bytes = 0
    try:
        with destination.open("wb") as handle:
            while chunk := await file.read(1024 * 1024):
                size_bytes += len(chunk)
                if size_bytes > max_upload_bytes:
                    raise HTTPException(status_code=413, detail="Uploaded file exceeds the configured size limit")
                handle.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    with Session(engine) as session:
        document = DocumentRecord(
            filename=safe_filename,
            stored_path=str(destination),
            content_type=file.content_type or "application/octet-stream",
            size_bytes=size_bytes,
        )
        session.add(document)
        session.commit()
        session.refresh(document)

        systems = discover_systems_from_file(str(destination), content_type=file.content_type)
        stored_systems = _persist_inventory(session, systems, document_id=document.id)

        return {
            "document": {
                "id": document.id,
                "filename": document.filename,
                "content_type": document.content_type,
                "size_bytes": document.size_bytes,
            },
            "systems": [_inventory_payload(system) for system in stored_systems],
        }


@app.get("/documents")
async def list_documents() -> List[Dict[str, Any]]:
    with Session(engine) as session:
        documents = session.exec(select(DocumentRecord)).all()
        return [
            {
                "id": document.id,
                "filename": document.filename,
                "content_type": document.content_type,
                "size_bytes": document.size_bytes,
                "created_at": document.created_at.isoformat(),
            }
            for document in documents
        ]


@app.get("/inventory")
async def list_inventory(
    search: str = "",
    category: str = "",
    criticality: str = "",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Dict[str, Any]:
    with Session(engine) as session:
        # Sort by ID descending so newest items are first
        statement = select(InventorySystem).order_by(InventorySystem.id.desc())
        rows = session.exec(statement).all()
        items = [_inventory_payload(row) for row in rows]

        if search:
            lowered = search.lower()
            items = [item for item in items if lowered in item["name"].lower() or lowered in item["category"].lower() or lowered in item["source_reference"].lower()]
        if category:
            items = [item for item in items if item["category"] == category]
        if criticality:
            items = [item for item in items if item["criticality"] == criticality]

        total = len(items)
        page_val = page if isinstance(page, int) else page.default
        page_size_val = page_size if isinstance(page_size, int) else page_size.default
        start = (page_val - 1) * page_size_val
        paged = items[start:start + page_size_val]
        return {"items": paged, "total": total, "page": page_val, "page_size": page_size_val}


@app.delete("/inventory", status_code=204)
async def clear_inventory():
    with Session(engine) as session:
        session.exec(SQLModel.metadata.tables["inventorysystem"].delete())
        session.commit()
    return None


@app.get("/inventory/export/json")
async def export_inventory_json() -> FileResponse:
    with Session(engine) as session:
        items = [_inventory_payload(row) for row in session.exec(select(InventorySystem)).all()]
    output_path = settings.reports_dir / "inventory_export.json"
    output_path.write_text(json.dumps(items, indent=2), encoding="utf-8")
    return FileResponse(output_path, media_type="application/json", filename="inventory_export.json")


@app.get("/inventory/export/csv")
async def export_inventory_csv() -> FileResponse:
    with Session(engine) as session:
        items = [_inventory_payload(row) for row in session.exec(select(InventorySystem)).all()]
    output_path = settings.reports_dir / "inventory_export.csv"
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["name", "category", "auth_method", "criticality", "confidence_score", "evidence", "source_reference"],
        )
        writer.writeheader()
        for item in items:
            writer.writerow({key: item.get(key, "") for key in writer.fieldnames})
    return FileResponse(output_path, media_type="text/csv", filename="inventory_export.csv")


@app.post("/use-cases", status_code=201)
async def create_use_case(payload: UseCaseCreate) -> Dict[str, Any]:
    with Session(engine) as session:
        use_case = UseCase(
        title=payload.title,
        description=payload.description,
        business_goal=payload.business_goal,
        target_systems=payload.target_systems,
        data_flows=payload.data_flows,
        frequency=payload.frequency,
        criticality=payload.criticality
    )
        if not use_case.business_goal:
            use_case.business_goal = use_case.description or use_case.title
        session.add(use_case)
        session.commit()
        session.refresh(use_case)
        return _use_case_payload(use_case)


@app.get("/use-cases")
async def list_use_cases() -> List[Dict[str, Any]]:
    with Session(engine) as session:
        return [_use_case_payload(row) for row in session.exec(select(UseCase)).all()]


@app.post("/use-cases/discover", status_code=200)
async def discover_goals() -> Dict[str, Any]:
    text_content = ""
    with Session(engine) as session:
        documents = session.exec(select(DocumentRecord)).all()
        for doc in documents:
            try:
                chunks = ingest_document(doc.stored_path, content_type=doc.content_type)
                if chunks:
                    text_content += "\n" + "\n".join(c["content"] for c in chunks if "content" in c)
            except Exception as e:
                logger.error(f"Error reading document {doc.filename} during goal discovery: {e}")
        
        text_content = text_content[:10000].strip()

        discovered = None
        if text_content:
            prompt = (
                "Review the following systems documentation and identify 2-3 potential integration use cases or automation goals. "
                "For each use case, specify: \n"
                "1. title: A concise name (e.g. 'Invoice Automation')\n"
                "2. description: What the automation does and achieves (e.g. 'Automatically sync sales opportunities to generate NetSuite invoices')\n"
                "3. target_systems: A list of systems involved (e.g. ['Salesforce', 'NetSuite'])\n\n"
                f"Documentation Text:\n{text_content}\n\n"
                "Return the output STRICTLY as a JSON object with a single key 'use_cases' containing the list of objects."
            )
            try:
                from core.llm import call_gemini
                res = call_gemini(prompt, response_mime_type="application/json")
                if res and isinstance(res, dict) and "use_cases" in res:
                    discovered = res["use_cases"]
            except Exception as e:
                logger.error(f"LLM goal discovery failed: {e}")

        if discovered:
            sanitized_discovered = []
            for item in discovered:
                if not isinstance(item, dict):
                    continue
                title = item.get("title") or item.get("use_case") or item.get("name")
                description = item.get("description") or item.get("business_goal") or item.get("goal") or "Auto-discovered automation goal."
                target_systems = item.get("target_systems") or item.get("systems") or []
                if not isinstance(target_systems, list):
                    target_systems = [str(target_systems)]
                if title:
                    sanitized_discovered.append({
                        "title": str(title),
                        "description": str(description),
                        "target_systems": [str(s) for s in target_systems if s]
                    })
            discovered = sanitized_discovered

        if not discovered:
            discovered = []
            inventory = [_inventory_payload(row) for row in session.exec(select(InventorySystem)).all()]
            system_names = [sys["name"] for sys in inventory]
            
            has_crm = any(x in [s.lower() for s in system_names] for x in ["salesforce", "hubspot", "pipedrive", "crm"])
            has_erp = any(x in [s.lower() for s in system_names] for x in ["netsuite", "stripe", "quickbooks", "sap", "billing"])
            
            crm_name = next((s for s in system_names if s.lower() in ["salesforce", "hubspot", "pipedrive"]), "CRM")
            erp_name = next((s for s in system_names if s.lower() in ["netsuite", "stripe", "quickbooks"]), "ERP")

            if has_crm and has_erp:
                discovered.append({
                    "title": "Invoice & Billing Automation",
                    "description": f"Automatically create invoices and billing schedules in {erp_name} when deals are marked as Won in {crm_name}.",
                    "target_systems": [crm_name, erp_name]
                })
            
            if "Stripe" in system_names:
                other = next((s for s in system_names if s != "Stripe"), None)
                discovered.append({
                    "title": "Payment Reconciliation Sync",
                    "description": f"Sync Stripe charge events and transfer payouts directly to {other or 'the ledger'} for automatic reconciliation.",
                    "target_systems": ["Stripe"] + ([other] if other else [])
                })
            
            if len(system_names) >= 2 and not discovered:
                discovered.append({
                    "title": "Cross-System Sync",
                    "description": f"Enable real-time data sync and updates between {system_names[0]} and {system_names[1]}.",
                    "target_systems": [system_names[0], system_names[1]]
                })
            
            if len(system_names) == 1 and not discovered:
                discovered.append({
                    "title": f"{system_names[0]} Pipeline Automation",
                    "description": f"Automate manual data entries, event webhooks, and status transitions inside {system_names[0]}.",
                    "target_systems": [system_names[0]]
                })

            if not discovered:
                discovered = [
                    {
                        "title": "Invoice Automation",
                        "description": "Automatically create invoices from Salesforce opportunities.",
                        "target_systems": ["Salesforce", "NetSuite", "Stripe"]
                    },
                    {
                        "title": "Customer Profile Sync",
                        "description": "Synchronize lead accounts and customer contact profiles across front-office and back-office services.",
                        "target_systems": ["HubSpot", "Salesforce"]
                    }
                ]

        inserted_payloads = []
        for item in discovered:
            exists = session.exec(select(UseCase).where(UseCase.title == item["title"])).first()
            if not exists:
                use_case = UseCase(
                    title=item["title"],
                    description=item["description"],
                    business_goal=item["description"],
                    target_systems=item.get("target_systems", []),
                    data_flows=[],
                    frequency="Real-time",
                    criticality="High"
                )
                session.add(use_case)
                session.commit()
                session.refresh(use_case)
                inserted_payloads.append(_use_case_payload(use_case))
            else:
                inserted_payloads.append(_use_case_payload(exists))
                
        return {"use_cases": inserted_payloads}



@app.post("/gap-analysis", status_code=201)
async def run_gap_analysis(payload: GapAnalysisRequest) -> Dict[str, Any]:
    with Session(engine) as session:
        use_case = UseCase(
        title=payload.title,
        description=payload.description,
        business_goal=payload.business_goal,
        target_systems=payload.target_systems,
        data_flows=payload.data_flows,
        frequency=payload.frequency,
        criticality=payload.criticality
    )
        if not use_case.business_goal:
            use_case.business_goal = payload.business_goal
        session.add(use_case)
        session.commit()
        session.refresh(use_case)
        use_case_id = use_case.id
    return get_gap_report(use_case_id)


@app.get("/gaps/{use_case_id}")
async def gap_report(use_case_id: int) -> Dict[str, Any]:
    return get_gap_report(use_case_id)


@app.post("/generate-connectors", status_code=201)
async def generate_connectors(payload: ConnectorGenerationRequest) -> Dict[str, Any]:
    payload_dict = {
        "system_name": payload.system_name,
        "category": payload.category,
        "auth_method": payload.auth_method,
        "use_case_title": payload.use_case_title,
        "language": payload.language,
    }
    return generate_automation_package(payload_dict, language=payload.language)


@app.get("/artifacts")
async def list_artifacts() -> List[Dict[str, Any]]:
    with Session(engine) as session:
        artifacts = session.exec(select(GeneratedArtifact)).all()
        return [
            {
                "id": artifact.id,
                "system_name": artifact.system_name,
                "language": artifact.language,
                "filename": artifact.filename,
                "artifact_dir": artifact.artifact_dir,
                "created_at": artifact.created_at.isoformat(),
                "validation": artifact.artifact_json.get("validation", {}),
            }
            for artifact in artifacts
        ]


@app.post("/validate", status_code=201)
async def validate(payload: ValidationRequest) -> Dict[str, Any]:
    artifact_payload: Optional[Dict[str, Any]] = None
    with Session(engine) as session:
        if payload.artifact_id:
            artifact = session.get(GeneratedArtifact, payload.artifact_id)
            if not artifact:
                raise HTTPException(status_code=404, detail="Artifact not found")
            artifact_payload = artifact.artifact_json["connector"]
        else:
            if not payload.filename or not payload.code:
                raise HTTPException(status_code=400, detail="Provide artifact_id or filename + code")
            artifact_payload = {
                "filename": payload.filename,
                "language": payload.language,
                "code": payload.code,
                "tests": payload.tests,
            }

        result = validate_code_in_sandbox(artifact_payload)
        session.add(
            ValidationRun(
                artifact_id=payload.artifact_id,
                filename=artifact_payload["filename"],
                language=artifact_payload.get("language", payload.language),
                status=result["status"],
                result_json=result,
            )
        )
        session.commit()
        return result


@app.get("/validations")
async def list_validations() -> List[Dict[str, Any]]:
    with Session(engine) as session:
        validations = session.exec(select(ValidationRun)).all()
        return [row.result_json for row in validations]


@app.get("/reports")
async def reports() -> Dict[str, Any]:
    with Session(engine) as session:
        validations = [row.result_json for row in session.exec(select(ValidationRun)).all()]
        artifacts = [
            {
                "id": artifact.id,
                "system_name": artifact.system_name,
                "language": artifact.language,
                "filename": artifact.filename,
                "created_at": artifact.created_at.isoformat(),
            }
            for artifact in session.exec(select(GeneratedArtifact)).all()
        ]
    return {
        "documents": await list_documents(),
        "inventory": await list_inventory(),
        "use_cases": await list_use_cases(),
        "artifacts": artifacts,
        "validations": validations,
    }


@app.get("/reports/gaps/{use_case_id}.json")
async def export_gap_report(use_case_id: int) -> FileResponse:
    report = get_gap_report(use_case_id)
    output_path = settings.reports_dir / f"gap_report_{use_case_id}.json"
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return FileResponse(output_path, media_type="application/json", filename=output_path.name)


@app.get("/demo/workflow")
async def demo_workflow() -> Dict[str, Any]:
    return {
        "steps": [
            "Upload document",
            "Discover systems",
            "Run gap analysis",
            "Generate connector",
            "Validate connector",
            "Export report",
        ],
        "estimated_minutes": 3,
    }


app.middleware_stack = app.build_middleware_stack()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
