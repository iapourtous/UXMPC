# UXMCP Prompts Index

This document catalogs all LLM prompts found in the UXMCP codebase, organized by service and purpose.

## 1. Meta Chat Service (`backend/app/services/meta_chat_service.py`)

### 1.1 Request Analysis Prompt
- **Location**: Line 124
- **Purpose**: Analyze user requests to determine if an agent should handle them
- **Key Features**:
  - Identifies trigger words for agent delegation
  - Determines response type (agent vs direct)
  - Returns structured JSON with intent analysis
- **Suggested Filename**: `meta_chat_analyze_request.txt`

### 1.2 Agent Selection Prompt  
- **Location**: Line 212
- **Purpose**: Select the best existing agent for a user request
- **Key Features**:
  - Matches user requests with available agents
  - Considers synonyms and related terms
  - Returns specific agent name
- **Suggested Filename**: `meta_chat_select_agent.txt`

### 1.3 Direct Response Prompt
- **Location**: Line 333
- **Purpose**: Generate direct responses without using an agent
- **Suggested Filename**: `meta_chat_direct_response.txt`

### 1.4 HTML Response Generation Prompt
- **Location**: Line 402
- **Purpose**: Generate beautiful HTML/CSS/JS visualizations for responses
- **Key Features**:
  - Context-aware styling (weather, calculations, data)
  - Responsive and interactive design
  - Complete HTML page generation
- **Suggested Filename**: `meta_chat_html_response.txt`

## 2. Agent Service (`backend/app/services/agent_service.py`)

### 2.1 Service Creation Prompt
- **Location**: Line 530
- **Purpose**: Generate initial service code from description
- **Key Features**:
  - Detailed coding rules (imports, structure, dependencies)
  - External API integration instructions
  - Test case generation
- **Suggested Filename**: `agent_service_create_initial.txt`

### 2.2 Test Parameter Generation Prompt
- **Location**: Line 781
- **Purpose**: Generate appropriate test parameters for services
- **Suggested Filename**: `agent_service_generate_test_params.txt`

### 2.3 Fix Activation Error Prompt
- **Location**: Line 850
- **Purpose**: Fix service activation errors
- **Suggested Filename**: `agent_service_fix_activation.txt`

### 2.4 Fix Service Error Prompt
- **Location**: Line 943
- **Purpose**: Fix service test failures
- **Suggested Filename**: `agent_service_fix_test_error.txt`

### 2.5 Test Result Evaluation Prompt
- **Location**: Line 1152
- **Purpose**: Evaluate if test results match expectations
- **Key Features**:
  - Lenient evaluation rules
  - Focus on functionality over exact matches
- **Suggested Filename**: `agent_service_evaluate_test.txt`

### 2.6 Fix Based on Test Result Prompt
- **Location**: Line 1230
- **Purpose**: Fix code based on observed test failures
- **Suggested Filename**: `agent_service_fix_from_test.txt`

## 3. Service Generator (`backend/app/services/service_generator.py`)

### 3.1 Service Generation Prompt
- **Location**: Line 90 (GENERATION_PROMPT constant)
- **Purpose**: Generate complete service implementation from specifications
- **Key Features**:
  - Service type-specific generation (tool/resource/prompt)
  - Parameter extraction
  - JSON schema generation
- **Suggested Filename**: `service_generator_main.txt`

## 4. Meta Agent Service (`backend/app/services/meta_agent_service.py`)

### 4.1 Agent Requirements Analysis Prompt
- **Location**: Line 272
- **Purpose**: Analyze agent requirements and create comprehensive plan
- **Key Features**:
  - Domain identification
  - Complexity assessment
  - Agent profile generation with personality, objectives, constraints
- **Suggested Filename**: `meta_agent_analyze_requirements.txt`

## 5. Tool Analyzer (`backend/app/core/tool_analyzer.py`)

### 5.1 Required Tools Analysis Prompt
- **Location**: Line 38
- **Purpose**: Identify minimal set of tools needed for an agent
- **Suggested Filename**: `tool_analyzer_identify_tools.txt`

### 5.2 Service Matching Prompt
- **Location**: Line 116
- **Purpose**: Match required tools with existing services
- **Suggested Filename**: `tool_analyzer_match_services.txt`

### 5.3 Service Compatibility Evaluation Prompt
- **Location**: Line 184
- **Purpose**: Evaluate how well a service matches a requirement
- **Suggested Filename**: `tool_analyzer_evaluate_compatibility.txt`

### 5.4 Tool Specification Generation Prompt
- **Location**: Line 243
- **Purpose**: Generate detailed specification for creating new tools
- **Suggested Filename**: `tool_analyzer_generate_spec.txt`

## 6. Agent Executor (`backend/app/services/agent_executor.py`)

### 6.1 Dynamic System Prompt Construction
- **Location**: Lines 196-267
- **Purpose**: Build enhanced system prompts with agent identity
- **Key Features**:
  - Incorporates backstory, objectives, constraints
  - Adds reasoning strategies
  - Includes personality traits
  - Memory context integration
- **Suggested Filename**: `agent_executor_system_prompt_template.txt`

## System Prompt Patterns

### Common Patterns Found:
1. **JSON Response Format**: Most prompts request JSON responses with specific schemas
2. **Role-Based Instructions**: System messages define expert roles
3. **Temperature Control**: Different temperatures for different tasks (0.1-0.7)
4. **Iterative Refinement**: Many prompts support error correction loops
5. **Context Injection**: Dynamic context added based on agent configuration

### Prompt Engineering Best Practices Observed:
1. Clear structure with sections (##, ###)
2. Explicit examples provided
3. Important rules emphasized with CAPS
4. Step-by-step instructions
5. Error handling guidance
6. Output format specifications

## Recommendations for Centralization

1. **Create a `prompts/` directory** with subdirectories by service
2. **Use template variables** for dynamic content (e.g., `{agent_name}`, `{description}`)
3. **Version control** prompts separately for easier updates
4. **Create a prompt loader utility** that reads from files
5. **Add prompt validation** to ensure required variables are provided
6. **Enable A/B testing** by supporting multiple prompt versions