from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId
from app.models.service import PyObjectId
from enum import Enum


class DocumentType(str, Enum):
    """Supported document types"""
    PDF = "pdf"
    TEXT = "text"
    MARKDOWN = "markdown"
    HTML = "html"
    JSON = "json"
    CSV = "csv"
    DOCX = "docx"
    XLSX = "xlsx"
    IMAGE = "image"
    OTHER = "other"


class DocumentCategory(str, Enum):
    """Document categories"""
    DOCUMENTATION = "documentation"
    CODE = "code"
    DATA = "data"
    REPORT = "report"
    PRESENTATION = "presentation"
    REFERENCE = "reference"
    MANUAL = "manual"
    OTHER = "other"


class DocumentBase(BaseModel):
    """Base model for documents"""
    name: str = Field(..., description="Document name")
    type: DocumentType = Field(..., description="Document type")
    description: Optional[str] = Field(None, description="Document description")
    workspace_id: str = Field(..., description="Workspace ID this document belongs to")
    category: DocumentCategory = Field(DocumentCategory.OTHER, description="Document category")
    tags: List[str] = Field(default=[], description="Tags for classification")
    content: Optional[str] = Field(None, description="Extracted text content")
    content_embedding: Optional[List[float]] = Field(None, description="Vector embedding for semantic search")
    blob_id: Optional[str] = Field(None, description="GridFS blob ID for original file")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    mime_type: Optional[str] = Field(None, description="MIME type of the document")
    metadata: Dict[str, Any] = Field(
        default={}, 
        description="Additional metadata (author, creation date, etc.)"
    )
    access_count: int = Field(default=0, description="Number of times accessed")
    last_accessed: Optional[datetime] = Field(None, description="Last access timestamp")
    is_public: bool = Field(default=False, description="Whether document is publicly accessible")
    chunk_ids: List[str] = Field(default=[], description="IDs of document chunks in vector store")


class DocumentCreate(BaseModel):
    """Model for creating a document (without file content)"""
    name: str
    type: DocumentType
    description: Optional[str] = None
    workspace_id: str
    category: DocumentCategory = DocumentCategory.OTHER
    tags: List[str] = []
    metadata: Dict[str, Any] = {}
    is_public: bool = False


class DocumentUpdate(BaseModel):
    """Model for updating document metadata"""
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[DocumentCategory] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    is_public: Optional[bool] = None


class DocumentInDB(DocumentBase):
    """Model for document stored in database"""
    id: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[str] = Field(None, description="User/agent who created the document")
    updated_by: Optional[str] = Field(None, description="User/agent who last updated the document")

    model_config = {
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str}
    }


class Document(DocumentInDB):
    """Complete document model"""
    pass


class DocumentSearch(BaseModel):
    """Model for document search request"""
    query: str = Field(..., description="Search query")
    workspace_ids: Optional[List[str]] = Field(None, description="Filter by workspace IDs")
    categories: Optional[List[DocumentCategory]] = Field(None, description="Filter by categories")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    types: Optional[List[DocumentType]] = Field(None, description="Filter by document types")
    date_from: Optional[datetime] = Field(None, description="Filter documents created after this date")
    date_to: Optional[datetime] = Field(None, description="Filter documents created before this date")
    use_semantic: bool = Field(True, description="Use semantic search with embeddings")
    limit: int = Field(10, ge=1, le=100, description="Maximum number of results")


class DocumentSearchResult(BaseModel):
    """Result from document search"""
    document: Document
    score: float = Field(..., description="Relevance score (0-1)")
    excerpt: Optional[str] = Field(None, description="Relevant excerpt from document")
    highlights: List[str] = Field(default=[], description="Highlighted matching sections")


class DocumentChunk(BaseModel):
    """Model for document chunks stored in vector database"""
    document_id: str
    chunk_index: int
    content: str
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = {}