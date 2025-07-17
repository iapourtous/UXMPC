"""
Agent Service for Autonomous Service Creation

This module implements the intelligent agent that can create, test,
debug, and fix services automatically based on natural language descriptions.
"""

import json
import httpx
import asyncio
from typing import Dict, Any, List, Optional, AsyncGenerator
from datetime import datetime
from app.models.llm import LLMProfile
from app.services.llm_crud import llm_crud
from app.core.agent_tools import AgentTools
from app.core.service_documentation import (
    get_service_documentation,
    get_examples_by_type,
    get_common_errors_solutions
)
from app.core.prompt_manager import load_prompt
import logging

logger = logging.getLogger(__name__)


class ServiceCreatorAgent:
    """Autonomous agent for creating UXMCP services"""
    
    def __init__(self, llm_profile: LLMProfile, app):
        self.llm_profile = llm_profile
        self.tools = AgentTools(app)
        self.max_iterations = 30
        self.conversation_history = []
        self._yield_queue = None
        
    async def create_service_from_description(
        self,
        name: str,
        description: str,
        service_type: str = "tool",
        api_documentation: Optional[str] = None,
        api_base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        api_headers: Optional[dict] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Create a service from natural language description.
        Yields progress updates as the agent works.
        """
        # Initialize tracking
        service_id = None
        iteration = 0
        success = False
        
        try:
            # Step 1: Analyze requirements
            yield {
                "step": "analyzing",
                "message": f"Analyzing requirements for '{name}'...",
                "details": {"description": description, "type": service_type}
            }
            
            # Get context documentation
            context = self._build_context(service_type)
            
            # Step 2: Generate initial service
            yield {
                "step": "generating",
                "message": "Generating initial service code...",
                "progress": 10
            }
            
            initial_code = await self._generate_initial_service(
                name, description, service_type, context,
                api_documentation, api_base_url, api_key, api_headers
            )
            
            if not initial_code:
                yield {
                    "step": "error",
                    "message": "Failed to generate initial service code",
                    "error": "LLM generation failed"
                }
                return
            
            # Step 3: Create the service
            yield {
                "step": "creating",
                "message": "Creating service in UXMCP...",
                "progress": 20
            }
            
            create_result = await self.tools.create_service(
                name=initial_code["name"],
                service_type=service_type,
                route=initial_code["route"],
                method=initial_code["method"],
                code=initial_code["code"],
                params=initial_code["params"],
                dependencies=initial_code.get("dependencies", []),
                output_schema=initial_code.get("output_schema"),
                description=description,
                documentation=initial_code.get("documentation"),
                llm_profile=self.llm_profile.name
            )
            
            if not create_result["success"]:
                yield {
                    "step": "error",
                    "message": "Failed to create service",
                    "error": create_result["error"]
                }
                return
            
            service_id = create_result["service_id"]
            
            # Step 3.5: Validate code syntax BEFORE any activation attempt
            yield {
                "step": "validating_code",
                "message": "Validating code syntax and import patterns...",
                "progress": 22
            }
            
            # Validate the code for problematic patterns
            validation_result = await self.tools.validate_code_syntax(initial_code["code"])
            if validation_result["success"] and not validation_result["valid"]:
                yield {
                    "step": "fixing_syntax",
                    "message": "Found code issues, fixing automatically...",
                    "issues": validation_result["issues"],
                    "progress": 23
                }
                
                # Fix the code automatically
                fixed_code = initial_code["code"]
                if validation_result.get("has_from_imports"):
                    # Apply all the fixes
                    for fix in validation_result.get("fixes", []):
                        fixed_code = fixed_code.replace(fix["find"], fix["replace"])
                        # Also update usage patterns
                        if "usage_change" in fix:
                            parts = fix["usage_change"].split(" → ")
                            if len(parts) == 2:
                                fixed_code = fixed_code.replace(parts[0], parts[1])
                    
                    # Update the service code
                    update_result = await self.tools.update_service_code(
                        service_id,
                        fixed_code,
                        initial_code.get("dependencies", [])
                    )
                    
                    if update_result["success"]:
                        yield {
                            "step": "code_fixed",
                            "message": "Fixed import patterns in code",
                            "progress": 24
                        }
                        # Update initial_code for future reference
                        initial_code["code"] = fixed_code
            
            # Step 3.6: Analyze code and install dependencies BEFORE activation
            yield {
                "step": "analyzing_dependencies",
                "message": "Analyzing code dependencies...",
                "progress": 25
            }
            
            # Analyze the code for imports
            import_analysis = await self.tools.analyze_code_imports(initial_code["code"])
            if import_analysis["success"] and import_analysis.get("packages_needed"):
                yield {
                    "step": "installing_dependencies",
                    "message": f"Found {len(import_analysis['packages_needed'])} packages to install",
                    "progress": 30
                }
                
                # Install each needed package
                for pkg_info in import_analysis["packages_needed"]:
                    package_name = pkg_info["package_name"]
                    import_name = pkg_info["import_name"]
                    
                    yield {
                        "step": "checking_package",
                        "message": f"Checking package '{package_name}' (imported as '{import_name}')...",
                        "progress": 35
                    }
                    
                    # Check if package is available
                    check_result = await self.tools.check_package_available(package_name)
                    if check_result["success"] and check_result.get("available"):
                        # Install the package
                        yield {
                            "step": "installing",
                            "message": f"Installing {package_name}...",
                            "progress": 40
                        }
                        
                        install_result = await self.tools.install_package(package_name)
                        if install_result["success"]:
                            yield {
                                "step": "installed",
                                "message": f"Successfully installed {package_name}",
                                "progress": 45
                            }
                        else:
                            yield {
                                "step": "install_warning",
                                "message": f"Could not install {package_name}: {install_result.get('error')}",
                                "progress": 45
                            }
                    else:
                        yield {
                            "step": "package_not_found",
                            "message": f"Package '{package_name}' not found on PyPI",
                            "progress": 40
                        }
            
            # Step 4: Iterative improvement loop
            error_history = []  # Track errors to detect loops
            while iteration < self.max_iterations and not success:
                iteration += 1
                progress = 20 + (iteration * 60 / self.max_iterations)
                
                yield {
                    "step": "activating",
                    "message": f"Attempting to activate service (attempt {iteration})...",
                    "progress": progress
                }
                
                # Try to activate
                activate_result = await self.tools.activate_service(service_id)
                
                if activate_result["success"]:
                    # Service activated! Now test it
                    yield {
                        "step": "testing",
                        "message": "Service activated! Running tests...",
                        "progress": progress + 10
                    }
                    
                    test_result = await self._test_service(service_id, initial_code["params"])
                    
                    if test_result["success"]:
                        # Check if there are any hidden errors in the response
                        response_data = test_result.get("response", {})
                        has_hidden_error = False
                        error_msg = None
                        
                        if isinstance(response_data, dict):
                            # Check for error field
                            if "error" in response_data and response_data["error"]:
                                has_hidden_error = True
                                error_msg = response_data["error"]
                            # Check for exception/traceback
                            elif "exception" in response_data or "traceback" in response_data:
                                has_hidden_error = True
                                error_msg = "Service execution resulted in exception"
                        
                        # Also check logs for any errors
                        logs_result = await self.tools.get_service_logs(service_id, limit=10)
                        if logs_result.get("logs"):
                            for log in logs_result["logs"]:
                                if log.get("level") == "ERROR":
                                    has_hidden_error = True
                                    error_msg = log.get("message", "Error found in logs")
                                    break
                        
                        if not has_hidden_error:
                            # Test with the provided test cases if available
                            if initial_code.get("test_cases"):
                                yield {
                                    "step": "running_test_cases",
                                    "message": f"Running {len(initial_code['test_cases'])} test cases...",
                                    "progress": progress + 15
                                }
                                
                                # Run interactive test and fix
                                async for update in self._interactive_test_and_fix(
                                    service_id, 
                                    initial_code["test_cases"],
                                    initial_code
                                ):
                                    yield update
                                
                                # Check if all tests passed
                                final_test_result = await self._run_all_test_cases(
                                    service_id,
                                    initial_code.get("test_cases", [])
                                )
                                
                                if final_test_result["all_passed"]:
                                    success = True
                                    yield {
                                        "step": "success",
                                        "message": "Service created and all tests passed!",
                                        "progress": 100,
                                        "service_id": service_id,
                                        "test_result": test_result
                                    }
                                else:
                                    # Some tests failed but service is working
                                    # Consider it a partial success to avoid infinite loop
                                    success = True
                                    yield {
                                        "step": "partial_success",
                                        "message": f"Service created but {len(final_test_result.get('failed_tests', []))} test(s) failed",
                                        "progress": 90,
                                        "service_id": service_id,
                                        "failed_tests": final_test_result.get("failed_tests", []),
                                        "warning": "Service is functional but may not handle all edge cases"
                                    }
                            else:
                                # No test cases provided, mark as success
                                success = True
                                yield {
                                    "step": "success",
                                    "message": "Service created and tested successfully!",
                                    "progress": 100,
                                    "service_id": service_id,
                                    "test_result": test_result
                                }
                        else:
                            # Test passed but service has errors
                            yield {
                                "step": "hidden_error_found",
                                "message": f"Test passed but found error: {error_msg}",
                                "progress": progress + 5
                            }
                            
                            # Continue to fix the error
                            test_result["success"] = False
                            test_result["error"] = error_msg
                    else:
                        # Test failed, need to fix
                        current_error = test_result.get('error', 'Unknown error')
                        
                        # Check if we're in an error loop
                        if current_error in error_history:
                            yield {
                                "step": "error",
                                "message": f"Stuck in error loop: {current_error}",
                                "error": "Unable to resolve recurring error after multiple attempts"
                            }
                            break
                        
                        error_history.append(current_error)
                        
                        yield {
                            "step": "debugging",
                            "message": f"Test failed: {current_error}",
                            "progress": progress + 5
                        }
                        
                        # Get logs and fix
                        async for fix_update in self._fix_service_error(
                            service_id, test_result, initial_code
                        ):
                            yield fix_update
                else:
                    # Activation failed
                    yield {
                        "step": "debugging", 
                        "message": f"Activation failed: {activate_result.get('error', 'Unknown error')}",
                        "progress": progress + 5
                    }
                    
                    # Check if it's a missing module error or undefined name error
                    error_msg = activate_result.get('error', '')
                    if ('ModuleNotFoundError' in error_msg or 'No module named' in error_msg or 
                        'Missing dependency:' in error_msg or "name 'urllib' is not defined" in error_msg):
                        # Try to install missing package
                        import re
                        module_match = re.search(r"No module named '([^']+)'", error_msg)
                        if not module_match:
                            module_match = re.search(r"Missing dependency: ([^\s]+)", error_msg)
                        if not module_match:
                            # Check for undefined name errors (like urllib)
                            module_match = re.search(r"name '(\w+)' is not defined", error_msg)
                        
                        if module_match:
                            missing_module = module_match.group(1)
                            
                            # Map import names to package names
                            package_map = {
                                'bs4': 'beautifulsoup4',
                                'PIL': 'pillow',
                                'cv2': 'opencv-python',
                                'sklearn': 'scikit-learn',
                                'yaml': 'pyyaml',
                                'lxml': 'lxml',
                                'numpy': 'numpy',
                                'pandas': 'pandas',
                                'matplotlib': 'matplotlib',
                                'seaborn': 'seaborn',
                                'scipy': 'scipy',
                                'nltk': 'nltk',
                                'torch': 'torch',
                                'tensorflow': 'tensorflow'
                            }
                            
                            # Check if it's a standard library module that just needs to be added to dependencies
                            stdlib_modules = {
                                'urllib', 'os', 'sys', 'json', 'datetime', 'time', 're', 'math', 
                                'random', 'http', 'collections', 'itertools', 'functools', 'hashlib',
                                'base64', 'string', 'io', 'pathlib', 'subprocess', 'threading'
                            }
                            
                            if missing_module in stdlib_modules:
                                # It's a standard library module, just add to dependencies
                                yield {
                                    "step": "adding_stdlib",
                                    "message": f"Adding standard library module '{missing_module}' to dependencies",
                                    "progress": progress + 2
                                }
                                
                                # Get current service details and update dependencies
                                service_details = await self.tools.get_service_details(service_id)
                                if service_details["success"]:
                                    current_deps = service_details["service"].get("dependencies", [])
                                    if missing_module not in current_deps:
                                        current_deps.append(missing_module)
                                        await self.tools.update_service_code(
                                            service_id,
                                            service_details["service"]["code"],
                                            dependencies=current_deps
                                        )
                                        yield {
                                            "step": "stdlib_added",
                                            "message": f"Added '{missing_module}' to dependencies",
                                            "progress": progress + 3
                                        }
                                continue  # Retry activation
                            
                            # Get the actual package name for external modules
                            package_to_install = package_map.get(missing_module, missing_module)
                            
                            yield {
                                "step": "installing",
                                "message": f"Missing module '{missing_module}' detected. Installing package '{package_to_install}'...",
                                "progress": progress + 2
                            }
                            
                            # Check if package is available
                            check_result = await self.tools.check_package_available(package_to_install)
                            if check_result["success"] and check_result.get("available"):
                                # Install the package
                                install_result = await self.tools.install_package(package_to_install)
                                if install_result["success"]:
                                    yield {
                                        "step": "installed",
                                        "message": f"Successfully installed {package_to_install}",
                                        "progress": progress + 3
                                    }
                                    # Update dependencies if needed
                                    service_details = await self.tools.get_service_details(service_id)
                                    if service_details["success"]:
                                        current_deps = service_details["service"].get("dependencies", [])
                                        if package_to_install not in current_deps:
                                            current_deps.append(package_to_install)
                                            await self.tools.update_service_code(
                                                service_id, 
                                                service_details["service"]["code"],
                                                dependencies=current_deps
                                            )
                                    # Continue with next iteration to retry activation
                                    continue
                                else:
                                    yield {
                                        "step": "install_failed",
                                        "message": f"Failed to install {package_to_install}: {install_result.get('error')}",
                                        "progress": progress + 3
                                    }
                    
                    # Get logs and fix
                    logs_result = await self.tools.get_service_logs(service_id, limit=20)
                    
                    fix_result = await self._fix_activation_error(
                        service_id, activate_result, logs_result.get("logs", []), initial_code
                    )
                    
                    if fix_result["success"]:
                        yield {
                            "step": "fixed",
                            "message": "Applied fix, retrying...",
                            "fix": fix_result["fix_applied"]
                        }
                    else:
                        yield {
                            "step": "error",
                            "message": "Failed to fix error",
                            "error": fix_result["error"]
                        }
                        break
            
            if not success:
                yield {
                    "step": "timeout",
                    "message": f"Could not create working service after {self.max_iterations} attempts",
                    "service_id": service_id
                }
                
        except Exception as e:
            logger.error(f"Agent error: {str(e)}")
            yield {
                "step": "error",
                "message": "Unexpected error in agent",
                "error": str(e)
            }
    
    def _build_context(self, service_type: str) -> str:
        """Build context documentation for the LLM"""
        context = get_service_documentation()
        context += "\n\n" + get_examples_by_type(service_type)
        context += "\n\n" + get_common_errors_solutions()
        return context
    
    async def _generate_initial_service(
        self,
        name: str,
        description: str,
        service_type: str,
        context: str,
        api_documentation: Optional[str] = None,
        api_base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        api_headers: Optional[dict] = None
    ) -> Optional[Dict[str, Any]]:
        """Generate initial service code using LLM"""
        # Build API section if needed
        api_section = ""
        if api_documentation:
            api_section = load_prompt(
                "agent_service/api_section_template",
                api_documentation=api_documentation,
                api_base_url=api_base_url,
                api_key_info=f'"{api_key}"' if api_key else "Not provided",
                api_headers=api_headers,
                api_key_instruction=f'Use this EXACT API key in your code: "{api_key}" (hardcode it directly, do NOT use environment variables)' if api_key else 'No API key provided, handle accordingly'
            )
        
        prompt = load_prompt(
            "agent_service/generate_initial_service",
            name=name,
            service_type=service_type,
            description=description,
            api_section=api_section,
            context=context
        )
        
        try:
            messages = [
                {"role": "system", "content": "You are an expert Python developer creating UXMCP services."},
                {"role": "user", "content": prompt}
            ]
            
            response = await self._call_llm(messages, temperature=0.3)
            
            if response:
                # Parse JSON response
                try:
                    # Extract JSON from response if wrapped in markdown
                    import re
                    json_match = re.search(r'\{[\s\S]*\}', response)
                    if json_match:
                        service_data = json.loads(json_match.group())
                        return service_data
                except json.JSONDecodeError:
                    logger.error("Failed to parse LLM response as JSON")
                    
        except Exception as e:
            logger.error(f"Failed to generate initial service: {str(e)}")
            
        return None
    
    async def _test_service(
        self,
        service_id: str,
        params: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Test the service with appropriate parameters"""
        # Get service details to understand what it does
        service_details = await self.tools.get_service_details(service_id)
        if not service_details["success"]:
            return {"success": False, "error": "Could not get service details"}
        
        service = service_details["service"]
        
        # Ask LLM to generate appropriate test parameters
        test_params = await self._generate_test_params(service)
        
        if not test_params:
            # Fallback to basic test params if LLM fails
            test_params = {}
            for param in params:
                if param.get("required", True):
                    if param["type"] == "string":
                        test_params[param["name"]] = "test_value"
                    elif param["type"] == "number":
                        test_params[param["name"]] = 1
                    elif param["type"] == "boolean":
                        test_params[param["name"]] = True
                    elif param["type"] == "array":
                        test_params[param["name"]] = []
                    else:
                        test_params[param["name"]] = {}
        
        # Call the test service
        result = await self.tools.test_service(service_id, test_params)
        
        # Log test details for debugging
        logger.info(f"Test result for {service['name']}: {result}")
        
        # Enhanced validation: check if response contains error fields
        if result["success"] and result.get("response"):
            response_data = result.get("response", {})
            
            # Check for error indicators in the response
            if isinstance(response_data, dict):
                # Look for common error patterns
                if "error" in response_data and response_data["error"]:
                    # Service returned an error in its response
                    result["success"] = False
                    result["error"] = f"Service returned error: {response_data['error']}"
                elif "exception" in response_data or "traceback" in response_data:
                    # Service had an exception
                    result["success"] = False
                    result["error"] = "Service execution resulted in exception"
        
        # If test failed but no specific error, try to get more info
        if not result["success"] and not result.get("error"):
            if result.get("status_code"):
                result["error"] = f"HTTP {result['status_code']} error"
            else:
                # Get logs to understand what happened
                logs_result = await self.tools.get_service_logs(service_id, limit=5)
                if logs_result.get("logs"):
                    last_error = None
                    for log in logs_result["logs"]:
                        if log.get("level") == "ERROR":
                            last_error = log.get("message", "Unknown error in logs")
                            break
                    if last_error:
                        result["error"] = f"Service error: {last_error}"
                    else:
                        result["error"] = "Test failed but no error details available"
                else:
                    result["error"] = "Test failed with no error details"
        
        return result
    
    async def _generate_test_params(
        self,
        service: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Ask LLM to generate appropriate test parameters for a service"""
        prompt = load_prompt(
            "agent_service/generate_test_params_detailed",
            service_name=service['name'],
            description=service.get('description', 'No description'),
            route=service['route'],
            method=service['method'],
            service_type=service['service_type'],
            parameters=json.dumps(service.get('params', []), indent=2)
        )
        
        try:
            messages = [
                {"role": "system", "content": "You are generating test parameters for services. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ]
            
            response = await self._call_llm(messages, temperature=0.3)
            
            if response:
                # Parse JSON response
                import re
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    return json.loads(json_match.group())
                    
        except Exception as e:
            logger.error(f"Failed to generate test params: {str(e)}")
            
        return None
    
    async def _fix_activation_error(
        self,
        service_id: str,
        activate_result: Dict[str, Any],
        logs: List[Dict[str, Any]],
        original_code: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Fix activation errors using LLM"""
        error_info = {
            "error": activate_result.get("error", "Unknown error"),
            "error_type": activate_result.get("error_type"),
            "logs": logs[-5:] if logs else []  # Last 5 log entries
        }
        
        # Analyze error
        analysis = await self.tools.analyze_error(
            error_info["error"],
            original_code["code"],
            error_info.get("error_type")
        )
        
        prompt = load_prompt(
            "agent_service/fix_activation_error",
            error=error_info['error'],
            error_type=error_info.get('error_type', 'Unknown'),
            code=original_code['code'],
            dependencies=original_code.get('dependencies', []),
            analysis=json.dumps(analysis, indent=2),
            logs=json.dumps(error_info['logs'], indent=2)
        )
        
        try:
            messages = [
                {"role": "system", "content": "You are debugging a Python UXMCP service. Fix the error."},
                {"role": "user", "content": prompt}
            ]
            
            response = await self._call_llm(messages, temperature=0.1)
            
            if response:
                # Parse fix
                import re
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    fix_data = json.loads(json_match.group())
                    
                    # Apply the fix
                    update_result = await self.tools.update_service_code(
                        service_id,
                        fix_data["code"],
                        fix_data.get("dependencies", original_code.get("dependencies", []))
                    )
                    
                    if update_result["success"]:
                        return {
                            "success": True,
                            "fix_applied": fix_data.get("fix_description", "Code updated")
                        }
                        
        except Exception as e:
            logger.error(f"Failed to fix activation error: {str(e)}")
        
        return {"success": False, "error": "Could not generate fix"}
    
    async def _fix_service_error(
        self,
        service_id: str,
        test_result: Dict[str, Any],
        original_code: Dict[str, Any]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Fix service test errors"""
        # Similar to activation error fixing but for runtime errors
        logs_result = await self.tools.get_service_logs(service_id, limit=20)
        
        error_info = {
            "test_error": test_result.get("error", "Test failed"),
            "response": test_result.get("response"),
            "status_code": test_result.get("status_code"),
            "logs": logs_result.get("logs", [])[-5:]
        }
        
        # First, analyze the error to get specific fixes
        error_analysis = None
        if isinstance(error_info.get('response'), dict) and 'error' in error_info['response']:
            error_analysis = await self.tools.analyze_error(
                error_info['response']['error'],
                original_code['code']
            )
        
        prompt = load_prompt(
            "agent_service/fix_service_error",
            test_error=error_info['test_error'],
            response=json.dumps(error_info['response'], indent=2),
            status_code=error_info['status_code'],
            current_code=original_code['code'],
            output_schema=json.dumps(original_code.get('output_schema', {}), indent=2),
            error_analysis=json.dumps(error_analysis, indent=2) if error_analysis else 'No specific analysis available',
            logs=json.dumps(error_info['logs'], indent=2)
        )
        
        try:
            messages = [
                {"role": "system", "content": "You are fixing a Python UXMCP service to pass tests."},
                {"role": "user", "content": prompt}
            ]
            
            response = await self._call_llm(messages, temperature=0.1)
            
            if response:
                import re
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    fix_data = json.loads(json_match.group())
                    
                    # Deactivate service first
                    await self.tools.deactivate_service(service_id)
                    
                    # Apply the fix
                    update_result = await self.tools.update_service_code(
                        service_id,
                        fix_data["code"],
                        output_schema=fix_data.get("output_schema")
                    )
                    
                    if update_result["success"]:
                        yield {
                            "step": "fixed",
                            "message": f"Applied fix: {fix_data.get('fix_description', 'Code updated')}",
                            "fix": fix_data.get("fix_description")
                        }
                        
        except Exception as e:
            logger.error(f"Failed to fix service error: {str(e)}")
    
    async def _call_llm(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7
    ) -> Optional[str]:
        """Call the LLM API"""
        try:
            endpoint = self.llm_profile.endpoint or "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.llm_profile.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.llm_profile.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": self.llm_profile.max_tokens
            }
            
            # Add JSON mode if supported
            if self.llm_profile.mode == "json":
                payload["response_format"] = {"type": "json_object"}
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                
                result = response.json()
                return result["choices"][0]["message"]["content"]
                
        except Exception as e:
            logger.error(f"LLM API call failed: {str(e)}")
            return None
    
    async def _interactive_test_and_fix(
        self,
        service_id: str,
        test_cases: List[Dict[str, Any]],
        original_code: Dict[str, Any]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Interactively test the service and allow the LLM to fix issues
        Shows the LLM exactly what happens when calling the service
        """
        max_fix_attempts = 5
        
        for idx, test_case in enumerate(test_cases):
            yield {
                "step": "testing_case",
                "message": f"Testing case {idx + 1}: {test_case.get('description', 'Test case')}",
                "test_case": test_case
            }
            
            fix_attempts = 0
            test_passed = False
            
            while fix_attempts < max_fix_attempts and not test_passed:
                # Run the test
                test_params = test_case.get("params", {})
                expected_output = test_case.get("expected_output", {})
                
                result = await self.tools.test_service(service_id, test_params)
                
                # Show the LLM what happened
                yield {
                    "step": "test_result",
                    "message": f"Test {idx + 1} result",
                    "request": test_params,
                    "response": result.get("response"),
                    "success": result.get("success"),
                    "error": result.get("error")
                }
                
                # Ask LLM to evaluate the result
                evaluation = await self._evaluate_test_result(
                    test_case,
                    result,
                    expected_output
                )
                
                if evaluation["passed"]:
                    test_passed = True
                    yield {
                        "step": "test_passed",
                        "message": f"Test case {idx + 1} passed!",
                        "evaluation": evaluation
                    }
                else:
                    fix_attempts += 1
                    yield {
                        "step": "test_failed",
                        "message": f"Test case {idx + 1} failed. Attempting fix {fix_attempts}/{max_fix_attempts}",
                        "evaluation": evaluation
                    }
                    
                    # Ask LLM to fix the code based on what it saw
                    fix_result = await self._fix_based_on_test_result(
                        service_id,
                        test_case,
                        result,
                        evaluation,
                        original_code
                    )
                    
                    if fix_result["success"]:
                        yield {
                            "step": "fix_applied",
                            "message": fix_result.get("fix_description", "Code updated"),
                            "attempt": fix_attempts
                        }
                    else:
                        yield {
                            "step": "fix_failed",
                            "message": "Could not generate fix",
                            "error": fix_result.get("error")
                        }
                        break
            
            # If we exhausted fix attempts without success
            if not test_passed and fix_attempts >= max_fix_attempts:
                yield {
                    "step": "test_abandoned",
                    "message": f"Test case {idx + 1} abandoned after {max_fix_attempts} fix attempts",
                    "test_case": test_case.get('description', 'Test case')
                }
    
    async def _evaluate_test_result(
        self,
        test_case: Dict[str, Any],
        result: Dict[str, Any],
        expected_output: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Ask LLM to evaluate if the test result matches expectations
        """
        prompt = load_prompt(
            "agent_service/evaluate_test_lenient",
            test_description=test_case.get('description', 'No description'),
            input_params=json.dumps(test_case.get('params', {}), indent=2),
            expected_output=json.dumps(expected_output, indent=2),
            actual_success=result.get('success'),
            actual_response=json.dumps(result.get('response'), indent=2),
            actual_error=result.get('error', 'None')
        )
        
        try:
            messages = [
                {"role": "system", "content": "You are evaluating test results for UXMCP services. Be VERY LENIENT - if a service returns data successfully, it should PASS the test. Only fail for actual errors or crashes."},
                {"role": "user", "content": prompt}
            ]
            
            response = await self._call_llm(messages, temperature=0.1)
            
            if response:
                import re
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    return json.loads(json_match.group())
        except Exception as e:
            logger.error(f"Failed to evaluate test result: {str(e)}")
        
        return {
            "passed": False,
            "reason": "Could not evaluate result",
            "issues": ["Evaluation failed"],
            "suggestions": []
        }
    
    async def _fix_based_on_test_result(
        self,
        service_id: str,
        test_case: Dict[str, Any],
        result: Dict[str, Any],
        evaluation: Dict[str, Any],
        original_code: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Fix the code based on the test result the LLM just saw
        """
        # Get current code
        service_details = await self.tools.get_service_details(service_id)
        if not service_details["success"]:
            return {"success": False, "error": "Could not get service details"}
        
        current_code = service_details["service"]["code"]
        
        prompt = load_prompt(
            "agent_service/fix_based_on_test",
            test_description=test_case.get('description'),
            test_params=json.dumps(test_case.get('params', {}), indent=2),
            expected_output=json.dumps(test_case.get('expected_output', {}), indent=2),
            actual_response=json.dumps(result.get('response'), indent=2),
            evaluation_reason=evaluation.get('reason'),
            issues=json.dumps(evaluation.get('issues', []), indent=2),
            suggestions=json.dumps(evaluation.get('suggestions', []), indent=2),
            current_code=current_code
        )
        
        try:
            messages = [
                {"role": "system", "content": "You are fixing UXMCP service code based on test results."},
                {"role": "user", "content": prompt}
            ]
            
            response = await self._call_llm(messages, temperature=0.2)
            
            if response:
                import re
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    fix_data = json.loads(json_match.group())
                    
                    # Update the service
                    update_result = await self.tools.update_service_code(
                        service_id,
                        fix_data["code"],
                        fix_data.get("dependencies", original_code.get("dependencies", []))
                    )
                    
                    if update_result["success"]:
                        return {
                            "success": True,
                            "fix_description": fix_data.get("fix_description", "Code updated")
                        }
        except Exception as e:
            logger.error(f"Failed to fix based on test result: {str(e)}")
        
        return {"success": False, "error": "Could not generate fix"}
    
    async def _run_all_test_cases(
        self,
        service_id: str,
        test_cases: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Run all test cases and return summary
        """
        results = []
        all_passed = True
        
        for test_case in test_cases:
            test_params = test_case.get("params", {})
            expected_output = test_case.get("expected_output", {})
            
            result = await self.tools.test_service(service_id, test_params)
            evaluation = await self._evaluate_test_result(test_case, result, expected_output)
            
            results.append({
                "description": test_case.get("description", "Test case"),
                "passed": evaluation["passed"],
                "reason": evaluation.get("reason", ""),
                "result": result
            })
            
            if not evaluation["passed"]:
                all_passed = False
        
        return {
            "all_passed": all_passed,
            "results": results,
            "failed_tests": [r for r in results if not r["passed"]]
        }


# Factory function
async def create_agent(llm_profile_name: str, app) -> ServiceCreatorAgent:
    """Create a service creator agent with specified LLM profile"""
    llm_profile = await llm_crud.get_by_name(llm_profile_name)
    if not llm_profile or not llm_profile.active:
        raise ValueError(f"LLM profile '{llm_profile_name}' not found or inactive")
    
    # Ensure LLM profile is in JSON mode for structured responses
    if llm_profile.mode != "json":
        raise ValueError(f"LLM profile '{llm_profile_name}' must be configured with mode='json' for AI agent. Current mode: '{llm_profile.mode}'")
    
    return ServiceCreatorAgent(llm_profile, app)