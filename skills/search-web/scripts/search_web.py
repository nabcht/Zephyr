"""Web search skill — optimized DuckDuckGo search."""

from __future__ import annotations

try:
    from duckduckgo_search import DDGS
except ImportError:
    try:
        from ddgs import DDGS  # type: ignore[no-redef]
    except ImportError:
        DDGS = None


async def search_web(query: str, max_results: int = 5, freshness: str | None = None) -> str:
    """Search the web for up-to-date information."""
    if DDGS is None:
        return (
            "Web search is unavailable because neither 'duckduckgo-search' nor 'ddgs' is installed. "
            "Install one of them to enable this skill."
        )

    try:
        with DDGS() as ddgs:
            valid_freshness = freshness if freshness in {"d", "w", "m", "y"} else None
            results = list(
                ddgs.text(
                    query,
                    max_results=max_results,
                    timelimit=valid_freshness,
                    region="wt-wt",
                )
            )
    except Exception as exc:
        return f"Web search failed. Error: {exc}"

    if not results:
        return f"No results found for '{query}'. Try rephrasing or removing freshness constraints."

    lines: list[str] = []
    for index, result in enumerate(results, 1):
        title = result.get("title", "No Title")
        href = result.get("href", "#")
        body = result.get("body", "No description available.")
        lines.append(f"{index}. **{title}**\n   {href}\n   {body}")

    return "\n\n".join(lines)