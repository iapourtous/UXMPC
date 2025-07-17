import json
import httpx
from typing import Dict, Any, List
from app.models.service import Service
from app.services.llm_crud import llm_crud
import logging

logger = logging.getLogger(__name__)

# Prompts for test generation and validation
GENERATE_TESTS_PROMPT = """You are a service testing expert. Analyze the following MCP service and generate test cases.

Service Information:
- Name: {name}
- Type: {service_type}
- Route: {route}
- Method: {method}
- Description: {description}
- Parameters: {params}
- Documentation: {documentation}
- Output Schema (for tools only): {output_schema}

IMPORTANT: If this is a tool service and an Output Schema is provided, use it to understand 
the exact structure and types of the response. The Output Schema is a JSON Schema that defines 
what the service returns.

Generate 3 test cases in JSON format:
1. A nominal/happy path test case
2. An edge case test
3. An error case test (if applicable)

Return ONLY a JSON array with test cases. Each test case should have:
{{
  "name": "test case name",
  "description": "what this tests",
  "params": {{}},  // parameters to send
  "expected": {{   // expected response characteristics
    "status": 200,  // expected HTTP status
    "has_fields": [],  // fields that should exist in response
    "validations": []  // semantic validations as strings
  }}
}}

IMPORTANT: For tool services, base your expectations on the actual Output Schema provided, NOT on assumptions.
For example, if the schema shows "humidity" as type "string", expect a string, not a number.
For resource and prompt services, use the documentation and description to understand the expected behavior.

For path parameters like {{city}}, include them in params.
For GET requests with path params, params will be used in the URL.
For POST requests, params will be sent as JSON body."""

VALIDATE_RESPONSE_PROMPT = """You are a service testing expert. Validate if this service response is correct.

Service: {service_name}
Test Case: {test_name}
Parameters Sent: {params}
Expected: {expected}
Output Schema: {output_schema}
Actual Response: {response}
HTTP Status: {status}
{logs_section}

Analyze if the response is valid considering:
1. Does it match the Output Schema (if provided)?
2. Does it match the expected structure?
3. Are the values semantically correct?
4. Does it follow the documented behavior?
5. Are there any errors or warnings in the logs?

IMPORTANT: For tool services with an Output Schema, use it as the source of truth for validation.
For example, if the schema defines "humidity" as a string, then "32%" is valid even if it contains a percentage sign.
For resource services, expect "content" and "mimeType" fields.
For prompt services, expect "template" field.

Return a JSON object:
{{
  "valid": true/false,
  "issues": [],  // list of issues found (be specific about schema violations)
  "summary": "brief summary of validation"
}}"""


