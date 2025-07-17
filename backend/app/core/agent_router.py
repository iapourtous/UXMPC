from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from typing import Union, Dict, Any
import json
import logging
from app.models.agent import Agent, AgentExecution
from app.services.agent_executor import agent_executor

logger = logging.getLogger(__name__)


def create_agent_handler(agent: Agent):
    """Create a dynamic handler function for an agent endpoint"""
    
    async def agent_handler(request: Request):
        try:
            # Parse request body
            if agent.input_schema == "text":
                # For text input, try to get raw body
                body = await request.body()
                try:
                    # Try to decode as text
                    input_data = body.decode('utf-8')
                except:
                    # If it's JSON, extract the text content
                    data = await request.json()
                    if isinstance(data, str):
                        input_data = data
                    elif isinstance(data, dict) and "text" in data:
                        input_data = data["text"]
                    elif isinstance(data, dict) and "input" in data:
                        input_data = data["input"]
                    else:
                        raise HTTPException(
                            status_code=400,
                            detail="For text input, send plain text or JSON with 'text' or 'input' field"
                        )
            else:
                # For structured input, expect JSON
                input_data = await request.json()
            
            # Create execution request
            execution_request = AgentExecution(
                input=input_data,
                conversation_history=None,  # Could be extended to support stateful conversations
                execution_options={}
            )
            
            # Execute the agent
            result = await agent_executor.execute(agent, execution_request)
            
            # Handle response based on output schema
            if not result.success:
                raise HTTPException(status_code=500, detail=result.error)
            
            # Return response with execution ID in headers
            headers = {"X-Execution-ID": result.execution_id} if result.execution_id else {}
            
            if agent.output_schema == "text":
                # For text output, return plain text or wrapped in JSON
                if isinstance(result.output, str):
                    return JSONResponse(
                        content={"output": result.output},
                        headers=headers
                    )
                else:
                    return JSONResponse(
                        content={"output": json.dumps(result.output)},
                        headers=headers
                    )
            else:
                # For structured output, return as JSON
                return JSONResponse(
                    content=result.output,
                    headers=headers
                )
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in agent handler for {agent.name}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Agent execution error: {str(e)}")
    
    # Set function name for better debugging
    agent_handler.__name__ = f"agent_{agent.name}_handler"
    
    return agent_handler


async def mount_agent(app: FastAPI, agent: Agent):
    """Mount an agent as a dynamic route"""
    try:
        # Create the handler
        handler = create_agent_handler(agent)
        
        # Add the route
        app.add_api_route(
            path=agent.endpoint,
            endpoint=handler,
            methods=["POST"],  # Agents always use POST for execution
            name=f"agent_{agent.name}",
            tags=["Agents"],
            summary=agent.description or f"Agent: {agent.name}",
            response_model=None
        )
        
        logger.info(f"Mounted agent {agent.name} at POST {agent.endpoint}")
        
    except Exception as e:
        logger.error(f"Failed to mount agent {agent.name}: {str(e)}")
        raise


async def unmount_agent(app: FastAPI, agent: Agent):
    """Unmount an agent from dynamic routes"""
    try:
        # Remove from FastAPI routes
        app.router.routes = [
            route for route in app.router.routes 
            if not (hasattr(route, "path") and route.path == agent.endpoint and 
                   hasattr(route, "methods") and "POST" in route.methods)
        ]
        
        logger.info(f"Unmounted agent {agent.name} from POST {agent.endpoint}")
        
    except Exception as e:
        logger.error(f"Failed to unmount agent {agent.name}: {str(e)}")
        raise


async def mount_all_active_agents(app: FastAPI):
    """Mount all active agents on startup"""
    from app.services.agent_crud import agent_crud
    
    try:
        active_agents = await agent_crud.list(active_only=True)
        for agent in active_agents:
            try:
                await mount_agent(app, agent)
            except Exception as e:
                logger.error(f"Failed to mount agent {agent.name} on startup: {str(e)}")
                # Continue with other agents
                
    except Exception as e:
        logger.error(f"Failed to mount active agents on startup: {str(e)}")