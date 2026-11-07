"""Advisory comparison of explicit Limits source/ref clauses with step bounds.

This does not interpret free-form numeric claims, establish provenance, or make
the package pass a gate. Unrecognized prose receives no assessment. The narrow
grammar covers the source/ref clauses used in the Gym facts-page repair.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$")
_LIMITS_LABEL = re.compile(r"^\s*(?:\*\*|__)?Limits\b(?:\*\*|__)?\s*[:.(]", re.I)
_REF = re.compile(r"(?<![\w`])(?:`ref(?:erence)?`|ref(?:erence)?)\s*(?:=|:)?\s*`([^`\n]+)`", re.I)
_SOURCE = re.compile(r"(?<![\w`])(?:`source`|source)\s*(?:=|:)?\s*`([^`\n]+)`", re.I)
_NO_SOURCE = re.compile(r"\b(?:with\s+)?no source\b", re.I)


def limits_blocks(text: str) -> list[str]:
    """Plain Limits paragraphs or paragraphs beneath an exact Limits heading.

    Fenced examples, other sections and later unlabelled plain paragraphs are
    excluded. Each paragraph stays separate; assertions in different paragraphs
    are never joined into a claim.
    """
    blocks: list[str] = []
    paragraph: list[str] = []
    section_level: int | None = None
    labelled = False
    fence: str | None = None

    def flush() -> None:
        nonlocal paragraph, labelled
        if paragraph and (labelled or section_level is not None):
            blocks.append(" ".join(line.strip() for line in paragraph))
        paragraph = []
        labelled = False

    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(("```", "~~~")):
            flush()
            marker = stripped[:3]
            if fence is None:
                fence = marker
            elif marker == fence:
                fence = None
            continue
        if fence is not None:
            continue
        heading = _HEADING.match(line)
        if heading:
            flush()
            level, title = len(heading[1]), heading[2]
            if section_level is not None and level <= section_level:
                section_level = None
            if title.strip().lower() == "limits":
                section_level = level
            continue
        if not line.strip():
            flush()
            continue
        if not paragraph:
            labelled = bool(_LIMITS_LABEL.match(line))
        paragraph.append(line)
    flush()
    return blocks


def compare_limits(text: str, reference: object) -> list[str]:
    """Flag recognized source/ref tokens absent from current step action bounds.

    A token is compared with the union of actual step action-bound values. This
    avoids guessing which of several action fields a free-form sentence means.
    It cannot find swapped per-field citations or validate numeric equivalence.
    """
    if not isinstance(reference, dict):
        return []
    bounds = []
    actions = reference.get("actions")
    if not isinstance(actions, list):
        return []
    for action in actions:
        if not isinstance(action, dict) or action.get("cap_id") != "cap.world.step.v1":
            continue
        inputs = action.get("inputs")
        if not isinstance(inputs, list):
            continue
        for field in inputs:
            if (isinstance(field, dict) and isinstance(field.get("name"), str)
                    and field["name"].startswith("action.")
                    and isinstance(field.get("limit"), dict)):
                bounds.append(field["limit"])
    if not bounds:
        return []
    refs = {b["ref"] for b in bounds if isinstance(b.get("ref"), str)}
    sources = {b.get("source") for b in bounds if b.get("source") is None or isinstance(b.get("source"), str)}
    notes: list[str] = []
    for block in limits_blocks(text):
        # A Limits section can also document unrelated device controls. Require
        # an explicit action/step word before interpreting a source/ref clause.
        if not re.search(r"\b(?:action|step)\b", block, re.I):
            continue
        named_refs = set(_REF.findall(block))
        named_sources = set(_SOURCE.findall(block))
        # Historical pages called the synthetic env-id reference a source.
        historical_refs = {value for value in named_sources if re.search(r":\s*action_space$", value)}
        named_refs.update(historical_refs)
        named_sources -= historical_refs
        if _NO_SOURCE.search(block):
            named_sources.add(None)
        for value in sorted(named_refs - refs):
            notes.append(f"FACTS_LIMITS_REVIEW: facts.md Limits names ref {value!r}, which is absent from "
                         f"the current step action-bound refs {sorted(refs)!r}; the prose may be stale")
        for value in sorted(named_sources - sources, key=lambda item: str(item)):
            notes.append(f"FACTS_LIMITS_REVIEW: facts.md Limits names source {value!r}, which is absent from "
                         f"the current step action-bound sources {sorted(sources, key=lambda item: str(item))!r}; "
                         "the prose may be stale")
    return list(dict.fromkeys(notes))


def facts_limits_notes(directory: Path) -> list[str]:
    """Read only local prose and generated JSON; never inspect or import upstream."""
    try:
        text = (directory / "facts.md").read_text(encoding="utf-8")
        reference = json.loads((directory / "reference.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return []  # Gate/layout checks own unreadable or absent package inputs.
    return compare_limits(text, reference)