class TestService:
    
    async def generate_test_cases(self, service: Service, llm_profile: Any) -> List[Dict[str, Any]]:
        """Generate test cases using LLM"""
        # Get output schema if available (only for tools)
        output_schema = "No output schema defined"
        if service.service_type == 'tool' and hasattr(service, 'output_schema') and service.output_schema:
            output_schema = json.dumps(service.output_schema, indent=2)
        
        prompt = GENERATE_TESTS_PROMPT.format(
            name=service.name,
            service_type=service.service_type,
            route=service.route,
            method=service.method,
            description=service.description or "No description",
            params=json.dumps([p.model_dump() for p in service.params], indent=2),
            documentation=service.documentation or "No documentation provided",
            output_schema=output_schema
        )
        
        try:
            # Use the same approach as ChatService
            messages = []
            
            # Add system prompt if provided
            if llm_profile.system_prompt:
                messages.append({"role": "system", "content": llm_profile.system_prompt})
            
            # Add our test generation prompt
            messages.append({"role": "user", "content": prompt})
            
            # Call LLM API
            endpoint = llm_profile.endpoint or "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {llm_profile.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": llm_profile.model,
                "messages": messages,
                "temperature": 0.3,  # Lower temperature for more consistent test generation
                "max_tokens": llm_profile.max_tokens
            }
            
            # Use JSON mode only if the LLM profile supports it
            if llm_profile.mode == "json":
                payload["response_format"] = {"type": "json_object"}
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                
                # Parse JSON response
                data = json.loads(content)
                # Handle if the response is wrapped in an object
                if "test_cases" in data:
                    return data["test_cases"]
                elif isinstance(data, list):
                    return data
                else:
                    # Try to extract array from the response
                    import re
                    json_match = re.search(r'\[[\s\S]*\]', content)
                    if json_match:
                        return json.loads(json_match.group())
                    else:
                        return self._generate_default_test_cases(service)
                        
        except Exception as e:
            import traceback
            logger.error(f"Failed to generate test cases with LLM: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return self._generate_default_test_cases(service)
    
    def _generate_default_test_cases(self, service: Service) -> List[Dict[str, Any]]:
        """Generate default test cases if LLM fails"""
        test_cases = []
        
        # Default happy path test
        params = {}
        for param in service.params:
            if param.type == "string":
                params[param.name] = "test"
            elif param.type == "number":
                params[param.name] = 42
            elif param.type == "boolean":
                params[param.name] = True
            elif param.type == "array":
                params[param.name] = []
            else:
                params[param.name] = {}
        
        test_cases.append({
            "name": "Happy Path Test",
            "description": "Test with valid default parameters",
            "params": params,
            "expected": {
                "status": 200,
                "has_fields": [],
                "validations": ["Response should be valid"]
            }
        })
        
        return test_cases
    
    async def execute_test_case(self, service: Service, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single test case"""
        try:
            # Build the URL
            url = f"http://localhost:8000{service.route}"
            params = test_case.get("params", {})
            
            # Store execution_id for log retrieval
            self.last_execution_id = None
            
            # Replace path parameters
            for param_name, param_value in params.items():
                url = url.replace(f"{{{param_name}}}", str(param_value))
            
            # Prepare the request
            async with httpx.AsyncClient() as client:
                if service.method == "GET":
                    # For GET, non-path params go as query params
                    query_params = {k: v for k, v in params.items() if f"{{{k}}}" not in service.route}
                    response = await client.get(url, params=query_params)
                elif service.method == "POST":
                    # For POST, all params go in body
                    response = await client.post(url, json=params)
                elif service.method == "PUT":
                    response = await client.put(url, json=params)
                elif service.method == "DELETE":
                    response = await client.delete(url)
                else:
                    response = await client.request(service.method, url, json=params)
            
            # Try to extract execution_id from response headers if available
            execution_id_header = response.headers.get("X-Execution-ID")
            if execution_id_header:
                self.last_execution_id = execution_id_header
            
            return {
                "status": response.status_code,
                "response": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text,
                "headers": dict(response.headers),
                "execution_id": execution_id_header
            }
            
        except Exception as e:
            logger.error(f"Failed to execute test case: {str(e)}")
            return {
                "status": 0,
                "error": str(e),
                "response": None
            }
    
    async def validate_response(self, service: Service, test_case: Dict[str, Any], 
                               actual_response: Dict[str, Any], llm_profile: Any, 
                               logs: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Validate response using LLM"""
        # Format logs section if available
        logs_section = ""
        if logs:
            logs_section = "\n\nExecution Logs:\n"
            for log in logs:
                logs_section += f"[{log['level']}] {log['message']}"
                if log.get('details'):
                    logs_section += f" - {json.dumps(log['details'])}"
                logs_section += "\n"
        
        # Get output schema if available (only for tools)
        output_schema = "No output schema defined"
        if service.service_type == 'tool' and hasattr(service, 'output_schema') and service.output_schema:
            output_schema = json.dumps(service.output_schema, indent=2)
        
        prompt = VALIDATE_RESPONSE_PROMPT.format(
            service_name=service.name,
            test_name=test_case.get("name", "Unknown Test"),
            params=json.dumps(test_case.get("params", {})),
            expected=json.dumps(test_case.get("expected", {})),
            output_schema=output_schema,
            response=json.dumps(actual_response.get("response")),
            status=actual_response.get("status"),
            logs_section=logs_section
        )
        
        try:
            # Use the same approach as ChatService
            messages = []
            
            # Add system prompt if provided
            if llm_profile.system_prompt:
                messages.append({"role": "system", "content": llm_profile.system_prompt})
            
            # Add our validation prompt
            messages.append({"role": "user", "content": prompt})
            
            # Call LLM API
            endpoint = llm_profile.endpoint or "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {llm_profile.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": llm_profile.model,
                "messages": messages,
                "temperature": 0.1,  # Very low temperature for consistent validation
                "max_tokens": llm_profile.max_tokens
            }
            
            # Use JSON mode only if the LLM profile supports it
            if llm_profile.mode == "json":
                payload["response_format"] = {"type": "json_object"}
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                
                # Parse JSON response
                validation = json.loads(content)
                return validation
                
        except Exception as e:
            logger.error(f"Failed to validate with LLM: {str(e)}")
            return {
                "valid": actual_response.get("status") == 200,
                "issues": [str(e)],
                "summary": "LLM validation failed"
            }


async def test_service_with_llm(service: Service) -> Dict[str, Any]:
    """Main function to test a service using LLM"""
    test_service = TestService()
    
    # Get the LLM profile
    llm_profile = await llm_crud.get_by_name(service.llm_profile)
    if not llm_profile or not llm_profile.active:
        raise ValueError(f"LLM profile '{service.llm_profile}' not found or inactive")
    
    # Generate test cases
    test_cases = await test_service.generate_test_cases(service, llm_profile)
    
    # Execute test cases and validate
    results = []
    for test_case in test_cases:
        # Execute the test
        execution_result = await test_service.execute_test_case(service, test_case)
        
        # Get logs for this execution if there's an execution_id
        execution_logs = []
        if hasattr(test_service, 'last_execution_id') and test_service.last_execution_id:
            from app.core.database import get_database
            db = get_database()
            logs_collection = db["service_logs"]
            
            cursor = logs_collection.find({
                "execution_id": test_service.last_execution_id
            }).sort("timestamp", 1)
            
            async for log in cursor:
                execution_logs.append({
                    "timestamp": log["timestamp"].isoformat(),
                    "level": log["level"],
                    "message": log["message"],
                    "details": log.get("details", {})
                })
        
        # Validate the response
        validation_result = await test_service.validate_response(
            service, test_case, execution_result, llm_profile, execution_logs
        )
        
        results.append({
            "test_case": test_case,
            "execution": execution_result,
            "validation": validation_result,
            "logs": execution_logs
        })
    
    # Summary
    total_tests = len(results)
    passed_tests = sum(1 for r in results if r["validation"].get("valid", False))
    
    return {
        "service": {
            "name": service.name,
            "type": service.service_type,
            "route": service.route
        },
        "llm_profile": service.llm_profile,
        "summary": {
            "total": total_tests,
            "passed": passed_tests,
            "failed": total_tests - passed_tests,
            "success_rate": f"{(passed_tests/total_tests*100):.1f}%" if total_tests > 0 else "0%"
        },
        "results": results
    }