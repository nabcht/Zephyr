import logging
from pathlib import Path
import config

log = logging.getLogger("zephyr.manage_persona")

async def update_agent_role(role: str, system_prompt_markdown: str) -> str:
    """
    Creates or updates the system prompt instructions for a specific Agency agent.
    
    Args:
        role: The agent name (e.g., 'Supervisor', 'Researcher', 'Coder', 'Reviewer').
        system_prompt_markdown: The full text of the system prompt. 
                                MUST include the '{{durable_facts}}' placeholder.
    """
    normalized_role = role.strip()
    if normalized_role not in config.AGENCY_ROLES:
        allowed_roles = ", ".join(config.AGENCY_ROLES)
        return f"❌ Unknown agent role '{role}'. Allowed roles: {allowed_roles}."

    persona_dir: Path = config.PERSONAS_DIR
    persona_dir.mkdir(parents=True, exist_ok=True)

    file_path = persona_dir / f"{normalized_role}.md"
    
    # Validation: Ensure facts placeholder is present
    if config.PERSONA_PLACEHOLDER not in system_prompt_markdown:
        system_prompt_markdown = (
            system_prompt_markdown.rstrip()
            + f"\n\n## Durable Facts about the User\n{config.PERSONA_PLACEHOLDER}"
        )
        
    try:
        file_path.write_text(system_prompt_markdown, encoding="utf-8")
        log.info("Updated persona: %s", normalized_role)
        return f"✅ Agent '{normalized_role}' has been successfully updated in the μBrain. All future /mission calls will use these new instructions."
    except Exception as exc:
        return f"❌ Failed to update persona: {exc}"