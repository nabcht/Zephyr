---
name: archive-researcher
description: Deep-search Claude-Mem archive history using the search -> ids -> details workflow.
tags: [researcher, universal]
compatibility: Requires Python 3.10+
---

# archive-researcher

Use this skill when the agent needs historical technical context from Claude-Mem
that is too detailed for the local truth layer alone.

The skill follows Claude-Mem's token-efficient pattern:

1. Search for candidate observations.
2. Extract the relevant IDs.
3. Fetch full observation details only for those IDs.