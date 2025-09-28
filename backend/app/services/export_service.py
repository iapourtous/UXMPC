"""
Export service for UXMCP data
Exports LLM profiles, services (tools), and agents to separate JSON files
"""

import json
import logging
from typing import Dict, Any, List
from datetime import datetime
from app.services.llm_crud import llm_crud
from app.services.service_crud import service_crud
from app.services.agent_crud import agent_crud

logger = logging.getLogger(__name__)


class ExportService:
    """Service to export UXMCP data to JSON format"""
    
    async def export_llm_profiles(self) -> Dict[str, Any]:
        """Export all LLM profiles to JSON format"""
        try:
            profiles = await llm_crud.list(skip=0, limit=1000)
            
            export_data = {
                "export_type": "llm_profiles",
                "export_date": datetime.utcnow().isoformat(),
                "total_count": len(profiles),
                "profiles": []
            }
            
            for profile in profiles:
                profile_data = {
                    "id": profile.id,
                    "name": profile.name,
                    "model": profile.model,
                    "endpoint": profile.endpoint,
                    "api_key": profile.api_key,
                    "max_tokens": profile.max_tokens,
                    "temperature": profile.temperature,
                    "mode": profile.mode,
                    "system_prompt": profile.system_prompt,
                    "description": profile.description,
                    "active": profile.active,
                    "created_at": profile.created_at.isoformat() if profile.created_at else None,
                    "updated_at": profile.updated_at.isoformat() if profile.updated_at else None
                }
                export_data["profiles"].append(profile_data)
            
            return export_data
        except Exception as e:
            logger.error(f"Error exporting LLM profiles: {e}")
            raise
    
    async def export_services(self) -> Dict[str, Any]:
        """Export all services/tools to JSON format"""
        try:
            services = await service_crud.list(skip=0, limit=1000)
            
            export_data = {
                "export_type": "services",
                "export_date": datetime.utcnow().isoformat(),
                "total_count": len(services),
                "services": []
            }
            
            for service in services:
                # Convert params to dict if they are objects
                params_data = []
                if service.params:
                    for param in service.params:
                        if hasattr(param, 'dict'):
                            params_data.append(param.dict())
                        elif isinstance(param, dict):
                            params_data.append(param)
                        else:
                            params_data.append({
                                "name": getattr(param, 'name', ''),
                                "type": getattr(param, 'type', 'string'),
                                "required": getattr(param, 'required', False),
                                "description": getattr(param, 'description', '')
                            })
                
                service_data = {
                    "id": service.id,
                    "name": service.name,
                    "service_type": service.service_type,
                    "route": service.route,
                    "method": service.method,
                    "params": params_data,
                    "code": service.code,
                    "dependencies": service.dependencies,
                    "input_schema": service.input_schema,
                    "output_schema": service.output_schema,
                    "llm_profile": service.llm_profile,
                    "description": service.description,
                    "documentation": service.documentation,
                    "active": service.active,
                    "created_at": service.created_at.isoformat() if service.created_at else None,
                    "updated_at": service.updated_at.isoformat() if service.updated_at else None
                }
                
                # Add type-specific fields
                if service.service_type == "resource":
                    service_data["mime_type"] = service.mime_type
                elif service.service_type == "prompt":
                    service_data["prompt_template"] = service.prompt_template
                    service_data["prompt_args"] = service.prompt_args
                
                export_data["services"].append(service_data)
            
            return export_data
        except Exception as e:
            logger.error(f"Error exporting services: {e}")
            raise
    
    async def export_agents(self) -> Dict[str, Any]:
        """Export all agents to JSON format"""
        try:
            agents = await agent_crud.list(skip=0, limit=1000)
            
            export_data = {
                "export_type": "agents",
                "export_date": datetime.utcnow().isoformat(),
                "total_count": len(agents),
                "agents": []
            }
            
            for agent in agents:
                agent_data = {
                    "id": agent.id,
                    "name": agent.name,
                    "llm_profile": agent.llm_profile,
                    "mcp_services": agent.mcp_services,
                    "system_prompt": agent.system_prompt,
                    "pre_prompt": agent.pre_prompt,
                    "endpoint": agent.endpoint,
                    "input_schema": agent.input_schema,
                    "output_schema": agent.output_schema,
                    "description": agent.description,
                    "active": agent.active,
                    "temperature": agent.temperature,
                    "max_tokens": agent.max_tokens,
                    "allow_parallel_tool_calls": agent.allow_parallel_tool_calls,
                    "require_tool_use": agent.require_tool_use,
                    "max_iterations": agent.max_iterations,
                    
                    # 7D Configuration
                    "backstory": agent.backstory,
                    "objectives": agent.objectives,
                    "constraints": agent.constraints,
                    "memory_enabled": agent.memory_enabled,
                    "memory_config": agent.memory_config,
                    "reasoning_strategy": agent.reasoning_strategy,
                    "reasoning_config": agent.reasoning_config,
                    "personality_traits": agent.personality_traits,
                    "decision_policies": agent.decision_policies,
                    
                    "created_at": agent.created_at.isoformat() if agent.created_at else None,
                    "updated_at": agent.updated_at.isoformat() if agent.updated_at else None
                }
                export_data["agents"].append(agent_data)
            
            return export_data
        except Exception as e:
            logger.error(f"Error exporting agents: {e}")
            raise
    
    async def export_all(self) -> Dict[str, Any]:
        """Export all data (LLM profiles, services, and agents) in a single structure"""
        try:
            llm_data = await self.export_llm_profiles()
            services_data = await self.export_services()
            agents_data = await self.export_agents()
            
            export_data = {
                "export_type": "complete",
                "export_date": datetime.utcnow().isoformat(),
                "llm_profiles": llm_data["profiles"],
                "services": services_data["services"],
                "agents": agents_data["agents"],
                "statistics": {
                    "total_llm_profiles": llm_data["total_count"],
                    "total_services": services_data["total_count"],
                    "total_agents": agents_data["total_count"],
                    "active_llm_profiles": sum(1 for p in llm_data["profiles"] if p["active"]),
                    "active_services": sum(1 for s in services_data["services"] if s["active"]),
                    "active_agents": sum(1 for a in agents_data["agents"] if a["active"])
                }
            }
            
            return export_data
        except Exception as e:
            logger.error(f"Error exporting all data: {e}")
            raise
    
    async def save_exports_to_files(self, output_dir: str = "/tmp") -> Dict[str, str]:
        """Save all exports to separate JSON files"""
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            files_created = {}
            
            # Export LLM profiles
            llm_data = await self.export_llm_profiles()
            llm_file = f"{output_dir}/llm_profiles_{timestamp}.json"
            with open(llm_file, 'w', encoding='utf-8') as f:
                json.dump(llm_data, f, indent=2, ensure_ascii=False)
            files_created["llm_profiles"] = llm_file
            
            # Export services
            services_data = await self.export_services()
            services_file = f"{output_dir}/services_{timestamp}.json"
            with open(services_file, 'w', encoding='utf-8') as f:
                json.dump(services_data, f, indent=2, ensure_ascii=False)
            files_created["services"] = services_file
            
            # Export agents
            agents_data = await self.export_agents()
            agents_file = f"{output_dir}/agents_{timestamp}.json"
            with open(agents_file, 'w', encoding='utf-8') as f:
                json.dump(agents_data, f, indent=2, ensure_ascii=False)
            files_created["agents"] = agents_file
            
            # Export complete data
            complete_data = await self.export_all()
            complete_file = f"{output_dir}/uxmcp_complete_{timestamp}.json"
            with open(complete_file, 'w', encoding='utf-8') as f:
                json.dump(complete_data, f, indent=2, ensure_ascii=False)
            files_created["complete"] = complete_file
            
            return files_created
        except Exception as e:
            logger.error(f"Error saving exports to files: {e}")
            raise


# Create singleton instance
export_service = ExportService()