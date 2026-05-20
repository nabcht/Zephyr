from __future__ import annotations

import unittest

from core.tool_registry import ToolRegistry


class ToolRegistryTests(unittest.TestCase):
    def test_register_derives_schema_from_signature(self) -> None:
        registry = ToolRegistry()

        def lookup(query: str, limit: int = 5, enabled: bool = True) -> str:
            return query

        registry.register(lookup, name="lookup", tags=["universal"], source="manual")
        tools = registry.list_tools()

        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0].name, "lookup")
        self.assertEqual(tools[0].parameters["properties"]["query"]["type"], "string")
        self.assertEqual(tools[0].parameters["properties"]["limit"]["type"], "integer")
        self.assertEqual(tools[0].parameters["properties"]["enabled"]["type"], "boolean")
        self.assertEqual(tools[0].parameters["required"], ["query"])

    def test_remove_by_source_keeps_other_tools(self) -> None:
        registry = ToolRegistry()
        registry.register(lambda: "builtin", name="builtin_tool", source="builtin")
        registry.register(lambda: "manual", name="manual_tool", source="manual")

        registry.remove_by_source({"builtin"})

        self.assertEqual(registry.list_tool_names(), ["manual_tool"])

    def test_compact_provider_schema_trims_descriptions_and_parameter_metadata(self) -> None:
        registry = ToolRegistry()

        def search_repository(query: str, include_archived_results: bool = False) -> str:
            return query

        registry.register(
            search_repository,
            name="search_repository",
            description=(
                "Search the repository for relevant files, symbols, and documentation comments. "
                "Use this when the user asks for concrete repository facts or implementation details."
            ),
            source="manual",
        )

        full_schema = registry.get_openai_tool_schemas()[0]
        compact_schema = registry.get_openai_tool_schemas(compact_for_provider=True)[0]

        self.assertIn("documentation comments", full_schema["function"]["description"])
        self.assertLess(len(compact_schema["function"]["description"]), len(full_schema["function"]["description"]))
        self.assertNotIn(
            "description",
            compact_schema["function"]["parameters"]["properties"]["query"],
        )


if __name__ == "__main__":
    unittest.main()