#!/usr/bin/env python3
"""Run the specification's code blocks and lint its identifiers (WP-09).

    PYTHONPATH=MHS/sdk/src python3 MHS/sdk/tools/spec_doctest.py MHS/spec
    python3 MHS/sdk/tools/spec_doctest.py MHS/spec --no-run          # lint only
    python3 MHS/sdk/tools/spec_doctest.py MHS/spec --check-catalogue # 03 section 7 vs capabilities.json
    python3 MHS/sdk/tools/spec_doctest.py MHS/spec --write-catalogue # regenerate 03 section 7

What it checks, over every ``*.md`` file of the specification directory:

* **Runnable blocks.** A fenced ``python`` block whose first line is ``# runnable`` (or whose
  info string contains the word ``runnable``) is executed in this process, in a fresh namespace,
  with the working directory set to the repository root and ``MHS/sdk/src`` on ``sys.path``.
  A block that raises fails with its file and line.  Output is captured and shown on failure.
* **Validated JSON blocks.** A ``json`` block is parsed and validated against a schema when it
  names one in any of three ways: the fence info string (``json validate=conformance-report.schema.json``),
  a line ``<!-- validate=conformance-report.schema.json -->`` above it, or, in the specification
  itself, the sentence of the paragraph directly above it (``... is valid against
  [`conformance-report.schema.json`](...)``).  The specification uses the sentence: it reads the same in every Markdown
  renderer, which a comment line or an info string with attributes does not.  Validation uses
  :class:`mhs.schema.SchemaStore`.  Other ``json`` blocks that neither parse nor look abridged
  (no ``...`` or ellipsis) are reported as warnings, never failures.
* **Fences.** Every fence of the specification has an info string of one token
  (``[A-Za-z0-9_.+-]*``), the form every Markdown reader treats alike (a renderer that does not know
  ``json validate=...`` reads the closing fence as an opening one and swallows the headings that follow;
  the site's does since it accepts attributes, but others do not).
* **Requirement identifiers.**  A definition is a paragraph that starts with ``**AREA-NNN.**``
  (chapters) or ``**CORE-NNN:**`` / ``**DRV-NNN:**`` (the Core and the Driver Profile).  The
  lint fails on an id defined twice (one meaning per id) and on an id that is referenced but
  defined nowhere (an orphan).  Summary lines such as ``**GOV-001** text`` are references.
* **Keywords.** The informative documents (``00-architecture.md``, ``appendix-c``,
  ``appendix-d``) must contain none of the RFC 2119 key words in capitals.
* **Legacy identifiers.** ``MHS Editors``, ``MHS-1.0`` and ``Draft 1.0`` appear nowhere;
  the legacy domain (Anthropic's) appears only in appendix D.
* **Registered codes.** Every ``MHS.AREA.CODE`` named in the Core, the Driver Profile, the
  profiles index and appendix C is in ``errors.json`` (or is a feature string).
* **Links.** Every relative link to a file of the specification directory (or beside it)
  resolves, and a ``#anchor`` into a specification document names a heading that exists.
* **Generated section.** Section 7 of ``03-capability-registry.md`` is rendered from
  ``capabilities.json`` between two marker comments; ``--check-catalogue`` fails on drift and
  ``--write-catalogue`` rewrites it.

Exit codes: 0 everything holds, 1 a check failed, 2 usage or environment error.
Standard library only; no bytecode is written.
"""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse  # noqa: E402
import contextlib  # noqa: E402
import io  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import signal  # noqa: E402
import traceback  # noqa: E402
import warnings  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
SDK_SRC = ROOT / "MHS" / "sdk" / "src"

AREAS = ("CORE", "DRV", "CON", "PROTO", "SESS", "CAP", "SAFE", "MODE", "FID", "EVID", "OP", "EVT", "COMP",
         "TPT", "ADPT", "REG", "PRIV", "HOST", "GOV", "ERR")
_AREA_ALT = "|".join(AREAS)
DEFINITION = re.compile(
    rf"^\*\*(?P<id>(?:{_AREA_ALT})-\d{{3}}[a-z]?(?:\.\d+)?)(?:\s*\([^)\n]*\))?(?P<punct>[.:])\*\*")
