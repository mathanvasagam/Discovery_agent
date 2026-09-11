from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, Column, Text
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UseCase(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    workspace_id: str = Field(default="default", index=True)
    title: str
    description: str
    business_goal: str = ""
    target_systems: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    data_flows: List[Dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    frequency: str = "Monthly"
    criticality: str = "Medium"
    created_at: datetime = Field(default_factory=utcnow, nullable=False)

    def normalized_goal(self) -> str:
        return self.business_goal or self.description or self.title


class DocumentRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    workspace_id: str = Field(default="default", index=True)
    filename: str
    stored_path: str
    content_type: str
    size_bytes: int = 0
    extracted_text: str = Field(default="", sa_column=Column(Text))
    retained: bool = True
    created_at: datetime = Field(default_factory=utcnow, nullable=False)


class InventorySystem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    workspace_id: str = Field(default="default", index=True)
    name: str = Field(index=True)
    category: str
    auth_method: str
    key_entities: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    business_processes: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    criticality: str
    confidence_score: float
    evidence: str
    all_evidence: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    inference_note: str = ""
    human_review_required: bool = False
    source_reference: str
    all_sources: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    page_number: Optional[int] = None
    line_number: Optional[int] = None
    created_at: datetime = Field(default_factory=utcnow, nullable=False)


class GapReportRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    workspace_id: str = Field(default="default", index=True)
    use_case_id: int = Field(foreign_key="usecase.id")
    report_json: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow, nullable=False)


class GeneratedArtifact(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    workspace_id: str = Field(default="default", index=True)
    system_name: str
    language: str
    filename: str
    artifact_dir: str
    artifact_json: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow, nullable=False)


class ValidationRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    workspace_id: str = Field(default="default", index=True)
    artifact_id: Optional[int] = Field(default=None, foreign_key="generatedartifact.id")
    filename: str
    language: str
    status: str
    result_json: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow, nullable=False)


class UseCaseCreate(SQLModel):
    title: str
    description: str
    business_goal: str = ""
    target_systems: List[str] = Field(default_factory=list)
    data_flows: List[Dict[str, Any]] = Field(default_factory=list)
    frequency: str = "Monthly"
    criticality: str = "Medium"


class GapAnalysisRequest(SQLModel):
    business_goal: str
    title: str = "Ad hoc analysis"
    description: str = ""
    target_systems: List[str] = Field(default_factory=list)
    data_flows: List[Dict[str, Any]] = Field(default_factory=list)
    frequency: str = "Monthly"
    criticality: str = "Medium"


class ConnectorGenerationRequest(SQLModel):
    system_name: str
    category: str = "Other"
    auth_method: str = "Unknown"
    use_case_title: str = "Automation"
    language: str = "python"


class ValidationRequest(SQLModel):
    artifact_id: Optional[int] = None
    filename: Optional[str] = None
    language: str = "python"
    code: str = ""
    tests: str = ""
