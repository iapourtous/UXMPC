import pytest
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import get_settings
from app.core.database import db
from app.main import app as fastapi_app
from httpx import AsyncClient

settings = get_settings()


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_db():
    # Use a test database
    test_client = AsyncIOMotorClient(settings.mongodb_url)
    test_database = test_client["uxmcp_test"]
    
    # Override the database instance
    db.client = test_client
    db.database = test_database
    
    yield test_database
    
    # Cleanup
    await test_client.drop_database("uxmcp_test")
    test_client.close()


@pytest.fixture
async def client(test_db):
    async with AsyncClient(app=fastapi_app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def sample_service():
    return {
        "name": "TestService",
        "route": "/test",
        "method": "GET",
        "description": "A test service",
        "code": "def handler(**params):\\n    return {'message': 'Hello from test'}",
        "dependencies": [],
        "params": [
            {
                "name": "name",
                "type": "string",
                "required": False,
                "description": "Name parameter"
            }
        ]
    }


@pytest.fixture
async def sample_llm_profile():
    return {
        "name": "test-gpt-4",
        "model": "gpt-4",
        "api_key": "test-key-123",
        "max_tokens": 2048,
        "temperature": 0.7,
        "mode": "json",
        "active": True
    }