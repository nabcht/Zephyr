# Python Custom Provider (/docs/providers/custom-providers/python)

This guide shows how to create custom providers for the Composio Python SDK. Custom providers enable compatibility with different AI frameworks and platforms.

# Provider architecture

The Composio SDK uses a provider architecture to adapt tools for different AI frameworks. The provider handles:

1. **Tool format transformation**: Converting Composio tools into formats compatible with specific AI platforms
2. **Platform-specific compatibility**: Providing helper methods for seamless compatibility

# Types of providers

There are two types of providers:

1. **Non-agentic providers**: Transform tools for platforms that don't have their own agency (e.g., OpenAI, Anthropic)
2. **Agentic providers**: Transform tools for platforms that have their own agency (e.g., LangChain, CrewAI)

# Provider class hierarchy

```
BaseProvider (Abstract)
├── NonAgenticProvider (Abstract)
│   └── OpenAIProvider (Concrete)
│   └── AnthropicProvider (Concrete)
│   └── [Your Custom Non-Agentic Provider] (Concrete)
└── AgenticProvider (Abstract)
    └── LangchainProvider (Concrete)
    └── [Your Custom Agentic Provider] (Concrete)
```

# Quick start

The fastest way to create a new provider is using the provider scaffolding script:

```bash
# Create a non-agentic provider
make create-provider name=myprovider

# Create an agentic provider
make create-provider name=myagent agentic=true

# Create provider with custom output directory
make create-provider name=myprovider output=/path/to/custom/dir

# Combine options
make create-provider name=myagent agentic=true output=/my/custom/path
```

This will create a new provider in the specified directory (default: `python/providers/<provider-name>/`) with:

* Complete package structure with `pyproject.toml`
* Provider implementation template
* Demo script
* README with usage examples
* Type annotations and proper inheritance

> The scaffolding script creates a fully functional provider template. You just need to implement the tool transformation logic specific to your platform. You can maintain your provider implementation in your own repository.

## Generated structure

The create-provider script generates the following structure:

```
python/providers/<provider-name>/
├── README.md                    # Documentation and usage examples
├── pyproject.toml              # Project configuration
├── setup.py                    # Setup script for pip compatibility
├── <provider-name>_demo.py     # Demo script showing usage
└── composio_<provider-name>/   # Package directory
    ├── __init__.py             # Package initialization
    ├── provider.py             # Provider implementation
    └── py.typed                # PEP 561 type marker
```

After generation, you can:

1. Navigate to the provider directory: `cd python/providers/<provider-name>`
2. Install in development mode: `uv pip install -e .`
3. Implement your provider logic in `composio_<provider-name>/provider.py`
4. Test with the demo script: `python <provider-name>_demo.py`

# Creating a non-agentic provider

Non-agentic providers inherit from the `NonAgenticProvider` abstract class:

```python
from typing import List, Optional, Sequence, TypeAlias
from composio.core.provider import NonAgenticProvider
from composio.types import Tool, Modifiers, ToolExecutionResponse

# Define your tool format
class MyAITool:
    def __init__(self, name: str, description: str, parameters: dict):
        self.name = name
        self.description = description
        self.parameters = parameters

# Define your tool collection format
MyAIToolCollection: TypeAlias = List[MyAITool]

# Create your provider
class MyAIProvider(NonAgenticProvider[MyAITool, MyAIToolCollection], name="my-ai-platform"):
    """Custom provider for My AI Platform"""

    def wrap_tool(self, tool: Tool) -> MyAITool:
        """Transform a single tool to platform format"""
        return MyAITool(
            name=tool.slug,
            description=tool.description or "",
            parameters={
                "type": "object",
                "properties": tool.input_parameters.get("properties", {}),
                "required": tool.input_parameters.get("required", [])
            }
        )

    def wrap_tools(self, tools: Sequence[Tool]) -> MyAIToolCollection:
        """Transform a collection of tools"""
        return [self.wrap_tool(tool) for tool in tools]

    # Optional: Custom helper methods for your AI platform
    def execute_my_ai_tool_call(
        self,
        user_id: str,
        tool_call: dict,
        modifiers: Optional[Modifiers] = None
    ) -> ToolExecutionResponse:
        """Execute a tool call in your platform's format

        Example usage:
        result = my_provider.execute_my_ai_tool_call(
            user_id="default",
            tool_call={"name": "GITHUB_STAR_REPO", "arguments": {"owner": "composiohq", "repo": "composio"}}
        )
        """
        # Use the built-in execute_tool method
        return self.execute_tool(
            slug=tool_call["name"],
            arguments=tool_call["arguments"],
            modifiers=modifiers,
            user_id=user_id
        )
```

# Creating an agentic provider

Agentic providers inherit from the `AgenticProvider` abstract class:

```python
from typing import Callable, Dict, List, Sequence
from composio.core.provider import AgenticProvider, AgenticProviderExecuteFn
from composio.types import Tool
from my_provider import AgentTool

# Import the Tool/Function class that represents a callable tool for your framework
# Optionally define your custom tool format below
# class AgentTool:
#     def __init__(self, name: str, description: str, execute: Callable, schema: dict):
#         self.name = name
#         self.description = description
#         self.execute = execute
#         self.schema = schema

# Define your tool collection format (typically a List)
AgentToolCollection: TypeAlias = List[AgentTool]

# Create your provider
class MyAgentProvider(AgenticProvider[AgentTool, List[AgentTool]], name="my-agent-platform"):
    """Custom provider for My Agent Platform"""

    def wrap_tool(self, tool: Tool, execute_tool: AgenticProviderExecuteFn) -> AgentTool:
        """Transform a single tool with execute function"""
        def execute_wrapper(**kwargs) -> Dict:
            result = execute_tool(tool.slug, kwargs)
            if not result.get("successful", False):
                raise Exception(result.get("error", "Tool execution failed"))
            return result.get("data", {})

        return AgentTool(
            name=tool.slug,
            description=tool.description or "",
            execute=execute_wrapper,
            schema=tool.input_parameters
        )

    def wrap_tools(
        self,
        tools: Sequence[Tool],
        execute_tool: AgenticProviderExecuteFn
    ) -> AgentToolCollection:
        """Transform a collection of tools with execute function"""
        return [self.wrap_tool(tool, execute_tool) for tool in tools]
```

# Using your custom provider

After creating your provider, use it with the Composio SDK:

## Non-agentic provider example

```python
from composio import Composio
from composio_myai import MyAIProvider
from myai import MyAIClient  # Your AI platform's client

# Initialize tools
myai_client = MyAIClient()
composio = Composio(provider=MyAIProvider())

# Define task
task = "Star a repo composiohq/composio on GitHub"

# Get GitHub tools that are pre-configured
tools = composio.tools.get(user_id="default", toolkits=["GITHUB"])

# Get response from your AI platform (example)
response = myai_client.chat.completions.create(
    model="your-model",
    tools=tools,  # These are in your platform's format
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": task},
    ],
)
print(response)

# Execute the function calls
result = composio.provider.handle_tool_calls(response=response, user_id="default")
print(result)
```

## Agentic provider example

```python
import asyncio
from agents import Agent, Runner
from composio_myagent import MyAgentProvider
from composio import Composio

# Initialize Composio toolset
composio = Composio(provider=MyAgentProvider())

# Get all the tools
tools = composio.tools.get(
    user_id="default",
    tools=["GITHUB_STAR_A_REPOSITORY_FOR_THE_AUTHENTICATED_USER"],
)

# Create an agent with the tools
agent = Agent(
    name="GitHub Agent",
    instructions="You are a helpful assistant that helps users with GitHub tasks.",
    tools=tools,
)

# Run the agent
async def main():
    result = await Runner.run(
        starting_agent=agent,
        input=(
            "Star the repository composiohq/composio on GitHub. If done "
            "successfully, respond with 'Action executed successfully'"
        ),
    )
    print(result.final_output)

asyncio.run(main())
```

# Best practices

