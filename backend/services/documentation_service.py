"""Read markdown documents from the centralized Docs folder."""

from __future__ import annotations

from pathlib import Path

import config


class DocumentationService:
    """Expose selected markdown documents as API-backed content."""

    _ALLOWED_DOCS = {
        "docs": "docs.md",
        "features": "Features.md",
        "glossary": "glossary.md",
        "api-docs": "API_DOCS.md",
        "privacy": "PRIVACY.md",
        "terms": "TERMS.md",
    }

    def __init__(self, *, docs_root: Path | None = None) -> None:
        self._docs_root = docs_root or (config.PROJECT_ROOT / "Docs")

    def get_document(self, slug: str) -> dict[str, str]:
        filename = self._ALLOWED_DOCS.get(slug)
        if filename is None:
            raise KeyError(slug)

        document_path = self._docs_root / filename
        if not document_path.exists():
            raise FileNotFoundError(document_path)

        raw_content = document_path.read_text(encoding="utf-8")
        title, content = self._extract_title_and_body(raw_content, fallback_title=slug.replace("-", " ").title())
        try:
            source_path = document_path.relative_to(config.PROJECT_ROOT).as_posix()
        except ValueError:
            source_path = str(document_path)

        return {
            "slug": slug,
            "title": title,
            "content": content,
            "source_path": source_path,
        }

    @staticmethod
    def _extract_title_and_body(raw_content: str, *, fallback_title: str) -> tuple[str, str]:
        lines = raw_content.splitlines()
        first_content_index: int | None = None
        for index, line in enumerate(lines):
            if line.strip():
                first_content_index = index
                break

        if first_content_index is None:
            return fallback_title, ""

        first_line = lines[first_content_index].strip()
        if not first_line.startswith("# "):
            return fallback_title, raw_content.strip()

        title = first_line[2:].strip() or fallback_title
        body_lines = lines[first_content_index + 1 :]
        while body_lines and not body_lines[0].strip():
            body_lines.pop(0)
        return title, "\n".join(body_lines).strip()