"""
Demo CRUD operations
"""

from typing import Optional, List
from datetime import datetime
from bson import ObjectId
from app.core.database import get_database
from app.models.demo import Demo, DemoCreate, DemoUpdate, DemoInDB
import logging

logger = logging.getLogger(__name__)


class DemoCRUD:
    def __init__(self):
        self.collection_name = "demos"
    
    async def create(self, demo: DemoCreate) -> Demo:
        """Create a new demo"""
        db = get_database()
        
        # Check if name already exists
        existing = await db[self.collection_name].find_one({"name": demo.name})
        if existing:
            raise ValueError(f"Demo with name '{demo.name}' already exists")
        
        # Create demo document
        demo_dict = demo.dict()
        demo_dict["created_at"] = datetime.utcnow()
        demo_dict["endpoint"] = f"/demos/{demo.name}"
        
        # Insert into database
        result = await db[self.collection_name].insert_one(demo_dict)
        demo_dict["id"] = str(result.inserted_id)
        demo_dict["_id"] = result.inserted_id
        
        logger.info(f"Created demo: {demo.name}")
        return Demo(**demo_dict)
    
    async def get(self, demo_id: str) -> Optional[Demo]:
        """Get a demo by ID"""
        db = get_database()
        
        if not ObjectId.is_valid(demo_id):
            return None
        
        demo = await db[self.collection_name].find_one({"_id": ObjectId(demo_id)})
        if demo:
            demo["id"] = str(demo["_id"])
            return Demo(**demo)
        return None
    
    async def get_by_name(self, name: str) -> Optional[Demo]:
        """Get a demo by its URL name"""
        db = get_database()
        
        demo = await db[self.collection_name].find_one({"name": name})
        if demo:
            demo["id"] = str(demo["_id"])
            return Demo(**demo)
        return None
    
    async def list(self, skip: int = 0, limit: int = 20) -> List[Demo]:
        """List all demos"""
        db = get_database()
        
        cursor = db[self.collection_name].find().sort("created_at", -1).skip(skip).limit(limit)
        demos = []
        
        async for demo in cursor:
            demo["id"] = str(demo["_id"])
            demos.append(Demo(**demo))
        
        return demos
    
    async def count(self) -> int:
        """Count total demos"""
        db = get_database()
        return await db[self.collection_name].count_documents({})
    
    async def update(self, demo_id: str, demo_update: DemoUpdate) -> Optional[Demo]:
        """Update a demo"""
        db = get_database()
        
        if not ObjectId.is_valid(demo_id):
            return None
        
        update_data = {k: v for k, v in demo_update.dict().items() if v is not None}
        if not update_data:
            return await self.get(demo_id)
        
        result = await db[self.collection_name].update_one(
            {"_id": ObjectId(demo_id)},
            {"$set": update_data}
        )
        
        if result.matched_count:
            return await self.get(demo_id)
        return None
    
    async def delete(self, demo_id: str) -> bool:
        """Delete a demo"""
        db = get_database()
        
        if not ObjectId.is_valid(demo_id):
            return False
        
        result = await db[self.collection_name].delete_one({"_id": ObjectId(demo_id)})
        
        if result.deleted_count:
            logger.info(f"Deleted demo: {demo_id}")
            return True
        return False
    
    async def search(self, query: str, skip: int = 0, limit: int = 20) -> List[Demo]:
        """Search demos by name or description"""
        db = get_database()
        
        # Simple text search on name and description
        search_filter = {
            "$or": [
                {"name": {"$regex": query, "$options": "i"}},
                {"description": {"$regex": query, "$options": "i"}},
                {"query": {"$regex": query, "$options": "i"}}
            ]
        }
        
        cursor = db[self.collection_name].find(search_filter).sort("created_at", -1).skip(skip).limit(limit)
        demos = []
        
        async for demo in cursor:
            demo["id"] = str(demo["_id"])
            demos.append(Demo(**demo))
        
        return demos


# Singleton instance
demo_crud = DemoCRUD()