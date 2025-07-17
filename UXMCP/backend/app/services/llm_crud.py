from typing import List, Optional
from datetime import datetime
from bson import ObjectId
from pymongo.errors import DuplicateKeyError
from app.core.database import get_database
from app.models.llm import LLMProfileCreate, LLMProfileUpdate, LLMProfile


class LLMProfileCRUD:
    def __init__(self):
        self.collection_name = "llms"
    
    @staticmethod
    def _prepare_document(doc):
        """Prepare MongoDB document for Pydantic model"""
        if doc and "_id" in doc:
            doc["id"] = str(doc["_id"])
            del doc["_id"]
        return doc
    
    async def create(self, llm_profile: LLMProfileCreate) -> LLMProfile:
        db = get_database()
        profile_dict = llm_profile.model_dump()
        profile_dict["created_at"] = datetime.utcnow()
        profile_dict["updated_at"] = datetime.utcnow()
        
        try:
            result = await db[self.collection_name].insert_one(profile_dict)
            created_profile = await db[self.collection_name].find_one({"_id": result.inserted_id})
            return LLMProfile(**self._prepare_document(created_profile))
        except DuplicateKeyError:
            raise ValueError(f"LLM profile with name '{llm_profile.name}' already exists")
    
    async def get(self, profile_id: str) -> Optional[LLMProfile]:
        db = get_database()
        if not ObjectId.is_valid(profile_id):
            return None
        
        profile = await db[self.collection_name].find_one({"_id": ObjectId(profile_id)})
        if profile:
            return LLMProfile(**self._prepare_document(profile))
        return None
    
    async def get_by_name(self, name: str) -> Optional[LLMProfile]:
        db = get_database()
        profile = await db[self.collection_name].find_one({"name": name})
        if profile:
            return LLMProfile(**self._prepare_document(profile))
        return None
    
    async def list(self, skip: int = 0, limit: int = 100, active_only: bool = False) -> List[LLMProfile]:
        db = get_database()
        filter_query = {"active": True} if active_only else {}
        
        cursor = db[self.collection_name].find(filter_query).skip(skip).limit(limit)
        profiles = []
        async for profile in cursor:
            profiles.append(LLMProfile(**self._prepare_document(profile)))
        return profiles
    
    async def update(self, profile_id: str, profile_update: LLMProfileUpdate) -> Optional[LLMProfile]:
        db = get_database()
        if not ObjectId.is_valid(profile_id):
            return None
        
        update_data = profile_update.model_dump(exclude_unset=True)
        if update_data:
            update_data["updated_at"] = datetime.utcnow()
            
            try:
                result = await db[self.collection_name].update_one(
                    {"_id": ObjectId(profile_id)},
                    {"$set": update_data}
                )
                
                if result.modified_count == 1:
                    updated_profile = await db[self.collection_name].find_one({"_id": ObjectId(profile_id)})
                    return LLMProfile(**self._prepare_document(updated_profile))
            except DuplicateKeyError:
                raise ValueError(f"LLM profile with name already exists")
        
        return None
    
    async def delete(self, profile_id: str) -> bool:
        db = get_database()
        if not ObjectId.is_valid(profile_id):
            return False
        
        result = await db[self.collection_name].delete_one({"_id": ObjectId(profile_id)})
        return result.deleted_count == 1


llm_crud = LLMProfileCRUD()