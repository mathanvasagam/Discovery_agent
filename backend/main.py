from __future__ import annotations
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

import csv
import io
import json
import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine, select

from core.code_generation_provider import generate_agent_definition, generate_connector
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
from core.provider_router import call_llm, get_llm_status, verify_llm_connection, verify_provider_connection
from core.sandbox import validate_code_in_sandbox
from core.security import security_middleware
from settings import settings


settings.validate_runtime()
settings.ensure_directories()

database_url = settings.database_url
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
elif database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
engine_kwargs: Dict[str, Any] = {
    "echo": False,
    "connect_args": connect_args,
    "pool_pre_ping": True,
}
if database_url.startswith("postgresql+psycopg://"):
    # Supabase's transaction pooler does not support client-side prepared statements.
    # Keep connection attempts bounded so a bad/unreachable pooler cannot hang app startup.
    connect_args["prepare_threshold"] = None
    connect_args["connect_timeout"] = 8
    engine_kwargs["pool_timeout"] = 10
    engine_kwargs["pool_recycle"] = 300

engine = create_engine(database_url, **engine_kwargs)
FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"
_database_initialized = False


@asynccontextmanager
async def lifespan(_: FastAPI):
    _initialize_database()
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
)
trusted_hosts = list(settings.parsed_allowed_hosts)
if not settings.is_production and "testserver" not in trusted_hosts:
    trusted_hosts.append("testserver")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts or ["*"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.parsed_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)
app.middleware("http")(security_middleware)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def ensure_compatibility_columns() -> None:
    """Add deployment-era columns to existing local databases without requiring a migration tool."""
    schema = {
        "usecase": {"workspace_id": "VARCHAR NOT NULL DEFAULT 'default'"},
        "documentrecord": {
            "workspace_id": "VARCHAR NOT NULL DEFAULT 'default'",
            "extracted_text": "TEXT NOT NULL DEFAULT ''",
            "retained": "BOOLEAN NOT NULL DEFAULT TRUE",
        },
        "inventorysystem": {"workspace_id": "VARCHAR NOT NULL DEFAULT 'default'"},
        "gapreportrecord": {"workspace_id": "VARCHAR NOT NULL DEFAULT 'default'"},
        "generatedartifact": {"workspace_id": "VARCHAR NOT NULL DEFAULT 'default'"},
        "validationrun": {"workspace_id": "VARCHAR NOT NULL DEFAULT 'default'"},
    }
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as connection:
        for table_name, additions in schema.items():
            if table_name not in existing_tables:
                continue
            existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, definition in additions.items():
                if column_name not in existing_columns:
                    connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"))
            if "workspace_id" in additions:
                connection.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{table_name}_workspace_id ON {table_name} (workspace_id)"))


def _initialize_database() -> bool:
    """Best-effort schema initialization.

    The web process must remain alive when the managed database is temporarily
    unavailable. Readiness stays false until the database can be reached and
    initialization succeeds.
    """
    global _database_initialized
    try:
        create_db_and_tables()
        ensure_compatibility_columns()
        _database_initialized = True
        logger.info("Database initialization completed.")
        return True
    except Exception as exc:
        _database_initialized = False
        logger.error("Database initialization unavailable: %s", exc)
        return False


def _database_ping() -> None:
    with Session(engine) as session:
        session.exec(text("SELECT 1"))


def _workspace_id(request: Request) -> str:
    return getattr(request.state, "workspace_id", "default")


def _workspace_select(model, workspace_id: str):
    return select(model).where(model.workspace_id == workspace_id)


def _slugify(name: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in name.lower()).strip("_") or "artifact"


