from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional
import json
import traceback
import ast
import sys
import importlib
import asyncio
import inspect
import re
import uuid
from functools import wraps
from app.models.service import Service
from app.core.mcp_manager import mcp_manager
from app.core.mongodb_logger import ServiceLogger
from app.core.service_logger import SimpleServiceLogger, create_service_logger_class
from app.core.database import get_database
import logging

logger = logging.getLogger(__name__)


def create_handler(service: Service):
    """Create a dynamic handler function from service definition"""
    
    # Extract path parameters from route
    path_params = []
    pattern = re.compile(r'\{(\w+)\}')
    matches = pattern.findall(service.route)
    for match in matches:
        path_params.append(match)
    
    # Create function code with correct signature
    param_list = ['request: Request']
    param_list.extend([f'{p}: str' for p in path_params])
    params_signature = ', '.join(param_list)
    
    # Build the params dict initialization
    params_init = '{'
    if path_params:
        params_init += ', '.join([f'"{p}": {p}' for p in path_params])
    params_init += '}'
    
    # Generate the function code
    func_code = f'''
async def dynamic_handler({params_signature}):
    # Generate unique execution ID
    execution_id = str(uuid.uuid4())
    
    # Get database for logging
    db = get_database()
    
    # Create service logger
    async_logger = ServiceLogger(db, service.id, service.name, execution_id)
    simple_logger = SimpleServiceLogger(async_logger)
    
    try:
        # Start with path parameters
        params = {params_init}
        
        # Add query parameters
        for key, value in request.query_params.items():
            params[key] = value
        
        # Add body parameters for POST/PUT/PATCH
        if service.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.json()
                if isinstance(body, dict):
                    params.update(body)
            except:
                pass
        
        # Log request data
        async_logger.set_request_data({{
            "method": service.method,
            "route": service.route,
            "params": params,
            "query": dict(request.query_params),
            "headers": dict(request.headers)
        }})
        
        await async_logger.info(f"Service execution started", params=params)
        
        # Create logger class for dynamic code
        DynamicLogger = create_service_logger_class()
        logger_instance = DynamicLogger()
        logger_instance._logger = simple_logger
        
        # Create a safe execution environment
        local_vars = {{
            "params": params,
            "logger": logger_instance,
            "log": logger_instance  # Alias for convenience
        }}
        global_vars = {{
            "__builtins__": __builtins__,
            "json": json,
            "HTTPException": HTTPException,
            "random": __import__("random"),
            "datetime": __import__("datetime"),
            "platform": __import__("platform"),
            "os": __import__("os"),
            "httpx": __import__("httpx"),
            "asyncio": __import__("asyncio"),
            "urllib": __import__("urllib"),
            "urllib.parse": __import__("urllib.parse"),
            "urllib.request": __import__("urllib.request"),
            "math": __import__("math"),
            "re": __import__("re"),
            "hashlib": __import__("hashlib"),
            "base64": __import__("base64"),
            "time": __import__("time"),
            "sys": __import__("sys"),
        }}
        
        # Import dependencies - simplified approach
        # Known package to module mappings
        package_mappings = {{
            "beautifulsoup4": "bs4",
            "pillow": "PIL",
            "scikit-learn": "sklearn",
            "opencv-python": "cv2",
            "pyyaml": "yaml",
            "python-dateutil": "dateutil",
            "mysqlclient": "MySQLdb",
            "psycopg2-binary": "psycopg2",
            "python-dotenv": "dotenv",
            "lxml": "lxml",
            "numpy": "numpy",
            "pandas": "pandas",
            "matplotlib": "matplotlib",
            "seaborn": "seaborn",
            "scipy": "scipy",
            "nltk": "nltk",
            "torch": "torch",
            "tensorflow": "tensorflow",
            "requests": "requests",
            "httpx": "httpx",
            "aiohttp": "aiohttp",
            "flask": "flask",
            "fastapi": "fastapi",
            "pydantic": "pydantic"
        }}
        
        for dep in service.dependencies:
            try:
                # Get the correct import name
                import_name = package_mappings.get(dep, dep)
                
                # Try to import the module
                if import_name in sys.modules:
                    module = sys.modules[import_name]
                else:
                    module = importlib.import_module(import_name)
                
                # Make the module available in the execution context
                global_vars[import_name] = module
                # Also make it available under the package name if different
                if dep != import_name:
                    global_vars[dep] = module
                
                # For beautifulsoup4, also make BeautifulSoup directly available
                if dep == "beautifulsoup4" and hasattr(module, 'BeautifulSoup'):
                    global_vars['BeautifulSoup'] = module.BeautifulSoup
                
                # For PIL/pillow, make Image directly available
                if dep == "pillow" and hasattr(module, 'Image'):
                    global_vars['Image'] = module.Image
                
                # Add common submodules to global_vars for easier access
                # This allows code to use things like urllib.parse without explicit import
                if import_name == "urllib":
                    import urllib.parse
                    import urllib.request
                    import urllib.error
                    # Make submodules available as attributes
                    module.parse = urllib.parse
                    module.request = urllib.request
                    module.error = urllib.error
                    # Also make them directly available
                    global_vars['urllib.parse'] = urllib.parse
                    global_vars['urllib.request'] = urllib.request
                    global_vars['urllib.error'] = urllib.error
                    
                await async_logger.debug(f"Loaded dependency: {{dep}} (imported as {{import_name}})")
                
            except ImportError as e:
                await async_logger.error(f"Failed to import dependency {{dep}}", error=str(e))
                raise HTTPException(status_code=500, detail=f"Missing dependency: {{dep}}")
        
        # Execute the service code
        exec(service.code, global_vars, local_vars)
        
        # The service code should define a handler function
        if "handler" not in local_vars:
            await async_logger.error("Service code missing handler function")
            raise HTTPException(status_code=500, detail="Service code must define a 'handler' function")
        
        handler = local_vars["handler"]
        
        # Call the handler with params
        await async_logger.debug("Calling handler function")
        result = await handler(**params) if asyncio.iscoroutinefunction(handler) else handler(**params)
        
        await async_logger.info("Service execution completed successfully", result_type=type(result).__name__)
        
        # Return JSON response with execution_id in headers
        if isinstance(result, dict) or isinstance(result, list):
            return JSONResponse(content=result, headers={{"X-Execution-ID": execution_id}})
        else:
            return JSONResponse(content={{"result": result}}, headers={{"X-Execution-ID": execution_id}})
            
    except HTTPException as e:
        await async_logger.error(f"HTTP Exception: {{e.status_code}}", detail=e.detail)
        raise
    except Exception as e:
        await async_logger.error(f"Service execution error", error=str(e), traceback=traceback.format_exc())
        logger.error(f"Error executing service {{service.name}}: {{str(e)}}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Service execution error: {{str(e)}}")
'''
    
    # Execute the generated code
    namespace = {
        'Request': Request,
        'JSONResponse': JSONResponse,
        'HTTPException': HTTPException,
        'service': service,
        'logger': logger,
        'json': json,
        'sys': sys,
        'importlib': importlib,
        'asyncio': asyncio,
        'traceback': traceback,
        'uuid': uuid,
        'get_database': get_database,
        'ServiceLogger': ServiceLogger,
        'SimpleServiceLogger': SimpleServiceLogger,
        'create_service_logger_class': create_service_logger_class,
        '__builtins__': __builtins__
    }
    
    exec(func_code, namespace)
    return namespace['dynamic_handler']


