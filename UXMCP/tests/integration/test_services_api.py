import pytest
from httpx import AsyncClient


class TestServicesAPI:
    @pytest.mark.asyncio
    async def test_create_service(self, client: AsyncClient, sample_service):
        response = await client.post("/services/", json=sample_service)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == sample_service["name"]
        assert data["route"] == sample_service["route"]
        assert data["active"] is False
        assert "id" in data
    
    @pytest.mark.asyncio
    async def test_list_services(self, client: AsyncClient, sample_service):
        # Create a service first
        await client.post("/services/", json=sample_service)
        
        # List services
        response = await client.get("/services/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert any(s["name"] == sample_service["name"] for s in data)
    
    @pytest.mark.asyncio
    async def test_get_service(self, client: AsyncClient, sample_service):
        # Create a service
        create_response = await client.post("/services/", json=sample_service)
        service_id = create_response.json()["id"]
        
        # Get the service
        response = await client.get(f"/services/{service_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == service_id
        assert data["name"] == sample_service["name"]
    
    @pytest.mark.asyncio
    async def test_update_service(self, client: AsyncClient, sample_service):
        # Create a service
        create_response = await client.post("/services/", json=sample_service)
        service_id = create_response.json()["id"]
        
        # Update the service
        update_data = {"description": "Updated description"}
        response = await client.put(f"/services/{service_id}", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "Updated description"
    
    @pytest.mark.asyncio
    async def test_activate_deactivate_service(self, client: AsyncClient, sample_service):
        # Create a service
        create_response = await client.post("/services/", json=sample_service)
        service_id = create_response.json()["id"]
        
        # Activate the service
        response = await client.post(f"/services/{service_id}/activate")
        assert response.status_code == 200
        data = response.json()
        assert data["active"] is True
        
        # Deactivate the service
        response = await client.post(f"/services/{service_id}/deactivate")
        assert response.status_code == 200
        data = response.json()
        assert data["active"] is False
    
    @pytest.mark.asyncio
    async def test_delete_service(self, client: AsyncClient, sample_service):
        # Create a service
        create_response = await client.post("/services/", json=sample_service)
        service_id = create_response.json()["id"]
        
        # Delete the service
        response = await client.delete(f"/services/{service_id}")
        assert response.status_code == 200
        
        # Verify it's deleted
        response = await client.get(f"/services/{service_id}")
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_cannot_delete_active_service(self, client: AsyncClient, sample_service):
        # Create and activate a service
        create_response = await client.post("/services/", json=sample_service)
        service_id = create_response.json()["id"]
        await client.post(f"/services/{service_id}/activate")
        
        # Try to delete active service
        response = await client.delete(f"/services/{service_id}")
        assert response.status_code == 400
        assert "Cannot delete active service" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_duplicate_name_error(self, client: AsyncClient, sample_service):
        # Create first service
        await client.post("/services/", json=sample_service)
        
        # Try to create with same name
        response = await client.post("/services/", json=sample_service)
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_duplicate_route_error(self, client: AsyncClient, sample_service):
        # Create first service
        await client.post("/services/", json=sample_service)
        
        # Try to create with same route but different name
        duplicate_route = sample_service.copy()
        duplicate_route["name"] = "DifferentName"
        response = await client.post("/services/", json=duplicate_route)
        assert response.status_code == 400
        assert "route" in response.json()["detail"].lower()