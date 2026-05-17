---
name: browser-search
description: Search local Chrome or Edge browser history for pages matching a keyword query. Use when the user wants to find previously visited websites or recall browsing history.
compatibility: Requires Python 3.10+. Chrome or Edge must be installed on the host system.
tags: [researcher]
---

# browser-search

Queries the local SQLite history database of Chrome or Edge for URLs and page
titles that match a keyword.  Copies the locked database to a temp file before
reading so the browser does not need to be closed.

## Usage

Call `browser_search(query, max_results=20)`.

## Implementation

Logic lives in `scripts/browser_search.py`.