async def mount_service(app: FastAPI, service: Service):
    """Mount a service as a dynamic route"""
    try:
        # Create the handler
        handler = create_handler(service)
        
        # Add the route
        app.add_api_route(
            path=service.route,
            endpoint=handler,
            methods=[service.method],
            name=f"dynamic_{service.name}",
            tags=["Dynamic Services"],
            summary=service.description or f"Dynamic service: {service.name}",
            response_model=None
        )
        
        # Register with MCP
        await mcp_manager.register_service(service)
        
        logger.info(f"Mounted service {service.name} at {service.method} {service.route}")
        
    except Exception as e:
        logger.error(f"Failed to mount service {service.name}: {str(e)}")
        raise


async def unmount_service(app: FastAPI, service: Service):
    """Unmount a service from dynamic routes"""
    try:
        # Remove from FastAPI routes
        app.router.routes = [
            route for route in app.router.routes 
            if not (hasattr(route, "path") and route.path == service.route and 
                   hasattr(route, "methods") and service.method in route.methods)
        ]
        
        # Unregister from MCP
        await mcp_manager.unregister_service(service.name)
        
        logger.info(f"Unmounted service {service.name} from {service.method} {service.route}")
        
    except Exception as e:
        logger.error(f"Failed to unmount service {service.name}: {str(e)}")
        raise


async def mount_all_active_services(app: FastAPI):
    """Mount all active services on startup"""
    from app.services.service_crud import service_crud
    
    try:
        active_services = await service_crud.list(active_only=True)
        for service in active_services:
            try:
                await mount_service(app, service)
            except Exception as e:
                logger.error(f"Failed to mount service {service.name} on startup: {str(e)}")
                # Continue with other services
                
    except Exception as e:
        logger.error(f"Failed to mount active services on startup: {str(e)}")