import pytest
from httpx import AsyncClient


class TestLLMsAPI:
    @pytest.mark.asyncio
    async def test_create_llm_profile(self, client: AsyncClient, sample_llm_profile):
        response = await client.post("/llms/", json=sample_llm_profile)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == sample_llm_profile["name"]
        assert data["model"] == sample_llm_profile["model"]
        assert data["active"] is True
        assert "id" in data
    
    @pytest.mark.asyncio
    async def test_list_llm_profiles(self, client: AsyncClient, sample_llm_profile):
        # Create a profile first
        await client.post("/llms/", json=sample_llm_profile)
        
        # List profiles
        response = await client.get("/llms/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert any(p["name"] == sample_llm_profile["name"] for p in data)
    
    @pytest.mark.asyncio
    async def test_get_llm_profile(self, client: AsyncClient, sample_llm_profile):
        # Create a profile
        create_response = await client.post("/llms/", json=sample_llm_profile)
        profile_id = create_response.json()["id"]
        
        # Get the profile
        response = await client.get(f"/llms/{profile_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == profile_id
        assert data["name"] == sample_llm_profile["name"]
    
    @pytest.mark.asyncio
    async def test_update_llm_profile(self, client: AsyncClient, sample_llm_profile):
        # Create a profile
        create_response = await client.post("/llms/", json=sample_llm_profile)
        profile_id = create_response.json()["id"]
        
        # Update the profile
        update_data = {"temperature": 0.5, "max_tokens": 2048}
        response = await client.put(f"/llms/{profile_id}", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["temperature"] == 0.5
        assert data["max_tokens"] == 2048
    
    @pytest.mark.asyncio
    async def test_delete_llm_profile(self, client: AsyncClient, sample_llm_profile):
        # Create a profile
        create_response = await client.post("/llms/", json=sample_llm_profile)
        profile_id = create_response.json()["id"]
        
        # Delete the profile
        response = await client.delete(f"/llms/{profile_id}")
        assert response.status_code == 200
        
        # Verify it's deleted
        response = await client.get(f"/llms/{profile_id}")
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_duplicate_name_error(self, client: AsyncClient, sample_llm_profile):
        # Create first profile
        await client.post("/llms/", json=sample_llm_profile)
        
        # Try to create with same name
        response = await client.post("/llms/", json=sample_llm_profile)
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]