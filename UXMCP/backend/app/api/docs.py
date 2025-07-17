from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from app.services.service_crud import service_crud
from datetime import datetime

router = APIRouter()


@router.get("/", response_class=PlainTextResponse)
async def generate_documentation():
    """Generate Markdown documentation for all active services"""
    
    # Get all active services
    active_services = await service_crud.list(active_only=True)
    
    # Build markdown
    md_lines = [
        "# UXMCP Active Services Documentation",
        f"\nGenerated on: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"\nTotal active services: {len(active_services)}",
        "\n---\n"
    ]
    
    for service in active_services:
        md_lines.extend([
            f"## {service.name}",
            f"\n**Route:** `{service.method} {service.route}`",
            f"\n**Description:** {service.description or 'No description provided'}",
            "\n### Parameters\n"
        ])
        
        if service.params:
            md_lines.append("| Name | Type | Required | Description |")
            md_lines.append("|------|------|----------|-------------|")
            
            for param in service.params:
                required = "Yes" if param.required else "No"
                desc = param.description or "-"
                md_lines.append(f"| {param.name} | {param.type} | {required} | {desc} |")
        else:
            md_lines.append("*No parameters*")
        
        if service.dependencies:
            md_lines.extend([
                "\n### Dependencies",
                "```python",
                "\n".join(service.dependencies),
                "```"
            ])
        
        if service.llm_profile:
            md_lines.append(f"\n**LLM Profile:** {service.llm_profile}")
        
        md_lines.extend([
            "\n### Code",
            "```python",
            service.code,
            "```",
            "\n---\n"
        ])
    
    return "\n".join(md_lines)