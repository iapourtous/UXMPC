# UXMCP Prompts Extraction Summary

## Overview
I've successfully searched and analyzed the UXMCP codebase for all LLM prompts. Here's what was found and extracted:

## Files Analyzed
1. **Meta Chat Service** (`meta_chat_service.py`) - 4 prompts
2. **Agent Service** (`agent_service.py`) - 6 prompts  
3. **Service Generator** (`service_generator.py`) - 1 prompt
4. **Meta Agent Service** (`meta_agent_service.py`) - 1 prompt
5. **Tool Analyzer** (`tool_analyzer.py`) - 4 prompts
6. **Agent Executor** (`agent_executor.py`) - Dynamic prompt construction
7. **Chat Service** (`chat.py`) - Uses LLM profiles' system prompts

## Total Prompts Found: 16+ distinct prompts

## Key Findings

### 1. Prompt Categories
- **Request Analysis**: Determining intent and routing
- **Service Generation**: Creating code from descriptions
- **Error Correction**: Fixing activation and test failures
- **Agent Configuration**: Building agent personalities and capabilities
- **Tool Discovery**: Identifying and matching required tools
- **Response Formatting**: Generating HTML visualizations

### 2. Common Patterns
- JSON response format requirements
- Step-by-step instructions with examples
- Error handling guidance
- Temperature control (0.1-0.7 based on task)
- Role-based system prompts

### 3. Complexity Levels
- **Simple**: Direct response generation
- **Medium**: Service matching and evaluation
- **Complex**: Full service code generation with test cases
- **Advanced**: Multi-step agent creation with tool generation

## Deliverables Created

### 1. Extracted Prompt Files
Created `/prompts/` directory with organized prompt files:
```
prompts/
├── PROMPTS_INDEX.md         # Complete catalog of all prompts
├── MIGRATION_GUIDE.md       # How to migrate to centralized prompts
├── SUMMARY_REPORT.md        # This summary
├── meta_chat/
│   ├── analyze_request.txt
│   ├── select_agent.txt
│   └── generate_html_response.txt
├── agent_service/
│   ├── create_initial_service.txt
│   ├── fix_activation_error.txt
│   ├── fix_test_error.txt
│   └── evaluate_test_result.txt
├── meta_agent/
│   └── analyze_requirements.txt
└── tool_analyzer/
    ├── identify_required_tools.txt
    └── match_services.txt
```

### 2. Prompt Loader Utility
Created `backend/app/core/prompt_loader.py`:
- Centralized prompt loading
- Variable substitution
- Caching for performance
- Validation capabilities
- Easy integration with existing code

### 3. Documentation
- **PROMPTS_INDEX.md**: Complete catalog with locations and purposes
- **MIGRATION_GUIDE.md**: Step-by-step migration instructions
- **SUMMARY_REPORT.md**: This summary document

## Recommendations

### Immediate Actions
1. **Test the prompt loader** with a small service first
2. **Migrate one service** as a proof of concept
3. **Set up version control** for the prompts directory

### Short Term (1-2 weeks)
1. **Migrate critical prompts** that change frequently
2. **Add prompt validation** to CI/CD pipeline
3. **Create prompt editing UI** in UXMCP admin

### Long Term
1. **A/B testing framework** for prompt optimization
2. **Prompt analytics** to track usage and performance
3. **Multi-language support** for prompts
4. **Prompt marketplace** for sharing optimized prompts

## Benefits of Centralization

1. **Maintainability**: Edit prompts without touching code
2. **Version Control**: Track prompt evolution separately
3. **Reusability**: Share prompts across services
4. **Testing**: Test prompts independently
5. **Documentation**: Prompts are self-documenting
6. **Optimization**: Easy to A/B test different versions

## Next Steps

To start using centralized prompts:

1. **Import the loader**:
   ```python
   from app.core.prompt_loader import load_prompt
   ```

2. **Load a prompt**:
   ```python
   prompt = load_prompt("meta_chat/analyze_request.txt", 
                       message=user_message,
                       agent_list=agents)
   ```

3. **Migrate gradually**: Start with frequently-changed prompts

## Technical Notes

- All prompts preserved exactly as found
- Variable placeholders use Python format syntax: `{variable_name}`
- Prompts support multi-line formatting and complex structures
- Cache mechanism prevents repeated file reads
- Error handling for missing files and variables

This centralization will significantly improve prompt management and enable rapid iteration on LLM interactions.