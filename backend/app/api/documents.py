"""
Documents API endpoints
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query, Depends
from fastapi.responses import StreamingResponse
from typing import List, Optional
import io
import logging

from app.models.document import (
    Document, DocumentCreate, DocumentUpdate, 
    DocumentSearch, DocumentSearchResult, DocumentType, DocumentCategory
)
from app.services.document_crud import document_crud

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])

# Initialize document extractor - import here to avoid circular imports
def get_extractor():
    from app.services.document_extractor import DocumentExtractor
    return DocumentExtractor()


@router.post("/", response_model=Document)
async def create_document(
    name: str = Form(...),
    type: DocumentType = Form(...),
    workspace_id: str = Form(...),
    description: Optional[str] = Form(None),
    category: DocumentCategory = Form(DocumentCategory.OTHER),
    tags: Optional[str] = Form(None),  # Comma-separated tags
    is_public: bool = Form(False),
    file: Optional[UploadFile] = File(None)
):
    """Create a new document with optional file upload"""
    try:
        # Parse tags
        tag_list = [tag.strip() for tag in tags.split(",")] if tags else []
        
        # Create document object
        document_data = DocumentCreate(
            name=name,
            type=type,
            workspace_id=workspace_id,
            description=description,
            category=category,
            tags=tag_list,
            is_public=is_public
        )
        
        # Handle file upload
        file_content = None
        mime_type = None
        if file:
            file_content = await file.read()
            mime_type = file.content_type
            
            # Reset file for potential re-reading
            await file.seek(0)
        
        # Create document
        document = await document_crud.create(
            document=document_data,
            file_content=file_content,
            file_name=file.filename if file else None,
            mime_type=mime_type
        )
        
        # Extract content asynchronously if file provided
        if file_content and document:
            try:
                # Extract content based on type
                extractor = get_extractor()
                content = await extractor.extract_content(
                    file_content=file_content,
                    document_type=type,
                    mime_type=mime_type
                )
                
                if content:
                    # Add content and generate embeddings
                    await document_crud.add_content_and_embeddings(
                        document_id=document.id,
                        content=content
                    )
            except Exception as e:
                logger.error(f"Error extracting content: {e}")
        
        return document
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating document: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/", response_model=List[Document])
async def list_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    workspace_id: Optional[str] = None,
    category: Optional[DocumentCategory] = None,
    tags: Optional[str] = None,  # Comma-separated tags
    type: Optional[DocumentType] = None
):
    """List documents with optional filters"""
    try:
        # Parse tags
        tag_list = [tag.strip() for tag in tags.split(",")] if tags else None
        
        documents = await document_crud.list(
            skip=skip,
            limit=limit,
            workspace_id=workspace_id,
            category=category.value if category else None,
            tags=tag_list,
            document_type=type.value if type else None
        )
        return documents
    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{document_id}", response_model=Document)
async def get_document(document_id: str):
    """Get a specific document"""
    document = await document_crud.get(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.get("/{document_id}/download")
async def download_document(document_id: str):
    """Download the original file of a document"""
    try:
        # Get document
        document = await document_crud.get(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        if not document.blob_id:
            raise HTTPException(status_code=404, detail="Document has no file content")
        
        # Get file content
        content = await document_crud.get_file_content(document_id)
        if not content:
            raise HTTPException(status_code=404, detail="File content not found")
        
        # Return file
        return StreamingResponse(
            io.BytesIO(content),
            media_type=document.mime_type or "application/octet-stream",
            headers={
                "Content-Disposition": f"attachment; filename={document.name}"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading document: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{document_id}", response_model=Document)
async def update_document(
    document_id: str,
    update: DocumentUpdate
):
    """Update document metadata"""
    try:
        document = await document_crud.update(document_id, update)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        return document
    except Exception as e:
        logger.error(f"Error updating document: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{document_id}")
async def delete_document(document_id: str):
    """Delete a document and its file content"""
    try:
        success = await document_crud.delete(document_id)
        if not success:
            raise HTTPException(status_code=404, detail="Document not found")
        return {"message": "Document deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/search", response_model=List[DocumentSearchResult])
async def search_documents(search: DocumentSearch):
    """Search documents with semantic search support"""
    try:
        results = await document_crud.search(search)
        return results
    except Exception as e:
        logger.error(f"Error searching documents: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{document_id}/extract")
async def extract_content(document_id: str):
    """Extract and index content from a document"""
    try:
        # Get document
        document = await document_crud.get(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        if not document.blob_id:
            raise HTTPException(status_code=400, detail="Document has no file content")
        
        # Get file content
        file_content = await document_crud.get_file_content(document_id)
        if not file_content:
            raise HTTPException(status_code=404, detail="File content not found")
        
        # Extract content
        extractor = get_extractor()
        content = await extractor.extract_content(
            file_content=file_content,
            document_type=document.type,
            mime_type=document.mime_type
        )
        
        if not content:
            raise HTTPException(status_code=400, detail="Could not extract content from document")
        
        # Add content and generate embeddings
        success = await document_crud.add_content_and_embeddings(
            document_id=document_id,
            content=content
        )
        
        if success:
            return {
                "message": "Content extracted and indexed successfully",
                "content_length": len(content),
                "preview": content[:500] if content else ""
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to index content")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error extracting content: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{document_id}/content")
async def get_document_content(document_id: str):
    """Get the extracted text content of a document"""
    try:
        document = await document_crud.get(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        if not document.content:
            # Try to extract if not already done
            if document.blob_id:
                file_content = await document_crud.get_file_content(document_id)
                if file_content:
                    extractor = get_extractor()
                    content = await extractor.extract_content(
                        file_content=file_content,
                        document_type=document.type,
                        mime_type=document.mime_type
                    )
                    
                    if content:
                        await document_crud.add_content_and_embeddings(
                            document_id=document_id,
                            content=content
                        )
                        return {"content": content}
            
            return {"content": "", "message": "No content available"}
        
        return {"content": document.content}
        
    except Exception as e:
        logger.error(f"Error getting document content: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")