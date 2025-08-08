"""
Workspace CRUD Service

This module provides CRUD operations for document workspaces.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from bson import ObjectId
import logging

from app.models.workspace import (
    Workspace, WorkspaceCreate, WorkspaceUpdate, WorkspaceStats
)
from app.core.database import get_database
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


class WorkspaceCRUD:
    """CRUD operations for workspaces"""
    
    def __init__(self):
        self.collection_name = "workspaces"
    
    async def create(self, workspace: WorkspaceCreate) -> Workspace:
        """Create a new workspace"""
        db = get_database()
        
        # Check if workspace with same name exists
        existing = await db[self.collection_name].find_one({"name": workspace.name})
        if existing:
            raise ValueError(f"Workspace with name '{workspace.name}' already exists")
        
        # Create workspace document
        workspace_dict = workspace.dict()
        workspace_dict["created_at"] = datetime.utcnow()
        workspace_dict["updated_at"] = datetime.utcnow()
        workspace_dict["document_count"] = 0
        workspace_dict["total_size"] = 0
        
        # Set default settings if not provided
        if workspace_dict.get("settings") is None:
            workspace_dict["settings"] = {
                "max_file_size": 52428800,  # 50MB
                "allowed_types": [],
                "auto_extract": True,
                "auto_embed": True,
                "retention_days": None,
            }
        
        # Insert into database
        result = await db[self.collection_name].insert_one(workspace_dict)
        workspace_dict["id"] = str(result.inserted_id)
        workspace_dict.pop("_id", None)
        
        logger.info(f"Created workspace: {workspace.name} with ID: {workspace_dict['id']}")
        return Workspace(**workspace_dict)
    
    async def get(self, workspace_id: str) -> Optional[Workspace]:
        """Get a workspace by ID"""
        db = get_database()
        
        # Try to convert to ObjectId if valid
        try:
            obj_id = ObjectId(workspace_id)
            workspace = await db[self.collection_name].find_one({"_id": obj_id})
        except:
            # If not valid ObjectId, search by string ID
            workspace = await db[self.collection_name].find_one({"id": workspace_id})
        
        if workspace:
            workspace["id"] = str(workspace.pop("_id", workspace_id))
            return Workspace(**workspace)
        return None
    
    async def get_by_name(self, name: str) -> Optional[Workspace]:
        """Get a workspace by name"""
        db = get_database()
        workspace = await db[self.collection_name].find_one({"name": name})
        
        if workspace:
            workspace["id"] = str(workspace.pop("_id"))
            return Workspace(**workspace)
        return None
    
    async def list(
        self, 
        skip: int = 0, 
        limit: int = 100,
        agent_id: Optional[str] = None,
        is_public: Optional[bool] = None
    ) -> List[Workspace]:
        """List workspaces with optional filters"""
        db = get_database()
        
        # Build filter
        filter_dict = {}
        if agent_id:
            filter_dict["$or"] = [
                {"agent_ids": agent_id},
                {"owner_id": agent_id}
            ]
        if is_public is not None:
            filter_dict["is_public"] = is_public
        
        cursor = db[self.collection_name].find(filter_dict).skip(skip).limit(limit)
        workspaces = []
        
        async for workspace in cursor:
            workspace["id"] = str(workspace.pop("_id"))
            workspaces.append(Workspace(**workspace))
        
        return workspaces
    
    async def update(self, workspace_id: str, update: WorkspaceUpdate) -> Optional[Workspace]:
        """Update a workspace"""
        db = get_database()
        
        # Get existing workspace
        existing = await self.get(workspace_id)
        if not existing:
            return None
        
        # Prepare update data
        update_dict = {k: v for k, v in update.dict().items() if v is not None}
        if update_dict:
            update_dict["updated_at"] = datetime.utcnow()
            
            # Update in database
            try:
                obj_id = ObjectId(workspace_id)
                await db[self.collection_name].update_one(
                    {"_id": obj_id},
                    {"$set": update_dict}
                )
            except:
                await db[self.collection_name].update_one(
                    {"id": workspace_id},
                    {"$set": update_dict}
                )
            
            logger.info(f"Updated workspace: {workspace_id}")
        
        return await self.get(workspace_id)
    
    async def delete(self, workspace_id: str) -> bool:
        """Delete a workspace"""
        db = get_database()
        
        # Check if workspace has documents
        documents_count = await db["documents"].count_documents({"workspace_id": workspace_id})
        if documents_count > 0:
            raise ValueError(f"Cannot delete workspace with {documents_count} documents. Delete documents first.")
        
        # Delete workspace
        try:
            obj_id = ObjectId(workspace_id)
            result = await db[self.collection_name].delete_one({"_id": obj_id})
        except:
            result = await db[self.collection_name].delete_one({"id": workspace_id})
        
        if result.deleted_count > 0:
            logger.info(f"Deleted workspace: {workspace_id}")
            return True
        return False
    
    async def add_agent_access(self, workspace_id: str, agent_id: str) -> bool:
        """Add an agent to workspace access list"""
        db = get_database()
        
        try:
            obj_id = ObjectId(workspace_id)
            result = await db[self.collection_name].update_one(
                {"_id": obj_id},
                {
                    "$addToSet": {"agent_ids": agent_id},
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )
        except:
            result = await db[self.collection_name].update_one(
                {"id": workspace_id},
                {
                    "$addToSet": {"agent_ids": agent_id},
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )
        
        return result.modified_count > 0
    
    async def remove_agent_access(self, workspace_id: str, agent_id: str) -> bool:
        """Remove an agent from workspace access list"""
        db = get_database()
        
        try:
            obj_id = ObjectId(workspace_id)
            result = await db[self.collection_name].update_one(
                {"_id": obj_id},
                {
                    "$pull": {"agent_ids": agent_id},
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )
        except:
            result = await db[self.collection_name].update_one(
                {"id": workspace_id},
                {
                    "$pull": {"agent_ids": agent_id},
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )
        
        return result.modified_count > 0
    
    async def update_stats(self, workspace_id: str, document_delta: int = 0, size_delta: int = 0):
        """Update workspace statistics"""
        db = get_database()
        
        try:
            obj_id = ObjectId(workspace_id)
            await db[self.collection_name].update_one(
                {"_id": obj_id},
                {
                    "$inc": {
                        "document_count": document_delta,
                        "total_size": size_delta
                    },
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )
        except:
            await db[self.collection_name].update_one(
                {"id": workspace_id},
                {
                    "$inc": {
                        "document_count": document_delta,
                        "total_size": size_delta
                    },
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )
    
    async def get_stats(self, workspace_id: str) -> Optional[WorkspaceStats]:
        """Get detailed statistics for a workspace"""
        db = get_database()
        
        # Get workspace
        workspace = await self.get(workspace_id)
        if not workspace:
            return None
        
        # Get document statistics
        pipeline = [
            {"$match": {"workspace_id": workspace_id}},
            {"$group": {
                "_id": None,
                "document_count": {"$sum": 1},
                "total_size": {"$sum": "$file_size"},
                "types": {"$push": "$type"},
                "categories": {"$push": "$category"}
            }}
        ]
        
        cursor = db["documents"].aggregate(pipeline)
        stats_data = await cursor.to_list(1)
        
        if stats_data:
            stats = stats_data[0]
            
            # Count types and categories
            type_counts = {}
            category_counts = {}
            
            for doc_type in stats.get("types", []):
                type_counts[doc_type] = type_counts.get(doc_type, 0) + 1
            
            for category in stats.get("categories", []):
                category_counts[category] = category_counts.get(category, 0) + 1
            
            # Get recent uploads (last 10)
            recent_cursor = db["documents"].find(
                {"workspace_id": workspace_id}
            ).sort("created_at", -1).limit(10)
            
            recent_uploads = []
            async for doc in recent_cursor:
                recent_uploads.append({
                    "id": str(doc.get("_id")),
                    "name": doc.get("name"),
                    "type": doc.get("type"),
                    "created_at": doc.get("created_at")
                })
            
            # Get most accessed (top 10)
            accessed_cursor = db["documents"].find(
                {"workspace_id": workspace_id, "access_count": {"$gt": 0}}
            ).sort("access_count", -1).limit(10)
            
            most_accessed = []
            async for doc in accessed_cursor:
                most_accessed.append({
                    "id": str(doc.get("_id")),
                    "name": doc.get("name"),
                    "type": doc.get("type"),
                    "access_count": doc.get("access_count")
                })
            
            return WorkspaceStats(
                workspace_id=workspace_id,
                document_count=stats.get("document_count", 0),
                total_size=stats.get("total_size", 0),
                document_types=type_counts,
                categories=category_counts,
                recent_uploads=recent_uploads,
                most_accessed=most_accessed,
                agent_access=[{"agent_id": aid} for aid in workspace.agent_ids]
            )
        
        return WorkspaceStats(
            workspace_id=workspace_id,
            document_count=0,
            total_size=0,
            document_types={},
            categories={},
            recent_uploads=[],
            most_accessed=[],
            agent_access=[]
        )


# Singleton instance
workspace_crud = WorkspaceCRUD()