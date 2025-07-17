from fastapi import APIRouter, HTTPException
from typing import List
from app.models.llm import LLMProfile, LLMProfileCreate, LLMProfileUpdate
from app.services.llm_crud import llm_crud


router = APIRouter()


@router.post("/", response_model=LLMProfile)
async def create_llm_profile(profile: LLMProfileCreate):
    try:
        return await llm_crud.create(profile)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=List[LLMProfile])
async def list_llm_profiles(skip: int = 0, limit: int = 100, active_only: bool = False):
    return await llm_crud.list(skip=skip, limit=limit, active_only=active_only)


@router.get("/{profile_id}", response_model=LLMProfile)
async def get_llm_profile(profile_id: str):
    profile = await llm_crud.get(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="LLM profile not found")
    return profile


@router.put("/{profile_id}", response_model=LLMProfile)
async def update_llm_profile(profile_id: str, profile_update: LLMProfileUpdate):
    try:
        profile = await llm_crud.update(profile_id, profile_update)
        if not profile:
            raise HTTPException(status_code=404, detail="LLM profile not found")
        return profile
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{profile_id}")
async def delete_llm_profile(profile_id: str):
    success = await llm_crud.delete(profile_id)
    if not success:
        raise HTTPException(status_code=404, detail="LLM profile not found")
    
    return {"message": "LLM profile deleted successfully"}