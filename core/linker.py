"""μBrain – Deterministic entity linker.

Extracts #PersonName and [[ProjectName]] tokens from text using pure regex
(no LLM, no external API) and maintains per-entity Markdown files under
config.ENTITIES_DIR with back-references to timeline.log line numbers.

The linker also infers deterministic relationships between people and projects
from nearby verbs inside a fact, then stores those relation edges alongside the
entity facts. Query-time entity context follows those edges one hop so related
projects or people can be surfaced even if the query only names one side.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path

import config

# ── Compiled patterns ─────────────────────────────────────────────────────────
# #PersonName  – capital-first, at least two letters, word-boundary terminated
_PERSON_RE = re.compile(r"#([A-Z][A-Za-z][A-Za-z0-9_]*)\b")

# [[ProjectName]] – alphanumeric with spaces, underscores, or hyphens
_PROJECT_RE = re.compile(r"\[\[([\w\s.-]+)\]\]")
_RELATION_LINE_RE = re.compile(
    r"^- \[REL L(?P<line_no>\d+)\] (?P<relation>[a-z_]+) -> (?P<target_type>person|project):(?P<target_name>.+)$",
    re.MULTILINE,
)


@dataclass(frozen=True, slots=True)
class EntityMention:
    entity_type: str
    name: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class EntityRelation:
    subject_type: str
    subject_name: str
    relation: str
    object_type: str
    object_name: str


@dataclass(frozen=True, slots=True)
class _RelationPattern:
    pattern: re.Pattern[str]
    left_type: str
    right_type: str
    left_relation: str
    right_relation: str


_RELATION_PATTERNS: tuple[_RelationPattern, ...] = (
    _RelationPattern(re.compile(r"\b(?:collaborat(?:e|es|ed|ing) on)\b"), "person", "project", "collaborates_on", "has_collaborator"),
    _RelationPattern(re.compile(r"\b(?:work(?:s|ed|ing)? on)\b"), "person", "project", "works_on", "has_contributor"),
    _RelationPattern(re.compile(r"\b(?:contribut(?:e|es|ed|ing) to)\b"), "person", "project", "contributes_to", "has_contributor"),
    _RelationPattern(re.compile(r"\b(?:lead(?:s|ing)?)\b"), "person", "project", "leads", "has_lead"),
    _RelationPattern(re.compile(r"\b(?:maintain(?:s|ed|ing)?)\b"), "person", "project", "maintains", "maintained_by"),
    _RelationPattern(re.compile(r"\b(?:build(?:s|ing)?)\b"), "person", "project", "builds", "built_by"),
    _RelationPattern(re.compile(r"\b(?:creat(?:e|es|ed|ing)|found(?:s|ed|ing))\b"), "person", "project", "creates", "created_by"),
    _RelationPattern(re.compile(r"\b(?:manag(?:e|es|ed|ing))\b"), "person", "project", "manages", "managed_by"),
    _RelationPattern(re.compile(r"\b(?:support(?:s|ed|ing))\b"), "person", "project", "supports", "supported_by"),
    _RelationPattern(re.compile(r"\b(?:review(?:s|ed|ing))\b"), "person", "project", "reviews", "reviewed_by"),
    _RelationPattern(re.compile(r"\b(?:research(?:es|ed|ing))\b"), "person", "project", "researches", "researched_by"),
    _RelationPattern(re.compile(r"\b(?:is|was|being)\s+led by\b|\bled by\b"), "project", "person", "led_by", "leads"),
    _RelationPattern(re.compile(r"\b(?:is|was|being)\s+maintained by\b|\bmaintained by\b"), "project", "person", "maintained_by", "maintains"),
    _RelationPattern(re.compile(r"\b(?:is|was|being)\s+built by\b|\bbuilt by\b"), "project", "person", "built_by", "builds"),
    _RelationPattern(re.compile(r"\b(?:is|was|being)\s+created by\b|\bcreated by\b"), "project", "person", "created_by", "creates"),
    _RelationPattern(re.compile(r"\b(?:is|was|being)\s+managed by\b|\bmanaged by\b"), "project", "person", "managed_by", "manages"),
    _RelationPattern(re.compile(r"\b(?:integrat(?:es|ed|ing) with)\b"), "project", "project", "integrates_with", "integrates_with"),
    _RelationPattern(re.compile(r"\b(?:depend(?:s|ed|ing)? on)\b"), "project", "project", "depends_on", "depended_on_by"),
    _RelationPattern(re.compile(r"\b(?:replace(?:s|d|ing)?)\b"), "project", "project", "replaces", "replaced_by"),
)


def extract_entity_mentions(text: str) -> list[EntityMention]:
    """Return ordered entity mentions with source spans preserved."""
    mentions: list[EntityMention] = []

    for match in _PERSON_RE.finditer(text):
        mentions.append(EntityMention("person", match.group(1), match.start(), match.end()))

    for match in _PROJECT_RE.finditer(text):
        mentions.append(EntityMention("project", match.group(1).strip(), match.start(), match.end()))

    mentions.sort(key=lambda mention: mention.start)
    return mentions


def _normalize_gap(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def extract_relations(text: str) -> list[EntityRelation]:
    """Infer deterministic relationships between extracted entity mentions."""
    mentions = extract_entity_mentions(text)
    if len(mentions) < 2:
        return []

    results: list[EntityRelation] = []
    seen: set[tuple[str, str, str, str, str]] = set()

    for left_index, left in enumerate(mentions):
        for right in mentions[left_index + 1:]:
            gap = _normalize_gap(text[left.end:right.start])
            if not gap or len(gap) > 160:
                continue

            matched_pattern: _RelationPattern | None = None
            for pattern in _RELATION_PATTERNS:
                if left.entity_type != pattern.left_type or right.entity_type != pattern.right_type:
                    continue
                if pattern.pattern.search(gap):
                    matched_pattern = pattern
                    break

            if matched_pattern is None:
                continue

            forward_key = (left.entity_type, left.name, matched_pattern.left_relation, right.entity_type, right.name)
            if forward_key not in seen:
                seen.add(forward_key)
                results.append(
                    EntityRelation(
                        subject_type=left.entity_type,
                        subject_name=left.name,
                        relation=matched_pattern.left_relation,
                        object_type=right.entity_type,
                        object_name=right.name,
                    )
                )

            reverse_key = (right.entity_type, right.name, matched_pattern.right_relation, left.entity_type, left.name)
            if reverse_key not in seen:
                seen.add(reverse_key)
                results.append(
                    EntityRelation(
                        subject_type=right.entity_type,
                        subject_name=right.name,
                        relation=matched_pattern.right_relation,
                        object_type=left.entity_type,
                        object_name=left.name,
                    )
                )

    return results


def extract_entities(text: str) -> list[tuple[str, str]]:
    """Return a deduplicated list of (entity_type, entity_name) tuples found in *text*.

    entity_type is either ``"person"`` or ``"project"``.
    """
    seen: set[tuple[str, str]] = set()
    results: list[tuple[str, str]] = []

    for mention in extract_entity_mentions(text):
        key = (mention.entity_type, mention.name)
        if key in seen:
            continue
        seen.add(key)
        results.append(key)

    return results


def _entity_path(entity_name: str) -> Path:
    return config.ENTITIES_DIR / f"{entity_name}.md"


def _ensure_entity_file(entity_name: str) -> Path:
    config.ENTITIES_DIR.mkdir(parents=True, exist_ok=True)
    entity_path = _entity_path(entity_name)
    if not entity_path.exists():
        entity_path.write_text(f"# {entity_name}\n\n", encoding="utf-8")
    return entity_path


def _append_unique_line(entity_name: str, line: str) -> None:
    entity_path = _ensure_entity_file(entity_name)
    existing_lines = entity_path.read_text(encoding="utf-8").splitlines()
    if line in existing_lines:
        return
    with entity_path.open("a", encoding="utf-8") as fh:
        fh.write(f"{line}\n")


def _render_relation_line(relation: EntityRelation, line_no: int) -> str:
    return (
        f"- [REL L{line_no}] {relation.relation} -> "
        f"{relation.object_type}:{relation.object_name}"
    )


def _related_entities_from_content(content: str) -> list[tuple[str, str]]:
    related: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for match in _RELATION_LINE_RE.finditer(content):
        entity_key = (match.group("target_type"), match.group("target_name").strip())
        if entity_key in seen:
            continue
        seen.add(entity_key)
        related.append(entity_key)

    return related


def update_entity_file(entity_name: str, fact: str, line_no: int) -> None:
    """Append *fact* to the entity's Markdown file, tagged with *line_no*.

    Creates the file with a heading if it does not yet exist.
    """
    _append_unique_line(entity_name, f"- [L{line_no}] {fact}")


def update_entity_relation(relation: EntityRelation, line_no: int) -> None:
    """Append a relationship line to the source entity file if it is not already present."""
    _append_unique_line(relation.subject_name, _render_relation_line(relation, line_no))


def update_entities_from_fact(fact: str, line_no: int) -> None:
    """Extract all entities from *fact* and update their individual files."""
    for _entity_type, name in extract_entities(fact):
        update_entity_file(name, fact, line_no)
    for relation in extract_relations(fact):
        update_entity_relation(relation, line_no)


def get_entity_context(query: str) -> str:
    """Return concatenated entity-file contents for every entity found in *query*.

    Returns an empty string if no entity files exist for the extracted tokens.
    """
    if not config.ENTITIES_DIR.exists():
        return ""

    parts: list[str] = []
    direct_entities = extract_entities(query)
    seen_entities: set[tuple[str, str]] = set()
    related_entities: list[tuple[str, str]] = []

    for entity_key in direct_entities:
        if entity_key in seen_entities:
            continue
        seen_entities.add(entity_key)
        _entity_type, name = entity_key
        entity_path = _entity_path(name)
        if not entity_path.exists():
            continue
        content = entity_path.read_text(encoding="utf-8").strip()
        if content:
            parts.append(content)
            for related_entity in _related_entities_from_content(content):
                if related_entity not in seen_entities and related_entity not in related_entities:
                    related_entities.append(related_entity)

    for _entity_type, name in related_entities:
        entity_path = _entity_path(name)
        if not entity_path.exists():
            continue
        content = entity_path.read_text(encoding="utf-8").strip()
        if content:
            parts.append(content)
            seen_entities.add((_entity_type, name))

    return "\n---\n".join(parts)
