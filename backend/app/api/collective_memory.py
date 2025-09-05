"""
API endpoints for collective memory and knowledge graph
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any

from app.models.n4l_memory import (
    N4LSearchRequest, N4LConsensusRequest, N4LStatement, 
    N4LGraph, CollectiveMemory, N4LRelationType
)
from app.services.collective_memory_service import collective_memory_service

router = APIRouter(prefix="/collective-memory", tags=["collective_memory"])


@router.post("/search", response_model=List[N4LStatement])
async def search_collective_knowledge(request: N4LSearchRequest):
    """
    Search the collective knowledge graph
    
    Query can include:
    - Text query for semantic search
    - Entity name to find related statements
    - Relation type filter (0-3)
    - Context domains filter
    - Minimum confidence threshold
    """
    try:
        results = await collective_memory_service.search_knowledge(request)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entity/{entity}", response_model=N4LGraph)
async def get_entity_knowledge_graph(
    entity: str,
    depth: int = Query(2, ge=1, le=5, description="Graph traversal depth")
):
    """
    Get the knowledge graph around a specific entity
    
    Returns all statements connected to the entity up to the specified depth.
    """
    try:
        graph = await collective_memory_service.get_entity_graph(entity, depth)
        return graph
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/consensus")
async def handle_statement_consensus(request: N4LConsensusRequest):
    """
    Handle consensus building for N4L statements
    
    Actions:
    - propose: Propose a new statement
    - validate: Validate an existing statement (increases confidence)
    - dispute: Dispute a statement (decreases confidence)
    """
    try:
        updated_statement = await collective_memory_service.handle_consensus(request)
        if not updated_statement:
            raise HTTPException(status_code=404, detail="Statement not found")
        return updated_statement
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_collective_memory_stats():
    """
    Get statistics about the collective knowledge graph
    
    Returns:
    - Total statements and memories
    - Unique entities and agents
    - Confidence distribution
    """
    try:
        stats = await collective_memory_service.get_collective_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/n4l")
async def export_knowledge_as_n4l(
    domain: Optional[str] = Query(None, description="Filter by domain")
):
    """
    Export the collective knowledge graph in N4L format
    
    Returns a text document in N4L syntax that can be imported
    into other N4L-compatible systems.
    """
    try:
        document = await collective_memory_service.export_n4l_document(domain)
        return {"content": document, "format": "n4l"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process-memory")
async def process_consolidated_memory(
    consolidated_content: str,
    agent_id: str,
    source_memory_ids: List[str] = [],
    llm_profile: Optional[str] = None
):
    """
    Manually process a consolidated memory into the collective knowledge
    
    This is usually called automatically during memory consolidation,
    but can be triggered manually for testing or reprocessing.
    """
    try:
        collective_memory = await collective_memory_service.process_consolidated_memory(
            consolidated_content=consolidated_content,
            agent_id=agent_id,
            source_memory_ids=source_memory_ids,
            llm_profile_name=llm_profile
        )
        
        if not collective_memory:
            raise HTTPException(status_code=500, detail="Failed to process memory")
        
        return {
            "success": True,
            "statements_created": len(collective_memory.n4l_statements),
            "entities_extracted": collective_memory.extracted_entities,
            "memory_id": collective_memory.id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/domains")
async def get_knowledge_domains():
    """
    Get all domains/contexts in the collective knowledge
    """
    try:
        from app.core.database import get_database
        db = get_database()
        
        # Get unique contexts from statements
        pipeline = [
            {"$unwind": "$contexts"},
            {"$group": {"_id": "$contexts"}},
            {"$sort": {"_id": 1}}
        ]
        
        cursor = db["n4l_statements"].aggregate(pipeline)
        domains = [doc["_id"] async for doc in cursor]
        
        return {"domains": domains}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/top-entities")
async def get_top_entities(limit: int = Query(20, ge=1, le=100)):
    """
    Get the most connected entities in the knowledge graph
    """
    try:
        from app.core.database import get_database
        db = get_database()
        
        # Count entity occurrences
        pipeline = [
            {
                "$facet": {
                    "subjects": [
                        {"$group": {"_id": "$subject", "count": {"$sum": 1}}},
                        {"$sort": {"count": -1}},
                        {"$limit": limit}
                    ],
                    "objects": [
                        {"$group": {"_id": "$object", "count": {"$sum": 1}}},
                        {"$sort": {"count": -1}},
                        {"$limit": limit}
                    ]
                }
            }
        ]
        
        result = await db["n4l_statements"].aggregate(pipeline).to_list(1)
        
        if result:
            # Merge and sort entities
            entity_counts = {}
            for item in result[0]["subjects"] + result[0]["objects"]:
                entity = item["_id"]
                if entity in entity_counts:
                    entity_counts[entity] += item["count"]
                else:
                    entity_counts[entity] = item["count"]
            
            top_entities = sorted(
                entity_counts.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:limit]
            
            return {
                "entities": [
                    {"name": name, "connection_count": count}
                    for name, count in top_entities
                ]
            }
        
        return {"entities": []}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recent-statements")
async def get_recent_statements(limit: int = Query(10, ge=1, le=50)):
    """
    Get the most recently added N4L statements
    """
    try:
        from app.core.database import get_database
        db = get_database()
        
        cursor = db["n4l_statements"].find().sort("created_at", -1).limit(limit)
        statements = []
        
        async for doc in cursor:
            doc.pop("_id", None)
            statements.append(N4LStatement(**doc))
        
        return statements
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test/text-to-n4l")
async def test_text_to_n4l(text: str):
    """
    Test endpoint: Convert plain text to N4L statements
    
    This is a simple test endpoint that takes any text and converts it
    to N4L format, showing the extraction and conversion process.
    """
    try:
        from app.services.n4l_converter import n4l_converter
        from app.services.llm_crud import llm_crud
        from app.services.settings_crud import settings_crud
        
        # Get LLM profile
        settings = await settings_crud.get_or_create()
        llm_profile = await llm_crud.get_by_name(settings.summary_llm_profile)
        
        if not llm_profile or not llm_profile.active:
            raise HTTPException(status_code=500, detail="No active LLM profile available")
        
        # Convert to N4L
        collective_memory = await n4l_converter.convert_to_n4l(
            consolidated_content=text,
            agent_id="test_endpoint",
            source_memory_ids=["test"],
            llm_profile=llm_profile
        )
        
        # Format response
        n4l_syntax_list = []
        for stmt in collective_memory.n4l_statements:
            n4l_syntax_list.append(stmt.to_n4l_syntax())
        
        return {
            "input_text": text,
            "extracted_entities": collective_memory.extracted_entities,
            "n4l_statements": [stmt.dict() for stmt in collective_memory.n4l_statements],
            "n4l_syntax": "\n\n".join(n4l_syntax_list),
            "statement_count": len(collective_memory.n4l_statements)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/world-model/view")
async def view_world_model():
    """
    View the current N4L world model file
    
    Returns the contents of the world_model.n4l file which contains
    all collective knowledge in N4L format.
    """
    try:
        import os
        filepath = "/data/world_model.n4l"
        
        if not os.path.exists(filepath):
            return {
                "content": "# UXMCP Collective World Model\n# No knowledge yet\n",
                "message": "World model file is empty or doesn't exist yet. It will be created when memories are consolidated.",
                "filepath": filepath
            }
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Get file stats
        file_stats = os.stat(filepath)
        
        return {
            "content": content,
            "filepath": filepath,
            "size_bytes": file_stats.st_size,
            "last_modified": datetime.fromtimestamp(file_stats.st_mtime).isoformat(),
            "statement_count": content.count("\n") - content.count("#") - content.count("::")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/world-model/download")
async def download_world_model():
    """
    Download the N4L world model file
    
    Returns the world_model.n4l file as a downloadable attachment.
    """
    from fastapi.responses import FileResponse
    import os
    
    filepath = "/data/world_model.n4l"
    
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="World model file not found")
    
    return FileResponse(
        path=filepath,
        media_type="text/plain",
        filename="world_model.n4l"
    )