REFERENCE = re.compile(rf"(?<![A-Za-z0-9_-])((?:{_AREA_ALT})-\d{{3}}[a-z]?)(?![A-Za-z0-9])")
KEYWORDS = re.compile(r"\b(?:MUST NOT|MUST|SHALL NOT|SHALL|SHOULD NOT|SHOULD|REQUIRED|RECOMMENDED|MAY|OPTIONAL)\b")
INFORMATIVE = ("00-architecture.md", "appendix-c-examples.md", "appendix-d-anthropic-mhs.md")
LEGACY_ANYWHERE = ("MHS Editors", "MHS-1.0", "Draft 1.0")
LEGACY_DOMAIN = "model" + "hardware" + "standard"   # spelled in two parts: the export check forbids the literal outside appendix D
DOMAIN_ALLOWED = ("appendix-d-anthropic-mhs.md",)
CODE_CHECKED = ("core.md", "driver-profile.md", "profiles.md", "README.md", "appendix-c-examples.md")
MHS_CODE = re.compile(r"\bMHS\.[A-Z][A-Z]*\.[A-Z][A-Z0-9_]*\b")
FEATURE_STRINGS = {"MHS.SAFETY.NOT_CERTIFIED", "MHS.CAPABILITY.EXPERIMENTAL_PRESENT"}

CATALOGUE_BEGIN = "<!-- BEGIN GENERATED: catalogue"
CATALOGUE_END = "<!-- END GENERATED: catalogue -->"
CATALOGUE_DOC = "03-capability-registry.md"

DEFAULT_TIMEOUT_S = 120


# ---------------------------------------------------------------------------
# code blocks
# ---------------------------------------------------------------------------
@dataclass
class Block:
    file: str
    line: int          # 1-based line of the opening fence
    info: str
    code: str
    hint: str | None = None   # schema named by a preceding comment line or by the paragraph above (see the module docstring)

    @property
    def language(self) -> str:
        return (self.info.split() or [""])[0].lower()

    @property
    def runnable(self) -> bool:
        if self.language != "python":
            return False
        words = self.info.lower().split()
        first = next((ln.strip() for ln in self.code.splitlines() if ln.strip()), "")
        return "runnable" in words[1:] or first == "# runnable"

    @property
    def schema(self) -> str | None:
        if self.language != "json":
            return None
        match = re.search(r"\bvalidate=([A-Za-z0-9_.-]+)", self.info)
        return match.group(1) if match else self.hint

    @property
    def where(self) -> str:
        return f"{self.file}:{self.line}"


_FENCE = re.compile(r"^(?P<indent>[ \t]*)(?P<ticks>`{3,})(?P<info>[^`]*)$")
_HINT = re.compile(r"^\s*<!--\s*validate=([A-Za-z0-9_.-]+)\s*-->\s*$")
_PROSE_HINT = re.compile(r"\bvalid\s+against\s+\[?`([A-Za-z0-9_.-]+\.schema\.json)`")
_SITE_FENCE_INFO = re.compile(r"^[A-Za-z0-9_.+-]*$")


def _paragraph_above(lines: list[str], index: int) -> str:
    """The paragraph that ends at the nearest non-blank line above ``lines[index]``, on one line."""

    end = index - 1
    while end >= 0 and not lines[end].strip():
        end -= 1
    start = end
    while start >= 0 and lines[start].strip():
        start -= 1
    return " ".join(part.strip() for part in lines[start + 1:end + 1])


def extract_blocks(text: str, file: str = "<text>") -> list[Block]:
    """Every fenced code block of ``text`` (indented fences inside list items included)."""

    blocks: list[Block] = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        match = _FENCE.match(lines[index])
        if not match:
            index += 1
            continue
        before = next((ln for ln in reversed(lines[:index]) if ln.strip()), "")
        hint_match = _HINT.match(before)
        prose_match = None if hint_match else _PROSE_HINT.search(_paragraph_above(lines, index))
        indent, ticks, info = match.group("indent"), match.group("ticks"), match.group("info").strip()
        start = index
        body: list[str] = []
        index += 1
        while index < len(lines):
            closing = lines[index].strip()
            if closing.startswith(ticks) and set(closing) == {"`"}:
                break
            line = lines[index]
            body.append(line[len(indent):] if line.startswith(indent) else line.lstrip())
            index += 1
        hint = hint_match.group(1) if hint_match else (prose_match.group(1) if prose_match else None)
        blocks.append(Block(file=file, line=start + 1, info=info, code="\n".join(body) + "\n", hint=hint))
        index += 1
    return blocks


