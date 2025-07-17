import pytest
from datetime import datetime
from bson import ObjectId
from app.models.service import Service, ServiceCreate, ServiceUpdate, ServiceParam
from app.models.llm import LLMProfile, LLMProfileCreate, LLMProfileUpdate


class TestServiceModels:
    def test_service_create(self):
        data = {
            "name": "TestService",
            "route": "/test",
            "method": "POST",
            "params": [
                {"name": "input", "type": "string", "required": True}
            ],
            "code": "def handler(**params): pass",
            "dependencies": ["requests"],
            "description": "Test service"
        }
        
        service = ServiceCreate(**data)
        assert service.name == "TestService"
        assert service.route == "/test"
        assert service.method == "POST"
        assert len(service.params) == 1
        assert service.params[0].name == "input"
        assert service.active is False
    
    def test_service_update(self):
        update = ServiceUpdate(name="UpdatedService", active=True)
        assert update.name == "UpdatedService"
        assert update.active is True
        assert update.route is None
    
    def test_service_with_id(self):
        service_data = {
            "_id": ObjectId(),
            "name": "TestService",
            "route": "/test",
            "method": "GET",
            "code": "def handler(**params): pass",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        service = Service(**service_data)
        assert str(service.id) == str(service_data["_id"])
        assert service.name == "TestService"


class TestLLMModels:
    def test_llm_profile_create(self):
        data = {
            "name": "gpt-4-profile",
            "model": "gpt-4",
            "api_key": "sk-test123",
            "max_tokens": 4096,
            "temperature": 0.8
        }
        
        profile = LLMProfileCreate(**data)
        assert profile.name == "gpt-4-profile"
        assert profile.model == "gpt-4"
        assert profile.api_key == "sk-test123"
        assert profile.max_tokens == 4096
        assert profile.temperature == 0.8
        assert profile.active is True
    
    def test_llm_profile_update(self):
        update = LLMProfileUpdate(temperature=0.5, active=False)
        assert update.temperature == 0.5
        assert update.active is False
        assert update.name is None
        assert update.model is None