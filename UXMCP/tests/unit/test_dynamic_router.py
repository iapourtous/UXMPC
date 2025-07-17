import pytest
from fastapi import FastAPI
from app.models.service import Service, ServiceParam
from app.core.dynamic_router import create_handler
import json


class TestDynamicRouter:
    @pytest.mark.asyncio
    async def test_create_handler_simple(self):
        service = Service(
            id="123",
            name="SimpleService",
            route="/simple",
            method="GET",
            code="""
def handler(**params):
    return {"message": "Hello World"}
""",
            dependencies=[],
            params=[],
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00"
        )
        
        handler = create_handler(service)
        
        # Mock request
        class MockRequest:
            query_params = {}
            async def json(self):
                return {}
        
        request = MockRequest()
        result = await handler(request)
        
        assert result.status_code == 200
        body = json.loads(result.body)
        assert body["message"] == "Hello World"
    
    @pytest.mark.asyncio
    async def test_create_handler_with_params(self):
        service = Service(
            id="123",
            name="ParamService",
            route="/param",
            method="GET",
            code="""
def handler(**params):
    name = params.get('name', 'Guest')
    return {"greeting": f"Hello {name}"}
""",
            dependencies=[],
            params=[
                ServiceParam(name="name", type="string", required=False)
            ],
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00"
        )
        
        handler = create_handler(service)
        
        # Mock request with query params
        class MockRequest:
            query_params = {"name": "Alice"}
            async def json(self):
                return {}
        
        request = MockRequest()
        result = await handler(request)
        
        assert result.status_code == 200
        body = json.loads(result.body)
        assert body["greeting"] == "Hello Alice"
    
    @pytest.mark.asyncio
    async def test_create_handler_with_dependencies(self):
        service = Service(
            id="123",
            name="DependencyService",
            route="/deps",
            method="GET",
            code="""
def handler(**params):
    import json
    data = {"status": "ok"}
    return json.loads(json.dumps(data))
""",
            dependencies=["json"],
            params=[],
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00"
        )
        
        handler = create_handler(service)
        
        class MockRequest:
            query_params = {}
            async def json(self):
                return {}
        
        request = MockRequest()
        result = await handler(request)
        
        assert result.status_code == 200
        body = json.loads(result.body)
        assert body["status"] == "ok"