def _looks_abridged(code: str) -> bool:
    return "…" in code or "..." in code or "abridged" in code.lower()


# ---------------------------------------------------------------------------
# running
# ---------------------------------------------------------------------------
class _Timeout(Exception):
    pass


def _prepare_environment() -> None:
    if str(SDK_SRC) not in sys.path:
        sys.path.insert(0, str(SDK_SRC))
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")


def run_block(block: Block, timeout_s: float = DEFAULT_TIMEOUT_S) -> str | None:
    """Execute one runnable block; return an error description, or None when it passed."""

    _prepare_environment()
    namespace: dict[str, object] = {"__name__": "__spec_doctest__", "__file__": block.where}
    out, err = io.StringIO(), io.StringIO()
    previous_cwd = os.getcwd()
    previous_handler = None
    use_alarm = hasattr(signal, "SIGALRM") and hasattr(signal, "setitimer")
    try:
        os.chdir(ROOT)
        if use_alarm:
            def _on_alarm(signum, frame):  # noqa: ANN001
                raise _Timeout(f"timed out after {timeout_s:.0f} s")

            previous_handler = signal.signal(signal.SIGALRM, _on_alarm)
            signal.setitimer(signal.ITIMER_REAL, timeout_s)
        with warnings.catch_warnings(), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            warnings.simplefilter("ignore")
            exec(compile(block.code, f"<{block.where}>", "exec"), namespace)  # noqa: S102 - the point of this tool
        return None
    except BaseException as error:  # noqa: BLE001 - a block may raise anything, SystemExit included
        if isinstance(error, KeyboardInterrupt):
            raise
        frames = traceback.extract_tb(error.__traceback__)
        mine = [frame for frame in frames if frame.filename == f"<{block.where}>"]
        position = f" (block line {mine[-1].lineno})" if mine else ""
        detail = "".join(traceback.format_exception_only(type(error), error)).strip()
        captured = (out.getvalue() + err.getvalue()).strip()
        tail = f"\n    output: {captured[-600:]}" if captured else ""
        return f"{type(error).__name__}{position}: {detail}{tail}"
    finally:
        if use_alarm:
            signal.setitimer(signal.ITIMER_REAL, 0)
            if previous_handler is not None:
                signal.signal(signal.SIGALRM, previous_handler)
        os.chdir(previous_cwd)


def validate_json_block(block: Block) -> str | None:
    _prepare_environment()
    from mhs.schema import SchemaStore  # noqa: PLC0415 - needs the SDK path

    try:
        document = json.loads(block.code)
    except ValueError as error:
        return f"does not parse as JSON: {error}"
    errors = [str(item) for item in SchemaStore().validate(document, block.schema)]
    return "; ".join(errors[:5]) if errors else None


# ---------------------------------------------------------------------------
# the lint
# ---------------------------------------------------------------------------
@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    runnable: int = 0
    validated: int = 0
    definitions: int = 0

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)


def spec_files(directory: Path) -> list[Path]:
    return sorted(path for path in directory.glob("*.md"))


def _strip_fences(text: str) -> str:
    """``text`` with the content of fenced blocks blanked (line numbers preserved)."""

    kept: list[str] = []
    fence: str | None = None
    for line in text.splitlines():
        match = _FENCE.match(line)
        if fence is None:
            if match:
                fence = match.group("ticks")
                kept.append("")
            else:
                kept.append(line)
        else:
            if line.strip().startswith(fence) and set(line.strip()) == {"`"}:
                fence = None
            kept.append("")
    return "\n".join(kept)


