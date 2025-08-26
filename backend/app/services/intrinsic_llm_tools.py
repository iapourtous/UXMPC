"""
Intrinsic LLM Tools for Chain of Thought

This module provides LLM-native tools that leverage the language model's
inherent capabilities for reasoning, analysis, and synthesis. These tools
are always available in CoT, even when no external tools are provided.
"""

from typing import Dict, Any, List, Optional
import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Define all intrinsic tool names for easy checking
INTRINSIC_TOOL_NAMES = [
    "logical_reasoning",
    "text_comprehension", 
    "semantic_analysis",
    "summarization",
    "knowledge_synthesis",
    "pattern_recognition",
    "causal_analysis",
    "hypothesis_generation",
    "problem_decomposition",
    "critical_evaluation",
    "analogy_reasoning",
    "creative_brainstorming",
    "classification",
    "completeness_check",
    "scenario_exploration"
]

# OpenAI Tools format definitions for intrinsic LLM capabilities
INTRINSIC_LLM_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "logical_reasoning",
            "description": "Perform step-by-step logical reasoning, deduction, induction, or syllogistic analysis",
            "parameters": {
                "type": "object",
                "properties": {
                    "problem": {
                        "type": "string",
                        "description": "The logical problem or statement to analyze"
                    },
                    "approach": {
                        "type": "string",
                        "enum": ["deduction", "induction", "abduction", "syllogism", "propositional"],
                        "description": "Type of logical reasoning to apply"
                    },
                    "premises": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of premises to work from"
                    }
                },
                "required": ["problem"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "text_comprehension",
            "description": "Extract key information, answer questions, or analyze provided text content",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to analyze"
                    },
                    "question": {
                        "type": "string",
                        "description": "Specific question to answer about the text"
                    },
                    "extract_type": {
                        "type": "string",
                        "enum": ["main_points", "entities", "relationships", "facts", "arguments"],
                        "description": "Type of information to extract"
                    }
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "semantic_analysis",
            "description": "Analyze meaning, implications, nuances, and hidden assumptions in content",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Content to analyze semantically"
                    },
                    "focus": {
                        "type": "string",
                        "enum": ["meaning", "implications", "assumptions", "contradictions", "ambiguities"],
                        "description": "Aspect to focus the analysis on"
                    }
                },
                "required": ["content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "summarization",
            "description": "Create concise, context-aware summaries of complex information",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Content to summarize"
                    },
                    "max_length": {
                        "type": "integer",
                        "description": "Maximum length in characters (optional)"
                    },
                    "style": {
                        "type": "string",
                        "enum": ["bullet_points", "paragraph", "executive", "technical"],
                        "description": "Summary style"
                    },
                    "focus_areas": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific aspects to emphasize"
                    }
                },
                "required": ["content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "knowledge_synthesis",
            "description": "Combine multiple pieces of information into a coherent understanding",
            "parameters": {
                "type": "object",
                "properties": {
                    "information_pieces": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of information pieces to synthesize"
                    },
                    "synthesis_goal": {
                        "type": "string",
                        "description": "What to achieve with the synthesis"
                    },
                    "resolve_contradictions": {
                        "type": "boolean",
                        "description": "Attempt to resolve contradictions if found"
                    }
                },
                "required": ["information_pieces"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "pattern_recognition",
            "description": "Identify conceptual patterns, trends, or recurring themes",
            "parameters": {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "string",
                        "description": "Data or observations to analyze"
                    },
                    "pattern_type": {
                        "type": "string",
                        "enum": ["conceptual", "behavioral", "structural", "temporal", "causal"],
                        "description": "Type of pattern to look for"
                    }
                },
                "required": ["data"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "causal_analysis",
            "description": "Analyze cause-and-effect relationships and causal chains",
            "parameters": {
                "type": "object",
                "properties": {
                    "situation": {
                        "type": "string",
                        "description": "Situation or phenomenon to analyze"
                    },
                    "identify": {
                        "type": "string",
                        "enum": ["root_causes", "effects", "causal_chain", "contributing_factors"],
                        "description": "What to identify in the analysis"
                    }
                },
                "required": ["situation"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "hypothesis_generation",
            "description": "Generate plausible hypotheses or explanations for observations",
            "parameters": {
                "type": "object",
                "properties": {
                    "observations": {
                        "type": "string",
                        "description": "Observations requiring explanation"
                    },
                    "constraints": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Constraints that hypotheses must satisfy"
                    },
                    "number": {
                        "type": "integer",
                        "description": "Number of hypotheses to generate",
                        "default": 3
                    }
                },
                "required": ["observations"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "problem_decomposition",
            "description": "Break down complex problems into manageable sub-problems",
            "parameters": {
                "type": "object",
                "properties": {
                    "problem": {
                        "type": "string",
                        "description": "Complex problem to decompose"
                    },
                    "approach": {
                        "type": "string",
                        "enum": ["hierarchical", "sequential", "parallel", "functional"],
                        "description": "Decomposition approach"
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum decomposition depth",
                        "default": 3
                    }
                },
                "required": ["problem"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "critical_evaluation",
            "description": "Critically evaluate arguments, claims, or proposals",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Content to evaluate critically"
                    },
                    "criteria": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Evaluation criteria to apply"
                    },
                    "identify_flaws": {
                        "type": "boolean",
                        "description": "Focus on identifying logical flaws and biases",
                        "default": True
                    }
                },
                "required": ["content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analogy_reasoning",
            "description": "Use analogical reasoning to transfer insights between domains",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_domain": {
                        "type": "string",
                        "description": "Known domain or situation"
                    },
                    "target_domain": {
                        "type": "string",
                        "description": "Domain to apply insights to"
                    },
                    "mapping_focus": {
                        "type": "string",
                        "enum": ["structural", "functional", "causal", "surface"],
                        "description": "Type of analogical mapping"
                    }
                },
                "required": ["source_domain", "target_domain"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "creative_brainstorming",
            "description": "Generate creative ideas, solutions, or alternatives",
            "parameters": {
                "type": "object",
                "properties": {
                    "challenge": {
                        "type": "string",
                        "description": "Challenge or opportunity to address"
                    },
                    "constraints": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Constraints to work within"
                    },
                    "techniques": {
                        "type": "array",
                        "items": {"type": "string"},
                        "enum": ["lateral_thinking", "scamper", "reverse_brainstorming", "mind_mapping"],
                        "description": "Creativity techniques to apply"
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "Number of ideas to generate",
                        "default": 5
                    }
                },
                "required": ["challenge"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "classification",
            "description": "Categorize or classify items based on characteristics",
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "string",
                        "description": "Items or content to classify"
                    },
                    "categories": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Predefined categories (optional)"
                    },
                    "criteria": {
                        "type": "string",
                        "description": "Classification criteria to apply"
                    }
                },
                "required": ["items"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "completeness_check",
            "description": "Check if all necessary aspects of a problem have been addressed",
            "parameters": {
                "type": "object",
                "properties": {
                    "problem": {
                        "type": "string",
                        "description": "Problem or question being addressed"
                    },
                    "solution_attempt": {
                        "type": "string",
                        "description": "Current solution or answer attempt"
                    },
                    "requirements": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific requirements to check"
                    }
                },
                "required": ["problem", "solution_attempt"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "scenario_exploration",
            "description": "Explore what-if scenarios and potential outcomes",
            "parameters": {
                "type": "object",
                "properties": {
                    "base_scenario": {
                        "type": "string",
                        "description": "Current situation or base scenario"
                    },
                    "variables": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Variables to modify in scenarios"
                    },
                    "time_horizon": {
                        "type": "string",
                        "enum": ["short_term", "medium_term", "long_term"],
                        "description": "Time horizon for scenarios"
                    },
                    "scenarios_count": {
                        "type": "integer",
                        "description": "Number of scenarios to explore",
                        "default": 3
                    }
                },
                "required": ["base_scenario"]
            }
        }
    }
]


