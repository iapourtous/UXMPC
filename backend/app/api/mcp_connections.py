from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional, Dict, Any
import logging
from app.models.mcp_connection import (
    MCPConnection, 
    MCPConnectionCreate, 
    MCPConnectionUpdate, 
    MCPConnectionTest,
    MCPToolCall,
    MCPToolResult
)
from app.services.mcp_connection_service import mcp_connection_service
from app.services.mcp_client_service import mcp_client_service
from app.services.mcp_auth_service import mcp_auth_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/", response_model=MCPConnection)
async def create_connection(connection: MCPConnectionCreate):
    """Create a new MCP connection"""
    try:
        return await mcp_connection_service.create_connection(connection)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create MCP connection: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create MCP connection")


@router.get("/", response_model=List[MCPConnection])
async def list_connections(
    skip: int = 0,
    limit: int = 100
):
    """List all MCP connections"""
    try:
        return await mcp_connection_service.get_connections(skip=skip, limit=limit)
    except Exception as e:
        logger.error(f"Failed to list MCP connections: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list MCP connections")


@router.get("/{connection_id}", response_model=MCPConnection)
async def get_connection(connection_id: str):
    """Get a specific MCP connection"""
    connection = await mcp_connection_service.get_connection(connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="MCP connection not found")
    return connection


@router.put("/{connection_id}", response_model=MCPConnection)
async def update_connection(connection_id: str, update: MCPConnectionUpdate):
    """Update an MCP connection"""
    try:
        updated_connection = await mcp_connection_service.update_connection(connection_id, update)
        if not updated_connection:
            raise HTTPException(status_code=404, detail="MCP connection not found")
        return updated_connection
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update MCP connection: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update MCP connection")


@router.delete("/{connection_id}")
async def delete_connection(connection_id: str):
    """Delete an MCP connection"""
    try:
        success = await mcp_connection_service.delete_connection(connection_id)
        if not success:
            raise HTTPException(status_code=404, detail="MCP connection not found")
        return {"message": "MCP connection deleted successfully"}
    except Exception as e:
        logger.error(f"Failed to delete MCP connection: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete MCP connection")


@router.post("/{connection_id}/test", response_model=MCPConnectionTest)
async def test_connection(connection_id: str):
    """Test an MCP connection"""
    try:
        # Check if connection exists
        connection = await mcp_connection_service.get_connection(connection_id)
        if not connection:
            raise HTTPException(status_code=404, detail="MCP connection not found")
        
        # Test the connection
        test_result = await mcp_client_service.test_connection(connection_id)
        return test_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to test MCP connection: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to test MCP connection")


