"""
Agent Tools for UXMCP Service Creation

This module provides tools that the LLM agent can use to create,
test, debug, and manage services autonomously.
"""

from typing import Dict, Any, List, Optional
from app.services.service_crud import service_crud
from app.models.service import ServiceCreate, ServiceUpdate, ServiceParam
from app.core.dynamic_router import mount_service, unmount_service
from fastapi import FastAPI
import httpx
import json
import logging
import urllib.parse
import subprocess
import pkg_resources

logger = logging.getLogger(__name__)


class AgentTools:
    """Collection of tools for the service creation agent"""
    
    def __init__(self, app: FastAPI):
        self.app = app
        self.base_url = "http://localhost:8000"
    
    async def create_service(
        self,
        name: str,
        service_type: str,
        route: str,
        method: str,
        code: str,
        params: List[Dict[str, Any]],
        dependencies: List[str] = None,
        output_schema: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
        documentation: Optional[str] = None,
        llm_profile: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new service in UXMCP
        
        Returns:
            Dict with 'success', 'service_id', and 'error' (if any)
        """
        try:
            # Convert param dicts to ServiceParam objects
            service_params = []
            for param in params:
                service_params.append(ServiceParam(**param))
            
            # Create service data
            service_data = ServiceCreate(
                name=name,
                service_type=service_type,
                route=route,
                method=method,
                code=code,
                params=service_params,
                dependencies=dependencies or [],
                output_schema=output_schema,
                description=description,
                documentation=documentation,
                llm_profile=llm_profile,
                active=False  # Always create inactive
            )
            
            # Create the service
            service = await service_crud.create(service_data)
            
            return {
                "success": True,
                "service_id": service.id,
                "service": service.dict(),
                "message": f"Service '{name}' created successfully"
            }
            
        except Exception as e:
            logger.error(f"Failed to create service: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    async def update_service_code(
        self,
        service_id: str,
        code: str,
        dependencies: Optional[List[str]] = None,
        output_schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Update the code of an existing service
        
        Returns:
            Dict with 'success' and 'error' (if any)
        """
        try:
            update_data = ServiceUpdate(code=code)
            
            if dependencies is not None:
                update_data.dependencies = dependencies
                
            if output_schema is not None:
                update_data.output_schema = output_schema
            
            service = await service_crud.update(service_id, update_data)
            
            if not service:
                return {
                    "success": False,
                    "error": "Service not found"
                }
            
            return {
                "success": True,
                "message": "Service code updated successfully",
                "service": service.dict()
            }
            
        except Exception as e:
            logger.error(f"Failed to update service code: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    async def activate_service(self, service_id: str) -> Dict[str, Any]:
        """
        Activate a service and mount its route
        
        Returns:
            Dict with 'success', 'active' status, and 'error' (if any)
        """
        try:
            # Get the service
            service = await service_crud.get(service_id)
            if not service:
                return {
                    "success": False,
                    "error": "Service not found"
                }
            
            if service.active:
                return {
                    "success": True,
                    "active": True,
                    "message": "Service is already active"
                }
            
            # Mount the service route
            await mount_service(self.app, service)
            
            # Update service status
            activated_service = await service_crud.activate(service_id)
            
            return {
                "success": True,
                "active": True,
                "message": f"Service '{service.name}' activated successfully"
            }
            
        except Exception as e:
            logger.error(f"Failed to activate service: {str(e)}")
            return {
                "success": False,
                "active": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "hint": "Check service code and dependencies"
            }
    
    async def deactivate_service(self, service_id: str) -> Dict[str, Any]:
        """
        Deactivate a service
        
        Returns:
            Dict with 'success' and 'error' (if any)
        """
        try:
            # Get the service
            service = await service_crud.get(service_id)
            if not service:
                return {
                    "success": False,
                    "error": "Service not found"
                }
            
            if not service.active:
                return {
                    "success": True,
                    "message": "Service is already inactive"
                }
            
            # Unmount the service route
            await unmount_service(self.app, service)
            
            # Update service status
            deactivated_service = await service_crud.deactivate(service_id)
            
            return {
                "success": True,
                "message": f"Service '{service.name}' deactivated successfully"
            }
            
        except Exception as e:
            logger.error(f"Failed to deactivate service: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def test_service(
        self,
        service_id: str,
        test_params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Test a service by calling its endpoint
        
        Returns:
            Dict with 'success', 'response', 'status_code', and 'error' (if any)
        """
        try:
            # Get the service
            service = await service_crud.get(service_id)
            if not service:
                return {
                    "success": False,
                    "error": "Service not found"
                }
            
            if not service.active:
                return {
                    "success": False,
                    "error": "Service is not active. Activate it first."
                }
            
            # Build the URL
            url = f"{self.base_url}{service.route}"
            params = test_params or {}
            
            # Log what we're testing
            logger.info(f"Testing service {service.name} with params: {params}")
            
            # Separate path params from body/query params
            path_params = {}
            other_params = {}
            
            for param_name, param_value in params.items():
                if f"{{{param_name}}}" in service.route:
                    path_params[param_name] = param_value
                else:
                    other_params[param_name] = param_value
            
            # Replace path parameters in URL
            for param_name, param_value in path_params.items():
                url = url.replace(f"{{{param_name}}}", str(param_value))
            
            # Make the request
            async with httpx.AsyncClient(timeout=30.0) as client:
                if service.method == "GET":
                    # For GET, non-path params go as query params
                    query_params = {}
                    for k, v in other_params.items():
                        # Convert complex objects to JSON strings for query params
                        if isinstance(v, (dict, list)):
                            query_params[k] = json.dumps(v)
                        else:
                            query_params[k] = v
                    response = await client.get(url, params=query_params)
                elif service.method == "POST":
                    # For POST, send all non-path params in body
                    response = await client.post(url, json=other_params)
                elif service.method == "PUT":
                    response = await client.put(url, json=params)
                elif service.method == "DELETE":
                    response = await client.delete(url)
                else:
                    response = await client.request(service.method, url, json=params)
            
            # Parse response
            try:
                response_data = response.json()
            except:
                response_data = response.text
            
            # Log the response for debugging
            logger.info(f"Test response: status={response.status_code}, data={response_data}")
            
            # Extract error details if available
            error_detail = None
            if response.status_code >= 400:
                if isinstance(response_data, dict):
                    # FastAPI error format
                    error_detail = response_data.get('detail', response_data.get('error', str(response_data)))
                else:
                    error_detail = str(response_data)
            
            return {
                "success": response.status_code < 400,
                "status_code": response.status_code,
                "response": response_data,
                "error": error_detail,
                "url": url,
                "method": service.method,
                "test_params": params  # Include what params were used
            }
            
        except Exception as e:
            logger.error(f"Failed to test service: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    async def get_service_logs(
        self,
        service_id: str,
        limit: int = 50,
        level: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get recent logs for a service
        
        Returns:
            Dict with 'success', 'logs' array, and 'error' (if any)
        """
        try:
            async with httpx.AsyncClient() as client:
                params = {"limit": limit}
                if level:
                    params["level"] = level
                    
                response = await client.get(
                    f"{self.base_url}/logs/services/{service_id}/latest",
                    params=params
                )
                
                if response.status_code == 200:
                    logs = response.json()
                    
                    # Simplify logs for agent
                    simplified_logs = []
                    for log in logs:
                        simplified_logs.append({
                            "timestamp": log.get("timestamp"),
                            "level": log.get("level"),
                            "message": log.get("message"),
                            "details": log.get("details", {})
                        })
                    
                    return {
                        "success": True,
                        "logs": simplified_logs,
                        "count": len(simplified_logs)
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Failed to fetch logs: {response.status_code}"
                    }
                    
        except Exception as e:
            logger.error(f"Failed to get service logs: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_service_details(self, service_id: str) -> Dict[str, Any]:
        """
        Get full details of a service
        
        Returns:
            Dict with 'success', 'service' details, and 'error' (if any)
        """
        try:
            service = await service_crud.get(service_id)
            if not service:
                return {
                    "success": False,
                    "error": "Service not found"
                }
            
            return {
                "success": True,
                "service": service.dict()
            }
            
        except Exception as e:
            logger.error(f"Failed to get service details: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def analyze_error(
        self,
        error_message: str,
        code: str,
        error_type: str = None
    ) -> Dict[str, Any]:
        """
        Analyze an error and suggest fixes
        
        Returns:
            Dict with analysis and suggestions
        """
        # Common error patterns and solutions
        error_patterns = {
            "ModuleNotFoundError": {
                "pattern": r"No module named '(\w+)'",
                "suggestion": "Add '{module}' to the dependencies list"
            },
            "NameError": {
                "pattern": r"name '(\w+)' is not defined",
                "suggestion": "Variable '{name}' is not defined. Check spelling or import it."
            },
            "KeyError": {
                "pattern": r"KeyError: '(\w+)'",
                "suggestion": "Use params.get('{key}', default_value) instead of params['{key}']"
            },
            "TypeError": {
                "pattern": r"unsupported operand type",
                "suggestion": "Check parameter types. Convert strings to numbers if needed."
            },
            "AttributeError": {
                "pattern": r"'(\w+)' object has no attribute '(\w+)'",
                "suggestion": "The object doesn't have that attribute. Check the API documentation."
            }
        }
        
        import re
        
        suggestions = []
        specific_fix = None
        
        # SPECIFIC CHECK FOR datetime.utcnow() error
        if "module 'datetime' has no attribute 'utcnow'" in error_message:
            suggestions.append("Use datetime.datetime.utcnow() instead of datetime.utcnow()")
            specific_fix = {
                "find": "datetime.utcnow()",
                "replace": "datetime.datetime.utcnow()",
                "explanation": "When importing datetime as a module, you need to use datetime.datetime.utcnow()"
            }
        
        # CHECK FOR from X import Y errors
        if "is not defined" in error_message:
            # Extract the undefined name
            match = re.search(r"name '(\w+)' is not defined", error_message)
            if match:
                undefined_name = match.group(1)
                
                # Check if it's likely an import issue
                import_patterns = {
                    "unquote": ("urllib.parse", "urllib.parse.unquote"),
                    "quote": ("urllib.parse", "urllib.parse.quote"),
                    "urlencode": ("urllib.parse", "urllib.parse.urlencode"),
                    "BeautifulSoup": ("bs4", "bs4.BeautifulSoup"),
                    "Image": ("PIL", "PIL.Image"),
                    "datetime": ("datetime", "datetime.datetime"),
                    "timedelta": ("datetime", "datetime.timedelta"),
                    "join": ("os.path", "os.path.join"),
                    "exists": ("os.path", "os.path.exists"),
                    "basename": ("os.path", "os.path.basename"),
                    "dirname": ("os.path", "os.path.dirname"),
                }
                
                if undefined_name in import_patterns:
                    module, full_path = import_patterns[undefined_name]
                    suggestions.append(f"Use {full_path}() instead of importing {undefined_name}")
                    specific_fix = {
                        "undefined": undefined_name,
                        "module": module,
                        "solution": f"Replace '{undefined_name}' with '{full_path}'",
                        "explanation": "The dynamic environment requires full module paths"
                    }
                elif any(f"from {mod}" in code for mod in ["urllib", "datetime", "os", "bs4", "PIL"]):
                    suggestions.append("Remove 'from X import Y' and use full module paths instead")
                    specific_fix = {
                        "pattern": "from X import Y",
                        "solution": f"Find where '{undefined_name}' is imported and use full module path",
                        "explanation": "The dynamic environment doesn't support 'from X import Y' syntax"
                    }
        
        # Check for import errors
        if "No module named" in error_message:
            match = re.search(r"No module named '(\w+)'", error_message)
            if match:
                module = match.group(1)
                suggestions.append(f"Add '{module}' to the dependencies list")
        
        # Check for undefined variables
        if "is not defined" in error_message:
            match = re.search(r"name '(\w+)' is not defined", error_message)
            if match:
                var_name = match.group(1)
                if var_name in ['datetime', 'json', 'math', 'random']:
                    suggestions.append(f"Import {var_name} module")
                else:
                    suggestions.append(f"Define {var_name} or check spelling")
        
        # Check for key errors
        if "KeyError" in error_message:
            suggestions.append("Use .get() method with default values for dictionary access")
        
        # Check for handler function
        if "handler" in error_message and "not found" in error_message:
            suggestions.append("Make sure your function is named exactly 'handler'")
        
        # Check for JSON serialization errors
        if "is not JSON serializable" in error_message:
            suggestions.append("Convert non-serializable objects (datetime, etc.) to strings")
        
        return {
            "error_message": error_message,
            "error_type": error_type,
            "suggestions": suggestions,
            "specific_fix": specific_fix,
            "common_fix": suggestions[0] if suggestions else "Review the error message and code"
        }
    
    def get_tools_list(self) -> List[Dict[str, Any]]:
        """
        Get a list of all available tools with their descriptions
        
        Returns:
            List of tool definitions for the agent
        """
        return [
            {
                "name": "create_service",
                "description": "Create a new UXMCP service with specified configuration",
                "parameters": ["name", "service_type", "route", "method", "code", "params", "dependencies", "output_schema"]
            },
            {
                "name": "update_service_code", 
                "description": "Update the code and dependencies of an existing service",
                "parameters": ["service_id", "code", "dependencies", "output_schema"]
            },
            {
                "name": "activate_service",
                "description": "Activate a service to make it available at its endpoint",
                "parameters": ["service_id"]
            },
            {
                "name": "test_service",
                "description": "Test a service by calling its endpoint with parameters",
                "parameters": ["service_id", "test_params"]
            },
            {
                "name": "get_service_logs",
                "description": "Get recent logs for a service to debug errors",
                "parameters": ["service_id", "limit", "level"]
            },
            {
                "name": "analyze_error",
                "description": "Analyze an error message and suggest fixes",
                "parameters": ["error_message", "code", "error_type"]
            },
            {
                "name": "list_installed_packages",
                "description": "List all installed Python packages in the environment",
                "parameters": []
            },
            {
                "name": "check_package_available",
                "description": "Check if a package is available on PyPI",
                "parameters": ["package_name"]
            },
            {
                "name": "install_package",
                "description": "Install a Python package using pip",
                "parameters": ["package_name", "version"]
            },
            {
                "name": "analyze_code_imports",
                "description": "Analyze Python code to find all import statements and needed packages",
                "parameters": ["code"]
            },
            {
                "name": "validate_code_syntax",
                "description": "Validate Python code and detect problematic patterns like 'from X import Y'",
                "parameters": ["code"]
            }
        ]
    
    async def validate_code_syntax(self, code: str) -> Dict[str, Any]:
        """
        Validate Python code and detect problematic patterns
        
        Returns:
            Dict with 'valid', 'issues' list, and suggested fixes
        """
        try:
            import ast
            import re
            
            issues = []
            fixes = []
            
            # Check for 'from X import Y' patterns
            from_import_pattern = r'^\s*from\s+(\S+)\s+import\s+(.+)$'
            lines = code.split('\n')
            
            for i, line in enumerate(lines):
                match = re.match(from_import_pattern, line)
                if match:
                    module = match.group(1)
                    imports = match.group(2)
                    
                    # Special handling for common cases
                    if module == 'bs4' and 'BeautifulSoup' in imports:
                        issues.append({
                            "line": i + 1,
                            "issue": f"'from bs4 import BeautifulSoup' will not work in dynamic environment",
                            "fix": "Replace with 'import bs4' and use 'bs4.BeautifulSoup()'"
                        })
                        fixes.append({
                            "find": line,
                            "replace": "import bs4",
                            "usage_change": "BeautifulSoup(...) → bs4.BeautifulSoup(...)"
                        })
                    elif module == 'PIL' and 'Image' in imports:
                        issues.append({
                            "line": i + 1,
                            "issue": f"'from PIL import Image' will not work in dynamic environment",
                            "fix": "Replace with 'import PIL' and use 'PIL.Image'"
                        })
                        fixes.append({
                            "find": line,
                            "replace": "import PIL",
                            "usage_change": "Image.open(...) → PIL.Image.open(...)"
                        })
                    else:
                        issues.append({
                            "line": i + 1,
                            "issue": f"'from {module} import {imports}' may not work in dynamic environment",
                            "fix": f"Replace with 'import {module}' and use '{module}.{imports}'"
                        })
            
            # Try to parse with AST to check syntax
            try:
                ast.parse(code)
                syntax_valid = True
            except SyntaxError as e:
                syntax_valid = False
                issues.append({
                    "line": e.lineno,
                    "issue": f"Syntax error: {e.msg}",
                    "fix": "Fix the syntax error"
                })
            
            return {
                "success": True,
                "valid": syntax_valid and len(issues) == 0,
                "syntax_valid": syntax_valid,
                "issues": issues,
                "fixes": fixes,
                "has_from_imports": len(fixes) > 0
            }
            
        except Exception as e:
            logger.error(f"Failed to validate code: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def analyze_code_imports(self, code: str) -> Dict[str, Any]:
        """
        Analyze Python code to extract all import statements
        
        Returns:
            Dict with 'success', 'imports' list, and 'error' (if any)
        """
        try:
            import ast
            import re
            
            imports = []
            modules_to_check = set()
            
            # Try to parse with AST first
            try:
                tree = ast.parse(code)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            imports.append({
                                "type": "import",
                                "module": alias.name,
                                "alias": alias.asname
                            })
                            # Get the base module name
                            base_module = alias.name.split('.')[0]
                            modules_to_check.add(base_module)
                            
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            imports.append({
                                "type": "from",
                                "module": node.module,
                                "names": [alias.name for alias in node.names]
                            })
                            # Get the base module name
                            base_module = node.module.split('.')[0]
                            modules_to_check.add(base_module)
                            
            except SyntaxError:
                # Fallback to regex if AST parsing fails
                # Match 'import module' or 'import module as alias'
                import_pattern = r'^\s*import\s+([a-zA-Z_][a-zA-Z0-9_\.]*)'
                # Match 'from module import ...'
                from_pattern = r'^\s*from\s+([a-zA-Z_][a-zA-Z0-9_\.]*)\s+import'
                
                for line in code.split('\n'):
                    import_match = re.match(import_pattern, line)
                    if import_match:
                        module = import_match.group(1)
                        base_module = module.split('.')[0]
                        modules_to_check.add(base_module)
                        
                    from_match = re.match(from_pattern, line)
                    if from_match:
                        module = from_match.group(1)
                        base_module = module.split('.')[0]
                        modules_to_check.add(base_module)
            
            # Check which modules need to be installed
            stdlib_modules = {
                'os', 'sys', 'json', 'datetime', 'time', 're', 'math', 'random',
                'urllib', 'http', 'collections', 'itertools', 'functools', 'hashlib',
                'base64', 'string', 'io', 'pathlib', 'subprocess', 'threading',
                'multiprocessing', 'logging', 'traceback', 'inspect', 'importlib',
                'ast', 'statistics', 'decimal', 'fractions', 'uuid', 'platform',
                'socket', 'ssl', 'email', 'html', 'xml', 'csv', 'sqlite3'
            }
            
            # Remove stdlib modules
            external_modules = modules_to_check - stdlib_modules
            
            # Map import names to package names
            package_map = {
                'bs4': 'beautifulsoup4',
                'PIL': 'pillow',
                'cv2': 'opencv-python',
                'sklearn': 'scikit-learn',
                'yaml': 'pyyaml',
                'dateutil': 'python-dateutil',
                'MySQLdb': 'mysqlclient',
                'psycopg2': 'psycopg2-binary',
                'dotenv': 'python-dotenv',
                'google': 'protobuf',  # or other google packages
                'OpenSSL': 'pyopenssl',
                'lxml': 'lxml',
                'numpy': 'numpy',
                'pandas': 'pandas',
                'matplotlib': 'matplotlib',
                'seaborn': 'seaborn',
                'scipy': 'scipy',
                'nltk': 'nltk',
                'torch': 'torch',
                'tensorflow': 'tensorflow',
                'requests': 'requests',
                'httpx': 'httpx',
                'aiohttp': 'aiohttp',
                'flask': 'flask',
                'fastapi': 'fastapi',
                'pydantic': 'pydantic'
            }
            
            # Convert to package names
            packages_needed = []
            for module in external_modules:
                package_name = package_map.get(module, module)
                packages_needed.append({
                    "import_name": module,
                    "package_name": package_name
                })
            
            return {
                "success": True,
                "imports": imports,
                "modules_found": list(modules_to_check),
                "external_modules": list(external_modules),
                "packages_needed": packages_needed
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze imports: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def list_installed_packages(self) -> Dict[str, Any]:
        """
        List all installed Python packages
        
        Returns:
            Dict with 'success', 'packages' list, and 'error' (if any)
        """
        try:
            # Get installed packages
            installed_packages = []
            for pkg in pkg_resources.working_set:
                installed_packages.append({
                    "name": pkg.key,
                    "version": pkg.version,
                    "location": pkg.location
                })
            
            # Sort by name
            installed_packages.sort(key=lambda x: x["name"])
            
            return {
                "success": True,
                "packages": installed_packages,
                "count": len(installed_packages)
            }
            
        except Exception as e:
            logger.error(f"Failed to list packages: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def check_package_available(self, package_name: str) -> Dict[str, Any]:
        """
        Check if a package is available on PyPI
        
        Returns:
            Dict with 'success', 'available', 'info', and 'error' (if any)
        """
        try:
            # Use pip to search for package info
            result = subprocess.run(
                ["pip", "index", "versions", package_name],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                # Parse the output to get available versions
                output = result.stdout
                available = package_name in output
                
                # Extract version info if available
                versions = []
                if available and "Available versions:" in output:
                    lines = output.split('\n')
                    for i, line in enumerate(lines):
                        if "Available versions:" in line and i + 1 < len(lines):
                            version_line = lines[i + 1].strip()
                            versions = [v.strip() for v in version_line.split(',')][:10]  # First 10 versions
                            break
                
                return {
                    "success": True,
                    "available": available,
                    "package_name": package_name,
                    "versions": versions,
                    "info": output if available else f"Package '{package_name}' not found on PyPI"
                }
            else:
                return {
                    "success": True,
                    "available": False,
                    "package_name": package_name,
                    "error": result.stderr or f"Package '{package_name}' not found"
                }
                
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Command timed out"
            }
        except Exception as e:
            logger.error(f"Failed to check package: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def install_package(
        self, 
        package_name: str, 
        version: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Install a Python package using pip
        
        Returns:
            Dict with 'success', 'message', and 'error' (if any)
        """
        try:
            # Construct package specification
            package_spec = package_name
            if version:
                package_spec = f"{package_name}=={version}"
            
            logger.info(f"Installing package: {package_spec}")
            
            # Run pip install
            result = subprocess.run(
                ["pip", "install", package_spec],
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )
            
            if result.returncode == 0:
                # Check if package is now installed
                try:
                    pkg = pkg_resources.get_distribution(package_name)
                    installed_version = pkg.version
                    
                    return {
                        "success": True,
                        "message": f"Successfully installed {package_name} version {installed_version}",
                        "package": package_name,
                        "version": installed_version,
                        "output": result.stdout
                    }
                except:
                    # Package might be installed but not immediately available
                    return {
                        "success": True,
                        "message": f"Package {package_spec} installed (may require restart)",
                        "package": package_name,
                        "output": result.stdout
                    }
            else:
                return {
                    "success": False,
                    "error": f"Failed to install {package_spec}",
                    "stderr": result.stderr,
                    "stdout": result.stdout
                }
                
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Installation timed out after 5 minutes"
            }
        except Exception as e:
            logger.error(f"Failed to install package: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }