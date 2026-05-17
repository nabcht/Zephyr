---
name: manage-persona
description: Create, update, or refine the system prompts for the Agency roles (Supervisor, Researcher, Coder, Reviewer).
compatibility: ["python>=3.11"]
tags: ["supervisor", "universal"]
---

# manage-persona

This tool allows μZephyr to modify its own internal "Agency" personas. By writing to the `knowledge/brain/personas/` directory, this skill changes the fundamental behavior and instructions of the Supervisor, Researcher, Coder, and Reviewer agents.

## Usage

This skill is primarily used by the **Supervisor** or the user to:
1.  **Specialise agents**: e.g., "Update the Researcher to focus specifically on technical documentation."
2.  **Add context**: Ensure agents are aware of new integrations like **Claude-Mem**.
3.  **Refine performance**: Adjust the Reviewer's strictness or the Coder's formatting style.

### Important Note
All persona files must include the `{{durable_facts}}` placeholder to ensure the agent maintains access to the user's long-term memory. If missing, this tool will append it automatically.