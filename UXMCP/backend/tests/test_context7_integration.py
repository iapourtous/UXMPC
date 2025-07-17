"""
Tests for Context7 MCP integration
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.core.context7_client import Context7MCPClient
from app.core.agent_tools import AgentTools
from app.core.service_documentation import get_external_documentation, get_enhanced_context


@pytest.mark.asyncio
async def test_context7_client_resolve_library():
    """Test library ID resolution"""
    client = Context7MCPClient()
    
    # Mock the HTTP response
    with patch('httpx.AsyncClient.post') as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {
                "id": "/newsapi/newsapi-python",
                "name": "newsapi",
                "description": "NewsAPI Python Client"
            }
        }
        mock_post.return_value = mock_response
        
        result = await client.resolve_library_id("newsapi")
        
        assert result is not None
        assert result["id"] == "/newsapi/newsapi-python"
        assert result["name"] == "newsapi"


@pytest.mark.asyncio
async def test_context7_client_get_docs():
    """Test documentation fetching"""
    client = Context7MCPClient()
    
    with patch('httpx.AsyncClient.post') as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {
                "content": "# NewsAPI Documentation\n\nExample usage..."
            }
        }
        mock_post.return_value = mock_response
        
        docs = await client.get_library_docs("/newsapi/newsapi-python")
        
        assert docs is not None
        assert "NewsAPI Documentation" in docs


@pytest.mark.asyncio
async def test_context7_disabled():
    """Test behavior when Context7 is disabled"""
    client = Context7MCPClient()
    client.enabled = False
    
    result = await client.resolve_library_id("fastapi")
    assert result is None
    
    docs = await client.get_library_docs("/fastapi/fastapi")
    assert docs is None


@pytest.mark.asyncio
async def test_library_extraction():
    """Test library extraction from description"""
    tools = AgentTools(app=MagicMock())
    
    # Test with explicit library mentions
    result = await tools.extract_libraries_from_description(
        "Create a service using FastAPI to fetch data from NewsAPI",
        "tool"
    )
    
    assert result["success"] is True
    assert "fastapi" in result["libraries"]
    assert "newsapi" in result["libraries"]
    
    # Test with API mentions
    result = await tools.extract_libraries_from_description(
        "Build a weather API client",
        "tool"
    )
    
    assert result["success"] is True
    assert "weather" in result["libraries"]


@pytest.mark.asyncio
async def test_enhanced_context_generation():
    """Test enhanced context generation with external docs"""
    with patch('app.core.context7_client.context7_client.resolve_library_id') as mock_resolve:
        with patch('app.core.context7_client.context7_client.get_library_docs') as mock_get_docs:
            mock_resolve.return_value = {"id": "/requests/requests"}
            mock_get_docs.return_value = "# Requests Library\n\nHTTP for Humans"
            
            context = await get_enhanced_context(
                service_type="tool",
                libraries=["requests"],
                topic=None
            )
            
            assert "UXMCP Service Creation Guide" in context
            assert "External Library Documentation" in context
            assert "Requests Library" in context


@pytest.mark.asyncio
async def test_external_documentation_error_handling():
    """Test error handling in external documentation fetching"""
    with patch('app.core.context7_client.context7_client.resolve_library_id') as mock_resolve:
        mock_resolve.side_effect = Exception("Network error")
        
        # Should not raise exception, just return empty string
        docs = await get_external_documentation(["fastapi"])
        assert docs == ""


@pytest.mark.asyncio 
async def test_library_detection_with_llm():
    """Test LLM-based library detection"""
    tools = AgentTools(app=MagicMock())
    
    with patch('httpx.AsyncClient.post') as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": '{"libraries": [{"name": "requests", "reason": "HTTP calls", "confidence": "high"}], "primary_library": "requests", "topic_focus": "api integration"}'
                }
            }]
        }
        mock_post.return_value = mock_response
        
        result = await tools.detect_libraries_with_llm(
            "Create HTTP client for external API",
            "tool",
            "https://api.openai.com/v1/chat/completions",
            "test-key",
            "gpt-4"
        )
        
        assert result["success"] is True
        assert "requests" in result["libraries"]
        assert result["primary_library"] == "requests"
        assert result["topic_focus"] == "api integration"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])