@router.post("/{connection_id}/sync")
async def sync_connection(connection_id: str):
    """Synchronize tools and capabilities from MCP server"""
    try:
        # Check if connection exists
        connection = await mcp_connection_service.get_connection(connection_id)
        if not connection:
            raise HTTPException(status_code=404, detail="MCP connection not found")
        
        # Sync server info
        cache = await mcp_client_service.sync_server_info(connection_id)
        if not cache:
            raise HTTPException(status_code=500, detail="Failed to synchronize server information")
        
        return {
            "message": "Server synchronized successfully",
            "tools_count": len(cache.tools),
            "resources_count": len(cache.resources),
            "prompts_count": len(cache.prompts),
            "cached_at": cache.cached_at.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to sync MCP connection: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to sync MCP connection")


@router.get("/{connection_id}/tools")
async def get_connection_tools(connection_id: str):
    """Get available tools from an MCP connection"""
    try:
        # Check if connection exists
        connection = await mcp_connection_service.get_connection(connection_id)
        if not connection:
            raise HTTPException(status_code=404, detail="MCP connection not found")
        
        # Get tools
        tools = await mcp_client_service.get_available_tools(connection_id)
        return {
            "connection_id": connection_id,
            "connection_name": connection.name,
            "tools": tools,
            "tools_count": len(tools)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get tools: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get tools")


@router.get("/{connection_id}/resources")
async def get_connection_resources(connection_id: str):
    """Get available resources from an MCP connection"""
    try:
        # Check if connection exists
        connection = await mcp_connection_service.get_connection(connection_id)
        if not connection:
            raise HTTPException(status_code=404, detail="MCP connection not found")
        
        # Get resources
        resources = await mcp_client_service.get_resources(connection_id)
        return {
            "connection_id": connection_id,
            "connection_name": connection.name,
            "resources": resources,
            "resources_count": len(resources)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get resources: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get resources")


@router.get("/{connection_id}/prompts")
async def get_connection_prompts(connection_id: str):
    """Get available prompts from an MCP connection"""
    try:
        # Check if connection exists
        connection = await mcp_connection_service.get_connection(connection_id)
        if not connection:
            raise HTTPException(status_code=404, detail="MCP connection not found")
        
        # Get prompts
        prompts = await mcp_client_service.get_prompts(connection_id)
        return {
            "connection_id": connection_id,
            "connection_name": connection.name,
            "prompts": prompts,
            "prompts_count": len(prompts)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get prompts: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get prompts")


@router.post("/{connection_id}/tools/{tool_name}/execute", response_model=MCPToolResult)
async def execute_tool(connection_id: str, tool_name: str, tool_call: MCPToolCall):
    """Execute a tool on an MCP server"""
    try:
        # Check if connection exists
        connection = await mcp_connection_service.get_connection(connection_id)
        if not connection:
            raise HTTPException(status_code=404, detail="MCP connection not found")
        
        # Validate connection_id matches
        if tool_call.connection_id != connection_id:
            raise HTTPException(status_code=400, detail="Connection ID mismatch")
        
        # Validate tool_name matches
        if tool_call.tool_name != tool_name:
            raise HTTPException(status_code=400, detail="Tool name mismatch")
        
        # Execute the tool
        result = await mcp_client_service.execute_tool(
            connection_id, 
            tool_name, 
            tool_call.parameters
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to execute tool: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to execute tool")


# Authentication endpoints
@router.get("/{connection_id}/auth")
async def get_auth_status(connection_id: str):
    """Get authentication status for a connection"""
    try:
        # Check if connection exists
        connection = await mcp_connection_service.get_connection(connection_id)
        if not connection:
            raise HTTPException(status_code=404, detail="MCP connection not found")
        
        # Get auth info
        auth = await mcp_auth_service.get_auth(connection_id)
        is_valid = await mcp_auth_service.is_token_valid(connection_id) if auth else False
        
        return {
            "connection_id": connection_id,
            "auth_type": connection.auth_type,
            "has_auth": auth is not None,
            "is_valid": is_valid,
            "expires_at": auth.expires_at.isoformat() if auth and auth.expires_at else None,
            "scopes": auth.scopes if auth else []
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get auth status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get auth status")


@router.post("/{connection_id}/auth/oauth")
async def start_oauth_flow(connection_id: str, auth_config: Dict[str, Any]):
    """Start OAuth authentication flow"""
    try:
        # Check if connection exists
        connection = await mcp_connection_service.get_connection(connection_id)
        if not connection:
            raise HTTPException(status_code=404, detail="MCP connection not found")
        
        if connection.auth_type != "oauth":
            raise HTTPException(status_code=400, detail="Connection is not configured for OAuth")
        
        # Start OAuth flow
        oauth_data = await mcp_auth_service.start_oauth_flow(connection_id, auth_config)
        return oauth_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start OAuth flow: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to start OAuth flow")


@router.post("/{connection_id}/auth/callback")
async def oauth_callback(connection_id: str, code: str, state: str):
    """Handle OAuth callback"""
    try:
        # Check if connection exists
        connection = await mcp_connection_service.get_connection(connection_id)
        if not connection:
            raise HTTPException(status_code=404, detail="MCP connection not found")
        
        # Handle callback
        auth = await mcp_auth_service.handle_oauth_callback(code, state)
        if not auth:
            raise HTTPException(status_code=400, detail="Invalid OAuth callback")
        
        # Update connection status to active if auth successful
        await mcp_connection_service.update_connection_status(connection_id, "active")
        
        return {
            "message": "OAuth authentication successful",
            "expires_at": auth.expires_at.isoformat() if auth.expires_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to handle OAuth callback: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to handle OAuth callback")


@router.post("/{connection_id}/auth/refresh")
async def refresh_token(connection_id: str):
    """Refresh access token"""
    try:
        # Check if connection exists
        connection = await mcp_connection_service.get_connection(connection_id)
        if not connection:
            raise HTTPException(status_code=404, detail="MCP connection not found")
        
        # Refresh token
        auth = await mcp_auth_service.refresh_token(connection_id)
        if not auth:
            raise HTTPException(status_code=400, detail="Failed to refresh token")
        
        return {
            "message": "Token refreshed successfully",
            "expires_at": auth.expires_at.isoformat() if auth.expires_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to refresh token: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to refresh token")


@router.post("/{connection_id}/auth/api-key")
async def store_api_key(connection_id: str, api_key_data: Dict[str, Any]):
    """Store API key authentication"""
    try:
        # Check if connection exists
        connection = await mcp_connection_service.get_connection(connection_id)
        if not connection:
            raise HTTPException(status_code=404, detail="MCP connection not found")
        
        if connection.auth_type != "api_key":
            raise HTTPException(status_code=400, detail="Connection is not configured for API key auth")
        
        api_key = api_key_data.get("api_key")
        if not api_key:
            raise HTTPException(status_code=400, detail="API key is required")
        
        # Store API key
        auth = await mcp_auth_service.store_api_key(
            connection_id, 
            api_key, 
            api_key_data.get("additional_data")
        )
        
        # Update connection status to active
        await mcp_connection_service.update_connection_status(connection_id, "active")
        
        return {
            "message": "API key stored successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to store API key: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to store API key")


@router.delete("/{connection_id}/auth")
async def delete_auth(connection_id: str):
    """Delete authentication for a connection"""
    try:
        # Check if connection exists
        connection = await mcp_connection_service.get_connection(connection_id)
        if not connection:
            raise HTTPException(status_code=404, detail="MCP connection not found")
        
        # Delete auth
        success = await mcp_auth_service.delete_auth(connection_id)
        
        # Update connection status
        await mcp_connection_service.update_connection_status(connection_id, "auth_required")
        
        return {
            "message": "Authentication deleted successfully" if success else "No authentication found"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete auth: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete auth")


# Management endpoints
@router.get("/sessions/info")
async def get_sessions_info():
    """Get information about active MCP sessions"""
    try:
        return await mcp_client_service.get_session_info()
    except Exception as e:
        logger.error(f"Failed to get sessions info: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get sessions info")


@router.post("/sessions/cleanup")
async def cleanup_sessions(max_idle_minutes: int = 30):
    """Clean up inactive MCP sessions"""
    try:
        cleaned = await mcp_client_service.cleanup_inactive_sessions(max_idle_minutes)
        return {"message": f"Cleaned up {cleaned} inactive sessions"}
    except Exception as e:
        logger.error(f"Failed to cleanup sessions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to cleanup sessions")