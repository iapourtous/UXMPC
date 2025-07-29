"""
Settings CRUD operations

Handles database operations for global settings with singleton pattern
to ensure only one settings document exists.
"""

from typing import Optional
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError
from bson import ObjectId

from app.models.settings import (
    GlobalSettings, GlobalSettingsCreate, 
    GlobalSettingsUpdate, GlobalSettingsInDB
)
from app.core.database import get_database
import logging

logger = logging.getLogger(__name__)


class SettingsCRUD:
    """CRUD operations for global settings"""
    
    def __init__(self):
        self.db: Optional[AsyncIOMotorDatabase] = None
        self.collection_name = "global_settings"
        self.settings_id = "global_settings_singleton"  # Fixed ID for singleton
    
    def _get_collection(self):
        """Get settings collection with lazy loading"""
        if self.db is None:
            self.db = get_database()
        return self.db[self.collection_name]
    
    async def get(self) -> Optional[GlobalSettings]:
        """Get global settings (singleton)"""
        collection = self._get_collection()
        
        # Try to find by our fixed ID first
        settings_data = await collection.find_one({"_id": self.settings_id})
        
        # If not found by fixed ID, try to find any settings document
        if not settings_data:
            settings_data = await collection.find_one({})
            
            # If found with different ID, update it to use our fixed ID
            if settings_data:
                old_id = settings_data["_id"]
                settings_data["_id"] = self.settings_id
                await collection.delete_one({"_id": old_id})
                await collection.insert_one(settings_data)
        
        if settings_data:
            return GlobalSettings(**settings_data)
        return None
    
    async def create_default(self) -> GlobalSettings:
        """Create default settings if none exist"""
        collection = self._get_collection()
        
        default_settings = GlobalSettingsInDB(
            id=self.settings_id,
            summary_llm_profile=None,
            user_context=None,
            compaction_settings={
                "enabled": True,
                "message_threshold": 5,
                "preserve_last_n": 3,
                "summary_max_tokens": 100
            }
        )
        
        settings_dict = default_settings.dict(by_alias=True)
        settings_dict["_id"] = self.settings_id  # Ensure we use our fixed ID
        
        try:
            await collection.insert_one(settings_dict)
            logger.info("Created default global settings")
        except DuplicateKeyError:
            # Settings already exist, return them
            return await self.get()
        
        return GlobalSettings(**settings_dict)
    
    async def get_or_create(self) -> GlobalSettings:
        """Get existing settings or create default ones"""
        settings = await self.get()
        if not settings:
            settings = await self.create_default()
        return settings
    
    async def update(self, settings_update: GlobalSettingsUpdate) -> Optional[GlobalSettings]:
        """Update global settings"""
        collection = self._get_collection()
        
        # Ensure settings exist
        current_settings = await self.get_or_create()
        
        # Prepare update data
        update_data = settings_update.dict(exclude_unset=True)
        if not update_data:
            return current_settings
        
        # Add updated_at timestamp
        update_data["updated_at"] = datetime.utcnow()
        
        # Update in database
        result = await collection.update_one(
            {"_id": self.settings_id},
            {"$set": update_data}
        )
        
        if result.modified_count > 0:
            logger.info(f"Updated global settings: {list(update_data.keys())}")
            return await self.get()
        
        return current_settings
    
    async def get_text_only_llm_profiles(self) -> list[str]:
        """Get list of LLM profiles that support text-only mode"""
        from app.services.llm_crud import llm_crud
        
        # Get all active LLM profiles
        llm_profiles = await llm_crud.list(active_only=True)
        
        # Filter for text-only profiles (mode == "text" or mode not specified)
        text_profiles = []
        for llm in llm_profiles:
            if llm.active and (not hasattr(llm, 'mode') or llm.mode == "text"):
                text_profiles.append(llm.name)
        
        return sorted(text_profiles)


# Create singleton instance
settings_crud = SettingsCRUD()