"""
Settings API endpoints

Provides endpoints for managing global system settings including
conversation compaction and user context configuration.
"""

from fastapi import APIRouter, HTTPException
from typing import List

from app.models.settings import GlobalSettings, GlobalSettingsUpdate
from app.services.settings_crud import settings_crud
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/", response_model=GlobalSettings)
async def get_settings():
    """Get current global settings"""
    try:
        settings = await settings_crud.get_or_create()
        return settings
    except Exception as e:
        logger.error(f"Failed to get settings: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve settings")


@router.put("/", response_model=GlobalSettings)
async def update_settings(settings_update: GlobalSettingsUpdate):
    """Update global settings"""
    try:
        # Validate LLM profile if provided
        if settings_update.summary_llm_profile is not None:
            available_profiles = await settings_crud.get_text_only_llm_profiles()
            if settings_update.summary_llm_profile and settings_update.summary_llm_profile not in available_profiles:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Invalid summary LLM profile. Available text-only profiles: {', '.join(available_profiles)}"
                )
        
        # Validate service generation LLM profile if provided
        if settings_update.service_generation_llm_profile is not None:
            available_profiles = await settings_crud.get_all_llm_profiles()
            if settings_update.service_generation_llm_profile and settings_update.service_generation_llm_profile not in available_profiles:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Invalid service generation LLM profile. Available profiles: {', '.join(available_profiles)}"
                )
        
        updated_settings = await settings_crud.update(settings_update)
        if not updated_settings:
            raise HTTPException(status_code=404, detail="Settings not found")
        
        return updated_settings
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update settings: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update settings")


@router.get("/llm-profiles-text", response_model=List[str])
async def get_text_only_llm_profiles():
    """Get list of LLM profiles that support text-only mode for summarization"""
    try:
        profiles = await settings_crud.get_text_only_llm_profiles()
        return profiles
    except Exception as e:
        logger.error(f"Failed to get LLM profiles: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve LLM profiles")


@router.get("/llm-profiles-json", response_model=List[str])
async def get_json_llm_profiles():
    """Get list of LLM profiles that support JSON mode for service generation"""
    try:
        profiles = await settings_crud.get_all_llm_profiles()
        return profiles
    except Exception as e:
        logger.error(f"Failed to get JSON LLM profiles: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve JSON LLM profiles")


@router.post("/reset")
async def reset_settings():
    """Reset settings to default values"""
    try:
        # Delete current settings
        collection = settings_crud._get_collection()
        await collection.delete_one({"_id": settings_crud.settings_id})
        
        # Create default settings
        default_settings = await settings_crud.create_default()
        
        return {
            "message": "Settings reset to default values",
            "settings": default_settings
        }
    except Exception as e:
        logger.error(f"Failed to reset settings: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to reset settings")