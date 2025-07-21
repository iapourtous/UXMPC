"""
Demo API endpoints

Endpoints for managing and serving interactive HTML/CSS/JS demos
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from typing import List, Optional
import logging

from app.models.demo import Demo, DemoCreate, DemoUpdate, DemoList
from app.services.demo_crud import demo_crud

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/", response_model=Demo)
async def create_demo(demo: DemoCreate):
    """Create a new demo"""
    try:
        logger.info(f"Creating demo with data: {demo.dict()}")
        created_demo = await demo_crud.create(demo)
        return created_demo
    except ValueError as e:
        logger.error(f"Validation error creating demo: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating demo: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create demo")


@router.get("/", response_model=DemoList)
async def list_demos(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None
):
    """List all demos with optional search"""
    try:
        if search:
            demos = await demo_crud.search(search, skip, limit)
        else:
            demos = await demo_crud.list(skip, limit)
        
        total = await demo_crud.count()
        
        return DemoList(
            demos=demos,
            total=total,
            page=(skip // limit) + 1,
            per_page=limit
        )
    except Exception as e:
        logger.error(f"Error listing demos: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list demos")


@router.get("/{name}", response_class=HTMLResponse)
async def serve_demo(name: str):
    """Serve the HTML content of a demo by name"""
    try:
        demo = await demo_crud.get_by_name(name)
        if not demo:
            raise HTTPException(status_code=404, detail=f"Demo '{name}' not found")
        
        # Return the HTML content directly
        return HTMLResponse(content=demo.html_content)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving demo {name}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to serve demo")


@router.get("/details/{demo_id}", response_model=Demo)
async def get_demo_details(demo_id: str):
    """Get demo details by ID"""
    try:
        demo = await demo_crud.get(demo_id)
        if not demo:
            raise HTTPException(status_code=404, detail="Demo not found")
        return demo
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting demo details: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get demo details")


@router.put("/{demo_id}", response_model=Demo)
async def update_demo(demo_id: str, demo_update: DemoUpdate):
    """Update a demo's metadata"""
    try:
        updated_demo = await demo_crud.update(demo_id, demo_update)
        if not updated_demo:
            raise HTTPException(status_code=404, detail="Demo not found")
        return updated_demo
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating demo: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update demo")


@router.delete("/{demo_id}")
async def delete_demo(demo_id: str):
    """Delete a demo"""
    try:
        success = await demo_crud.delete(demo_id)
        if not success:
            raise HTTPException(status_code=404, detail="Demo not found")
        return {"message": "Demo deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting demo: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete demo")