from typing import List, Optional
from datetime import datetime
from bson import ObjectId
from pymongo.errors import DuplicateKeyError
from app.core.database import get_database
from app.models.service import ServiceCreate, ServiceUpdate, Service


class ServiceCRUD:
    def __init__(self):
        self.collection_name = "services"
    
    @staticmethod
    def _prepare_document(doc):
        """Prepare MongoDB document for Pydantic model"""
        if doc and "_id" in doc:
            doc["id"] = str(doc["_id"])
            del doc["_id"]
        return doc
    
    async def create(self, service: ServiceCreate) -> Service:
        db = get_database()
        service_dict = service.model_dump()
        service_dict["created_at"] = datetime.utcnow()
        service_dict["updated_at"] = datetime.utcnow()
        
        try:
            result = await db[self.collection_name].insert_one(service_dict)
            created_service = await db[self.collection_name].find_one({"_id": result.inserted_id})
            return Service(**self._prepare_document(created_service))
        except DuplicateKeyError as e:
            if "name" in str(e):
                raise ValueError(f"Service with name '{service.name}' already exists")
            elif "route" in str(e):
                raise ValueError(f"Service with route '{service.route}' already exists")
            raise
    
    async def get(self, service_id: str) -> Optional[Service]:
        db = get_database()
        if not ObjectId.is_valid(service_id):
            return None
        
        service = await db[self.collection_name].find_one({"_id": ObjectId(service_id)})
        if service:
            return Service(**self._prepare_document(service))
        return None
    
    async def get_by_name(self, name: str) -> Optional[Service]:
        db = get_database()
        service = await db[self.collection_name].find_one({"name": name})
        if service:
            return Service(**self._prepare_document(service))
        return None
    
    async def get_by_route(self, route: str) -> Optional[Service]:
        db = get_database()
        service = await db[self.collection_name].find_one({"route": route})
        if service:
            return Service(**self._prepare_document(service))
        return None
    
    async def list(self, skip: int = 0, limit: int = 100, active_only: bool = False) -> List[Service]:
        db = get_database()
        filter_query = {"active": True} if active_only else {}
        
        cursor = db[self.collection_name].find(filter_query).skip(skip).limit(limit)
        services = []
        async for service in cursor:
            services.append(Service(**self._prepare_document(service)))
        return services
    
    async def update(self, service_id: str, service_update: ServiceUpdate) -> Optional[Service]:
        db = get_database()
        if not ObjectId.is_valid(service_id):
            return None
        
        update_data = service_update.model_dump(exclude_unset=True)
        if update_data:
            update_data["updated_at"] = datetime.utcnow()
            
            try:
                result = await db[self.collection_name].update_one(
                    {"_id": ObjectId(service_id)},
                    {"$set": update_data}
                )
                
                if result.modified_count >= 0:  # Return service even if nothing was modified
                    updated_service = await db[self.collection_name].find_one({"_id": ObjectId(service_id)})
                    return Service(**self._prepare_document(updated_service))
            except DuplicateKeyError as e:
                if "name" in str(e):
                    raise ValueError(f"Service with name already exists")
                elif "route" in str(e):
                    raise ValueError(f"Service with route already exists")
                raise
        
        return None
    
    async def delete(self, service_id: str) -> bool:
        db = get_database()
        if not ObjectId.is_valid(service_id):
            return False
        
        result = await db[self.collection_name].delete_one({"_id": ObjectId(service_id)})
        return result.deleted_count == 1
    
    async def activate(self, service_id: str) -> Optional[Service]:
        # Update the service to active=True
        db = get_database()
        if not ObjectId.is_valid(service_id):
            return None
        
        update_data = {"active": True, "updated_at": datetime.utcnow()}
        
        result = await db[self.collection_name].update_one(
            {"_id": ObjectId(service_id)},
            {"$set": update_data}
        )
        
        # Always return the updated service
        updated_service = await db[self.collection_name].find_one({"_id": ObjectId(service_id)})
        if updated_service:
            return Service(**self._prepare_document(updated_service))
        return None
    
    async def deactivate(self, service_id: str) -> Optional[Service]:
        # Update the service to active=False
        db = get_database()
        if not ObjectId.is_valid(service_id):
            return None
        
        update_data = {"active": False, "updated_at": datetime.utcnow()}
        
        result = await db[self.collection_name].update_one(
            {"_id": ObjectId(service_id)},
            {"$set": update_data}
        )
        
        # Always return the updated service
        updated_service = await db[self.collection_name].find_one({"_id": ObjectId(service_id)})
        if updated_service:
            return Service(**self._prepare_document(updated_service))
        return None


service_crud = ServiceCRUD()