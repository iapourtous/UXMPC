from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional
from app.models.service import Service, ServiceCreate, ServiceUpdate
from app.services.service_crud import service_crud
from app.core.dynamic_router import mount_service, unmount_service
from app.services.service_generator import service_generator
from fastapi import FastAPI
from pydantic import BaseModel


router = APIRouter()


class GenerateServiceRequest(BaseModel):
    name: str
    service_type: str
    route: str
    method: str = "GET"
    description: str
    llm_profile: str


@router.post("/", response_model=Service)
async def create_service(service: ServiceCreate):
    try:
        return await service_crud.create(service)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=List[Service])
async def list_services(skip: int = 0, limit: int = 100, active_only: bool = False):
    return await service_crud.list(skip=skip, limit=limit, active_only=active_only)


@router.get("/summary", response_model=List[Dict[str, Any]])
async def list_services_summary(active_only: bool = False):
    """Get a simplified list of services with only name and description for LLM analysis"""
    services = await service_crud.list(skip=0, limit=1000, active_only=active_only)
    return [
        {
            "id": service.id,
            "name": service.name,
            "description": service.description or "No description provided",
            "type": service.service_type,
            "route": service.route,
            "active": service.active
        }
        for service in services
    ]


@router.get("/{service_id}", response_model=Service)
async def get_service(service_id: str):
    service = await service_crud.get(service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return service


@router.put("/{service_id}", response_model=Service)
async def update_service(service_id: str, service_update: ServiceUpdate):
    try:
        service = await service_crud.update(service_id, service_update)
        if not service:
            raise HTTPException(status_code=404, detail="Service not found")
        return service
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{service_id}")
async def delete_service(service_id: str):
    # First check if service exists and is not active
    service = await service_crud.get(service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    if service.active:
        raise HTTPException(status_code=400, detail="Cannot delete active service. Deactivate it first.")
    
    success = await service_crud.delete(service_id)
    if not success:
        raise HTTPException(status_code=404, detail="Service not found")
    
    return {"message": "Service deleted successfully"}


@router.post("/{service_id}/activate", response_model=Service)
async def activate_service(service_id: str, app: FastAPI = Depends(lambda: router.app)):
    service = await service_crud.get(service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    if service.active:
        raise HTTPException(status_code=400, detail="Service is already active")
    
    try:
        # Mount the service route
        await mount_service(app, service)
        
        # Update service status
        activated_service = await service_crud.activate(service_id)
        return activated_service
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to activate service: {str(e)}")


@router.post("/{service_id}/deactivate", response_model=Service)
async def deactivate_service(service_id: str, app: FastAPI = Depends(lambda: router.app)):
    service = await service_crud.get(service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    if not service.active:
        raise HTTPException(status_code=400, detail="Service is already inactive")
    
    try:
        # Unmount the service route
        await unmount_service(app, service)
        
        # Update service status
        deactivated_service = await service_crud.deactivate(service_id)
        return deactivated_service
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to deactivate service: {str(e)}")


@router.post("/{service_id}/test")
async def test_service(service_id: str):
    from app.services.test_service import test_service_with_llm
    
    service = await service_crud.get(service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    if not service.llm_profile:
        raise HTTPException(status_code=400, detail="Service does not have an LLM profile configured")
    
    try:
        result = await test_service_with_llm(service)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to test service: {str(e)}")


@router.post("/generate")
async def generate_service(request: GenerateServiceRequest):
    try:
        # Generate service using LLM
        generated_data = await service_generator.generate_service(
            service_data=request.model_dump(),
            llm_profile_name=request.llm_profile
        )
        
        return generated_data
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate service: {str(e)}")