def _persist_inventory(
    session: Session,
    systems: List[Dict[str, Any]],
    document_id: Optional[int] = None,
    workspace_id: str = "default",
) -> List[InventorySystem]:
    stored: List[InventorySystem] = []
    for system in systems:
        # Check for existing system
        existing = session.exec(
            select(InventorySystem).where(
                InventorySystem.workspace_id == workspace_id,
                InventorySystem.name.ilike(system["name"]),
            )
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
                workspace_id=workspace_id,
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


def process_document(file_path: str, content_type: Optional[str] = None) -> tuple[List[Dict[str, Any]], str]:
    chunks = ingest_document(file_path, content_type=content_type)
    if not chunks:
        return [], ""
    redacted = redact_chunks(chunks)
    redacted_text = "\n".join(str(chunk.get("content", "")) for chunk in redacted)
    redacted_text = redacted_text[: settings.max_persisted_text_chars]
    return extract_inventory(redacted), redacted_text


def discover_systems_from_file(file_path: str, content_type: Optional[str] = None) -> List[Dict[str, Any]]:
    systems, _ = process_document(file_path, content_type=content_type)
    return systems


def get_gap_report(
    use_case_id: int,
    inventory: Optional[List[Dict[str, Any]]] = None,
    workspace_id: str = "default",
) -> Dict[str, Any]:
    with Session(engine) as session:
        use_case = session.exec(
            select(UseCase).where(UseCase.id == use_case_id, UseCase.workspace_id == workspace_id)
        ).first()
        if not use_case:
            raise HTTPException(status_code=404, detail="Use case not found")
        inventory_rows = inventory if inventory is not None else [
            _inventory_payload(row) for row in session.exec(_workspace_select(InventorySystem, workspace_id)).all()
        ]
        report = map_use_case_to_inventory(_use_case_payload(use_case), inventory_rows)
        session.add(GapReportRecord(workspace_id=workspace_id, use_case_id=use_case_id, report_json=report))
        session.commit()
        return report


def _artifact_output_paths(artifact_dir: Path, connector: Dict[str, Any]) -> Dict[str, Path]:
    code_path = artifact_dir / connector["filename"]
    tests_filename = connector.get("test_filename") or ("test_generated.py" if connector["language"] == "python" else "generated.test.js")
    tests_path = artifact_dir / tests_filename
    readme_path = artifact_dir / "README.md"
    return {"code": code_path, "tests": tests_path, "readme": readme_path}


def _write_generated_artifact(connector: Dict[str, Any], workspace_id: str = "default") -> Path:
    artifact_dir = settings.generated_dir / workspace_id / f"{_slugify(connector['filename'])}"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    output_paths = _artifact_output_paths(artifact_dir, connector)
    output_paths["code"].write_text(connector["code"], encoding="utf-8")
    output_paths["tests"].write_text(connector.get("tests", ""), encoding="utf-8")
    output_paths["readme"].write_text(connector.get("readme", ""), encoding="utf-8")
    for filename, content in connector.get("config_files", {}).items():
        (artifact_dir / filename).write_text(content, encoding="utf-8")
    return artifact_dir


def generate_automation_package(
    gap_entry: Dict[str, Any],
    language: str = "python",
    workspace_id: str = "default",
) -> Dict[str, Any]:
    connector = generate_connector(gap_entry, language=language)
    artifact_dir = _write_generated_artifact(connector, workspace_id=workspace_id)
    agent_definition = generate_agent_definition(gap_entry)
    validation = validate_code_in_sandbox(connector)

    with Session(engine) as session:
        artifact_record = GeneratedArtifact(
            workspace_id=workspace_id,
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
                workspace_id=workspace_id,
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


@app.get("/healthz", include_in_schema=False)
async def liveness() -> Dict[str, str]:
    """Process-level liveness used by Render/Docker health checks."""
    return {"status": "alive"}


@app.get("/health")
async def health() -> Dict[str, Any]:
    database_status = "healthy"
    try:
        _database_ping()
    except Exception as exc:
        database_status = "unavailable"
        logger.error("Database health check failed: %s", exc)

    return {
        "status": "healthy" if database_status == "healthy" else "degraded",
        "database": database_status,
        "llm": get_llm_status(),
        "runtime": settings.runtime_status(),
    }


@app.get("/ready")
async def readiness() -> Dict[str, Any]:
    try:
        if not _database_initialized and not _initialize_database():
            raise RuntimeError("Database initialization is incomplete.")
        _database_ping()
    except Exception as exc:
        logger.error("Readiness check failed: %s", exc)
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return {"status": "ready"}


@app.post("/integrations/llm/verify")
async def verify_llm_integration() -> Dict[str, Any]:
    """Verify configured providers in failover order and return the first healthy provider."""
    return verify_llm_connection()


@app.post("/integrations/groq/verify")
async def verify_groq_integration() -> Dict[str, Any]:
    """Validate only the configured Groq provider."""
    return verify_provider_connection("groq")


@app.post("/integrations/gemini/verify")
async def verify_gemini_integration() -> Dict[str, Any]:
    """Validate only the configured Gemini provider."""
    return verify_provider_connection("gemini")


@app.get("/dashboard")
async def dashboard(request: Request) -> Dict[str, Any]:
    workspace_id = _workspace_id(request)
    with Session(engine) as session:
        documents = session.exec(_workspace_select(DocumentRecord, workspace_id)).all()
        systems = session.exec(_workspace_select(InventorySystem, workspace_id)).all()
        use_cases = session.exec(_workspace_select(UseCase, workspace_id)).all()
        artifacts = session.exec(_workspace_select(GeneratedArtifact, workspace_id)).all()
        validations = session.exec(_workspace_select(ValidationRun, workspace_id)).all()
        gap_reports = session.exec(_workspace_select(GapReportRecord, workspace_id)).all()

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
async def upload_document(request: Request, file: UploadFile = File(...)) -> Dict[str, Any]:
    workspace_id = _workspace_id(request)
    safe_filename = Path((file.filename or "upload.bin").replace("\\", "/")).name
    suffix = Path(safe_filename).suffix.lower()
    allowed_extensions = {
        ".pdf", ".txt", ".md", ".markdown", ".csv", ".docx", ".xlsx",
        ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp",
    }
    if safe_filename in {"", ".", ".."} or suffix not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Unsupported or invalid upload filename")

    workspace_uploads = settings.uploads_dir / workspace_id
    workspace_uploads.mkdir(parents=True, exist_ok=True)
    destination = workspace_uploads / safe_filename
    if destination.exists():
        destination = workspace_uploads / f"{Path(safe_filename).stem}_{uuid4().hex[:8]}{suffix}"

    max_upload_bytes = settings.max_upload_bytes
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

    try:
        systems, extracted_text = process_document(str(destination), content_type=file.content_type)
        retained_path = str(destination) if settings.retain_uploads else ""
        with Session(engine) as session:
            document = DocumentRecord(
                workspace_id=workspace_id,
                filename=safe_filename,
                stored_path=retained_path,
                content_type=file.content_type or "application/octet-stream",
                size_bytes=size_bytes,
                extracted_text=extracted_text,
                retained=settings.retain_uploads,
            )
            session.add(document)
            session.commit()
            session.refresh(document)
            stored_systems = _persist_inventory(
                session,
                systems,
                document_id=document.id,
                workspace_id=workspace_id,
            )

            return {
                "document": {
                    "id": document.id,
                    "filename": document.filename,
                    "content_type": document.content_type,
                    "size_bytes": document.size_bytes,
                    "retained": document.retained,
                },
                "systems": [_inventory_payload(system) for system in stored_systems],
            }
    finally:
        if not settings.retain_uploads:
            destination.unlink(missing_ok=True)


@app.get("/documents")
async def list_documents(request: Request) -> List[Dict[str, Any]]:
    workspace_id = _workspace_id(request)
    with Session(engine) as session:
        documents = session.exec(_workspace_select(DocumentRecord, workspace_id)).all()
        return [
            {
                "id": document.id,
                "filename": document.filename,
                "content_type": document.content_type,
                "size_bytes": document.size_bytes,
                "retained": document.retained,
                "created_at": document.created_at.isoformat(),
            }
            for document in documents
        ]


@app.get("/inventory")
async def list_inventory(
    request: Request,
    search: str = "",
    category: str = "",
    criticality: str = "",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Dict[str, Any]:
    workspace_id = _workspace_id(request)
    with Session(engine) as session:
        # Sort by ID descending so newest items are first
        statement = _workspace_select(InventorySystem, workspace_id).order_by(InventorySystem.id.desc())
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
async def clear_inventory(request: Request):
    workspace_id = _workspace_id(request)
    with Session(engine) as session:
        table = SQLModel.metadata.tables["inventorysystem"]
        session.exec(table.delete().where(table.c.workspace_id == workspace_id))
        session.commit()
    return None


@app.get("/inventory/export/json")
async def export_inventory_json(request: Request) -> Response:
    workspace_id = _workspace_id(request)
    with Session(engine) as session:
        items = [_inventory_payload(row) for row in session.exec(_workspace_select(InventorySystem, workspace_id)).all()]
    return Response(
        content=json.dumps(items, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="inventory_export.json"'},
    )


@app.get("/inventory/export/csv")
async def export_inventory_csv(request: Request) -> Response:
    workspace_id = _workspace_id(request)
    with Session(engine) as session:
        items = [_inventory_payload(row) for row in session.exec(_workspace_select(InventorySystem, workspace_id)).all()]
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=["name", "category", "auth_method", "criticality", "confidence_score", "evidence", "source_reference"],
    )
    writer.writeheader()
    for item in items:
        writer.writerow({key: item.get(key, "") for key in writer.fieldnames})
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="inventory_export.csv"'},
    )


@app.post("/use-cases", status_code=201)
async def create_use_case(request: Request, payload: UseCaseCreate) -> Dict[str, Any]:
    workspace_id = _workspace_id(request)
    with Session(engine) as session:
        use_case = UseCase(
        workspace_id=workspace_id,
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
async def list_use_cases(request: Request) -> List[Dict[str, Any]]:
    workspace_id = _workspace_id(request)
    with Session(engine) as session:
        return [_use_case_payload(row) for row in session.exec(_workspace_select(UseCase, workspace_id)).all()]


@app.post("/use-cases/discover", status_code=200)
async def discover_goals(request: Request) -> Dict[str, Any]:
    workspace_id = _workspace_id(request)
    text_content = ""
    with Session(engine) as session:
        documents = session.exec(_workspace_select(DocumentRecord, workspace_id)).all()
        for doc in documents:
            if doc.extracted_text:
                text_content += "\n" + doc.extracted_text
                continue
            if doc.retained and doc.stored_path:
                try:
                    chunks = ingest_document(doc.stored_path, content_type=doc.content_type)
                    if chunks:
                        redacted_chunks = redact_chunks(chunks)
                        text_content += "\n" + "\n".join(c["content"] for c in redacted_chunks if "content" in c)
                except Exception as exc:
                    logger.error("Error reading retained document %s during goal discovery: %s", doc.filename, exc)
        
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
                res = call_llm(prompt, response_mime_type="application/json")
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
            inventory = [_inventory_payload(row) for row in session.exec(_workspace_select(InventorySystem, workspace_id)).all()]
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
            exists = session.exec(
                select(UseCase).where(UseCase.workspace_id == workspace_id, UseCase.title == item["title"])
            ).first()
            if not exists:
                use_case = UseCase(
                    workspace_id=workspace_id,
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
async def run_gap_analysis(request: Request, payload: GapAnalysisRequest) -> Dict[str, Any]:
    workspace_id = _workspace_id(request)
    with Session(engine) as session:
        use_case = UseCase(
        workspace_id=workspace_id,
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
    return get_gap_report(use_case_id, workspace_id=workspace_id)


@app.get("/gaps/{use_case_id}")
async def gap_report(request: Request, use_case_id: int) -> Dict[str, Any]:
    return get_gap_report(use_case_id, workspace_id=_workspace_id(request))


@app.post("/generate-connectors", status_code=201)
async def generate_connectors(request: Request, payload: ConnectorGenerationRequest) -> Dict[str, Any]:
    payload_dict = {
        "system_name": payload.system_name,
        "category": payload.category,
        "auth_method": payload.auth_method,
        "use_case_title": payload.use_case_title,
        "language": payload.language,
    }
    return generate_automation_package(
        payload_dict,
        language=payload.language,
        workspace_id=_workspace_id(request),
    )


@app.get("/artifacts")
async def list_artifacts(request: Request) -> List[Dict[str, Any]]:
    workspace_id = _workspace_id(request)
    with Session(engine) as session:
        artifacts = session.exec(_workspace_select(GeneratedArtifact, workspace_id)).all()
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
async def validate(request: Request, payload: ValidationRequest) -> Dict[str, Any]:
    workspace_id = _workspace_id(request)
    artifact_payload: Optional[Dict[str, Any]] = None
    with Session(engine) as session:
        if payload.artifact_id:
            artifact = session.exec(
                select(GeneratedArtifact).where(
                    GeneratedArtifact.id == payload.artifact_id,
                    GeneratedArtifact.workspace_id == workspace_id,
                )
            ).first()
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
                workspace_id=workspace_id,
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
async def list_validations(request: Request) -> List[Dict[str, Any]]:
    workspace_id = _workspace_id(request)
    with Session(engine) as session:
        validations = session.exec(_workspace_select(ValidationRun, workspace_id)).all()
        return [row.result_json for row in validations]


@app.get("/reports")
async def reports(request: Request) -> Dict[str, Any]:
    workspace_id = _workspace_id(request)
    with Session(engine) as session:
        documents = session.exec(_workspace_select(DocumentRecord, workspace_id)).all()
        inventory_rows = session.exec(_workspace_select(InventorySystem, workspace_id).order_by(InventorySystem.id.desc())).all()
        use_cases = session.exec(_workspace_select(UseCase, workspace_id)).all()
        validations = [row.result_json for row in session.exec(_workspace_select(ValidationRun, workspace_id)).all()]
        artifact_rows = session.exec(_workspace_select(GeneratedArtifact, workspace_id)).all()

        artifacts = [
            {
                "id": artifact.id,
                "system_name": artifact.system_name,
                "language": artifact.language,
                "filename": artifact.filename,
                "created_at": artifact.created_at.isoformat(),
            }
            for artifact in artifact_rows
        ]
        document_payloads = [
            {
                "id": document.id,
                "filename": document.filename,
                "content_type": document.content_type,
                "size_bytes": document.size_bytes,
                "retained": document.retained,
                "created_at": document.created_at.isoformat(),
            }
            for document in documents
        ]
        inventory_items = [_inventory_payload(row) for row in inventory_rows]

    return {
        "documents": document_payloads,
        "inventory": {"items": inventory_items, "total": len(inventory_items), "page": 1, "page_size": len(inventory_items) or 10},
        "use_cases": [_use_case_payload(row) for row in use_cases],
        "artifacts": artifacts,
        "validations": validations,
    }


@app.get("/reports/gaps/{use_case_id}.json")
async def export_gap_report(request: Request, use_case_id: int) -> Response:
    report = get_gap_report(use_case_id, workspace_id=_workspace_id(request))
    filename = f"gap_report_{use_case_id}.json"
    return Response(
        content=json.dumps(report, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/", include_in_schema=False)
async def application_root():
    index_path = FRONTEND_DIST / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return JSONResponse({"name": settings.app_name, "status": "api-only", "health": "/health"})


@app.get("/assets/{asset_path:path}", include_in_schema=False)
async def frontend_assets(asset_path: str):
    assets_root = (FRONTEND_DIST / "assets").resolve()
    candidate = (assets_root / asset_path).resolve()
    try:
        candidate.relative_to(assets_root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Asset not found") from exc
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="Asset not found")
    return FileResponse(candidate)


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
