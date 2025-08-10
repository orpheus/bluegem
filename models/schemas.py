"""
Pydantic schemas for data validation and serialization
Following patterns from agent/therma_pydantic.py
"""

from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator, HttpUrl
import re
from uuid import uuid4


class ProjectStatus(str, Enum):
    """Project lifecycle states"""
    DRAFT = "draft"
    ACTIVE = "active"
    REVIEW = "review"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ConfidenceLevel(str, Enum):
    """Confidence levels for quality scoring"""
    HIGH = "high"        # 0.8+
    MEDIUM = "medium"    # 0.6-0.8
    LOW = "low"         # 0.4-0.6
    CRITICAL = "critical"  # <0.4


class IntentAction(str, Enum):
    """Possible user intent actions"""
    CREATE_PROJECT = "create_project"
    ADD_PRODUCTS = "add_products"
    UPDATE_PRODUCT = "update_product"
    DELETE_PRODUCT = "delete_product"
    GENERATE_SPECBOOK = "generate_specbook"
    LIST_PROJECTS = "list_projects"
    LIST_PRODUCTS = "list_products"
    SEARCH_PRODUCTS = "search_products"
    VERIFY_PRODUCT = "verify_product"
    UNKNOWN = "unknown"


class ExportFormat(str, Enum):
    """Supported export formats"""
    CSV = "csv"
    PDF = "pdf"
    EXCEL = "excel"
    JSON = "json"


class Project(BaseModel):
    """Project model for architectural projects"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(..., min_length=1, max_length=200)
    status: ProjectStatus = Field(default=ProjectStatus.DRAFT)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    archived_at: Optional[datetime] = None
    
    @field_validator('name')
    def validate_name(cls, v):
        """Ensure project name is valid"""
        if not re.match(r'^[\w\s\-\.]+$', v):
            raise ValueError('Project name contains invalid characters')
        return v.strip()
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class Product(BaseModel):
    """Product model matching existing extraction format"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    url: HttpUrl
    image_url: Optional[HttpUrl] = None
    type: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    model_no: Optional[str] = None
    qty: int = Field(default=1, ge=1)
    key: Optional[str] = None  # Revit key
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    verified: bool = Field(default=False)
    last_checked: Optional[datetime] = None
    extraction_metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    @field_validator('type')
    def normalize_type(cls, v):
        """Normalize product type"""
        return v.strip().title()
    
    @property
    def confidence_level(self) -> ConfidenceLevel:
        """Get confidence level based on score"""
        if self.confidence_score >= 0.8:
            return ConfidenceLevel.HIGH
        elif self.confidence_score >= 0.6:
            return ConfidenceLevel.MEDIUM
        elif self.confidence_score >= 0.4:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.CRITICAL


class Intent(BaseModel):
    """Parsed user intent from natural language"""
    action: IntentAction
    confidence: float = Field(ge=0.0, le=1.0)
    entities: Dict[str, Any] = Field(default_factory=dict)
    raw_text: str
    
    @property
    def project_name(self) -> Optional[str]:
        """Extract project name from entities"""
        return self.entities.get("project")
    
    @property
    def urls(self) -> List[str]:
        """Extract URLs from entities"""
        return self.entities.get("urls", [])
    
    @property
    def product_id(self) -> Optional[str]:
        """Extract product ID from entities"""
        return self.entities.get("product_id")


class Context(BaseModel):
    """Conversation context for maintaining state"""
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    active_project_id: Optional[str] = None
    active_project_name: Optional[str] = None
    conversation_history: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    last_activity: datetime = Field(default_factory=datetime.now)
    
    def add_message(self, role: str, content: str):
        """Add message to conversation history"""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        self.last_activity = datetime.now()


class QualityScore(BaseModel):
    """Quality assessment result"""
    overall_score: float = Field(ge=0.0, le=1.0)
    completeness_score: float = Field(ge=0.0, le=1.0)
    accuracy_score: float = Field(ge=0.0, le=1.0)
    missing_fields: List[str] = Field(default_factory=list)
    issues: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    
    @property
    def needs_review(self) -> bool:
        """Check if manual review is needed"""
        return self.overall_score < 0.8 or len(self.issues) > 0


class Change(BaseModel):
    """Detected change in product data"""
    field: str
    old_value: Any
    new_value: Any
    change_type: str  # "added", "removed", "modified"
    detected_at: datetime = Field(default_factory=datetime.now)


class VerificationRequest(BaseModel):
    """Request for manual verification"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    product_id: str
    project_id: str
    reason: str
    priority: int = Field(default=5, ge=1, le=10)
    created_at: datetime = Field(default_factory=datetime.now)
    reviewed_at: Optional[datetime] = None
    reviewer: Optional[str] = None
    corrections: Dict[str, Any] = Field(default_factory=dict)


class SpecbookExport(BaseModel):
    """Specbook export configuration"""
    project_id: str
    format: ExportFormat
    include_images: bool = Field(default=True)
    include_unverified: bool = Field(default=False)
    filters: Dict[str, Any] = Field(default_factory=dict)
    template: str = Field(default="default")
    
    @field_validator('template')
    def validate_template(cls, v):
        """Ensure template exists"""
        valid_templates = ["default", "revit", "minimal", "detailed"]
        if v not in valid_templates:
            raise ValueError(f"Template must be one of {valid_templates}")
        return v


class TaskResult(BaseModel):
    """Result from async task execution"""
    task_id: str = Field(default_factory=lambda: str(uuid4()))
    status: str  # "pending", "running", "completed", "failed"
    result: Optional[Any] = None
    error: Optional[str] = None
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    @property
    def duration(self) -> Optional[float]:
        """Calculate task duration in seconds"""
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None