import type { ToolCatalogEntry } from "./types/api";

export type ToolCatalogCategoryId = "code-generation" | "memory" | "core";

interface ToolCatalogKeywordRule {
  keywords: string[];
  requiredTags?: string[];
}

export interface ToolCatalogCategoryDefinition {
  id: ToolCatalogCategoryId;
  title: string;
  description: string;
  emptyMessage: string;
  excludedSources?: string[];
  explicitToolNames?: string[];
  namePrefixes?: string[];
  nameIncludes?: string[];
  contentKeywordRule?: ToolCatalogKeywordRule;
}

const DEFAULT_TOOL_CATALOG_CATEGORY_ID: ToolCatalogCategoryId = "core";

export const TOOL_CATALOG_CATEGORY_DEFINITIONS: ToolCatalogCategoryDefinition[] = [
  {
    id: "code-generation",
    title: "Code Generation Tools",
    description: "Repository-changing tools for drafting, applying, merging, testing, and package or skill creation work.",
    emptyMessage: "No code-generation tools are currently visible.",
    excludedSources: ["mcp"],
    explicitToolNames: [
      "apply_core_change",
      "install_python_package",
      "merge_python_files",
      "prepare_sandbox_backend",
      "propose_core_change",
      "run_test_in_sandbox",
      "write_skill",
    ],
    namePrefixes: ["write_", "apply_", "merge_", "propose_", "install_"],
    nameIncludes: ["run_test", "prepare_sandbox_backend"],
    contentKeywordRule: {
      keywords: ["write", "apply", "merge", "install", "propose", "test", "patch", "package"],
      requiredTags: ["coder"],
    },
  },
  {
    id: "memory",
    title: "Memory Tools",
    description: "Durable fact capture, deletion, and memory-evolution helpers.",
    emptyMessage: "No memory-focused tools are currently visible.",
    excludedSources: ["mcp"],
    explicitToolNames: ["memory_durable_fact", "memory_force_delete_durable_fact", "evolve_memory"],
  },
  {
    id: "core",
    title: "Core Tools",
    description: "Search, research, workflow, and runtime-inspection utilities outside memory and MCP integration.",
    emptyMessage: "No core tools are currently visible.",
  },
];

interface NormalizedToolCatalogCategoryDefinition {
  id: ToolCatalogCategoryId;
  explicitToolNames: Set<string>;
  excludedSources: Set<string>;
  namePrefixes: string[];
  nameIncludes: string[];
  requiredTags: Set<string>;
  keywordRule: ToolCatalogKeywordRule | null;
}

const NORMALIZED_CATEGORY_DEFINITIONS: NormalizedToolCatalogCategoryDefinition[] = TOOL_CATALOG_CATEGORY_DEFINITIONS.map((definition) => ({
  id: definition.id,
  explicitToolNames: new Set(definition.explicitToolNames ?? []),
  excludedSources: new Set((definition.excludedSources ?? []).map((source) => source.toLowerCase())),
  namePrefixes: (definition.namePrefixes ?? []).map((prefix) => prefix.toLowerCase()),
  nameIncludes: (definition.nameIncludes ?? []).map((value) => value.toLowerCase()),
  requiredTags: new Set((definition.contentKeywordRule?.requiredTags ?? []).map((tag) => tag.toLowerCase())),
  keywordRule: definition.contentKeywordRule ?? null,
}));

function matchesCategory(tool: ToolCatalogEntry, definition: NormalizedToolCatalogCategoryDefinition): boolean {
  if (definition.id === DEFAULT_TOOL_CATALOG_CATEGORY_ID) {
    return false;
  }

  if (definition.excludedSources.has(tool.source.toLowerCase())) {
    return false;
  }

  if (definition.explicitToolNames.has(tool.name)) {
    return true;
  }

  const normalizedName = tool.name.toLowerCase();
  if (definition.namePrefixes.some((prefix) => normalizedName.startsWith(prefix))) {
    return true;
  }
  if (definition.nameIncludes.some((value) => normalizedName.includes(value))) {
    return true;
  }

  if (definition.keywordRule === null) {
    return false;
  }

  const normalizedTags = new Set(tool.tags.map((tag) => tag.toLowerCase()));
  if (definition.requiredTags.size) {
    for (const tag of definition.requiredTags) {
      if (!normalizedTags.has(tag)) {
        return false;
      }
    }
  }

  const haystack = `${tool.name} ${tool.description}`.toLowerCase();
  return definition.keywordRule.keywords.some((keyword) => haystack.includes(keyword.toLowerCase()));
}

export function categorizeToolCatalogEntry(tool: ToolCatalogEntry): ToolCatalogCategoryId {
  for (const definition of NORMALIZED_CATEGORY_DEFINITIONS) {
    if (matchesCategory(tool, definition)) {
      return definition.id;
    }
  }

  return DEFAULT_TOOL_CATALOG_CATEGORY_ID;
}

export function sortToolCatalogEntries(tools: ToolCatalogEntry[]): ToolCatalogEntry[] {
  return [...tools].sort((left, right) => left.name.localeCompare(right.name));
}