class IntrinsicLLMToolsExecutor:
    """Executor for intrinsic LLM tools that leverage the model's native capabilities"""
    
    def __init__(self):
        self.tool_prompts = self._load_tool_prompts()
    
    def _load_tool_prompts(self) -> Dict[str, str]:
        """Load prompts from files in the prompts/intrinsic_tools directory"""
        prompts = {}
        
        # Get the base path for prompts
        base_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "prompts", "intrinsic_tools"
        )
        
        # Load each tool's prompt from its file
        for tool_name in INTRINSIC_TOOL_NAMES:
            prompt_file = os.path.join(base_path, f"{tool_name}.txt")
            
            try:
                with open(prompt_file, 'r') as f:
                    prompts[tool_name] = f.read()
                    logger.debug(f"Loaded prompt for {tool_name} from {prompt_file}")
            except FileNotFoundError:
                logger.warning(f"Prompt file not found for {tool_name}: {prompt_file}")
                # Provide a fallback prompt
                prompts[tool_name] = f"Execute {tool_name} with the provided arguments."
            except Exception as e:
                logger.error(f"Error loading prompt for {tool_name}: {str(e)}")
                prompts[tool_name] = f"Execute {tool_name} with the provided arguments."
        
        return prompts
    
    async def execute(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        llm_profile: Any,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute an intrinsic LLM tool"""
        
        if tool_name not in INTRINSIC_TOOL_NAMES:
            return {
                "success": False,
                "error": f"Unknown intrinsic tool: {tool_name}",
                "tool_type": "intrinsic"
            }
        
        try:
            # Get the prompt template for this tool
            prompt_template = self.tool_prompts.get(tool_name, "")
            
            # Prepare the prompt with arguments
            prompt = self._prepare_prompt(tool_name, prompt_template, arguments)
            
            # Call the LLM with specialized prompt
            from app.core.llm_client import LLMClient
            llm_client = LLMClient()
            
            result = await llm_client.call_advanced(
                llm_profile=llm_profile,
                prompt=prompt,
                temperature=0.3,  # Low temperature for precision
                max_tokens=2000,  # Reasonable limit for intrinsic tools
                json_mode=False  # Always text mode for intrinsic tools
            )
            
            if result:
                logger.info(f"Successfully executed intrinsic tool: {tool_name}")
                return {
                    "success": True,
                    "result": result,
                    "tool_type": "intrinsic",
                    "tool_name": tool_name
                }
            else:
                return {
                    "success": False,
                    "error": "No result from LLM",
                    "tool_type": "intrinsic",
                    "tool_name": tool_name
                }
                
        except Exception as e:
            logger.error(f"Error executing intrinsic tool {tool_name}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "tool_type": "intrinsic",
                "tool_name": tool_name
            }
    
    def _prepare_prompt(self, tool_name: str, template: str, arguments: Dict[str, Any]) -> str:
        """Prepare the prompt by filling in the template with arguments"""
        
        # Special handling for each tool's arguments
        if tool_name == "logical_reasoning":
            premises_text = ""
            if "premises" in arguments and arguments["premises"]:
                premises_text = "Premises:\n" + "\n".join(f"- {p}" for p in arguments["premises"])
            
            return template.format(
                problem=arguments.get("problem", ""),
                approach=arguments.get("approach", "deduction"),
                premises_text=premises_text
            )
        
        elif tool_name == "text_comprehension":
            question_text = ""
            if "question" in arguments:
                question_text = f"Question to answer: {arguments['question']}\n"
            
            extract_type = arguments.get("extract_type", "main_points")
            extraction_instructions = {
                "main_points": "Extract the main points and key ideas",
                "entities": "Identify all entities (people, places, organizations, etc.)",
                "relationships": "Map relationships between elements",
                "facts": "Extract concrete facts and data",
                "arguments": "Identify arguments and their structure"
            }
            
            return template.format(
                text=arguments.get("text", ""),
                question_text=question_text,
                extract_type=extract_type,
                extraction_instruction=extraction_instructions.get(extract_type, "Extract relevant information")
            )
        
        elif tool_name == "semantic_analysis":
            focus = arguments.get("focus", "meaning")
            focus_instructions = {
                "meaning": "underlying meanings and interpretations",
                "implications": "implications and consequences",
                "assumptions": "underlying assumptions and presuppositions",
                "contradictions": "internal contradictions or inconsistencies",
                "ambiguities": "ambiguous elements and multiple interpretations"
            }
            
            return template.format(
                content=arguments.get("content", ""),
                focus=focus,
                focus_instruction=focus_instructions.get(focus, "semantic elements")
            )
        
        elif tool_name == "summarization":
            length_constraint = ""
            if "max_length" in arguments:
                length_constraint = f"Maximum length: {arguments['max_length']} characters\n"
            
            focus_instruction = ""
            if "focus_areas" in arguments and arguments["focus_areas"]:
                focus_instruction = "Focus areas: " + ", ".join(arguments["focus_areas"]) + "\n"
            
            style = arguments.get("style", "paragraph")
            style_requirements = {
                "bullet_points": "Use clear bullet points",
                "paragraph": "Write flowing paragraphs",
                "executive": "Create executive summary format",
                "technical": "Use technical precision"
            }
            
            return template.format(
                content=arguments.get("content", ""),
                style=style,
                length_constraint=length_constraint,
                focus_instruction=focus_instruction,
                additional_requirements=style_requirements.get(style, "Be clear and concise")
            )
        
        elif tool_name == "knowledge_synthesis":
            information_list = "\n".join(
                f"{i+1}. {piece}" 
                for i, piece in enumerate(arguments.get("information_pieces", []))
            )
            
            contradiction_instruction = ""
            if arguments.get("resolve_contradictions", False):
                contradiction_instruction = "Identify and attempt to resolve any contradictions"
            else:
                contradiction_instruction = "Note any contradictions found"
            
            return template.format(
                information_list=information_list,
                synthesis_goal=arguments.get("synthesis_goal", "Create comprehensive understanding"),
                resolve_contradictions=arguments.get("resolve_contradictions", False),
                contradiction_instruction=contradiction_instruction
            )
        
        elif tool_name == "pattern_recognition":
            return template.format(
                data=arguments.get("data", ""),
                pattern_type=arguments.get("pattern_type", "conceptual")
            )
        
        elif tool_name == "causal_analysis":
            identify = arguments.get("identify", "causal_chain")
            identify_instructions = {
                "root_causes": "root causes and originating factors",
                "effects": "effects and consequences",
                "causal_chain": "complete causal chain",
                "contributing_factors": "all contributing factors"
            }
            
            return template.format(
                situation=arguments.get("situation", ""),
                identify=identify,
                identify_instruction=identify_instructions.get(identify, "causal elements")
            )
        
        elif tool_name == "hypothesis_generation":
            constraints_text = ""
            if "constraints" in arguments and arguments["constraints"]:
                constraints_text = "Constraints:\n" + "\n".join(f"- {c}" for c in arguments["constraints"]) + "\n"
                constraint_instruction = "Respect all constraints"
            else:
                constraint_instruction = "Be creative but plausible"
            
            return template.format(
                observations=arguments.get("observations", ""),
                constraints_text=constraints_text,
                number=arguments.get("number", 3),
                constraint_instruction=constraint_instruction
            )
        
        elif tool_name == "problem_decomposition":
            return template.format(
                problem=arguments.get("problem", ""),
                approach=arguments.get("approach", "hierarchical"),
                max_depth=arguments.get("max_depth", 3)
            )
        
        elif tool_name == "critical_evaluation":
            criteria_text = ""
            if "criteria" in arguments and arguments["criteria"]:
                criteria_text = "Evaluation criteria: " + ", ".join(arguments["criteria"]) + "\n"
                evaluation_instruction = "Apply specified criteria"
            else:
                evaluation_instruction = "Apply general critical thinking"
            
            return template.format(
                content=arguments.get("content", ""),
                criteria_text=criteria_text,
                identify_flaws=arguments.get("identify_flaws", True),
                evaluation_instruction=evaluation_instruction
            )
        
        elif tool_name == "analogy_reasoning":
            return template.format(
                source_domain=arguments.get("source_domain", ""),
                target_domain=arguments.get("target_domain", ""),
                mapping_focus=arguments.get("mapping_focus", "structural")
            )
        
        elif tool_name == "creative_brainstorming":
            constraints_text = ""
            constraint_instruction = "Think freely"
            if "constraints" in arguments and arguments["constraints"]:
                constraints_text = "Constraints:\n" + "\n".join(f"- {c}" for c in arguments["constraints"]) + "\n"
                constraint_instruction = "Work within constraints"
            
            techniques_text = ""
            technique_instruction = "Use creative thinking"
            if "techniques" in arguments and arguments["techniques"]:
                techniques_text = "Techniques: " + ", ".join(arguments["techniques"]) + "\n"
                technique_instruction = f"Apply {', '.join(arguments['techniques'])} techniques"
            
            return template.format(
                challenge=arguments.get("challenge", ""),
                constraints_text=constraints_text,
                techniques_text=techniques_text,
                quantity=arguments.get("quantity", 5),
                technique_instruction=technique_instruction,
                constraint_instruction=constraint_instruction
            )
        
        elif tool_name == "classification":
            categories_text = ""
            category_instruction = "Create appropriate categories"
            if "categories" in arguments and arguments["categories"]:
                categories_text = "Categories: " + ", ".join(arguments["categories"]) + "\n"
                category_instruction = "Use provided categories"
            
            return template.format(
                items=arguments.get("items", ""),
                categories_text=categories_text,
                criteria=arguments.get("criteria", "logical grouping"),
                category_instruction=category_instruction
            )
        
        elif tool_name == "completeness_check":
            requirements_text = ""
            if "requirements" in arguments and arguments["requirements"]:
                requirements_text = "Requirements:\n" + "\n".join(f"- {r}" for r in arguments["requirements"]) + "\n"
            
            return template.format(
                problem=arguments.get("problem", ""),
                solution_attempt=arguments.get("solution_attempt", ""),
                requirements_text=requirements_text
            )
        
        elif tool_name == "scenario_exploration":
            variables_text = ""
            if "variables" in arguments and arguments["variables"]:
                variables_text = "Variables to modify:\n" + "\n".join(f"- {v}" for v in arguments["variables"]) + "\n"
            
            return template.format(
                base_scenario=arguments.get("base_scenario", ""),
                variables_text=variables_text,
                time_horizon=arguments.get("time_horizon", "medium_term"),
                scenarios_count=arguments.get("scenarios_count", 3)
            )
        
        # Default fallback
        return f"Execute {tool_name} with arguments: {arguments}"


# Create singleton instance
intrinsic_tools_executor = IntrinsicLLMToolsExecutor()