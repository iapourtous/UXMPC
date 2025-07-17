from fastapi import APIRouter
from app.core.mcp_manager import mcp_manager
import json

router = APIRouter()

@router.get("/mcp/config")
async def get_mcp_config():
    """Get MCP configuration for clients"""
    # Generate MCP configuration manually
    config = {
        "mcpServers": {
            "uxmcp": {
                "command": "docker",
                "args": ["exec", "-i", "uxmcp_api_1", "python", "-m", "fastmcp", "run", "app.main:mcp_server"],
                "env": {
                    "PYTHONPATH": "/app"
                }
            }
        }
    }
    return config

@router.get("/mcp/info")
async def get_mcp_info():
    """Get information about available MCP capabilities"""
    mcp = mcp_manager.mcp
    
    # Get registered tools from our manager
    tools = []
    for name, tool in mcp_manager.tools.items():
        tools.append({
            "name": name,
            "description": f"Dynamic tool: {name}"
        })
    
    # Get resources
    resources = []
    for name, resource in mcp_manager.resources.items():
        resources.append({
            "name": name,
            "uri": f"resource://{name}",
            "description": f"Dynamic resource: {name}",
            "mime_type": "text/plain"
        })
    
    # Get prompts
    prompts = []
    for name, prompt in mcp_manager.prompts.items():
        prompts.append({
            "name": name,
            "description": f"Dynamic prompt: {name}"
        })
    
    return {
        "server_name": "UXMCP Dynamic Services",
        "capabilities": {
            "tools": len(tools),
            "resources": len(resources),
            "prompts": len(prompts)
        },
        "tools": tools,
        "resources": resources,
        "prompts": prompts
    }