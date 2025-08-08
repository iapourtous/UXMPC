"""
Document CRUD Service

This module provides CRUD operations for documents with GridFS storage
and vector embeddings support.
"""

from typing import List, Optional, Dict, Any, BinaryIO
from datetime import datetime
from bson import ObjectId
import logging
import hashlib
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
import io

from app.models.document import (
    Document, DocumentCreate, DocumentUpdate, DocumentSearch,
    DocumentSearchResult, DocumentType, DocumentChunk
)
from app.models.workspace import Workspace
from app.core.database import get_database
from app.core.memory_config import get_vector_store
from app.services.workspace_crud import workspace_crud

logger = logging.getLogger(__name__)


class DocumentCRUD:
    """CRUD operations for documents"""
    
    def __init__(self):
        self.collection_name = "documents"
        self.vector_store = get_vector_store()
    
    async def create(
        self, 
        document: DocumentCreate,
        file_content: Optional[bytes] = None,
        file_name: Optional[str] = None,
        mime_type: Optional[str] = None,
        created_by: Optional[str] = None
    ) -> Document:
        """Create a new document with optional file upload"""
        db = get_database()
        
        # Verify workspace exists
        workspace = await workspace_crud.get(document.workspace_id)
        if not workspace:
            raise ValueError(f"Workspace {document.workspace_id} not found")
        
        # Check workspace settings
        settings = workspace.settings or {}
        max_file_size = settings.get("max_file_size", 52428800)  # 50MB default
        
        # Create document record
        document_dict = document.dict()
        document_dict["created_at"] = datetime.utcnow()
        document_dict["updated_at"] = datetime.utcnow()
        document_dict["created_by"] = created_by
        document_dict["access_count"] = 0
        document_dict["chunk_ids"] = []
        
        # Handle file upload if provided
        if file_content:
            file_size = len(file_content)
            if file_size > max_file_size:
                raise ValueError(f"File size {file_size} exceeds maximum {max_file_size}")
            
            # Store file in GridFS
            fs = AsyncIOMotorGridFSBucket(db)
            
            # Create file metadata
            file_metadata = {
                "document_name": document.name,
                "workspace_id": document.workspace_id,
                "mime_type": mime_type or "application/octet-stream",
                "original_name": file_name or document.name,
                "upload_date": datetime.utcnow()
            }
            
            # Upload to GridFS
            file_stream = io.BytesIO(file_content)
            grid_id = await fs.upload_from_stream(
                file_name or document.name,
                file_stream,
                metadata=file_metadata
            )
            
            document_dict["blob_id"] = str(grid_id)
            document_dict["file_size"] = file_size
            document_dict["mime_type"] = mime_type
            
            logger.info(f"Uploaded file to GridFS: {grid_id}")
        
        # Insert document into database
        result = await db[self.collection_name].insert_one(document_dict)
        document_dict["id"] = str(result.inserted_id)
        document_dict.pop("_id", None)
        
        # Update workspace stats
        await workspace_crud.update_stats(
            document.workspace_id, 
            document_delta=1,
            size_delta=document_dict.get("file_size", 0)
        )
        
        logger.info(f"Created document: {document.name} with ID: {document_dict['id']}")
        return Document(**document_dict)
    
    async def get(self, document_id: str) -> Optional[Document]:
        """Get a document by ID"""
        db = get_database()
        
        try:
            obj_id = ObjectId(document_id)
            document = await db[self.collection_name].find_one({"_id": obj_id})
        except:
            document = await db[self.collection_name].find_one({"id": document_id})
        
        if document:
            document["id"] = str(document.pop("_id", document_id))
            
            # Update access count and timestamp
            await db[self.collection_name].update_one(
                {"_id": ObjectId(document["id"])},
                {
                    "$inc": {"access_count": 1},
                    "$set": {"last_accessed": datetime.utcnow()}
                }
            )
            
            return Document(**document)
        return None
    
    async def get_file_content(self, document_id: str) -> Optional[bytes]:
        """Get the file content from GridFS"""
        db = get_database()
        document = await self.get(document_id)
        
        if not document or not document.blob_id:
            return None
        
        fs = AsyncIOMotorGridFSBucket(db)
        
        try:
            grid_id = ObjectId(document.blob_id)
            stream = await fs.open_download_stream(grid_id)
            content = await stream.read()
            return content
        except Exception as e:
            logger.error(f"Error downloading file from GridFS: {e}")
            return None
    
    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        workspace_id: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        document_type: Optional[str] = None
    ) -> List[Document]:
        """List documents with filters"""
        db = get_database()
        
        # Build filter
        filter_dict = {}
        if workspace_id:
            filter_dict["workspace_id"] = workspace_id
        if category:
            filter_dict["category"] = category
        if tags:
            filter_dict["tags"] = {"$in": tags}
        if document_type:
            filter_dict["type"] = document_type
        
        cursor = db[self.collection_name].find(filter_dict).skip(skip).limit(limit)
        documents = []
        
        async for document in cursor:
            document["id"] = str(document.pop("_id"))
            documents.append(Document(**document))
        
        return documents
    
    async def update(
        self, 
        document_id: str, 
        update: DocumentUpdate,
        updated_by: Optional[str] = None
    ) -> Optional[Document]:
        """Update document metadata"""
        db = get_database()
        
        # Get existing document
        existing = await self.get(document_id)
        if not existing:
            return None
        
        # Prepare update data
        update_dict = {k: v for k, v in update.dict().items() if v is not None}
        if update_dict:
            update_dict["updated_at"] = datetime.utcnow()
            if updated_by:
                update_dict["updated_by"] = updated_by
            
            # Update in database
            try:
                obj_id = ObjectId(document_id)
                await db[self.collection_name].update_one(
                    {"_id": obj_id},
                    {"$set": update_dict}
                )
            except:
                await db[self.collection_name].update_one(
                    {"id": document_id},
                    {"$set": update_dict}
                )
            
            logger.info(f"Updated document: {document_id}")
        
        return await self.get(document_id)
    
    async def delete(self, document_id: str) -> bool:
        """Delete a document and its file content"""
        db = get_database()
        
        # Get document
        document = await self.get(document_id)
        if not document:
            return False
        
        # Delete file from GridFS if exists
        if document.blob_id:
            fs = AsyncIOMotorGridFSBucket(db)
            try:
                await fs.delete(ObjectId(document.blob_id))
                logger.info(f"Deleted file from GridFS: {document.blob_id}")
            except Exception as e:
                logger.error(f"Error deleting file from GridFS: {e}")
        
        # Delete vector embeddings if exist
        if document.chunk_ids:
            for chunk_id in document.chunk_ids:
                try:
                    self.vector_store.delete_memory(
                        agent_id=f"doc_{document.workspace_id}",
                        memory_id=chunk_id
                    )
                except Exception as e:
                    logger.error(f"Error deleting chunk {chunk_id}: {e}")
        
        # Delete document
        try:
            obj_id = ObjectId(document_id)
            result = await db[self.collection_name].delete_one({"_id": obj_id})
        except:
            result = await db[self.collection_name].delete_one({"id": document_id})
        
        if result.deleted_count > 0:
            # Update workspace stats
            await workspace_crud.update_stats(
                document.workspace_id,
                document_delta=-1,
                size_delta=-document.file_size if document.file_size else 0
            )
            
            logger.info(f"Deleted document: {document_id}")
            return True
        
        return False
    
    async def search(
        self,
        search: DocumentSearch
    ) -> List[DocumentSearchResult]:
        """Search documents with semantic search support"""
        db = get_database()
        
        # Build base filter
        filter_dict = {}
        if search.workspace_ids:
            filter_dict["workspace_id"] = {"$in": search.workspace_ids}
        if search.categories:
            filter_dict["category"] = {"$in": [c.value for c in search.categories]}
        if search.tags:
            filter_dict["tags"] = {"$in": search.tags}
        if search.types:
            filter_dict["type"] = {"$in": [t.value for t in search.types]}
        if search.date_from:
            filter_dict["created_at"] = {"$gte": search.date_from}
        if search.date_to:
            if "created_at" in filter_dict:
                filter_dict["created_at"]["$lte"] = search.date_to
            else:
                filter_dict["created_at"] = {"$lte": search.date_to}
        
        results = []
        
        if search.use_semantic and search.query:
            # Semantic search using vector store
            workspace_ids = search.workspace_ids or []
            
            # Search in vector store for each workspace
            for workspace_id in workspace_ids:
                try:
                    vector_results = self.vector_store.search_memories(
                        agent_id=f"doc_{workspace_id}",
                        query=search.query,
                        k=search.limit
                    )
                    
                    # Get corresponding documents
                    for vr in vector_results:
                        doc_id = vr.get("metadata", {}).get("document_id")
                        if doc_id:
                            doc = await self.get(doc_id)
                            if doc:
                                results.append(DocumentSearchResult(
                                    document=doc,
                                    score=vr.get("score", 0.0),
                                    excerpt=vr.get("content", "")[:200],
                                    highlights=[vr.get("content", "")[:100]]
                                ))
                except Exception as e:
                    logger.error(f"Error in semantic search: {e}")
        
        # Fallback to text search if no semantic results or semantic disabled
        if not results or not search.use_semantic:
            # Text search in MongoDB
            if search.query:
                filter_dict["$or"] = [
                    {"name": {"$regex": search.query, "$options": "i"}},
                    {"description": {"$regex": search.query, "$options": "i"}},
                    {"content": {"$regex": search.query, "$options": "i"}},
                    {"tags": {"$regex": search.query, "$options": "i"}}
                ]
            
            cursor = db[self.collection_name].find(filter_dict).limit(search.limit)
            
            async for doc in cursor:
                doc["id"] = str(doc.pop("_id"))
                document = Document(**doc)
                
                # Calculate simple relevance score based on matches
                score = 0.5  # Base score for match
                if search.query:
                    query_lower = search.query.lower()
                    if query_lower in document.name.lower():
                        score += 0.3
                    if document.description and query_lower in document.description.lower():
                        score += 0.2
                
                results.append(DocumentSearchResult(
                    document=document,
                    score=min(score, 1.0),
                    excerpt=document.description[:200] if document.description else "",
                    highlights=[]
                ))
        
        # Sort by score
        results.sort(key=lambda x: x.score, reverse=True)
        
        return results[:search.limit]
    
    async def add_content_and_embeddings(
        self,
        document_id: str,
        content: str,
        chunks: Optional[List[str]] = None
    ) -> bool:
        """Add extracted content and generate embeddings"""
        db = get_database()
        
        # Get document
        document = await self.get(document_id)
        if not document:
            return False
        
        # Update content
        await db[self.collection_name].update_one(
            {"_id": ObjectId(document_id)},
            {
                "$set": {
                    "content": content,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        # Generate chunks if not provided
        if not chunks:
            # Simple chunking by paragraphs or fixed size
            max_chunk_size = 1000
            chunks = []
            
            if len(content) <= max_chunk_size:
                chunks = [content]
            else:
                # Split by paragraphs first
                paragraphs = content.split('\n\n')
                current_chunk = ""
                
                for para in paragraphs:
                    if len(current_chunk) + len(para) <= max_chunk_size:
                        current_chunk += para + "\n\n"
                    else:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = para + "\n\n"
                
                if current_chunk:
                    chunks.append(current_chunk.strip())
        
        # Store chunks in vector store
        chunk_ids = []
        collection_name = f"doc_{document.workspace_id}"
        
        for i, chunk in enumerate(chunks):
            chunk_id = f"{document_id}_chunk_{i}"
            
            # Add to vector store
            self.vector_store.add_memory(
                agent_id=collection_name,
                memory_id=chunk_id,
                content=chunk,
                metadata={
                    "document_id": document_id,
                    "document_name": document.name,
                    "chunk_index": i,
                    "workspace_id": document.workspace_id,
                    "category": document.category,
                    "type": document.type
                }
            )
            
            chunk_ids.append(chunk_id)
        
        # Update document with chunk IDs
        await db[self.collection_name].update_one(
            {"_id": ObjectId(document_id)},
            {
                "$set": {
                    "chunk_ids": chunk_ids,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        logger.info(f"Added {len(chunks)} chunks for document {document_id}")
        return True


# Singleton instance
document_crud = DocumentCRUD()