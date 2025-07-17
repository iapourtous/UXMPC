import pytest
from httpx import AsyncClient


class TestDocsAPI:
    @pytest.mark.asyncio
    async def test_generate_documentation_empty(self, client: AsyncClient):
        response = await client.get("/docs/")
        assert response.status_code == 200
        content = response.text
        assert "UXMCP Active Services Documentation" in content
        assert "Total active services: 0" in content
    
    @pytest.mark.asyncio
    async def test_generate_documentation_with_services(self, client: AsyncClient, sample_service):
        # Create and activate a service
        create_response = await client.post("/services/", json=sample_service)
        service_id = create_response.json()["id"]
        await client.post(f"/services/{service_id}/activate")
        
        # Get documentation
        response = await client.get("/docs/")
        assert response.status_code == 200
        content = response.text
        
        assert "UXMCP Active Services Documentation" in content
        assert "Total active services: 1" in content
        assert sample_service["name"] in content
        assert sample_service["route"] in content
        assert sample_service["method"] in content
        assert sample_service["description"] in content
        assert "def handler(**params):" in content