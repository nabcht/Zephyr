---
name: search-personal-data
description: Search local files using hybrid semantic and keyword retrieval (ChromaDB + Whoosh). Falls back to recursive grep when the index is unavailable. Use when the user wants to find information in their local documents.
compatibility: Requires Python 3.10+. ChromaDB and Whoosh indexes should be built via the index-files skill for best results.
tags: [researcher]
---

# search-personal-data

Two-tier search strategy:

1. **Hybrid retrieval** (preferred) — semantic vector search via ChromaDB
   combined with exact keyword matching via Whoosh, merged and ranked.
2. **Grep fallback** — recursive file scan when no index is available.

## Usage

Call `search_personal_data(query, directory="", max_results=10)`.

## Implementation

Logic lives in `scripts/search_personal_data.py`.
