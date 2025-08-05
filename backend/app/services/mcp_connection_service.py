from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from bson import ObjectId
from pymongo.errors import DuplicateKeyError
from app.core.database import get_database
from app.models.mcp_connection import (
    MCPConnection, 
    MCPConnectionCreate, 
    MCPConnectionUpdate, 
    MCPAuth, 
    MCPServerCache,
    MCPConnectionTest
)
import logging

logger = logging.getLogger(__name__)


class MCPConnectionService:
    def __init__(self):
        self.collection_name = "mcp_connections"
        self.auth_collection_name = "mcp_auth"
        self.cache_collection_name = "mcp_server_cache"
    
    @staticmethod
    def _prepare_document(doc):
        """Prepare MongoDB document for Pydantic model"""
        if doc and "_id" in doc:
            doc["id"] = str(doc["_id"])
            del doc["_id"]
        return doc
    
    async def create_connection(self, connection_data: MCPConnectionCreate) -> MCPConnection:
        """Create a new MCP connection"""
        db = get_database()
        connection_dict = connection_data.model_dump()
        connection_dict["created_at"] = datetime.utcnow()
        connection_dict["updated_at"] = datetime.utcnow()
        connection_dict["status"] = "inactive"
        connection_dict["retry_count"] = 0
        
        try:
            result = await db[self.collection_name].insert_one(connection_dict)
            created_connection = await db[self.collection_name].find_one({"_id": result.inserted_id})
            return MCPConnection(**self._prepare_document(created_connection))
        except DuplicateKeyError as e:
            if "name" in str(e):
                raise ValueError(f"MCP connection with name '{connection_data.name}' already exists")
            raise
    
    async def get_connections(self, skip: int = 0, limit: int = 100) -> List[MCPConnection]:
        """Get all MCP connections with pagination"""
        db = get_database()
        cursor = db[self.collection_name].find().skip(skip).limit(limit).sort("created_at", -1)
        connections = []
        async for doc in cursor:
            connections.append(MCPConnection(**self._prepare_document(doc)))
        return connections
    
    async def get_connection(self, connection_id: str) -> Optional[MCPConnection]:
        """Get a specific MCP connection by ID"""
        db = get_database()
        if not ObjectId.is_valid(connection_id):
            return None
        
        connection = await db[self.collection_name].find_one({"_id": ObjectId(connection_id)})
        if connection:
            return MCPConnection(**self._prepare_document(connection))
        return None
    
    async def get_connection_by_name(self, name: str) -> Optional[MCPConnection]:
        """Get a connection by name"""
        db = get_database()
        connection = await db[self.collection_name].find_one({"name": name})
        if connection:
            return MCPConnection(**self._prepare_document(connection))
        return None
    
    async def update_connection(self, connection_id: str, data: MCPConnectionUpdate) -> Optional[MCPConnection]:
        """Update an MCP connection"""
        db = get_database()
        if not ObjectId.is_valid(connection_id):
            return None
        
        update_dict = {k: v for k, v in data.model_dump().items() if v is not None}
        if not update_dict:
            return await self.get_connection(connection_id)
        
        update_dict["updated_at"] = datetime.utcnow()
        
        try:
            result = await db[self.collection_name].update_one(
                {"_id": ObjectId(connection_id)},
                {"$set": update_dict}
            )
            
            if result.modified_count > 0:
                return await self.get_connection(connection_id)
            return None
        except DuplicateKeyError as e:
            if "name" in str(e):
                raise ValueError(f"MCP connection with name '{data.name}' already exists")
            raise
    
    async def delete_connection(self, connection_id: str) -> bool:
        """Delete an MCP connection and its related data"""
        db = get_database()
        if not ObjectId.is_valid(connection_id):
            return False
        
        # Delete related auth data
        await db[self.auth_collection_name].delete_many({"connection_id": connection_id})
        
        # Delete cached server data
        await db[self.cache_collection_name].delete_many({"connection_id": connection_id})
        
        # Delete the connection
        result = await db[self.collection_name].delete_one({"_id": ObjectId(connection_id)})
        return result.deleted_count > 0
    
    async def update_connection_status(self, connection_id: str, status: str, error: Optional[str] = None) -> bool:
        """Update connection status and error"""
        db = get_database()
        if not ObjectId.is_valid(connection_id):
            return False
        
        update_data = {
            "status": status,
            "updated_at": datetime.utcnow()
        }
        
        if error:
            update_data["last_error"] = error
            # Handle retry count increment separately
            await db[self.collection_name].update_one(
                {"_id": ObjectId(connection_id)},
                {"$inc": {"retry_count": 1}}
            )
        else:
            update_data["last_error"] = None
            update_data["retry_count"] = 0
            if status == "active":
                update_data["last_ping"] = datetime.utcnow()
        
        result = await db[self.collection_name].update_one(
            {"_id": ObjectId(connection_id)},
            {"$set": update_data}
        )
        
        return result.modified_count > 0
    
    async def get_active_connections(self) -> List[MCPConnection]:
        """Get all active MCP connections"""
        db = get_database()
        cursor = db[self.collection_name].find({"status": "active"})
        connections = []
        async for doc in cursor:
            connections.append(MCPConnection(**self._prepare_document(doc)))
        return connections
    
    async def get_connections_for_agent(self, agent_mcp_connections: List[str]) -> List[MCPConnection]:
        """Get connections assigned to a specific agent"""
        if not agent_mcp_connections:
            return []
        
        db = get_database()
        object_ids = [ObjectId(conn_id) for conn_id in agent_mcp_connections if ObjectId.is_valid(conn_id)]
        
        cursor = db[self.collection_name].find({"_id": {"$in": object_ids}})
        connections = []
        async for doc in cursor:
            connections.append(MCPConnection(**self._prepare_document(doc)))
        return connections
    
    async def cleanup_failed_connections(self, max_retry_count: int = 5) -> int:
        """Clean up connections that have exceeded retry limits"""
        db = get_database()
        result = await db[self.collection_name].update_many(
            {
                "retry_count": {"$gte": max_retry_count},
                "status": {"$ne": "inactive"}
            },
            {
                "$set": {
                    "status": "error",
                    "last_error": f"Exceeded maximum retry count of {max_retry_count}",
                    "updated_at": datetime.utcnow()
                }
            }
        )
        return result.modified_count
    
    async def ping_active_connections(self) -> Dict[str, bool]:
        """Ping all active connections to check health"""
        connections = await self.get_active_connections()
        results = {}
        
        for connection in connections:
            # This would be implemented with actual MCP client ping
            # For now, we just update the last_ping timestamp
            success = await self._ping_connection(connection)
            results[connection.id] = success
            
            if success:
                await self.update_connection_status(connection.id, "active")
            else:
                await self.update_connection_status(connection.id, "error", "Ping failed")
        
        return results
    
    async def _ping_connection(self, connection: MCPConnection) -> bool:
        """Internal method to ping a connection (placeholder for actual implementation)"""
        # This would use the MCPClientService when implemented
        # For now, return True as a placeholder
        return True


class MCPConnectionServiceSingleton:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = MCPConnectionService()
        return cls._instance


# Global instance
mcp_connection_service = MCPConnectionServiceSingleton()