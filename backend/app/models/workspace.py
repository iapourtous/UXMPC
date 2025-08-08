from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId
from app.models.service import PyObjectId


class WorkspaceBase(BaseModel):
    """Base model for document workspaces"""
    name: str = Field(..., description="Workspace name")
    description: Optional[str] = Field(None, description="Workspace description")
    owner_id: Optional[str] = Field(None, description="Owner user/agent ID")
    agent_ids: List[str] = Field(default=[], description="List of agent IDs with access")
    is_public: bool = Field(default=False, description="Whether workspace is publicly accessible")
    settings: Dict[str, Any] = Field(
        default={
            "max_file_size": 52428800,  # 50MB default
            "allowed_types": [],  # Empty means all types allowed
            "auto_extract": True,  # Auto-extract content from uploads
            "auto_embed": True,  # Auto-generate embeddings
            "retention_days": None,  # None means no auto-deletion
        },
        description="Workspace-specific settings"
    )
    metadata: Dict[str, Any] = Field(default={}, description="Additional metadata")
    document_count: int = Field(default=0, description="Number of documents in workspace")
    total_size: int = Field(default=0, description="Total size of all documents in bytes")


class WorkspaceCreate(BaseModel):
    """Model for creating a workspace"""
    name: str
    description: Optional[str] = None
    owner_id: Optional[str] = None
    agent_ids: List[str] = []
    is_public: bool = False
    settings: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = {}


class WorkspaceUpdate(BaseModel):
    """Model for updating a workspace"""
    name: Optional[str] = None
    description: Optional[str] = None
    agent_ids: Optional[List[str]] = None
    is_public: Optional[bool] = None
    settings: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class WorkspaceInDB(WorkspaceBase):
    """Model for workspace stored in database"""
    id: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str}
    }


class Workspace(WorkspaceInDB):
    """Complete workspace model"""
    pass


class WorkspaceStats(BaseModel):
    """Statistics for a workspace"""
    workspace_id: str
    document_count: int
    total_size: int
    document_types: Dict[str, int]
    categories: Dict[str, int]
    recent_uploads: List[Dict[str, Any]]
    most_accessed: List[Dict[str, Any]]
    agent_access: List[Dict[str, Any]]