1. **Keep providers focused**: Each provider should integrate with one specific platform
2. **Handle errors gracefully**: Catch and transform errors from tool execution
3. **Follow platform conventions**: Adopt naming and structural conventions of the target platform
4. **Use type annotations**: Leverage Python's typing system for better IDE support and documentation
5. **Cache transformed tools**: Store transformed tools when appropriate to improve performance
6. **Add helper methods**: Provide convenient methods for common platform-specific operations
7. **Document your provider**: Include docstrings and usage examples
8. **Set meaningful provider names**: Use the name parameter for telemetry and debugging

---

📚 **More documentation:** [View all docs](https://docs.composio.dev/llms.txt) | [Glossary](https://docs.composio.dev/llms.mdx/docs/glossary) | [Cookbooks](https://docs.composio.dev/llms.mdx/cookbooks) | [API Reference](https://docs.composio.dev/llms.mdx/reference)

---

# Composio SDK — Instructions for AI Code Generators

**Purpose:** Enforce only the **current** and **correct** patterns for integrating [Composio](https://composio.dev/) tools into AI agents.
**Scope:** All AI-generated code using Composio must follow these guardrails.

---

## 1. Correct Composio Integration

Composio supports two integration modes: **Native Tools** (with a provider package) and **MCP** (no provider package needed).

### Native Tools

```python
# ✅ CORRECT — Python (defaults to OpenAI)
from composio import Composio

composio = Composio()
session = composio.create(user_id="user_123")
tools = session.tools()
# Pass tools to your agent/LLM framework
```

```typescript
// ✅ CORRECT — TypeScript (defaults to OpenAI)
import { Composio } from "@composio/core";

const composio = new Composio();
const session = await composio.create("user_123");
const tools = await session.tools();
// Pass tools to your agent/LLM framework
```

For other providers, pass the provider explicitly. Provider packages follow the naming convention: `composio_<provider>` for Python, `@composio/<provider>` for TypeScript.

### MCP

Use `session.mcp.url` and `session.mcp.headers` with any MCP-compatible client (Claude Desktop, Cursor, OpenAI Agents, etc.). No provider package needed.

---

## 2. CRITICAL INSTRUCTIONS FOR AI MODELS

### 2.1 — ALWAYS DO THE FOLLOWING

1. **Use `composio.create(user_id)`** to create a session — this is the entry point for all Composio integrations.
2. **Use `session.tools()`** for native tool integration or **`session.mcp.url`** for MCP integration.
3. **Import** from the correct provider package (`composio_<provider>` for Python, `@composio/<provider>` for TypeScript).
4. **Pass `user_id` to `composio.create()`**, not to individual tool calls.

### 2.2 — NEVER DO THE FOLLOWING

1. **Do not** instruct users to manually create auth configs or connected accounts before running.
2. **Do not** import from `composio_openai` / `@composio/openai` when using OpenAI Agents SDK — use `composio_openai_agents` / `@composio/openai-agents` instead.

### 2.3 — DISCOURAGED (do not use unless user explicitly asks)

Do **not** generate `composio.tools.get()`, `composio.tools.execute()`, or `composio.provider.handle_tool_calls()` unless the user explicitly requests direct tool execution. These are a supported but **not recommended** low-level interface.


---

## Terminology Migration (old → current)

If you encounter these terms in error messages, old documentation, or user prompts, translate them to the current equivalents. **Do not use the old terms in generated code or explanations.**

| Old term (v1/v2) | Current term (v3) | In code |
|---|---|---|
| entity ID | user ID | `user_id` parameter |
| actions | tools | e.g., `GITHUB_CREATE_ISSUE` is a *tool* |
| apps / appType | toolkits | e.g., `github` is a *toolkit* |
| integration / integration ID | auth config / auth config ID | `auth_config_id` parameter |
| connection | connected account | `connected_accounts` namespace |
| ComposioToolSet / OpenAIToolSet | `Composio` class with a provider | `Composio(provider=...)` |
| toolset | provider | e.g., `OpenAIProvider` |

If a user says "entity ID", they mean `user_id`. If they say "integration", they mean "auth config". Always respond using the current terminology.

