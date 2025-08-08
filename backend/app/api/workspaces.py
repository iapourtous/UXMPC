"""
Workspaces API endpoints
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import logging

from app.models.workspace import (
    Workspace, WorkspaceCreate, WorkspaceUpdate, WorkspaceStats
)
from app.services.workspace_crud import workspace_crud

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.post("/", response_model=Workspace)
async def create_workspace(workspace: WorkspaceCreate):
    """Create a new workspace"""
    try:
        return await workspace_crud.create(workspace)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating workspace: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/", response_model=List[Workspace])
async def list_workspaces(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    agent_id: Optional[str] = None,
    is_public: Optional[bool] = None
):
    """List workspaces with optional filters"""
    try:
        workspaces = await workspace_crud.list(
            skip=skip,
            limit=limit,
            agent_id=agent_id,
            is_public=is_public
        )
        return workspaces
    except Exception as e:
        logger.error(f"Error listing workspaces: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{workspace_id}", response_model=Workspace)
async def get_workspace(workspace_id: str):
    """Get a specific workspace"""
    workspace = await workspace_crud.get(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


@router.get("/by-name/{name}", response_model=Workspace)
async def get_workspace_by_name(name: str):
    """Get a workspace by name"""
    workspace = await workspace_crud.get_by_name(name)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


@router.put("/{workspace_id}", response_model=Workspace)
async def update_workspace(
    workspace_id: str,
    update: WorkspaceUpdate
):
    """Update a workspace"""
    try:
        workspace = await workspace_crud.update(workspace_id, update)
        if not workspace:
            raise HTTPException(status_code=404, detail="Workspace not found")
        return workspace
    except Exception as e:
        logger.error(f"Error updating workspace: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{workspace_id}")
async def delete_workspace(workspace_id: str):
    """Delete a workspace"""
    try:
        success = await workspace_crud.delete(workspace_id)
        if not success:
            raise HTTPException(status_code=404, detail="Workspace not found")
        return {"message": "Workspace deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting workspace: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{workspace_id}/agents/{agent_id}")
async def add_agent_access(workspace_id: str, agent_id: str):
    """Add an agent to workspace access list"""
    try:
        success = await workspace_crud.add_agent_access(workspace_id, agent_id)
        if not success:
            raise HTTPException(status_code=404, detail="Workspace not found")
        return {"message": f"Agent {agent_id} added to workspace {workspace_id}"}
    except Exception as e:
        logger.error(f"Error adding agent access: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{workspace_id}/agents/{agent_id}")
async def remove_agent_access(workspace_id: str, agent_id: str):
    """Remove an agent from workspace access list"""
    try:
        success = await workspace_crud.remove_agent_access(workspace_id, agent_id)
        if not success:
            raise HTTPException(status_code=404, detail="Workspace not found")
        return {"message": f"Agent {agent_id} removed from workspace {workspace_id}"}
    except Exception as e:
        logger.error(f"Error removing agent access: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{workspace_id}/stats", response_model=WorkspaceStats)
async def get_workspace_stats(workspace_id: str):
    """Get detailed statistics for a workspace"""
    try:
        stats = await workspace_crud.get_stats(workspace_id)
        if not stats:
            raise HTTPException(status_code=404, detail="Workspace not found")
        return stats
    except Exception as e:
        logger.error(f"Error getting workspace stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")