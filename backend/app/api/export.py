"""
API endpoints for exporting UXMCP data
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from typing import Dict, Any
import os
import json
from datetime import datetime
from app.services.export_service import export_service

router = APIRouter()


@router.get("/llm-profiles")
async def export_llm_profiles():
    """
    Export all LLM profiles to JSON format
    Returns the JSON data directly
    """
    try:
        data = await export_service.export_llm_profiles()
        return JSONResponse(content=data, media_type="application/json")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export LLM profiles: {str(e)}")


@router.get("/services")
async def export_services():
    """
    Export all services/tools to JSON format
    Returns the JSON data directly
    """
    try:
        data = await export_service.export_services()
        return JSONResponse(content=data, media_type="application/json")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export services: {str(e)}")


@router.get("/agents")
async def export_agents():
    """
    Export all agents to JSON format
    Returns the JSON data directly
    """
    try:
        data = await export_service.export_agents()
        return JSONResponse(content=data, media_type="application/json")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export agents: {str(e)}")


@router.get("/all")
async def export_all():
    """
    Export all data (LLM profiles, services, and agents) in a single JSON structure
    Returns the JSON data directly
    """
    try:
        data = await export_service.export_all()
        return JSONResponse(content=data, media_type="application/json")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export all data: {str(e)}")


@router.get("/download/llm-profiles")
async def download_llm_profiles():
    """
    Export LLM profiles and download as JSON file
    """
    try:
        data = await export_service.export_llm_profiles()
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"llm_profiles_{timestamp}.json"
        filepath = f"/tmp/{filename}"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return FileResponse(
            path=filepath,
            media_type="application/json",
            filename=filename,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download LLM profiles: {str(e)}")


@router.get("/download/services")
async def download_services():
    """
    Export services and download as JSON file
    """
    try:
        data = await export_service.export_services()
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"services_{timestamp}.json"
        filepath = f"/tmp/{filename}"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return FileResponse(
            path=filepath,
            media_type="application/json",
            filename=filename,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download services: {str(e)}")


@router.get("/download/agents")
async def download_agents():
    """
    Export agents and download as JSON file
    """
    try:
        data = await export_service.export_agents()
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"agents_{timestamp}.json"
        filepath = f"/tmp/{filename}"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return FileResponse(
            path=filepath,
            media_type="application/json",
            filename=filename,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download agents: {str(e)}")


@router.get("/download/all")
async def download_all():
    """
    Export all data and download as JSON file
    """
    try:
        data = await export_service.export_all()
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"uxmcp_complete_{timestamp}.json"
        filepath = f"/tmp/{filename}"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return FileResponse(
            path=filepath,
            media_type="application/json",
            filename=filename,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download complete export: {str(e)}")


@router.post("/save-all")
async def save_all_exports():
    """
    Save all exports to separate JSON files on the server
    Returns the file paths created
    """
    try:
        files_created = await export_service.save_exports_to_files("/tmp")
        return {
            "success": True,
            "message": "All exports saved successfully",
            "files": files_created
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save exports: {str(e)}")