from typing import List, Optional, Dict, Any
from bson import ObjectId
from datetime import datetime
from app.models.agent import Agent, AgentCreate, AgentUpdate
from app.core.database import get_database
import logging

logger = logging.getLogger(__name__)


class AgentCRUD:
    @property
    def collection(self):
        db = get_database()
        return db["agents"]
    
    async def create(self, agent: AgentCreate) -> Agent:
        """Create a new agent"""
        agent_dict = agent.model_dump()
        agent_dict["created_at"] = datetime.utcnow()
        agent_dict["updated_at"] = datetime.utcnow()
        
        # Check if agent with same name exists
        existing = await self.collection.find_one({"name": agent.name})
        if existing:
            raise ValueError(f"Agent with name '{agent.name}' already exists")
        
        # Check if endpoint is already taken
        existing_endpoint = await self.collection.find_one({"endpoint": agent.endpoint})
        if existing_endpoint:
            raise ValueError(f"Endpoint '{agent.endpoint}' is already in use")
        
        result = await self.collection.insert_one(agent_dict)
        agent_dict["id"] = str(result.inserted_id)
        
        return Agent(**agent_dict)
    
    async def get(self, agent_id: str) -> Optional[Agent]:
        """Get an agent by ID"""
        try:
            doc = await self.collection.find_one({"_id": ObjectId(agent_id)})
            if doc:
                doc["id"] = str(doc["_id"])
                del doc["_id"]
                return Agent(**doc)
        except Exception as e:
            logger.error(f"Error getting agent: {e}")
        return None
    
    async def get_by_name(self, name: str) -> Optional[Agent]:
        """Get an agent by name"""
        doc = await self.collection.find_one({"name": name})
        if doc:
            doc["id"] = str(doc["_id"])
            del doc["_id"]
            return Agent(**doc)
        return None
    
    async def get_by_endpoint(self, endpoint: str) -> Optional[Agent]:
        """Get an agent by endpoint"""
        doc = await self.collection.find_one({"endpoint": endpoint})
        if doc:
            doc["id"] = str(doc["_id"])
            del doc["_id"]
            return Agent(**doc)
        return None
    
    async def list(self, skip: int = 0, limit: int = 100, active_only: bool = False) -> List[Agent]:
        """List all agents"""
        query = {"active": True} if active_only else {}
        cursor = self.collection.find(query).skip(skip).limit(limit)
        
        agents = []
        async for doc in cursor:
            doc["id"] = str(doc["_id"])
            del doc["_id"]
            agents.append(Agent(**doc))
        
        return agents
    
    async def update(self, agent_id: str, agent_update: AgentUpdate) -> Optional[Agent]:
        """Update an agent"""
        update_data = agent_update.model_dump(exclude_unset=True)
        
        if not update_data:
            return await self.get(agent_id)
        
        # Check name uniqueness if updating name
        if "name" in update_data:
            existing = await self.collection.find_one({
                "name": update_data["name"],
                "_id": {"$ne": ObjectId(agent_id)}
            })
            if existing:
                raise ValueError(f"Agent with name '{update_data['name']}' already exists")
        
        # Check endpoint uniqueness if updating endpoint
        if "endpoint" in update_data:
            existing = await self.collection.find_one({
                "endpoint": update_data["endpoint"],
                "_id": {"$ne": ObjectId(agent_id)}
            })
            if existing:
                raise ValueError(f"Endpoint '{update_data['endpoint']}' is already in use")
        
        update_data["updated_at"] = datetime.utcnow()
        
        result = await self.collection.update_one(
            {"_id": ObjectId(agent_id)},
            {"$set": update_data}
        )
        
        if result.modified_count:
            return await self.get(agent_id)
        
        return None
    
    async def delete(self, agent_id: str) -> bool:
        """Delete an agent"""
        result = await self.collection.delete_one({"_id": ObjectId(agent_id)})
        return result.deleted_count > 0
    
    async def activate(self, agent_id: str) -> Optional[Agent]:
        """Activate an agent"""
        result = await self.collection.update_one(
            {"_id": ObjectId(agent_id)},
            {"$set": {"active": True, "updated_at": datetime.utcnow()}}
        )
        
        if result.modified_count:
            return await self.get(agent_id)
        
        return None
    
    async def deactivate(self, agent_id: str) -> Optional[Agent]:
        """Deactivate an agent"""
        result = await self.collection.update_one(
            {"_id": ObjectId(agent_id)},
            {"$set": {"active": False, "updated_at": datetime.utcnow()}}
        )
        
        if result.modified_count:
            return await self.get(agent_id)
        
        return None
    
    async def validate_dependencies(self, agent: Agent) -> Dict[str, Any]:
        """Validate that all agent dependencies exist"""
        from app.services.llm_crud import llm_crud
        from app.services.service_crud import service_crud
        
        errors = []
        warnings = []
        
        # Check LLM profile
        llm_profile = await llm_crud.get_by_name(agent.llm_profile)
        if not llm_profile:
            errors.append(f"LLM profile '{agent.llm_profile}' not found")
        elif not llm_profile.active:
            warnings.append(f"LLM profile '{agent.llm_profile}' is not active")
        
        # Check MCP services
        missing_services = []
        inactive_services = []
        
        for service_name in agent.mcp_services:
            service = await service_crud.get_by_name(service_name)
            if not service:
                missing_services.append(service_name)
            elif not service.active:
                inactive_services.append(service_name)
        
        if missing_services:
            errors.append(f"MCP services not found: {', '.join(missing_services)}")
        if inactive_services:
            warnings.append(f"MCP services not active: {', '.join(inactive_services)}")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }


# Singleton instance
agent_crud = AgentCRUD()