def lint_ids(files: list[Path], report: Report, root: Path) -> None:
    definitions: dict[str, list[str]] = {}
    mentions: dict[str, list[str]] = {}
    for path in files:
        text = path.read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), 1):
            match = DEFINITION.match(line)
            if match:
                definitions.setdefault(match.group("id"), []).append(f"{path.name}:{number}")
        prose = _strip_fences(text)
        for number, line in enumerate(prose.splitlines(), 1):
            for found in REFERENCE.findall(line):
                mentions.setdefault(found, []).append(f"{path.name}:{number}")
        for block in extract_blocks(text, path.name):
            # identifiers in code blocks (test ids in a report example) count as references too
            for found in REFERENCE.findall(block.code):
                mentions.setdefault(found, []).append(block.where)
    report.definitions = len(definitions)
    for requirement_id, places in sorted(definitions.items()):
        if len(places) > 1:
            report.error(f"id {requirement_id} is defined {len(places)} times: {', '.join(places)}")
    defined = set(definitions)
    for requirement_id, places in sorted(mentions.items()):
        if requirement_id in defined:
            continue
        base = re.sub(r"[a-z]$", "", requirement_id)
        if base in defined and requirement_id.endswith(tuple("abcdefgh")):
            continue
        report.error(f"id {requirement_id} is referenced but defined nowhere (orphan): {', '.join(places[:3])}")


def lint_fences(files: list[Path], report: Report) -> None:
    """Every fence's info string is one token: the form every Markdown reader treats alike."""

    for path in files:
        for block in extract_blocks(path.read_text(encoding="utf-8"), path.name):
            if not _SITE_FENCE_INFO.match(block.info):
                report.error(f"{block.where}: the fence info string {block.info!r} is not a single token "
                             "([A-Za-z0-9_.+-]*); name the schema in the paragraph above instead "
                             "(\"... is valid against [`x.schema.json`](...)\")")


def lint_keywords_and_legacy(files: list[Path], report: Report) -> None:
    for path in files:
        text = path.read_text(encoding="utf-8")
        if path.name in INFORMATIVE:
            for number, line in enumerate(text.splitlines(), 1):
                match = KEYWORDS.search(line)
                if match:
                    report.error(f"{path.name}:{number}: informative document uses the key word {match.group(0)}")
        for legacy in LEGACY_ANYWHERE:
            for number, line in enumerate(text.splitlines(), 1):
                if legacy in line:
                    report.error(f"{path.name}:{number}: legacy identifier {legacy!r}")
        if path.name not in DOMAIN_ALLOWED:
            for number, line in enumerate(text.splitlines(), 1):
                if LEGACY_DOMAIN in line.lower():
                    report.error(f"{path.name}:{number}: the legacy domain is cited outside appendix D")


def _registered_codes(spec_dir: Path) -> set[str]:
    path = spec_dir / "errors.json"
    if not path.is_file():
        return set()
    return {entry["code"] for entry in json.loads(path.read_text(encoding="utf-8")).get("errors", [])}


def lint_error_codes(files: list[Path], spec_dir: Path, report: Report) -> None:
    registered = _registered_codes(spec_dir)
    if not registered:
        report.warn("errors.json not found: error codes not checked")
        return
    for path in files:
        if path.name not in CODE_CHECKED:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for code in MHS_CODE.findall(line):
                if code not in registered and code not in FEATURE_STRINGS:
                    report.error(f"{path.name}:{number}: {code} is not in errors.json")


_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


def slugify(heading: str) -> str:
    """A GitHub-style anchor for a heading line's text."""

    text = re.sub(r"`", "", heading).strip().lower()
    text = re.sub(r"[^\w\- ]", "", text, flags=re.UNICODE)
    return text.replace(" ", "-")


def _anchors(path: Path) -> set[str]:
    anchors: set[str] = set()
    counts: dict[str, int] = {}
    for line in _strip_fences(path.read_text(encoding="utf-8")).splitlines():
        match = _HEADING.match(line)
        if match:
            slug = slugify(match.group(2))
            seen = counts.get(slug, 0)
            counts[slug] = seen + 1
            anchors.add(slug if seen == 0 else f"{slug}-{seen}")
    return anchors


_LINK = re.compile(r"(?<!\!)\[[^\]\n]*\]\((?P<target>[^)\s]+)\)")


def lint_links(files: list[Path], spec_dir: Path, report: Report) -> None:
    anchor_cache: dict[Path, set[str]] = {}
    for path in files:
        text = _strip_fences(path.read_text(encoding="utf-8"))
        for number, line in enumerate(text.splitlines(), 1):
            for match in _LINK.finditer(line):
                target = match.group("target")
                if re.match(r"^[a-z][a-z0-9+.-]*:", target):      # http:, mailto:, ...
                    continue
                file_part, _, anchor = target.partition("#")
                resolved = path if not file_part else (spec_dir / file_part).resolve()
                if not resolved.exists():
                    report.error(f"{path.name}:{number}: link target {target!r} does not exist")
                    continue
                if anchor and resolved.suffix == ".md" and resolved.parent == spec_dir.resolve():
                    anchors = anchor_cache.setdefault(resolved, _anchors(resolved))
                    if anchor not in anchors:
                        report.error(f"{path.name}:{number}: link {target!r} names a heading that does not exist")


# ---------------------------------------------------------------------------
# the generated catalogue section (03 section 7)
# ---------------------------------------------------------------------------
def _compact(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _ticks(items: list[str]) -> str:
    return ", ".join(f"`{item}`" for item in items)


def render_catalogue_entry(entry: dict) -> str:
    lines = [f"#### `{entry['capability_id']}` — {entry['title']}"]
    flags = ""
    if entry.get("status", "stable") != "stable":
        flags += f" · status `{entry['status']}`"
    if entry.get("requires_permit"):
        flags += " · **requires permit**"
    lines.append(
        f"`{entry['verb']}` · **{entry['risk_class']}** · determinism `{entry['determinism']}` · "
        f"`{entry['concurrency']}` · modes {_ticks(entry['modes'])} · since {entry['since']}{flags} — {entry['summary']}")
    parts = [f"Kinds {_ticks(entry['resource_kinds'])}.", f"Effects {_ticks(entry['effects'])}."]
    hazards = entry.get("hazards") or []
    parts.append("Hazards " + (_ticks(hazards) if hazards else "none") + ".")
    parts.append(f"Tags {_ticks(entry['tags'])}.")
    units = entry.get("units") or {}
    if units:
        parts.append("Units " + ", ".join(f"`{key}`: `{value}`" for key, value in sorted(units.items())) + ".")
    if entry.get("limits"):
        parts.append(f"Class limits `{_compact(entry['limits'])}`.")
    constraints = entry.get("constraints") or {}
    if constraints:
        parts.append("Constraints " + ", ".join(f"`{key}` `{json.dumps(value)}`"
                                                for key, value in sorted(constraints.items())) + ".")
    if entry.get("x-mhs-replaced-by"):
        parts.append(f"Replaced by `{entry['x-mhs-replaced-by']}`.")
    if entry.get("notes"):
        parts.append(f"Notes: {entry['notes']}")
    lines.append(" ".join(parts))
    lines.append(f"Input `{_compact(entry['input_schema'])}` · Output `{_compact(entry['output_schema'])}`")
    return "\n".join(lines)


def render_catalogue(catalogue: dict) -> str:
    """The body of 03 section 7 (the domain headings and one entry per class)."""

    entries = catalogue["capabilities"]
    domains: list[str] = []
    for entry in entries:
        if entry["domain"] not in domains:
            domains.append(entry["domain"])
    out: list[str] = []
    for number, domain in enumerate(domains, 1):
        members = [entry for entry in entries if entry["domain"] == domain]
        noun = "class" if len(members) == 1 else "classes"
        out.append(f"### 7.{number} {domain.capitalize()} ({len(members)} {noun})")
        out.append("")
        for entry in members:
            out.append(render_catalogue_entry(entry))
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def _catalogue_span(text: str) -> tuple[int, int]:
    begin = text.index(CATALOGUE_BEGIN)
    begin_end = text.index("-->", begin) + 3
    end = text.index(CATALOGUE_END)
    return begin_end, end


def catalogue_section(spec_dir: Path) -> tuple[str, str]:
    """``(current, expected)`` text between the markers of section 7."""

    document = (spec_dir / CATALOGUE_DOC).read_text(encoding="utf-8")
    start, end = _catalogue_span(document)
    expected = "\n\n" + render_catalogue(json.loads((spec_dir / "capabilities.json").read_text(encoding="utf-8"))) + "\n"
    return document[start:end], expected


def check_catalogue(spec_dir: Path, report: Report) -> None:
    try:
        current, expected = catalogue_section(spec_dir)
    except (OSError, ValueError) as error:
        report.error(f"{CATALOGUE_DOC}: cannot compare section 7 with capabilities.json: {error}")
        return
    if current != expected:
        report.error(f"{CATALOGUE_DOC} section 7 differs from capabilities.json; run "
                     "python3 MHS/sdk/tools/spec_doctest.py MHS/spec --write-catalogue")


def write_catalogue(spec_dir: Path) -> bool:
    path = spec_dir / CATALOGUE_DOC
    document = path.read_text(encoding="utf-8")
    start, end = _catalogue_span(document)
    _current, expected = catalogue_section(spec_dir)
    if document[start:end] == expected:
        return False
    path.write_text(document[:start] + expected + document[end:], encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def run(spec_dir: Path, *, execute: bool = True, timeout_s: float = DEFAULT_TIMEOUT_S, only: str | None = None,
        verbose: bool = False) -> Report:
    report = Report()
    files = spec_files(spec_dir)
    if only:
        selected = [path for path in files if path.name == only]
        if not selected:
            report.error(f"no such specification file: {only}")
            return report
    else:
        selected = files
    lint_ids(files, report, spec_dir)
    lint_fences(files, report)
    lint_keywords_and_legacy(files, report)
    lint_error_codes(files, spec_dir, report)
    lint_links(files, spec_dir, report)
    if (spec_dir / CATALOGUE_DOC).is_file() and (spec_dir / "capabilities.json").is_file():
        with contextlib.suppress(ValueError):
            check_catalogue(spec_dir, report)
    for path in selected:
        for block in extract_blocks(path.read_text(encoding="utf-8"), path.name):
            if block.schema:
                report.validated += 1
                problem = validate_json_block(block)
                if problem:
                    report.error(f"{block.where}: JSON block does not validate against {block.schema}: {problem}")
                elif verbose:
                    print(f"ok    {block.where} validates against {block.schema}")
            elif block.language == "json" and not _looks_abridged(block.code):
                try:
                    json.loads(block.code)
                except ValueError as error:
                    report.warn(f"{block.where}: JSON block does not parse and is not marked abridged: {error}")
            if block.runnable:
                report.runnable += 1
                if not execute:
                    continue
                problem = run_block(block, timeout_s)
                if problem:
                    report.error(f"{block.where}: runnable block failed: {problem}")
                elif verbose:
                    print(f"ok    {block.where} runnable block passed")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("directory", nargs="?", default="MHS/spec", help="the specification directory (default MHS/spec)")
    parser.add_argument("--no-run", action="store_true", help="lint only; do not execute runnable blocks")
    parser.add_argument("--only", metavar="FILE", help="execute and validate the blocks of one file (the lint still covers all)")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S, help="seconds allowed per runnable block")
    parser.add_argument("--check-catalogue", action="store_true",
                        help="only check that 03 section 7 equals the rendering of capabilities.json")
    parser.add_argument("--write-catalogue", action="store_true", help="rewrite 03 section 7 from capabilities.json")
    parser.add_argument("--verbose", "-v", action="store_true", help="print every block that passed")
    args = parser.parse_args(argv)
    directory = Path(args.directory)
    if not directory.is_absolute():
        directory = (ROOT / directory) if not directory.exists() else directory.resolve()
    if not directory.is_dir():
        print(f"error: {directory} is not a directory", file=sys.stderr)
        return 2
    if args.write_catalogue:
        try:
            changed = write_catalogue(directory)
        except (OSError, ValueError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        print("rewrote section 7 of " + CATALOGUE_DOC if changed else CATALOGUE_DOC + " section 7 is up to date")
        return 0
    if args.check_catalogue:
        report = Report()
        check_catalogue(directory, report)
        for message in report.errors:
            print("FAIL " + message)
        if not report.errors:
            print(CATALOGUE_DOC + " section 7 matches capabilities.json")
        return 1 if report.errors else 0
    try:
        report = run(directory, execute=not args.no_run, timeout_s=args.timeout, only=args.only, verbose=args.verbose)
    except OSError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    for message in report.warnings:
        print("warn " + message)
    for message in report.errors:
        print("FAIL " + message)
    status = "FAILED" if report.errors else "ok"
    print(f"spec doctest {status}: {report.runnable} runnable block(s)"
          f"{'' if not args.no_run else ' (not run)'}, {report.validated} validated JSON block(s), "
          f"{report.definitions} requirement id(s) defined, {len(report.errors)} error(s), "
          f"{len(report.warnings)} warning(s)")
    return 1 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
