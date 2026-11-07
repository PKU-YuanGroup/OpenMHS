#!/usr/bin/env python3
"""Static site generator for the OpenMHS documentation site.

OpenMHS is an independent open-source project, not affiliated with or
endorsed by Anthropic, and not a reimplementation or compatible dialect of
Anthropic's MHS research preview.  Every generated page says so.

Deterministic, idempotent, standard-library only.  Reads the specification,
schemas, capability catalogue, registry and SDK documentation from the parent
workspace and emits a fully self-contained site.

    python3 MHS/site/build.py                       # build into MHS/site/_site/
    python3 MHS/site/build.py --out DIR             # build into DIR
    python3 MHS/site/build.py --site-url URL        # emit canonical links and a sitemap
    python3 MHS/site/build.py --release             # refuse the synthetic registry fallback
    python3 MHS/site/build.py --quiet               # build without per-section log

The public URL is a build parameter (``--site-url`` or ``$OPENMHS_SITE_URL``);
there is no default host.  Without it the site has no canonical links and no
sitemap, and it still works from ``file://`` or any static host.  Project
identifiers (name, versions, the non-affiliation sentence) come from
``MHS/sdk/src/mhs/_ids.py``.

No network access, no third-party packages, no wall-clock values in output.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import importlib.util
import io
import json
import os
import posixpath
import re
import shutil
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit, unquote

# ---------------------------------------------------------------------------
# Paths and constants
# ---------------------------------------------------------------------------

HERE = Path(__file__).resolve().parent
MHS = HERE.parent
WORKSPACE = MHS.parent
SRC = HERE
ASSETS = SRC / "assets"
DEPLOY = SRC / "deploy"
DEFAULT_OUT = SRC / "_site"
OUT = DEFAULT_OUT
OUT_MARKER = ".openmhs-site"
IDS_FILE = MHS / "sdk" / "src" / "mhs" / "_ids.py"


def _load_ids():
    """Load ``mhs/_ids.py`` by path, without importing the ``mhs`` package."""
    spec = importlib.util.spec_from_file_location("_openmhs_ids", IDS_FILE)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load project identifiers from {IDS_FILE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


IDS = _load_ids()

# The public URL is a build parameter; empty means "no canonical host".
SITE_URL = ""
RELEASE = False
SITE_NAME = IDS.PROJECT_NAME
SITE_SHORT = IDS.PROJECT_NAME
COPYRIGHT_HOLDER = "PKU-YUAN-Lab"
NON_AFFILIATION = IDS.NON_AFFILIATION
ANTHROPIC_PAGE_LABEL = "Relation to Anthropic's MHS preview"
BUILD_DATE = "2026-10-20"
SPEC_VERSION = IDS.SPEC_VERSION
# The wire revision shown as "protocol"; "1.0" means wire revision 1.
MHS_VERSION = IDS.WIRE_VERSION
DRAFT_LABEL = f"Development draft {SPEC_VERSION}"
BUNDLE_PREFIX = f"{IDS.DIST_NAME}-{SPEC_VERSION}"

DEFINITION = (
    "OpenMHS is an independent, open draft contract between AI agents and "
    "physical equipment — discovery, typed capabilities, an endpoint-enforced "
    "safety envelope and an evidence trail for instruments, robots, and the "
    "simulations that stand in for them."
)

# Document map.  Titles/summaries are used for the spec index and for clearly
# labelled in-preparation pages when a document has not yet landed.
DOC_ORDER = [
    ("core.md", "MHS-CORE", "OpenMHS Core",
     "The short normative core: the object model, the read, write and action primitives, limits and their evaluation order, e-stop and reset, receipts, modes, the control surfaces, strict mode and persistence."),
    ("driver-profile.md", "MHS-DRV", "Driver Profile",
     "The per-repository driver package: layout, the Driver API, the acceptance gate G1 to G9, provenance and review, fakes and the sandbox."),
    ("profiles.md", "MHS-PROF", "Optional profiles",
     "Which chapters belong to the core and which to an optional profile: sessions and permits, evidence, simulation, events, host, registry and governance."),
    ("00-architecture.md", "MHS-000", "Architecture overview",
     "Informative: the design, the reasons for it and the adoption path for the 2,967-repository corpus. It wins no conflict."),
    ("01-conformance.md", "MHS-001", "Conformance",
     "Levels CL0–CL5, five profiles, the executable suite, test identifiers and the report that backs a claim."),
    ("02-wire-protocol.md", "MHS-002", "Wire protocol",
     "JSON-RPC framing, the method table, receipts, operations, subscriptions, deadlines and the stable error vocabulary."),
    ("03-capability-registry.md", "MHS-003", "Capability registry",
     "Class identity and versioning, unit rules, and the catalogue of core capability classes."),
    ("04-safety.md", "MHS-004", "Safety and audit",
     "Risk classes, the endpoint-evaluated envelope, interlocks, permits, e-stop semantics, sessions and the evidence chain."),
    ("05-fidelity.md", "MHS-005", "Modes and fidelity",
     "The dual-world rule, fidelity contract F0–F3, determinism, replay, hybrid authority and gap disclosure."),
    ("06-adapters.md", "MHS-006", "Adapters and bridges",
     "Declarative adapter manifests, generic bridge runtimes, the mapping rules, integration tiers and recipes."),
    ("07-registry.md", "MHS-007", "Registry",
     "Package, device, adapter and conformance records; federation, trust levels, signing and search."),
    ("08-transports.md", "MHS-008", "Transports",
     "Transport bindings T1–T6: stdio, HTTP/SSE, WebSocket, the MCP projection, CLI and code API."),
    ("09-host-profile.md", "MHS-009", "Host profile",
     "What an agent harness must do to claim MHS-Host, and the normative OpenAI4S mapping."),
    ("10-governance.md", "MHS-010", "Governance",
     "The RFC process, versioning and deprecation, and the licensing of specification, code and registry data."),
    ("appendix-a-capabilities.md", "MHS-A", "Capability catalogue",
     "The generated, tabular presentation of every core capability class."),
    ("appendix-b-errors.md", "MHS-B", "Error registry",
     "The stable MHS.* code vocabulary, grouped by area, with retry and remediation semantics."),
    ("appendix-c-examples.md", "MHS-C", "End-to-end examples",
     "Informative transcripts for a lab instrument, a robot, a simulator and a hybrid workcell."),
    ("appendix-d-anthropic-mhs.md", "MHS-D", "Anthropic research preview",
     "What the Anthropic MHS research preview publishes, what it describes, and what this specification adopts, defines and refuses to claim."),
]
DOC_META = {rel: (doc_id, title, summary) for rel, doc_id, title, summary in DOC_ORDER}

FAMILY_META = {
    "gymnasium": ("Gymnasium environments", "Vectorised RL environments exposed as worlds through the gymnasium bridge: reset, step, observe, seed."),
    "mujoco": ("MuJoCo", "Rigid-body simulators and MJCF models. A strong fit for F1 dynamics and deterministic replay."),
    "pybullet": ("PyBullet", "Physics simulation with a mature Python API; typically F1 with contact and actuator gaps declared."),
    "isaac-sim": ("Isaac Sim", "NVIDIA's GPU simulation platform. Heavy setup, high scene fidelity, and explicit GPU requirements."),
    "isaac-lab": ("Isaac Lab", "Gym-style robot-learning environments built on Isaac Sim; large scene and asset surface."),
    "isaac-gym": ("Isaac Gym", "GPU RL environments with a proprietary runtime; adapter licensing must be checked before redistribution."),
    "gazebo": ("Gazebo", "ROS-adjacent robot simulation via gz-transport; usually paired with a ROS bridge and URDF/SDF assets."),
    "ros1": ("ROS 1", "Legacy ROS graphs. Exposed through rosbridge or a thin shim; lifecycle and message types need mapping."),
    "ros2": ("ROS 2", "rclpy or rosbridge endpoints. Services and actions map to OpenMHS commands; topics map to subscriptions."),
    "airsim": ("AirSim", "Drone and car simulation built on Unreal. Usually F1/F2 with rendering and sensor noise gaps."),
    "webots": ("Webots", "Robot simulation with controller processes; typically wrapped as a Python-object or HTTP bridge."),
    "unity": ("Unity", "Game-engine simulation and digital twins; ML-Agents or a custom socket bridge supplies the contract plane."),
    "drake": ("Drake", "Model-based robotics toolkit; analytic and contact-rich models, often F1 with strong determinism claims."),
    "sapien": ("SAPIEN", "Articulated-object simulation for manipulation; MuJoCo/PhysX backends and asset-heavy scenes."),
    "habitat": ("Habitat", "Embodied-AI simulation for navigation and manipulation; sensor fidelity and episode semantics are explicit gaps."),
    "brax-mjx": ("Brax / MJX", "JAX-based differentiable physics. Fast, deterministic, and typically exercised as a Gymnasium-style world."),
    "dm-env": ("dm_env", "DeepMind's environment interface; a small bridge maps step/reset/observation to world capabilities."),
    "python-object": ("Python objects", "Any importable class or function with a stable entry point; the lowest-ceremony bridge, and the most common."),
    "http-api": ("HTTP APIs", "REST or RPC services wrapped as devices; map routes and errors, never guess units."),
    "mcp-proxy": ("MCP servers", "Existing MCP tools re-exposed with device semantics. MCP supplies the tool seam; OpenMHS supplies contract, safety and evidence."),
    "cli-process": ("CLI processes", "Bounded command-line tools. R1+ by default, with deadlines and captured output; never unbounded shells."),
    "docker": ("Containers", "Packaged services and simulators with a defined lifecycle and readiness probe."),
    "serial": ("Serial devices", "Byte-level instruments and microcontrollers. The bridge must bound reads and writes and never block forever."),
    "scpi-visa": ("SCPI / VISA", "Test-and-measurement instruments over VISA. Preserve native status codes and timeouts alongside OpenMHS errors."),
    "sila2": ("SiLA 2", "Lab-automation gRPC standard. Observable commands and defined execution errors map well; units still need authoring."),
    "opentrons": ("Opentrons", "Liquid handlers and protocol runners. Deck, labware, tip and volume semantics are the hard part, not the transport."),
    "pylabrobot": ("PyLabRobot", "Lab automation framework with deck and resource models; needs a backend shim for hardware and simulation."),
    "micromanager": ("Micro-Manager", "Microscopy device runtime. Runtime property introspection supplies capability churn; imaging returns artifacts."),
    "bluesky-ophyd": ("Bluesky / Ophyd", "Beamline experiment orchestration. Ophyd's read/describe split is a direct model for observations and units."),
    "qcodes": ("QCoDeS", "Instrument drivers with first-class units and parameter validators; a natural source for typed read/write capabilities."),
    "madsci": ("MADSci", "Laboratory orchestration. Node actions, async status and resource/location records need to be projected onto commands and worlds."),
    "flowchem": ("Flow chemistry", "Device-and-component HTTP APIs with pint units; a simulated server can replace hardware without changing the contract."),
    "replay": ("Replay", "Recorded evidence served read-only. Replay endpoints expose the same contract and refuse mutation."),
    "lerobot-real": ("LeRobot hardware", "Real robot arms and teleoperation datasets; calibration and safety authority need to be declared."),
    "other": ("Other / unclassified", "Packages whose entry point, ecosystem or role does not yet map cleanly to a bridge family."),
}

FAMILY_ORDER = list(FAMILY_META.keys())

# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------


def esc(value) -> str:
    return html.escape(str(value), quote=False)


def attr(value) -> str:
    return html.escape(str(value), quote=True)


def fmt_int(n) -> str:
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return "0"


def fmt_bytes(n) -> str:
    n = float(n)
    if n < 1024:
        return f"{int(n)} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.2f} MB"


def sha256_hex(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()


def slugify(text: str) -> str:
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[*_~]", "", text)
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s-]+", "-", text).strip("-")
    return text or "section"


def strip_tags(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9_]+", text))


def human_date(iso: str) -> str:
    return (iso or BUILD_DATE)[:10]


def rel_root(path: str) -> str:
    """Relative prefix from an output file to the site root, with trailing slash."""
    parent = posixpath.dirname(path)
    if not parent:
        return ""
    return "../" * len(parent.split("/"))


def url_for(path: str, prefix: str | None = None, fragment: str = "", query: str = "") -> str:
    """Link to an output file; directories use an explicit index.html for file://."""
    if path == "index.html":
        target = "index.html"
    elif path.endswith("/index.html"):
        target = path
    elif path.endswith(".html"):
        target = path
    else:
        target = path
    if prefix is None:
        prefix = rel_root(target)
    href = prefix + target
    if query:
        href += "?" + query.lstrip("?")
    if fragment:
        href += "#" + fragment.lstrip("#")
    return href


def canonical_url(path: str) -> str:
    """Absolute URL of an output file, or "" when no site URL is configured."""
    if not SITE_URL:
        return ""
    if path == "index.html":
        return SITE_URL + "/"
    if path.endswith("/index.html"):
        return SITE_URL + "/" + path[: -len("index.html")]
    return SITE_URL + "/" + path


def normalize_site_url(value: str) -> str:
    """Validate ``--site-url`` and return it without a trailing slash."""
    value = (value or "").strip()
    if not value:
        return ""
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise SystemExit(f"--site-url must be an absolute http(s) URL, got {value!r}")
    host = parts.hostname or ""
    host_ok = bool(re.fullmatch(r"[A-Za-z0-9.\-]+", host) or (":" in host and re.fullmatch(r"[0-9A-Fa-f:.]+", host)))
    if re.search(r"\s", value) or not host_ok:
        raise SystemExit(f"--site-url has no valid host name (whitespace or illegal characters): {value!r}")
    if parts.username or parts.password:
        raise SystemExit(f"--site-url must not carry credentials: {value!r}")
    if parts.query or parts.fragment:
        raise SystemExit(f"--site-url must not carry a query or fragment: {value!r}")
    return value.rstrip("/")


def load_json(path: Path, default=None):
    if not path.is_file():
        return default
    try:
        return json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON in {path}: {exc}") from exc


BLOCK_TAGS = (
    "header|footer|main|section|article|aside|nav|div|p|h[1-6]|ul|ol|li|"
    "table|thead|tbody|tr|td|th|figure|details|summary|form|fieldset|"
    "dl|dt|dd|blockquote|pre"
)


def compact_html(text: str) -> str:
    """Conservative compaction: remove indentation/newlines before block tags.

    Inline whitespace, <pre> content and <textarea> values are left untouched.
    """
    text = re.sub(r"\n[ \t]*(?=<(?:/?(?:" + BLOCK_TAGS + r")\b))", "", text)
    return text


def write_text(rel: str, text: str) -> int:
    path = OUT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if rel.endswith(".html"):
        text = compact_html(text)
    data = text.encode("utf-8")
    path.write_bytes(data)
    return len(data)


def write_bytes(rel: str, data: bytes) -> int:
    path = OUT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return len(data)


# ---------------------------------------------------------------------------
# Markdown subset renderer
# ---------------------------------------------------------------------------

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
# An opening fence is a language word and, optionally, attributes such as "json validate=adapter.schema.json" (the specification
# marks the examples that the doctest tool runs this way); a closing fence has no info string.
FENCE_RE = re.compile(r"^(\s*)(`{3,}|~{3,})\s*([\w.+-]*)(?:\s+[^`]*)?$")
FENCE_CLOSE_RE = re.compile(r"^(\s*)(`{3,}|~{3,})\s*$")
ITEM_RE = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")
HR_RE = re.compile(r"^\s{0,3}([-*_])(?:\s*\1){2,}\s*$")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)(?:\s+\"([^\"]*)\")?\)")
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
AUTOLINK_RE = re.compile(r"<((?:https?://|mailto:)[^ >]+)>")


class MarkdownRenderer:
    """A deliberately small, deterministic CommonMark subset.

    Supports headings, pipe tables, fenced code, nested lists, block quotes,
    rules, paragraphs, inline code/bold/italic/strikethrough/links, automatic
    heading anchors and a table of contents.  Raw HTML is escaped.
    """

    def __init__(self, known_files: set[str], source_rel: str, output_rel: str):
        self.known = known_files
        self.source_rel = source_rel
        self.output_rel = output_rel
        self.toc: list[dict] = []
        self.slugs: dict[str, int] = {}
        self.pending: list[str] = []
        self.heading_ids: dict[str, str] = {}

    # -- links -------------------------------------------------------------
    def _map_source(self, source_path: str) -> str | None:
        norm = posixpath.normpath(source_path)
        if norm == "MHS/spec/README.md":
            return "spec/index.html"
        if norm == "MHS/spec/capabilities.json":
            return "spec/capabilities.json"
        if norm == "MHS/sdk/INTERFACE.md":
            return "sdk/index.html"
        if norm == "MHS/README.md":
            return "index.html"
        if norm.startswith("MHS/spec/") and norm.endswith(".md"):
            stem = posixpath.basename(norm)[:-3]
            return f"spec/{stem}.html"
        if norm.startswith("MHS/schema/"):
            return "schema/" + norm[len("MHS/schema/"):]
        if norm.startswith("MHS/registry/families/") and norm.endswith(".md"):
            stem = posixpath.basename(norm)[:-3]
            return f"families/{stem}.html"
        if norm.startswith("MHS/") and norm.endswith(".md"):
            stem = posixpath.basename(norm)[:-3]
            return f"{stem}.html"
        if norm.startswith("MHS/"):
            return norm[len("MHS/"):]
        return norm

    def resolve_href(self, href: str) -> tuple[str, bool] | None:
        href = href.strip()
        if not href:
            return None
        low = href.lower()
        if low.startswith("http://"):
            host = urlsplit(href).hostname or ""
            if host not in ("localhost", "127.0.0.1", "::1"):
                href = "https://" + href[len("http://"):]
        if low.startswith(("http://", "https://")):
            return href, True
        if low.startswith(("mailto:", "tel:")):
            return href, True
        if low.startswith(("javascript:", "data:", "vbscript:")):
            return None
        if href.startswith("#"):
            return href, False

        parts = urlsplit(href)
        raw_path = unquote(parts.path)
        query = parts.query
        fragment = parts.fragment
        if not raw_path:
            return href, False
        if raw_path.startswith("/"):
            # Root-absolute paths are wrong for a file:// mirror.  Treat them
            # as site-root relative and make them relative to this page.
            target_out = raw_path.lstrip("/")
        else:
            source_target = posixpath.normpath(
                posixpath.join(posixpath.dirname(self.source_rel), raw_path)
            )
            target_out = self._map_source(source_target)
        if not target_out:
            return None
        target_out = posixpath.normpath(target_out)
        if target_out.startswith("../") or target_out == "..":
            return None
        if target_out.endswith("/"):
            target_out += "index.html"
        if target_out not in self.known:
            # Tolerate links to a directory index written without the file.
            if target_out + "/index.html" in self.known:
                target_out += "/index.html"
            else:
                self.pending.append(href)
                return None
        here = posixpath.dirname(self.output_rel) or "."
        rel = posixpath.relpath(target_out, here)
        if query:
            rel += "?" + query
        if fragment:
            rel += "#" + fragment
        return rel, False

    # -- inline ------------------------------------------------------------
    def _plain(self, text: str) -> str:
        text = esc(text)
        text = re.sub(r"`([^`]+)`", lambda m: f"<code>{m.group(1)}</code>", text)
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<em>\1</em>", text)
        return text

    def inline(self, text: str) -> str:
        tokens: list[str] = []

        def stash(markup: str) -> str:
            tokens.append(markup)
            return f"\x00{len(tokens) - 1}\x00"

        text = re.sub(r"`([^`]+)`", lambda m: stash(f"<code>{esc(m.group(1))}</code>"), text)
        text = IMAGE_RE.sub(
            lambda m: stash(
                f'<span class="missing-image" role="img" aria-label="{attr(m.group(1))}">'
                f"{esc(m.group(1))}</span>"
            ),
            text,
        )

        def link_repl(m: re.Match) -> str:
            label, href, title = m.group(1), m.group(2), m.group(3)
            resolved = self.resolve_href(href)
            inner = self._plain(label)
            if resolved is None:
                return stash(
                    f'<span class="xref-pending" title="Referenced document or file is not '
                    f'published in this build">{inner}</span>'
                )
            out, external = resolved
            attrs = ' rel="noopener"' if external else ""
            if external and out.startswith("http://"):
                attrs += ' data-insecure="true"'
            if title:
                attrs += f' title="{attr(title)}"'
            css = ' class="external"' if external else ""
            return stash(f'<a href="{attr(out)}"{css}{attrs}>{inner}</a>')

        text = LINK_RE.sub(link_repl, text)
        text = AUTOLINK_RE.sub(
            lambda m: stash(
                f'<a href="{attr(m.group(1))}" class="external" rel="noopener">'
                f"{esc(m.group(1))}</a>"
            ),
            text,
        )
        text = esc(text)
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<em>\1</em>", text)
        text = re.sub(r"~~(.+?)~~", r"<del>\1</del>", text)
        text = re.sub(r"(?<![\w])_([^_\n]+)_(?![\w])", r"<em>\1</em>", text)
        # Resolve sentinels repeatedly: a link label may itself contain an
        # inline code span, so token 1's markup can contain token 0's sentinel.
        for _pass in range(8):
            remaining = False
            for idx, markup in enumerate(tokens):
                marker = f"\x00{idx}\x00"
                if marker in text:
                    text = text.replace(marker, markup)
                    remaining = True
            if not remaining:
                break
        # No control characters may survive into the HTML: an unresolved
        # sentinel is a rendering bug, not content.
        text = re.sub(r"\x00[0-9]*\x00", "", text)
        text = text.replace("\x00", "")
        return text

    # -- blocks ------------------------------------------------------------
    def heading(self, level: int, raw: str) -> str:
        plain = strip_tags(self._plain(raw))
        plain = re.sub(r"\s+", " ", plain).strip()
        base = slugify(plain)
        count = self.slugs.get(base, 0)
        self.slugs[base] = count + 1
        slug = base if count == 0 else f"{base}-{count + 1}"
        label = self.inline(raw)
        if level in (2, 3):
            self.toc.append({"level": level, "id": slug, "text": plain})
        return f'<h{level} id="{attr(slug)}">{label}</h{level}>\n'

    def split_row(self, line: str) -> list[str]:
        s = line.strip()
        if s.startswith("|"):
            s = s[1:]
        if s.endswith("|"):
            s = s[:-1]
        cells = re.split(r"(?<!\\)\|", s)
        return [c.strip().replace("\\|", "|") for c in cells]

    def is_table_start(self, lines: list[str], i: int) -> bool:
        if i + 1 >= len(lines):
            return False
        if not lines[i].lstrip().startswith("|"):
            return False
        sep = self.split_row(lines[i + 1])
        if not sep:
            return False
        return all(re.fullmatch(r":?-{2,}:?", c.replace(" ", "")) for c in sep if c != "") and any(
            c.strip() for c in sep
        )

    def is_block_start(self, lines: list[str], i: int) -> bool:
        line = lines[i]
        if not line.strip():
            return True
        if HEADING_RE.match(line) or FENCE_RE.match(line) or HR_RE.match(line):
            return True
        if line.lstrip().startswith(">"):
            return True
        if ITEM_RE.match(line):
            return True
        if self.is_table_start(lines, i):
            return True
        return False

    def parse_list(self, lines: list[str], i: int) -> tuple[str, int]:
        out: list[str] = []
        stack: list[dict] = []
        n = len(lines)

        def indent_of(s: str) -> int:
            return len(s.expandtabs(4)) - len(s.expandtabs(4).lstrip())

        while i < n:
            line = lines[i]
            if not line.strip():
                j = i + 1
                while j < n and not lines[j].strip():
                    j += 1
                if j < n and stack and (
                    ITEM_RE.match(lines[j]) or indent_of(lines[j]) > stack[-1]["indent"]
                ):
                    i += 1
                    continue
                break
            m = ITEM_RE.match(line)
            if m:
                indent = indent_of(line)
                tag = "ol" if re.match(r"\d", m.group(2)) else "ul"
                if not stack:
                    out.append(f"<{tag}>")
                    stack.append({"indent": indent, "tag": tag})
                elif indent > stack[-1]["indent"]:
                    out.append(f"<{tag}>")
                    stack.append({"indent": indent, "tag": tag})
                elif indent == stack[-1]["indent"]:
                    if tag != stack[-1]["tag"]:
                        out.append(f'</li></{stack[-1]["tag"]}><{tag}>')
                        stack[-1]["tag"] = tag
                    else:
                        out.append("</li>")
                else:
                    while stack and indent < stack[-1]["indent"]:
                        out.append(f'</li></{stack[-1]["tag"]}>')
                        stack.pop()
                    if not stack:
                        out.append(f"<{tag}>")
                        stack.append({"indent": indent, "tag": tag})
                    elif indent == stack[-1]["indent"]:
                        if tag != stack[-1]["tag"]:
                            out.append(f'</li></{stack[-1]["tag"]}><{tag}>')
                            stack[-1]["tag"] = tag
                        else:
                            out.append("</li>")
                    else:
                        out.append(f"<{tag}>")
                        stack.append({"indent": indent, "tag": tag})
                out.append("<li>" + self.inline(m.group(3).strip()))
                i += 1
                # Wrapped / lazy continuation lines belong to this item.
                while i < n:
                    nxt = lines[i]
                    if not nxt.strip() or ITEM_RE.match(nxt):
                        break
                    if HEADING_RE.match(nxt) or FENCE_RE.match(nxt) or HR_RE.match(nxt):
                        break
                    if nxt.lstrip().startswith(">"):
                        break
                    out.append(" " + self.inline(nxt.strip()))
                    i += 1
            else:
                if stack and not self.is_block_start(lines, i):
                    out.append(" " + self.inline(line.strip()))
                    i += 1
                else:
                    break
        while stack:
            out.append(f'</li></{stack[-1]["tag"]}>')
            stack.pop()
        return "".join(out), i

    def parse_table(self, lines: list[str], i: int) -> tuple[str, int]:
        header = self.split_row(lines[i])
        sep = self.split_row(lines[i + 1])
        aligns = []
        for c in sep:
            c = c.strip()
            if c.startswith(":") and c.endswith(":"):
                aligns.append("center")
            elif c.endswith(":"):
                aligns.append("right")
            else:
                aligns.append("left")
        i += 2
        rows = []
        while i < len(lines) and lines[i].strip().startswith("|"):
            cells = self.split_row(lines[i])
            if len(cells) < len(header):
                cells += [""] * (len(header) - len(cells))
            rows.append(cells[: len(header)])
            i += 1
        def align_attr(index: int) -> str:
            align = aligns[index] if index < len(aligns) else "left"
            return "" if align == "left" else f' class="t-{align[0]}"'

        th = "".join(
            f'<th scope="col"{align_attr(j)}>{self.inline(cell)}</th>'
            for j, cell in enumerate(header)
        )
        body = []
        for row in rows:
            tds = "".join(
                f"<td{align_attr(j)}>{self.inline(cell)}</td>"
                for j, cell in enumerate(row)
            )
            body.append(f"<tr>{tds}</tr>")
        table = (
            '<div class="table-wrap"><table><thead><tr>'
            + th
            + "</tr></thead><tbody>"
            + "".join(body)
            + "</tbody></table></div>\n"
        )
        return table, i

    def blocks(self, lines: list[str]) -> str:
        out: list[str] = []
        i = 0
        n = len(lines)
        while i < n:
            line = lines[i]
            if not line.strip():
                i += 1
                continue
            fence = FENCE_RE.match(line)
            if fence:
                marker = fence.group(2)
                lang = fence.group(3) or ""
                i += 1
                code_lines = []
                while i < n:
                    end = FENCE_CLOSE_RE.match(lines[i])
                    if end and end.group(2)[0] == marker[0] and len(end.group(2)) >= len(marker):
                        i += 1
                        break
                    code_lines.append(lines[i])
                    i += 1
                code = esc("\n".join(code_lines))
                lang_label = (
                    f'<span class="code-lang">{esc(lang)}</span>' if lang else '<span class="code-lang">text</span>'
                )
                out.append(
                    f'<div class="codeblock" data-lang="{attr(lang or "text")}">'
                    f'<div class="codeblock-bar">{lang_label}</div>'
                    f'<pre tabindex="0"><code>{code}</code></pre></div>\n'
                )
                continue
            heading = HEADING_RE.match(line)
            if heading:
                out.append(self.heading(len(heading.group(1)), heading.group(2)))
                i += 1
                continue
            if HR_RE.match(line):
                out.append("<hr>\n")
                i += 1
                continue
            if line.lstrip().startswith(">"):
                quote_lines = []
                while i < n and (lines[i].lstrip().startswith(">") or not lines[i].strip()):
                    if not lines[i].strip():
                        # A blank line ends the quote unless the next line continues it.
                        j = i + 1
                        if j < n and lines[j].lstrip().startswith(">"):
                            quote_lines.append("")
                            i += 1
                            continue
                        break
                    quote_lines.append(re.sub(r"^\s*>\s?", "", lines[i]))
                    i += 1
                out.append("<blockquote>" + self.blocks(quote_lines) + "</blockquote>\n")
                continue
            if self.is_table_start(lines, i):
                table, i = self.parse_table(lines, i)
                out.append(table)
                continue
            if ITEM_RE.match(line):
                listing, i = self.parse_list(lines, i)
                out.append(listing + "\n")
                continue
            # paragraph
            para = [line.strip()]
            i += 1
            while i < n and lines[i].strip() and not self.is_block_start(lines, i):
                para.append(lines[i].strip())
                i += 1
            joined = " ".join(para)
            joined = re.sub(r"  +", " ", joined)
            out.append(f"<p>{self.inline(joined)}</p>\n")
        return "".join(out)

    def render(self, text: str, skip_first_h1: bool = False) -> tuple[str, list[dict]]:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = text.split("\n")
        if skip_first_h1:
            for idx, line in enumerate(lines):
                if not line.strip():
                    continue
                if re.match(r"^#\s+", line):
                    lines = lines[:idx] + lines[idx + 1:]
                break
        body = self.blocks(lines)
        return body, self.toc


# ---------------------------------------------------------------------------
# Source documents
# ---------------------------------------------------------------------------


@dataclass
class Doc:
    rel: str
    stem: str
    doc_id: str
    title: str
    summary: str
    status: str
    normative: bool
    source: Path | None
    output: str
    placeholder: bool = False
    body: str = ""
    html: str = ""
    toc: list[dict] = field(default_factory=list)
    words: int = 0
    lead: str = ""


@dataclass
class DocPart:
    """One rendered part of a specification document.

    Long generated documents are paginated at a section boundary so no HTML
    page exceeds the project's 100 KB budget. Most documents have one part.
    """
    doc: Doc
    number: int
    total: int
    output: str
    body: str
    words: int
    range_label: str = ""


#: Documents too long for one page of the checker's 100 KiB budget: the file -> (the heading line that starts part 2, the labels
#: of the two parts). Part 2 is written to ``<stem>-part-2.html``; a link into a fragment of part 2 names that page.
SPLIT_DOCS = {
    "03-capability-registry.md": ("### 7.5 Fluid", ("Sections 1–7.4", "Sections 7.5–12")),
    "00-architecture.md": ("## 9. Adapter and bridge model", ("Sections 1–8", "Sections 9–16")),
    "core.md": ("## 7. Receipts, idempotency, revisions and long-running work", ("Sections 0–6", "Sections 7–15")),
}


def build_doc_parts(docs: list[Doc]) -> list[DocPart]:
    parts: list[DocPart] = []
    for doc in docs:
        if doc.placeholder or doc.rel not in SPLIT_DOCS:
            parts.append(DocPart(doc, 1, 1, doc.output, doc.body, doc.words))
            continue
        marker, labels = SPLIT_DOCS[doc.rel]
        split_at = doc.body.find("\n" + marker)
        if split_at < 0:
            parts.append(DocPart(doc, 1, 1, doc.output, doc.body, doc.words))
            continue
        split_at += 1
        bodies = [doc.body[:split_at].rstrip() + "\n", doc.body[split_at:]]
        for number, body in enumerate(bodies, start=1):
            output = doc.output if number == 1 else f"spec/{doc.stem}-part-{number}.html"
            parts.append(
                DocPart(doc, number, 2, output, body, word_count(body), labels[number - 1])
            )
    return parts


def extract_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        m = re.match(r"^#\s+(.+?)\s*$", line)
        if m:
            return re.sub(r"^MHS-[0-9A-Z]+\s+[—-]\s+", "", m.group(1)).strip()
    return fallback


def extract_lead(text: str) -> str:
    lines = text.splitlines()
    seen_h1 = False
    in_table = False
    para: list[str] = []
    for line in lines:
        s = line.strip()
        if s.startswith("# "):
            seen_h1 = True
            continue
        if not seen_h1:
            continue
        if s.startswith("|"):
            in_table = True
            continue
        if in_table and not s:
            in_table = False
            continue
        if in_table:
            continue
        if not s or s in ("---", "***", "___"):
            if para:
                break
            continue
        if s.startswith(("#", "```", "~~~", "- ", "* ", "> ")):
            if para:
                break
            continue
        para.append(s)
        if len(" ".join(para)) > 260:
            break
    lead = " ".join(para)
    lead = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", lead)
    # Inline code is literal: stripping emphasis markers from it corrupts
    # capability IDs and other identifiers in metadata and the search index.
    lead = re.sub(r"`([^`]+)`|[`*_]", lambda match: match.group(1) or "", lead)
    lead = re.sub(r"\s+", " ", lead).strip()
    return lead


def discover_docs() -> list[Doc]:
    spec_dir = MHS / "spec"
    existing = {}
    if spec_dir.is_dir():
        for p in sorted(spec_dir.glob("*.md")):
            if p.name == "README.md":
                continue
            existing[p.name] = p
    docs: list[Doc] = []
    for rel, doc_id, title, summary in DOC_ORDER:
        source = existing.get(rel)
        if rel not in {d[0] for d in DOC_ORDER}:
            continue
        stem = rel[:-3]
        output = f"spec/{stem}.html"
        if source is not None:
            text = read_text(source)
            real_title = extract_title(text, title)
            status_m = re.search(r"^\|\s*Status\s*\|\s*([^|]+?)\s*\|", text, re.MULTILINE)
            status = status_m.group(1).strip() if status_m else DRAFT_LABEL
            head = text[:5000].lower()
            normative = "normative" in head and not (
                "informative" in head and "normative content" not in head
            )
            docs.append(
                Doc(
                    rel=rel,
                    stem=stem,
                    doc_id=doc_id,
                    title=real_title,
                    summary=summary,
                    status=status,
                    normative=normative,
                    source=source,
                    output=output,
                    body=text,
                    words=word_count(text),
                    lead=extract_lead(text),
                )
            )
        else:
            docs.append(
                Doc(
                    rel=rel,
                    stem=stem,
                    doc_id=doc_id,
                    title=title,
                    summary=summary,
                    status="In preparation",
                    normative=True,
                    source=None,
                    output=output,
                    placeholder=True,
                )
            )
    # Any extra spec documents not in the map are still published.
    for name, p in existing.items():
        if name in {d.rel for d in docs}:
            continue
        text = read_text(p)
        stem = name[:-3]
        doc_id_m = re.match(r"^#\s+(MHS-[0-9A-Z]+)", text)
        docs.append(
            Doc(
                rel=name,
                stem=stem,
                doc_id=doc_id_m.group(1) if doc_id_m else stem,
                title=extract_title(text, stem),
                summary=extract_lead(text)[:180],
                status=DRAFT_LABEL if "draft" in text[:3000].lower() else "Published",
                normative="normative" in text[:4000].lower(),
                source=p,
                output=f"spec/{stem}.html",
                body=text,
                words=word_count(text),
                lead=extract_lead(text),
            )
        )
    return docs


# ---------------------------------------------------------------------------
# Registry data
# ---------------------------------------------------------------------------

LICENSE_BUCKETS = [
    ("MIT", "MIT"),
    ("Apache-2.0", "Apache-2.0"),
    ("BSD-3-Clause", "BSD-3-Clause"),
    ("BSD-2-Clause", "BSD-2-Clause"),
    ("GPL-3.0", "GPL-3.0"),
    ("GPL-2.0", "GPL-2.0"),
    ("AGPL-3.0", "AGPL-3.0"),
    ("LGPL-3.0", "LGPL-3.0"),
    ("LGPL-2.1", "LGPL-2.1"),
    ("MPL-2.0", "MPL-2.0"),
    ("CC0-1.0", "CC0-1.0"),
    ("CC-BY-SA-4.0", "CC-BY-SA-4.0"),
    ("CC-BY-4.0", "CC-BY-4.0"),
    ("ISC", "ISC"),
    ("Unlicense", "Unlicense"),
    ("Zlib", "Zlib"),
    ("SSPL-1.0", "SSPL-1.0"),
    ("EUPL-1.2", "EUPL-1.2"),
]

TIERS = ["A", "B", "C", "D", "X"]
TRACKS = [("labs", "Labs"), ("robots", "Robots")]
RINGS = [1, 2, 3]


def license_bucket(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw or raw.lower() == "unknown" or raw.lower().startswith("unknown"):
        return "Unknown"
    if raw.upper() == "NOASSERTION":
        return "Unasserted (NOASSERTION)"
    for prefix, label in LICENSE_BUCKETS:
        if raw.lower().startswith(prefix.lower()):
            return label
    if "MIT" in raw and "Apache" in raw:
        return "MIT"
    return "Other / custom"


def _synthetic_registry() -> dict:
    """Deterministic ~2,900-record fallback so the explorer is never empty."""
    families = [f for f in FAMILY_ORDER if f != "other"]
    tracks = ["labs", "robots"]
    licenses = ["MIT", "Apache-2.0", "BSD-3-Clause", "GPL-3.0", "unknown", "BSD-2-Clause"]
    records = []
    for i in range(2900):
        family = families[i % len(families)]
        track = tracks[i % 2]
        tier = TIERS[[0, 1, 1, 2, 3][i % 5]]
        ring = [1, 2, 2, 3][i % 4]
        modes = [["simulated"], ["hardware"], ["simulated", "hardware"]][i % 3]
        owner = f"synthetic-{family}"
        repo = f"{family}-tool-{i:04d}"
        records.append(
            {
                "package_id": f"gh.{owner}/{repo}",
                "title": f"{owner}/{repo}",
                "owner": owner,
                "repo": repo,
                "track": track,
                "families": [family],
                "tier": tier,
                "ring": ring,
                "modes": modes,
                "license": licenses[i % len(licenses)],
                "stars": (i * 37) % 500,
                "description": (
                    f"Synthetic placeholder record for the {family} family. "
                    "Generated because MHS/registry/index.json was not present at build time."
                ),
                "capabilities_offered": ["cap.device.describe.v1", "cap.world.step.v1"],
                "interfaces": ["Python SDK"],
                "languages": ["Python"],
                "adapter": {"bridge": family, "state": "declared", "present": False},
                "evidence": {"state": "declared", "read_by": "generator"},
                "next_action": "Integrate a detected entry point, publish a manifest, then run the conformance suite.",
                "has_manifest": False,
                "local_path": f"{track}/{owner}/{repo}",
                "repo_url": "",
            }
        )
    stats = {
        "total": len(records),
        "by_track": {"labs": 1450, "robots": 1450},
        "by_tier": {t: sum(1 for r in records if r["tier"] == t) for t in TIERS},
        "by_ring": {str(r): sum(1 for x in records if x["ring"] == r) for r in RINGS},
        "by_evidence": {"declared": len(records)},
        "by_mode": {m: sum(1 for r in records if m in r["modes"]) for m in ("hardware", "simulated", "replay")},
        "by_family": {f: sum(1 for r in records if f in r["families"]) for f in FAMILY_ORDER},
        "manifests": 0,
        "capability_claims": len(records) * 2,
    }
    return {
        "generated_at": BUILD_DATE,
        "registry_version": "1.0.0",
        "records": records,
        "stats": stats,
        "source_manifest": {"generator": "MHS/site synthetic fallback"},
        "_synthetic": True,
    }


def load_registry() -> dict:
    raw = load_json(MHS / "registry" / "index.json")
    if not isinstance(raw, dict) or not isinstance(raw.get("records"), list) or not raw["records"]:
        if RELEASE:
            raise SystemExit(
                "--release: MHS/registry/index.json is missing or has no records; "
                "a release build never publishes the synthetic fallback registry"
            )
        return _synthetic_registry()
    raw["_synthetic"] = False
    return raw


@dataclass
class Registry:
    raw: dict
    records: list[dict]
    stats: dict
    synthetic: bool
    generated_at: str
    family_counts: dict
    license_counts: dict
    track_counts: dict
    tier_counts: dict
    ring_counts: dict
    mode_counts: dict
    evidence_counts: dict

    @property
    def total(self) -> int:
        return len(self.records)


def prepare_registry(raw: dict) -> Registry:
    records = []
    family_counts: dict[str, int] = {}
    license_counts: dict[str, int] = {}
    track_counts: dict[str, int] = {}
    tier_counts: dict[str, int] = {}
    ring_counts: dict[str, int] = {}
    mode_counts: dict[str, int] = {}
    evidence_counts: dict[str, int] = {}
    for item in raw.get("records", []):
        rec = dict(item)
        rec["owner"] = str(rec.get("owner") or "unknown")
        rec["repo"] = str(rec.get("repo") or "unknown")
        rec["title"] = str(rec.get("title") or f"{rec['owner']}/{rec['repo']}")
        rec["slug"] = f"{rec['owner']}__{rec['repo']}"
        families = rec.get("families") or ["other"]
        rec["family"] = families[0] if families else "other"
        rec["family_slug"] = re.sub(r"[^a-z0-9]+", "-", str(rec["family"]).lower()).strip("-") or "other"
        rec["description"] = re.sub(r"\s+", " ", str(rec.get("description") or "")).strip()
        rec["license"] = str(rec.get("license") or "unknown")
        rec["license_bucket"] = license_bucket(rec["license"])
        rec["tier"] = str(rec.get("tier") or "?")
        rec["track"] = str(rec.get("track") or "labs")
        rec["ring"] = int(rec.get("ring") or 2)
        rec["modes"] = [str(m) for m in (rec.get("modes") or [])]
        rec["capabilities_offered"] = [str(c) for c in (rec.get("capabilities_offered") or [])]
        rec["interfaces"] = [str(i) for i in (rec.get("interfaces") or [])]
        rec["languages"] = [str(i) for i in (rec.get("languages") or [])]
        adapter = rec.get("adapter") or ({} if not rec.get("has_manifest") else {"state": "declared"})
        rec["adapter"] = adapter if isinstance(adapter, dict) else {"state": "declared"}
        rec["adapter_state"] = str(rec["adapter"].get("state") or ("declared" if rec.get("has_manifest") else "none"))
        evidence = rec.get("evidence") or {}
        if isinstance(evidence, dict):
            rec["evidence_state"] = str(evidence.get("state") or evidence.get("read_by") or "catalog")
            rec["evidence_notes"] = str(evidence.get("notes") or "")
            rec["evidence_files"] = evidence.get("files_read")
            rec["provenance_refs"] = evidence.get("provenance_refs") or []
        else:
            rec["evidence_state"] = str(evidence or "catalog")
            rec["evidence_notes"] = ""
            rec["evidence_files"] = None
            rec["provenance_refs"] = []
        rec["repo_url"] = str(rec.get("repo_url") or "")
        rec["next_action"] = re.sub(r"\s+", " ", str(rec.get("next_action") or "")).strip()
        rec["local_path"] = str(rec.get("local_path") or "")
        rec["stars"] = int(rec.get("stars") or 0)
        rec["has_manifest"] = bool(rec.get("has_manifest"))
        rec["integration"] = rec.get("integration") or {}
        rec["trust"] = str(rec.get("trust") or "unsigned")
        rec["cap_count"] = len(rec["capabilities_offered"])
        rec["family_counts"] = rec.get("families") or []
        records.append(rec)
        for fam in rec["family_counts"]:
            family_counts[fam] = family_counts.get(fam, 0) + 1
        license_counts[rec["license_bucket"]] = license_counts.get(rec["license_bucket"], 0) + 1
        track_counts[rec["track"]] = track_counts.get(rec["track"], 0) + 1
        tier_counts[rec["tier"]] = tier_counts.get(rec["tier"], 0) + 1
        ring_counts[str(rec["ring"])] = ring_counts.get(str(rec["ring"]), 0) + 1
        for mode in rec["modes"]:
            mode_counts[mode] = mode_counts.get(mode, 0) + 1
        evidence_counts[rec["evidence_state"]] = evidence_counts.get(rec["evidence_state"], 0) + 1
    records.sort(key=lambda r: (r["title"].lower(), r["package_id"]))
    return Registry(
        raw=raw,
        records=records,
        stats=raw.get("stats") or {},
        synthetic=bool(raw.get("_synthetic")),
        generated_at=str(raw.get("generated_at") or BUILD_DATE),
        family_counts=dict(sorted(family_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        license_counts=dict(sorted(license_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        track_counts=dict(sorted(track_counts.items())),
        tier_counts=dict(sorted(tier_counts.items())),
        ring_counts=dict(sorted(ring_counts.items(), key=lambda kv: int(kv[0]))),
        mode_counts=dict(sorted(mode_counts.items())),
        evidence_counts=dict(sorted(evidence_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
    )


# ---------------------------------------------------------------------------
# Capabilities, families, SDK
# ---------------------------------------------------------------------------


@dataclass
class Capabilities:
    version: str
    items: list[dict]
    by_id: dict
    domains: list[tuple[str, list[dict]]]
    source_present: bool

    @property
    def count(self) -> int:
        return len(self.items)

    @property
    def status_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for cap in self.items:
            counts[cap["_status"]] = counts.get(cap["_status"], 0) + 1
        return counts


def load_capabilities() -> Capabilities:
    data = load_json(MHS / "spec" / "capabilities.json", {}) or {}
    items = data.get("capabilities") or []
    if not isinstance(items, list):
        items = []
    for cap in items:
        cap["_slug"] = str(cap.get("capability_id") or "unknown")
        cap["_domain"] = str(cap.get("domain") or "other")
        cap["_title"] = str(cap.get("title") or cap["_slug"])
        cap["_summary"] = str(cap.get("summary") or "")
        cap["_tags"] = [str(t) for t in (cap.get("tags") or [])]
        cap["_modes"] = [str(m) for m in (cap.get("modes") or [])]
        cap["_risk"] = str(cap.get("risk_class") or "R0")
        cap["_verb"] = str(cap.get("verb") or "invoke")
        cap["_status"] = str(cap.get("status") or "stable")
    items.sort(key=lambda c: c["_slug"])
    by_id = {c["_slug"]: c for c in items}
    domains: dict[str, list[dict]] = {}
    for cap in items:
        domains.setdefault(cap["_domain"], []).append(cap)
    domain_order = sorted(domains, key=lambda d: (-len(domains[d]), d))
    return Capabilities(
        version=str(data.get("mhs_capabilities") or MHS_VERSION),
        items=items,
        by_id=by_id,
        domains=[(d, domains[d]) for d in domain_order],
        source_present=bool(items),
    )


@dataclass
class Family:
    slug: str
    name: str
    title: str
    description: str
    source: Path | None
    body: str = ""
    html: str = ""
    toc: list[dict] = field(default_factory=list)
    count: int = 0
    placeholder: bool = True


def slugify_family(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "other"


def load_families(registry: Registry) -> list[Family]:
    recipe_dir = MHS / "registry" / "families"
    recipes: dict[str, Path] = {}
    if recipe_dir.is_dir():
        for p in sorted(recipe_dir.glob("*.md")):
            recipes[p.stem] = p
    names = set(FAMILY_META) | set(registry.family_counts) | set(recipes)
    families: list[Family] = []
    for name in sorted(names, key=lambda n: (0 if n in FAMILY_META else 1, -registry.family_counts.get(n, 0), n)):
        slug = slugify_family(name)
        meta = FAMILY_META.get(name)
        source = recipes.get(name) or recipes.get(slug)
        if meta:
            title, description = meta
        else:
            title = name.replace("-", " ").title()
            description = f"Packages indexed under the {name} bridge family."
        if source is not None:
            text = read_text(source)
            title = extract_title(text, title)
            description = extract_lead(text)[:240] or description
            families.append(
                Family(
                    slug=slug,
                    name=name,
                    title=title,
                    description=description,
                    source=source,
                    body=text,
                    count=registry.family_counts.get(name, 0),
                    placeholder=False,
                )
            )
        else:
            families.append(
                Family(
                    slug=slug,
                    name=name,
                    title=title,
                    description=description,
                    source=None,
                    count=registry.family_counts.get(name, 0),
                    placeholder=True,
                )
            )
    # Collision guard: two family names with the same slug keep both pages distinct.
    seen: dict[str, int] = {}
    for fam in families:
        if fam.slug in seen:
            seen[fam.slug] += 1
            fam.slug = f"{fam.slug}-{seen[fam.slug]}"
        else:
            seen[fam.slug] = 1
    families.sort(key=lambda f: (-f.count, f.title.lower()))
    return families


@dataclass
class SdkDocs:
    readme: Path | None
    docs: list[Path]
    interface: Path | None
    modules: list[Path] = field(default_factory=list)
    tests: list[Path] = field(default_factory=list)
    suite_modules: list[Path] = field(default_factory=list)

    @property
    def present(self) -> bool:
        return self.readme is not None


def load_sdk() -> SdkDocs:
    readme = MHS / "sdk" / "README.md"
    docs_dir = MHS / "sdk" / "docs"
    docs = sorted(docs_dir.glob("*.md")) if docs_dir.is_dir() else []
    interface = MHS / "sdk" / "INTERFACE.md"
    src = MHS / "sdk" / "src" / "mhs"
    modules = (
        sorted(p for p in src.rglob("*.py") if "__pycache__" not in p.parts)
        if src.is_dir() else []
    )
    tests_dir = MHS / "sdk" / "tests"
    tests = (
        sorted(tests_dir.rglob("test_*.py")) if tests_dir.is_dir() else []
    )
    suite_dir = src / "conformance"
    suite_modules = (
        sorted(p for p in suite_dir.glob("*.py")) if suite_dir.is_dir() else []
    )
    return SdkDocs(
        readme=readme if readme.is_file() else None,
        docs=docs,
        interface=interface if interface.is_file() else None,
        modules=modules,
        tests=tests,
        suite_modules=suite_modules,
    )


# ---------------------------------------------------------------------------
# Page framework
# ---------------------------------------------------------------------------

ICONS = {
    "arrow": '<svg class="icon" viewBox="0 0 20 20" aria-hidden="true" focusable="false"><path d="M4 10h11M11 5l5 5-5 5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    "chevron": '<svg class="icon" viewBox="0 0 20 20" aria-hidden="true" focusable="false"><path d="M7 4l6 6-6 6" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    "search": '<svg class="icon" viewBox="0 0 20 20" aria-hidden="true" focusable="false"><circle cx="9" cy="9" r="5.5" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M13 13l4 4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>',
    "sun": '<svg class="icon icon-sun" viewBox="0 0 20 20" aria-hidden="true" focusable="false"><circle cx="10" cy="10" r="3.4" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M10 2v2M10 16v2M2 10h2M16 10h2M4.3 4.3l1.4 1.4M14.3 14.3l1.4 1.4M15.7 4.3l-1.4 1.4M5.7 14.3l-1.4 1.4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>',
    "moon": '<svg class="icon icon-moon" viewBox="0 0 20 20" aria-hidden="true" focusable="false"><path d="M15.5 12.4A6.2 6.2 0 017.6 4.5 6.5 6.5 0 1015.5 12.4z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg>',
    "menu": '<svg class="icon" viewBox="0 0 20 20" aria-hidden="true" focusable="false"><path d="M3 6h14M3 10h14M3 14h14" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>',
    "close": '<svg class="icon" viewBox="0 0 20 20" aria-hidden="true" focusable="false"><path d="M5 5l10 10M15 5L5 15" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>',
    "external": '<svg class="icon icon-external" viewBox="0 0 20 20" aria-hidden="true" focusable="false"><path d="M8 5H5.5A1.5 1.5 0 004 6.5v8A1.5 1.5 0 005.5 16h8a1.5 1.5 0 001.5-1.5V12M11 4h5v5M16 4l-7 7" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    "copy": '<svg class="icon" viewBox="0 0 20 20" aria-hidden="true" focusable="false"><rect x="7" y="7" width="9" height="9" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M13 7V5.5A1.5 1.5 0 0011.5 4h-7A1.5 1.5 0 003 5.5v7A1.5 1.5 0 004.5 14H6" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>',
    "check": '<svg class="icon" viewBox="0 0 20 20" aria-hidden="true" focusable="false"><path d="M4 10.5l4 4L16 6" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    "shield": '<svg class="icon" viewBox="0 0 20 20" aria-hidden="true" focusable="false"><path d="M10 2.5l6 2.2v4.9c0 3.7-2.5 6.5-6 7.9-3.5-1.4-6-4.2-6-7.9V4.7l6-2.2z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/><path d="M7.2 9.8l2 2 3.7-4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    "terminal": '<svg class="icon" viewBox="0 0 20 20" aria-hidden="true" focusable="false"><rect x="2.5" y="4" width="15" height="12" rx="2" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M5.5 8l2.5 2-2.5 2M10 12h4" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    "book": '<svg class="icon" viewBox="0 0 20 20" aria-hidden="true" focusable="false"><path d="M3.5 4.5A1.5 1.5 0 015 3h4v13H5a1.5 1.5 0 00-1.5 1.5v-13zM16.5 4.5A1.5 1.5 0 0015 3h-4v13h4a1.5 1.5 0 011.5 1.5v-13z" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/></svg>',
    "package": '<svg class="icon" viewBox="0 0 20 20" aria-hidden="true" focusable="false"><path d="M10 2.8l6.5 3.4v7.6L10 17.2l-6.5-3.4V6.2L10 2.8z" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/><path d="M3.7 6.3L10 9.7l6.3-3.4M10 9.7v7.2" fill="none" stroke="currentColor" stroke-width="1.4"/></svg>',
    "layers": '<svg class="icon" viewBox="0 0 20 20" aria-hidden="true" focusable="false"><path d="M10 2.8l7 3.7-7 3.7-7-3.7 7-3.7zM3 10.2l7 3.7 7-3.7M3 13.8l7 3.7 7-3.7" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/></svg>',
    "link": '<svg class="icon" viewBox="0 0 20 20" aria-hidden="true" focusable="false"><path d="M8.5 11.5a3 3 0 004.2 0l2.4-2.4a3 3 0 00-4.2-4.2l-1.1 1.1M11.5 8.5a3 3 0 00-4.2 0l-2.4 2.4a3 3 0 004.2 4.2l1.1-1.1" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>',
}


def svg_mark(cls: str = "brand-mark", size: int = 28) -> str:
    return (
        f'<svg class="{cls}" width="{size}" height="{size}" viewBox="0 0 32 32" aria-hidden="true" focusable="false">'
        '<rect x="1" y="1" width="30" height="30" rx="8" fill="var(--mark-bg, #1d4ed8)"/>'
        '<path d="M8 23V10.5l8 6.5 8-6.5V23" fill="none" stroke="var(--mark-fg, #fff)" stroke-width="2.1" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
        '<circle cx="8" cy="9" r="1.7" fill="var(--mark-fg, #fff)"/>'
        '<circle cx="24" cy="9" r="1.7" fill="var(--mark-fg, #fff)"/>'
        "</svg>"
    )


FAVICON = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
    '<rect width="32" height="32" rx="7" fill="#1d4ed8"/>'
    '<path d="M7 24V10l9 7 9-7v14" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>'
    '<circle cx="7" cy="8" r="2" fill="#fff"/><circle cx="25" cy="8" r="2" fill="#fff"/></svg>'
)

NAV = [
    ("spec/index.html", "Specification", "spec"),
    ("registry/index.html", "Registry", "registry"),
    ("capabilities/index.html", "Capabilities", "capabilities"),
    ("families/index.html", "Families", "families"),
    ("conformance/index.html", "Conformance", "conformance"),
    ("sdk/index.html", "SDK", "sdk"),
]


def nav_links(prefix: str, section: str) -> str:
    parts = []
    for path, label, key in NAV:
        current = ' aria-current="page"' if section == key else ""
        parts.append(f'<a href="{prefix}{path}"{current}>{esc(label)}</a>')
    return "".join(parts)


def header_html(prefix: str, section: str) -> str:
    mobile_links = []
    for path, label, key in NAV:
        current = ' aria-current="page"' if section == key else ""
        mobile_links.append(f'<a href="{prefix}{path}"{current}>{esc(label)}</a>')
    mobile_links.extend(
        [
            f'<a href="{prefix}playground/index.html">Playground</a>',
            f'<a href="{prefix}hosts/openai4s/index.html">OpenAI4S host</a>',
            f'<a href="{prefix}governance/index.html">Governance</a>',
            f'<a href="{prefix}download/index.html">Downloads</a>',
            f'<a href="{prefix}about/index.html">About</a>',
            f'<a href="{prefix}search/index.html">Search</a>',
        ]
    )
    return f"""<header class="site-header">
  <div class="wrap header-inner">
    <a class="brand" href="{prefix}index.html" aria-label="{SITE_NAME} home">
      {svg_mark()}
      <span class="brand-text"><strong>{SITE_NAME}</strong><span class="brand-sub">independent draft {SPEC_VERSION}</span></span>
    </a>
    <nav class="nav-primary" aria-label="Primary">{nav_links(prefix, section)}</nav>
    <div class="header-actions">
      <a class="icon-btn search-link" href="{prefix}search/index.html" aria-label="Search the site" title="Search (press /)">{ICONS['search']}</a>
      <button class="icon-btn theme-toggle" type="button" aria-label="Switch to dark colour scheme" title="Toggle colour scheme">
        {ICONS['sun']}{ICONS['moon']}
      </button>
      <a class="btn btn-sm btn-primary header-cta" href="{prefix}playground/index.html">Playground</a>
      <details class="nav-disclosure">
        <summary class="icon-btn menu-btn"><span class="sr-only">Open menu</span>{ICONS['menu']}</summary>
        <nav class="mobile-panel" aria-label="Mobile">{''.join(mobile_links)}</nav>
      </details>
    </div>
  </div>
</header>"""


def affiliation_banner(prefix: str) -> str:
    """The non-affiliation notice that opens every page."""
    return (
        '<div class="affiliation-banner" role="note"><div class="wrap">'
        f'<p>{esc(NON_AFFILIATION)} '
        f'<a href="{prefix}anthropic-mhs/index.html">{esc(ANTHROPIC_PAGE_LABEL)}</a></p>'
        "</div></div>"
    )


def footer_html(prefix: str) -> str:
    spec_links = "".join(
        f'<li><a href="{prefix}spec/{rel[:-3]}.html">{esc(doc_id)} · {esc(title)}</a></li>'
        for rel, doc_id, title, _ in DOC_ORDER[:6]
    )
    sitemap_link = f'<li><a href="{prefix}sitemap.xml">Sitemap</a></li>' if SITE_URL else ""
    return f"""<footer class="site-footer">
  <div class="wrap footer-grid">
    <div class="footer-brand">
      <a class="brand" href="{prefix}index.html" aria-label="{SITE_NAME} home">
        {svg_mark(size=26)}
        <span class="brand-text"><strong>{SITE_NAME}</strong><span class="brand-sub">independent draft {SPEC_VERSION}</span></span>
      </a>
      <p class="footer-def">An independent, open draft contract between AI agents and physical equipment: discovery, capabilities, a safety envelope and an evidence trail for instruments, robots and simulations.</p>
      <p class="footer-status"><span class="dot"></span> {SITE_NAME} {SPEC_VERSION} · {DRAFT_LABEL}</p>
    </div>
    <div>
      <h2 class="footer-head">Standard</h2>
      <ul class="footer-links">{spec_links}<li><a href="{prefix}spec/index.html">All specification documents</a></li></ul>
    </div>
    <div>
      <h2 class="footer-head">Ecosystem</h2>
      <ul class="footer-links">
        <li><a href="{prefix}registry/index.html">Registry explorer</a></li>
        <li><a href="{prefix}capabilities/index.html">Capability catalogue</a></li>
        <li><a href="{prefix}families/index.html">Bridge families</a></li>
        <li><a href="{prefix}sdk/index.html">Reference SDK</a></li>
        <li><a href="{prefix}hosts/openai4s/index.html">OpenAI4S host</a></li>
        <li><a href="{prefix}playground/index.html">Playground</a></li>
      </ul>
    </div>
    <div>
      <h2 class="footer-head">Project</h2>
      <ul class="footer-links">
        <li><a href="{prefix}conformance/index.html">Conformance</a></li>
        <li><a href="{prefix}governance/index.html">Governance &amp; licensing</a></li>
        <li><a href="{prefix}download/index.html">Downloads</a></li>
        <li><a href="{prefix}search/index.html">Search</a></li>
        <li><a href="{prefix}about/index.html">About {SITE_NAME}</a></li>
        <li><a href="{prefix}anthropic-mhs/index.html">{esc(ANTHROPIC_PAGE_LABEL)}</a></li>
        {sitemap_link}
      </ul>
    </div>
  </div>
  <div class="wrap footer-legal">
    <p>© 2026 {esc(COPYRIGHT_HOLDER)}. Specification text and registry data CC BY 4.0 · code and schemas MIT · quoted third-party text is not covered by these licences.</p>
    <p>{esc(NON_AFFILIATION)}</p>
    <p>{SITE_NAME} conformance is not safety certification. No trackers, no external fonts, no CDNs.</p>
  </div>
</footer>"""


def breadcrumbs_html(prefix: str, items: list[tuple[str, str | None]]) -> str:
    parts = [f'<li><a href="{prefix}index.html">Home</a></li>']
    for label, path in items:
        if path:
            parts.append(f'<li><a href="{prefix}{path}">{esc(label)}</a></li>')
        else:
            parts.append(f'<li aria-current="page">{esc(label)}</li>')
    return f'<nav class="breadcrumb" aria-label="Breadcrumb"><ol>{"".join(parts)}</ol></nav>'


def jsonld_for(
    title: str,
    description: str,
    path: str,
    og_type: str,
    breadcrumbs: list[tuple[str, str | None]] | None = None,
    extra: dict | None = None,
) -> str:
    # No Organization node: the project is not an incorporated body, and the
    # site never names an organisation it does not control.
    data: list[dict] = []
    website: dict = {"@type": "WebSite", "name": SITE_NAME}
    if SITE_URL:
        website["url"] = SITE_URL + "/"
    if og_type == "article":
        article = {
            "@context": "https://schema.org",
            "@type": "TechArticle",
            "headline": title,
            "description": description,
            "inLanguage": "en",
            "isPartOf": website,
        }
        if SITE_URL:
            article["url"] = canonical_url(path)
        data.append(article)
    else:
        data.append({"@context": "https://schema.org", **website, "description": description})
    if breadcrumbs and SITE_URL:
        items = [{"@type": "ListItem", "position": 1, "name": "Home", "item": SITE_URL + "/"}]
        for idx, (label, subpath) in enumerate(breadcrumbs, start=2):
            entry = {"@type": "ListItem", "position": idx, "name": label}
            if subpath:
                entry["item"] = SITE_URL + "/" + subpath
            items.append(entry)
        data.append({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": items})
    if extra:
        data.append(extra)
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f'<script type="application/ld+json">{payload}</script>'


def page_html(
    *,
    path: str,
    title: str,
    description: str,
    body: str,
    section: str = "",
    breadcrumbs: list[tuple[str, str | None]] | None = None,
    og_type: str = "website",
    noindex: bool = False,
    body_class: str = "",
    extra_head: str = "",
    structured_data: dict | None = None,
    canonical: bool = True,
) -> str:
    prefix = rel_root(path)
    full_title = title if title == SITE_NAME else f"{title} — {SITE_NAME}"
    desc = re.sub(r"\s+", " ", description).strip()
    if len(desc) > 200:
        desc = desc[:197].rsplit(" ", 1)[0] + "…"
    url = canonical_url(path)
    robots = '<meta name="robots" content="noindex,follow">\n' if noindex or path == "404.html" else ""
    canonical_tag = f'<link rel="canonical" href="{attr(url)}">\n' if url and canonical and path != "404.html" else ""
    og_url = f'<meta property="og:url" content="{attr(url)}">\n' if url else ""
    crumb_json = breadcrumbs if breadcrumbs else None
    ld = jsonld_for(title, desc, path, og_type, crumb_json, structured_data)
    theme_script = (
        "<script>try{var t=localStorage.getItem('mhs-theme');"
        "if(t==='light'||t==='dark')document.documentElement.dataset.theme=t}catch(e){}</script>"
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(full_title)}</title>
<meta name="description" content="{attr(desc)}">
{robots}{canonical_tag}<meta name="theme-color" content="#fbfbf9" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0c1118" media="(prefers-color-scheme: dark)">
<meta name="color-scheme" content="light dark">
<meta name="author" content="{attr(COPYRIGHT_HOLDER)}">
<meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:type" content="{attr(og_type)}">
<meta property="og:title" content="{attr(full_title)}">
<meta property="og:description" content="{attr(desc)}">
{og_url}<meta property="og:locale" content="en_US">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{attr(full_title)}">
<meta name="twitter:description" content="{attr(desc)}">
<link rel="icon" href="{prefix}favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="{prefix}assets/style.css">
{theme_script}
{ld}
{extra_head}<script defer src="{prefix}assets/app.js"></script>
</head>
<body class="{attr(body_class)}">
<a class="skip-link" href="#main">Skip to content</a>
{affiliation_banner(prefix)}
{header_html(prefix, section)}
<main id="main" tabindex="-1">
{body}
</main>
{footer_html(prefix)}
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Content helpers
# ---------------------------------------------------------------------------


def badge(text: str, tone: str = "neutral") -> str:
    return f'<span class="badge badge-{attr(tone)}">{esc(text)}</span>'


def btn(label: str, href: str, kind: str = "primary", icon: bool = False, attrs: str = "") -> str:
    icon_html = ICONS["arrow"] if icon else ""
    return (
        f'<a class="btn btn-{attr(kind)}" href="{attr(href)}"{attrs}>{esc(label)}{icon_html}</a>'
    )


def section_head(eyebrow: str, title: str, lead: str = "", center: bool = False, title_html: str | None = None) -> str:
    cls = " section-head-center" if center else ""
    lead_html = f'<p class="section-lead">{esc(lead)}</p>' if lead else ""
    title_markup = title_html if title_html is not None else esc(title)
    return (
        f'<div class="section-head{cls}"><p class="eyebrow">{esc(eyebrow)}</p>'
        f"<h2>{title_markup}</h2>{lead_html}</div>"
    )


def callout(title: str, body: str, kind: str = "note", icon: str = "") -> str:
    icon_html = ICONS.get(icon, "") if icon else ""
    return (
        f'<aside class="callout callout-{attr(kind)}">'
        f'<div class="callout-icon">{icon_html}</div><div><p class="callout-title">{esc(title)}</p>'
        f'<div class="callout-body">{body}</div></div></aside>'
    )


def codeblock(code: str, lexer: str = "json", caption: str = "") -> str:
    cap = f'<span class="code-lang">{esc(caption or lexer)}</span>' if (caption or lexer) else ""
    return (
        f'<div class="codeblock" data-lang="{attr(lexer)}"><div class="codeblock-bar">{cap}</div>'
        f'<pre tabindex="0"><code>{esc(code)}</code></pre></div>'
    )


def pill_list(items: list[str], cls: str = "pill") -> str:
    return "".join(f'<span class="{cls}">{esc(i)}</span>' for i in items)


def build_status(
    docs: list[Doc],
    registry: Registry,
    caps: Capabilities,
    families: list[Family],
    sdk: SdkDocs,
) -> dict:
    real_docs = [d for d in docs if not d.placeholder]
    recipes = [f for f in families if not f.placeholder]
    reports_dir = MHS / "conformance" / "reports"
    reports = sorted(reports_dir.glob("*.json")) if reports_dir.is_dir() else []
    suite_files = sdk.suite_modules
    runtime_tested = registry.evidence_counts.get("runtime_tested", 0)
    return {
        "docs_real": len(real_docs),
        "docs_total": len(docs),
        "docs_missing": len(docs) - len(real_docs),
        "registry_total": registry.total,
        "registry_manifests": int(registry.stats.get("manifests") or 0),
        "registry_claims": int(registry.stats.get("capability_claims") or 0),
        "runtime_tested": runtime_tested,
        "capabilities": caps.count,
        "families": len(families),
        "families_real": len(recipes),
        "sdk_present": sdk.present,
        "sdk_docs": len(sdk.docs),
        "sdk_modules": len(sdk.modules),
        "sdk_tests": len(sdk.tests),
        "suite_present": bool(suite_files),
        "suite_files": len(suite_files),
        "reports_count": len(reports),
        "registry_synthetic": registry.synthetic,
    }


# ---------------------------------------------------------------------------
# Pages: home
# ---------------------------------------------------------------------------


def home_page(ctx) -> str:
    p = ""
    st = ctx.status
    reg = ctx.registry
    docs = ctx.docs
    status_note = (
        f"{fmt_int(reg.total)} packages indexed"
        if not reg.synthetic
        else f"{fmt_int(reg.total)} synthetic packages (registry absent)"
    )
    hero = f"""
<section class="hero">
  <div class="hero-bg" aria-hidden="true"></div>
  <div class="wrap hero-grid">
    <div class="hero-copy">
      <p class="eyebrow"><span class="status-dot"></span> {SITE_NAME} {SPEC_VERSION} · {DRAFT_LABEL} · not affiliated with Anthropic</p>
      <h1>An open contract between <span class="accent">agents</span> and <span class="accent">equipment</span>.</h1>
      <p class="hero-definition">{esc(DEFINITION)}</p>
      <div class="hero-actions">
        {btn("Read the specification", "spec/index.html", "primary", icon=True)}
        {btn("Explore the registry", "registry/index.html", "secondary")}
      </div>
      <p class="hero-meta"><span>{status_note}</span><span>{st['capabilities']} capability classes</span><span>CL0–CL5 conformance</span></p>
    </div>
    <div class="hero-panel" aria-label="Example OpenMHS request and receipt">
      <div class="terminal">
        <div class="terminal-bar"><span class="term-dots" aria-hidden="true"><i></i><i></i><i></i></span><span class="terminal-title">one call · one receipt</span><span class="terminal-mode">simulated</span></div>
        <div class="terminal-body">
          <p class="terminal-comment"># request</p>
          <pre tabindex="0"><code><span class="tok-key">mhs.command</span> {{
  <span class="tok-key">"capability_id"</span>: <span class="tok-str">"cap.fluid.transfer.v1"</span>,
  <span class="tok-key">"input"</span>: {{
    <span class="tok-key">"source"</span>: <span class="tok-str">"plate:A1"</span>,
    <span class="tok-key">"target"</span>: <span class="tok-str">"plate:B3"</span>,
    <span class="tok-key">"volume"</span>: {{ <span class="tok-key">"value"</span>: <span class="tok-num">50</span>, <span class="tok-key">"unit"</span>: <span class="tok-str">"uL"</span> }}
  }},
  <span class="tok-key">"command_id"</span>: <span class="tok-str">"01J8ZQ3V6X…"</span>
}}</code></pre>
          <div class="terminal-divider"></div>
          <p class="terminal-comment"># receipt</p>
          <pre tabindex="0"><code>{{
  <span class="tok-key">"status"</span>: <span class="tok-ok">"completed"</span>,
  <span class="tok-key">"state_revision_after"</span>: <span class="tok-num">43</span>,
  <span class="tok-key">"state_hash_after"</span>: <span class="tok-str">"sha256:9f2c…"</span>,
  <span class="tok-key">"effects"</span>: [<span class="tok-str">"material.transfer"</span>],
  <span class="tok-key">"evidence"</span>: {{ <span class="tok-key">"seq"</span>: <span class="tok-num">812</span>, <span class="tok-key">"digest"</span>: <span class="tok-str">"sha256:4a1e…"</span> }}
}}</code></pre>
        </div>
        <div class="terminal-foot"><span>endpoint <code>mhs://lab-01:7331</code></span><span class="term-warn">not a safety certificate</span></div>
      </div>
      <p class="hero-panel-note">The same request shape moves a pipette, a robot joint or a simulated world. Mode and fidelity are declared, never inferred.</p>
    </div>
  </div>
  <div class="wrap hero-stats">
    <div class="stat"><span class="stat-value">{fmt_int(reg.total)}</span><span class="stat-label">packages indexed<br><a href="registry/index.html">explore the registry</a></span></div>
    <div class="stat"><span class="stat-value">{st['capabilities']}</span><span class="stat-label">core capability classes<br><a href="capabilities/index.html">browse the catalogue</a></span></div>
    <div class="stat"><span class="stat-value">{st['families']}</span><span class="stat-label">bridge families<br><a href="families/index.html">read the recipes</a></span></div>
    <div class="stat"><span class="stat-value">CL0–CL5</span><span class="stat-label">executable conformance<br><a href="conformance/index.html">the ladder</a></span></div>
  </div>
</section>
"""

    fixes = f"""
<section class="section" id="why">
  <div class="wrap">
    {section_head("Why OpenMHS", "Three failures the standard has to fix",
      "Every lab and robotics stack has the same integration story: a bespoke translator, safety knowledge in a PDF, and simulators that share nothing with the machines they model. OpenMHS makes the contract explicit.")}
    <div class="grid-3">
      <article class="card card-numbered">
        <span class="card-index">01</span>
        <h3>Integration is bespoke</h3>
        <p>Every instrument ships its own SDK, transport and vocabulary. Twelve instruments mean twelve translators that do not compose.</p>
        <p class="card-answer"><strong>OpenMHS:</strong> one JSON-RPC contract, declarative adapters, and reusable bridge families. The cost of support is a manifest and a thin shim, not a new driver.</p>
        <a class="text-link" href="spec/06-adapters.html">Adapters and bridges {ICONS['arrow']}</a>
      </article>
      <article class="card card-numbered">
        <span class="card-index">02</span>
        <h3>Agents cannot know what is safe</h3>
        <p>A model can read a docstring and still not know that 500&nbsp;mW will destroy a laser, that the door interlock is open, or that the arm already holds a plate.</p>
        <p class="card-answer"><strong>OpenMHS:</strong> limits, hazards, interlocks and permits travel in-band, and the endpoint evaluates them before any physical effect — not the model.</p>
        <a class="text-link" href="spec/04-safety.html">The safety envelope {ICONS['arrow']}</a>
      </article>
      <article class="card card-numbered">
        <span class="card-index">03</span>
        <h3>Simulation and hardware are separate universes</h3>
        <p>Most agent development happens in simulators, but drivers describe real devices. Two standards would double the work; treating them as identical would get someone hurt.</p>
        <p class="card-answer"><strong>OpenMHS:</strong> one object model, one wire protocol, two declared worlds. Mode and a fidelity contract make the difference machine-readable.</p>
        <a class="text-link" href="spec/05-fidelity.html">Modes and fidelity {ICONS['arrow']}</a>
      </article>
    </div>
  </div>
</section>
"""

    surfaces = f"""
<section class="section section-tint" id="surfaces">
  <div class="wrap">
    <div class="split-head">
      {section_head("The contract plane", "Three surfaces, one contract",
        "OpenMHS standardises what a device is, what it will do, and what happened. Each surface is machine-checkable; none of them lives in prose or in the agent's prompt.")}
      <a class="text-link split-link" href="spec/00-architecture.html#3-conceptual-model">Read the conceptual model {ICONS['arrow']}</a>
    </div>
    <div class="surface-grid">
      <article class="surface">
        <div class="surface-icon">{ICONS['layers']}</div>
        <p class="surface-kicker">01 · Discover</p>
        <h3>Declare the device and its capabilities</h3>
        <p>An endpoint publishes a device manifest: resources, bound capability classes, units, modes, safety declaration, fidelity contract. Schemas are addressable and versioned separately from the wire protocol.</p>
        <ul class="tick-list">
          <li>Endpoint discovery via <code>.well-known/mhs.json</code> or explicit configuration</li>
          <li>{st['capabilities']} typed capability classes with input and output schemas</li>
          <li>UCUM units at the boundary; ambiguous fields are schema errors</li>
        </ul>
        <div class="surface-links"><a href="capabilities/index.html">Capability catalogue</a><a href="spec/03-capability-registry.html">MHS-003</a></div>
      </article>
      <article class="surface">
        <div class="surface-icon">{ICONS['shield']}</div>
        <p class="surface-kicker">02 · Govern</p>
        <h3>Refuse before the device moves</h3>
        <p>The endpoint checks the session, grant, schema, limits, interlocks, permits, revision and lease — in that order, fail-closed, before any effect. Violations are receipts, not exceptions.</p>
        <ul class="tick-list">
          <li>Risk classes R0–R3 and per-capability limits</li>
          <li>Hardware e-stop required independently of OpenMHS</li>
          <li>Gated capabilities need a scoped, single-use permit</li>
        </ul>
        <div class="surface-links"><a href="spec/04-safety.html">MHS-004</a><a href="conformance/index.html">CL3 governed</a></div>
      </article>
      <article class="surface">
        <div class="surface-icon">{ICONS['check']}</div>
        <p class="surface-kicker">03 · Account</p>
        <h3>Make the physical outcome reviewable</h3>
        <p>Every command has a caller-generated id, an input digest and a retained receipt: status, revision, state hash, effects, errors and the native code. Receipts chain into tamper-evident evidence.</p>
        <ul class="tick-list">
          <li>Idempotent replay by <code>command_id</code>; reuse with different input fails closed</li>
          <li>Unknown outcomes are first-class, never inferred</li>
          <li>Offline-verifiable <code>sha256</code> evidence chain</li>
        </ul>
        <div class="surface-links"><a href="spec/02-wire-protocol.html#10-receipts">Receipts</a><a href="playground/index.html">Try the playground</a></div>
      </article>
    </div>
  </div>
</section>
"""

    cap_browse_label = f"Browse the {st['capabilities']} classes"
    capabilities_section = f"""
<section class="section" id="capabilities-not-drivers">
  <div class="wrap">
    <div class="capability-statement">
      <div>
        {section_head("Capabilities, not drivers", "Stop asking what a device is. Ask what it can do.", "Device categories do not compose. A “plate reader” and a “microscope” share no useful interface until their actions are described in the same typed vocabulary.")}
        <p class="lead-copy">OpenMHS describes a device as a set of capability classes bound to resources: <code>cap.sensing.image.v1</code>, <code>cap.motion.joint_position.v1</code>, <code>cap.fluid.transfer.v1</code>. Each binding carries units, limits, effects, hazards, determinism and risk. The driver becomes an implementation detail behind the binding, not the interface an agent has to learn.</p>
        <div class="hero-actions">
          {btn(cap_browse_label, "capabilities/index.html", "primary", icon=True)}
          {btn("How binding works", "spec/03-capability-registry.html#5-binding-a-class-to-a-device", "secondary")}
        </div>
      </div>
      <div class="capability-diagram" role="img" aria-label="A vendor driver, an SDK and a simulator all bind the same typed capability classes to resources, giving the agent one contract">
        <div class="cap-source"><span class="diagram-kicker">vendor driver</span><strong>SCPI instrument</strong><small>native commands, status codes</small></div>
        <div class="cap-source"><span class="diagram-kicker">SDK</span><strong>Python lab library</strong><small>classes, units, callbacks</small></div>
        <div class="cap-source"><span class="diagram-kicker">simulator</span><strong>MuJoCo world</strong><small>state, step, sensors</small></div>
        <div class="cap-merge" aria-hidden="true">↓</div>
        <div class="cap-contract"><span class="diagram-kicker">OpenMHS contract</span><strong>capability bindings</strong><div class="cap-chip-list"><code>cap.measure.voltage.v1</code><code>cap.fluid.transfer.v1</code><code>cap.world.step.v1</code></div></div>
        <div class="cap-merge" aria-hidden="true">↓</div>
        <div class="cap-agent"><span class="diagram-kicker">agent</span><strong>one invoke surface</strong><small>schema · safety · receipt · evidence</small></div>
      </div>
    </div>
  </div>
</section>
"""

    dual = f"""
<section class="section" id="sim-hardware">
  <div class="wrap">
    {section_head("Simulation and hardware", "One contract. Two declared worlds.",
      "OpenMHS is designed for the people who develop in simulation and deploy on equipment. The contract is identical; the truth claim is not.")}
    <div class="dual-panel">
      <div class="dual-graphic" role="img" aria-label="Hardware and simulated devices both bind to the same OpenMHS contract plane, with separate identities and explicit mode and fidelity">
        <div class="world-card world-hardware">
          <span class="world-tag">mode: hardware</span>
          <h3>Physical equipment</h3>
          <p>Drivers, SDKs, serial and VISA instruments, robots on a floor.</p>
          <p class="world-note">No fidelity contract required. Safety is enforced below and beside MHS.</p>
        </div>
        <div class="contract-spine">
          <span class="spine-label">OpenMHS contract plane</span>
          <span class="spine-line"></span>
          <span class="spine-caption">discover · invoke · receipt · evidence</span>
        </div>
        <div class="world-card world-sim">
          <span class="world-tag">mode: simulated</span>
          <h3>Simulated world</h3>
          <p>Gymnasium, MuJoCo, Gazebo, analytic workcells and digital twins.</p>
          <p class="world-note">Fidelity F0–F3, determinism claim and known gaps are required.</p>
        </div>
      </div>
      <div class="dual-copy">
        <h3>The differences are declared, not discovered</h3>
        <p><strong>Mode is not a trust flag.</strong> A session requests the device's declared mode; a mismatch is rejected. Switching from simulation to hardware is a different endpoint and device instance, never a flag flipped on a live session.</p>
        <p><strong>Fidelity is a contract.</strong> A simulator states its engine, fidelity level, timestep, determinism, replay support, validation record and — when non-empty — its gaps. Hiding a gap is a conformance failure.</p>
        <div class="mode-table" role="table" aria-label="Modes">
          <div class="mode-row mode-head" role="row"><span role="columnheader">Mode</span><span role="columnheader">Truth</span><span role="columnheader">Mutations</span></div>
          <div class="mode-row" role="row"><span role="cell"><code>hardware</code></span><span role="cell">the machine</span><span role="cell">yes</span></div>
          <div class="mode-row" role="row"><span role="cell"><code>simulated</code></span><span role="cell">the model</span><span role="cell">in the model</span></div>
          <div class="mode-row" role="row"><span role="cell"><code>hybrid</code></span><span role="cell">declared per resource</span><span role="cell">with authority</span></div>
          <div class="mode-row" role="row"><span role="cell"><code>replay</code></span><span role="cell">the recording</span><span role="cell">read-only</span></div>
        </div>
        <div class="fidelity-chips"><span>F0 analytic</span><span>F1 rigid body</span><span>F2 sensor &amp; actuator</span><span>F3 validated</span></div>
        <a class="text-link" href="spec/05-fidelity.html">Read the fidelity contract {ICONS['arrow']}</a>
      </div>
    </div>
    {callout("What OpenMHS does not promise", "<p>OpenMHS is a supervisory contract, not a real-time control loop and not a physics guarantee. A simulator can pass conformance and still be wrong for your experiment; read its declared gaps. A device can pass conformance and still be unsafe without independent hardware protection.</p>", "warn", "shield")}
  </div>
</section>
"""

    ladder_rows = [
        ("CL0", "Declared", "Manifests validate against the OpenMHS schemas. No runtime.", "Static"),
        ("CL1", "Observable", "Transport, discovery, reads and subscriptions with stable revisions.", "Read"),
        ("CL2", "Actuating", "Sessions, idempotent commands, receipts, cancellation, deadlines.", "Act"),
        ("CL3", "Governed", "Envelope enforcement, risk classes, permits, e-stop and reset.", "Govern"),
        ("CL4", "Reproducible", "Evidence export and verification; deterministic replay for simulators.", "Prove"),
        ("CL5", "Orchestrated", "Compositions, multi-device sessions, gap semantics, published claim.", "Orchestrate"),
    ]
    ladder = "".join(
        f'<li class="ladder-step"><a href="conformance/index.html#{level.lower()}"><span class="ladder-level">{level}</span>'
        f'<span class="ladder-body"><strong>{name}</strong><span>{desc}</span></span>'
        f'<span class="ladder-tag">{tag}</span></a></li>'
        for level, name, desc, tag in ladder_rows
    )
    conformance = f"""
<section class="section section-dark" id="conformance">
  <div class="wrap conformance-grid">
    <div>
      {section_head("Conformance", "A claim is a level, not a logo.",
        "A conformance claim names a profile and a level, and points to a machine-readable report that a third party can recompute. Prose claims are not conformance.")}
      <p class="on-dark-muted">The suite includes negative tests: interlock open, revision conflict, duplicate command id, deadline exceeded, cancellation, mode mismatch. A skipped test is not a passed test.</p>
      <div class="hero-actions">
        {btn("The conformance ladder", "conformance/index.html", "on-dark", icon=True)}
        {btn("How to self-certify", "conformance/index.html#self-certify", "ghost-dark")}
      </div>
    </div>
    <ol class="ladder">{ladder}</ol>
  </div>
</section>
"""

    ring_rows = [
        ("Ring 0", "Reference endpoints, runtime-verified", "A handful of endpoints we can execute locally to prove the protocol end to end.", 0),
        ("Ring 1", "Adapter manifests with code-level evidence", "Agent-read source, precise entry points, mapping sketch and safety profile.", ctx.registry.ring_counts.get("1", 0)),
        ("Ring 2", "Declarative manifests from static analysis", "Bounded scans produce a manifest skeleton, family recipe, tier, blockers and next action.", ctx.registry.ring_counts.get("2", 0)),
        ("Ring 3", "Family recipes and bridge code", "One recipe per family showing how any package in it becomes an OpenMHS endpoint.", ctx.registry.ring_counts.get("3", 0)),
    ]
    max_ring = max(r[3] for r in ring_rows) or 1
    rings = "".join(
        f'<div class="ring-row"><div class="ring-label"><span class="ring-num">{esc(label)}</span><span>{esc(title)}</span></div>'
        f'<div class="ring-bar"><span style="width:{max(2, round(count / max_ring * 100))}%"></span></div>'
        f'<div class="ring-meta"><strong>{fmt_int(count) if count else "0"}</strong><span>{esc(desc)}</span></div></div>'
        for label, title, desc, count in ring_rows
    )
    adoption = f"""
<section class="section" id="adoption">
  <div class="wrap">
    <div class="split-head">
      {section_head("Adoption", "Coverage, stated honestly.",
        "Every indexed package states its ring, evidence state and next action. No repository is silently marked supported, and no claim is made about whether it runs.")}
      <a class="text-link split-link" href="registry/index.html?ring=1">Browse agent-read packages {ICONS['arrow']}</a>
    </div>
    <div class="ring-layout">
      <div class="rings">{rings}</div>
      <aside class="ring-aside">
        <p class="ring-aside-kicker">Registry snapshot</p>
        <div class="mini-stat"><span>{fmt_int(reg.total)}</span><small>packages</small></div>
        <div class="mini-stat"><span>{fmt_int(st['registry_manifests'])}</span><small>with detected manifests</small></div>
        <div class="mini-stat"><span>{fmt_int(st['runtime_tested'])}</span><small>runtime-tested claims</small></div>
        <p class="ring-aside-note">“Detected manifest” is a file fact, not a conformance claim. Runtime verification is deliberately separate from static coverage.</p>
        <a class="text-link" href="spec/00-architecture-part-2.html#13-adoption-path-for-the-corpus">The adoption path {ICONS['arrow']}</a>
      </aside>
    </div>
  </div>
</section>
"""

    status_cards = []
    published = [
        f"{st['docs_real']} specification documents in draft ({st['docs_total']} mapped)",
        f"{st['capabilities']} machine-readable capability classes",
        f"{fmt_int(reg.total)} registry records from a {fmt_int(reg.stats.get('catalog_rows') or reg.total)}-row catalogue",
        "Eight JSON Schemas and two worked examples",
    ]
    if st["families_real"] == st["families"] and st["families"]:
        published.append(f"{st['families']} bridge-family recipe pages")
    if st["sdk_modules"]:
        published.append(f"Reference SDK source: {st['sdk_modules']} modules, {st['sdk_tests']} test files")
    if st["reports_count"]:
        published.append(f"{st['reports_count']} self-issued reference conformance reports (CL2–CL4)")
    status_cards.append(("Published", "good", published))
    in_progress = [
        "Release packaging and independent verification for the reference SDK",
        "Bridge implementations exercised against physical hardware",
        "Registry evidence beyond bounded static scans",
    ]
    if st["families_real"] < st["families"]:
        in_progress.append(f"Family recipes — {st['families_real']} of {st['families']} published")
    if not st["suite_present"]:
        in_progress.append("Executable conformance suite")
    status_cards.append(("In progress", "warn", in_progress))
    status_cards.append(
        ("Not claimed", "bad", [
            "Safety certification or regulatory approval",
            "Runtime-tested status for registry packages",
            "Verified conformance claims by a third party",
            "Fidelity validation for simulated devices",
        ])
    )
    status_html = "".join(
        f'<div class="status-col"><h3><span class="status-marker status-{tone}"></span>{esc(label)}</h3><ul>'
        + "".join(f"<li>{esc(item)}</li>" for item in items)
        + "</ul></div>"
        for label, tone, items in status_cards
    )
    status = f"""
<section class="section section-tint" id="status">
  <div class="wrap">
    {section_head("Status", "A complete draft, with the gaps labelled",
      "This site is the public face of a standard under review. The specification, schemas and registry are real artefacts; the SDK, recipes and conformance suite are being built in the open. We would rather label a gap than paper over it.")}
    <div class="status-panel">{status_html}</div>
    <div class="status-links">
      <a class="text-link" href="about/index.html#status">Read the full status and disclaimers {ICONS['arrow']}</a>
      <a class="text-link" href="governance/index.html">How the standard changes {ICONS['arrow']}</a>
    </div>
  </div>
</section>
"""

    cta = f"""
<section class="cta-band">
  <div class="wrap cta-inner">
    <div>
      <p class="eyebrow">Get started</p>
      <h2>Implement the contract, or inspect it first.</h2>
      <p>Read the core, validate a manifest, connect the SDK, or explore what already exists in the registry.</p>
    </div>
    <div class="cta-actions">
      {btn("Read the core", "spec/core.html", "on-dark", icon=True)}
      {btn("Download schemas", "download/index.html", "ghost-dark")}
    </div>
  </div>
</section>
"""

    body = hero + fixes + surfaces + capabilities_section + dual + conformance + adoption + status + cta
    return page_html(
        path="index.html",
        title=SITE_NAME,
        description=DEFINITION,
        body=body,
        section="home",
        og_type="website",
        body_class="page-home",
    )


# ---------------------------------------------------------------------------
# Pages: specification
# ---------------------------------------------------------------------------


def toc_markup(toc: list[dict], prefix: str = "") -> str:
    if not toc:
        return '<p class="toc-empty">No section headings.</p>'
    out = ['<ol class="toc-list">']
    for item in toc:
        level = item["level"]
        out.append(
            f'<li class="toc-level-{level}"><a href="#{attr(item["id"])}">{esc(item["text"])}</a></li>'
        )
    out.append("</ol>")
    return "".join(out)


def spec_index_page(ctx) -> str:
    p = "../"
    docs = ctx.docs
    st = ctx.status
    groups = [
        ("Core normative documents", docs[:8]),
        ("Transports, hosts and governance", docs[8:11]),
        ("Appendices", docs[11:]),
    ]
    cards = []
    for gtitle, items in groups:
        if not items:
            continue
        inner = []
        for doc in items:
            state_cls = " is-placeholder" if doc.placeholder else ""
            status_tone = "muted" if doc.placeholder else ("info" if doc.status.lower().startswith("generated") else "good")
            inner.append(
                f'<a class="doc-card{state_cls}" href="{doc.stem}.html">'
                f'<div class="doc-card-top"><span class="doc-id">{esc(doc.doc_id)}</span>{badge(doc.status, status_tone)}</div>'
                f"<h3>{esc(doc.title)}</h3><p>{esc(doc.summary)}</p>"
                f'<span class="doc-card-foot">{fmt_int(doc.words)} words <span aria-hidden="true">·</span> {esc(doc.rel)}</span></a>'
            )
        cards.append(f'<section class="doc-group"><h2>{esc(gtitle)}</h2><div class="doc-grid">{"".join(inner)}</div></section>')

    missing_note = ""
    if st["docs_missing"]:
        missing_note = callout(
            "Documents in preparation",
            f"<p>{st['docs_missing']} of {st['docs_total']} mapped documents are not yet present in this build. They appear on this page with an <em>In preparation</em> label and are excluded from search indexing and the sitemap. Their URLs are reserved and will resolve to the real text when published.</p>",
            "warn",
            "book",
        )

    reading_paths = [
        ("Implement an endpoint", ["core.html", "02-wire-protocol.html", "03-capability-registry.html", "04-safety.html", "05-fidelity.html"]),
        ("Write a driver for a repository", ["driver-profile.html", "core.html", "06-adapters.html", "03-capability-registry.html"]),
        ("Write a host or agent harness", ["core.html", "09-host-profile.html", "01-conformance.html", "02-wire-protocol.html"]),
        ("Review safety claims", ["04-safety.html", "05-fidelity.html", "01-conformance.html"]),
    ]
    by_stem = {d.stem: d for d in docs}
    path_cards = []
    for label, stems in reading_paths:
        links = []
        for stem in stems:
            doc = by_stem.get(stem)
            if not doc:
                continue
            state = " (in preparation)" if doc.placeholder else ""
            links.append(f'<li><a href="{doc.stem}.html">{esc(doc.doc_id)} · {esc(doc.title)}</a><span>{esc(state)}</span></li>')
        path_cards.append(f'<div class="path-card"><h3>{esc(label)}</h3><ol class="path-list">{"".join(links)}</ol></div>')

    body = f"""
<div class="wrap">
  {breadcrumbs_html(p, [("Specification", None)])}
  <header class="page-hero page-hero-docs">
    <p class="eyebrow">{SITE_NAME} {SPEC_VERSION} · specification set</p>
    <h1>The specification</h1>
    <p class="page-lead">The normative definition of OpenMHS: the contract plane, its wire protocol, the capability vocabulary, safety and fidelity semantics, adapters, the registry and executable conformance.</p>
    <div class="hero-actions">
      {btn("Start with the core", "core.html", "primary", icon=True)}
      {btn("Download the schema bundle", "../download/index.html", "secondary")}
    </div>
    <div class="doc-hero-stats">
      <span><strong>{st['docs_real']}</strong> published</span>
      <span><strong>{st['docs_missing']}</strong> in preparation</span>
      <span><strong>{fmt_int(sum(d.words for d in docs))}</strong> words</span>
      <span><strong>1.0</strong> protocol version</span>
    </div>
    {missing_note}
  </header>
  <div class="spec-layout">
    <div class="spec-main">
      {''.join(cards)}
      <section class="spec-section">
        {section_head("Reading paths", "Read by role", "The architecture document fixes the model. Every other document refines one section and must not contradict it.")}
        <div class="path-grid">{''.join(path_cards)}</div>
      </section>
      <section class="spec-section">
        {section_head("Conventions", "How to read the normative text", "")}
        <div class="convention-grid">
          <div><h3>Requirement language</h3><p>MUST, MUST NOT, REQUIRED, SHOULD, SHOULD NOT, MAY and OPTIONAL are interpreted as described in RFC 2119 and RFC 8174.</p></div>
          <div><h3>Requirement identifiers</h3><p>Requirements are numbered <code>AREA-NNN</code> (for example <code>SAFE-012</code>). The same identifier is the conformance test case id that checks the requirement.</p></div>
          <div><h3>Precedence</h3><p>When two documents disagree the higher one wins: the schemas and registries, then the core, then the driver profile, then chapters 01 to 10, then the appendices. The architecture overview is informative and wins nothing. A conflict is a defect, fixed by an erratum to the lower document.</p></div>
          <div><h3>Versioning</h3><p>The protocol is <code>1.0</code>. Capability classes carry their own MAJOR version. Registry records validate against versioned JSON Schemas.</p></div>
        </div>
      </section>
    </div>
    <aside class="spec-aside">
      <div class="aside-card">
        <h2>Machine-readable</h2>
        <ul class="aside-links">
          <li><a href="capabilities.json">capabilities.json <span>{fmt_bytes((MHS/'spec'/'capabilities.json').stat().st_size) if (MHS/'spec'/'capabilities.json').is_file() else ''}</span></a></li>
          <li><a href="../schema/device.schema.json">device.schema.json</a></li>
          <li><a href="../schema/adapter.schema.json">adapter.schema.json</a></li>
          <li><a href="../download/index.html">Schema bundle (.zip)</a></li>
        </ul>
      </div>
      <div class="aside-card aside-status">
        <h2>Status</h2>
        <p><strong>{DRAFT_LABEL}.</strong> This is not an approved international standard. Conformance is not safety certification.</p>
        <a class="text-link" href="../about/index.html#status">Status and disclaimers {ICONS['arrow']}</a>
      </div>
    </aside>
  </div>
</div>
"""
    return page_html(
        path="spec/index.html",
        title="Specification",
        description=f"The OpenMHS {SPEC_VERSION} document set: architecture, wire protocol, capability registry, safety, fidelity, adapters, registry, transports, host profile and governance.",
        body=body,
        section="spec",
        breadcrumbs=[("Specification", "spec/index.html")],
        og_type="article",
    )


def placeholder_body(doc: Doc, prefix: str) -> str:
    current_attr = ' aria-current="page"'
    doc_links = "".join(
        f'<li><a href="{d.stem}.html"{current_attr if d.rel == doc.rel else ""}>'
        f"{esc(d.doc_id)} · {esc(d.title)}</a></li>"
        for d in ctx_placeholder_docs
    )
    return f"""
<div class="doc-layout wrap">
  <aside class="doc-sidebar">
    <nav class="doc-nav" aria-label="Specification documents">
      <p class="side-title">Specification</p>
      <ol>{doc_links}</ol>
    </nav>
  </aside>
  <article class="doc-article">
    <p class="eyebrow">{esc(doc.doc_id)} · in preparation</p>
    <h1>{esc(doc.title)}</h1>
    <div class="doc-status-line">{badge("In preparation", "muted")}{badge("Not normative yet", "muted")}</div>
    {callout("This document is not published in this build", f"<p><strong>{esc(doc.rel)}</strong> is part of the OpenMHS document map but was absent from the source tree at build time. This page reserves the URL so links from published documents resolve. Nothing on this page is normative.</p>", "warn", "book")}
    <p class="lead">Expected scope: {esc(doc.summary)}</p>
    <p>The published core is <a href="core.html">OpenMHS Core</a>. It fixes the object model, the three primitives, limits, the safety duties of the endpoint, receipts and the control surfaces; this document extends it.</p>
    <p>Read the <a href="../conformance/index.html">conformance ladder</a>, browse the <a href="../capabilities/index.html">capability catalogue</a>, or return to the <a href="index.html">specification index</a>.</p>
    <nav class="pager" aria-label="Document navigation"><a href="index.html">← All specification documents</a></nav>
  </article>
</div>
"""


ctx_placeholder_docs: list[Doc] = []


def spec_doc_page(ctx, part: DocPart, index: int, all_parts: list[DocPart]) -> str:
    doc = part.doc
    prefix = "../"
    if doc.placeholder:
        global ctx_placeholder_docs
        ctx_placeholder_docs = ctx.docs
        body = placeholder_body(doc, prefix)
        return page_html(
            path=doc.output,
            title=doc.title,
            description=f"{doc.doc_id} — {doc.title} (in preparation). {doc.summary}",
            body=body,
            section="spec",
            breadcrumbs=[("Specification", "spec/index.html"), (doc.doc_id, None)],
            og_type="article",
            noindex=True,
        )

    renderer = MarkdownRenderer(ctx.known, f"MHS/spec/{doc.rel}", part.output)
    rendered, toc = renderer.render(part.body, skip_first_h1=True)
    doc.html = rendered
    doc.toc = toc
    is_generated = doc.status.lower().startswith("generated") or doc.doc_id == "MHS-A"
    badge_tone = "info" if is_generated else "good"
    status_label = "Generated" if is_generated else ("Normative" if doc.normative else "Informative")
    minutes = max(1, round(part.words / 220))
    nav_items = []
    for d in ctx.docs:
        current = ' aria-current="page"' if d.rel == doc.rel and part.number == 1 else ""
        cls = " is-placeholder" if d.placeholder else ""
        active = " is-active" if d.rel == doc.rel else ""
        sub = ""
        if d.rel == doc.rel and part.total > 1:
            sub_links = []
            for p in all_parts:
                if p.doc.rel != doc.rel:
                    continue
                cur = ' aria-current="page"' if p.number == part.number else ""
                sub_links.append(f'<li><a href="{posixpath.basename(p.output)}"{cur}>Part {p.number}</a></li>')
            sub = f'<ol class="doc-parts">{"".join(sub_links)}</ol>'
        nav_items.append(
            f'<li><a class="{cls.strip()}{active}" href="{d.stem}.html"{current}>'
            f'<span class="nav-doc-id">{esc(d.doc_id)}</span><span>{esc(d.title)}</span></a>{sub}</li>'
        )

    pager_parts = []
    prev_part = all_parts[index - 1] if index > 0 else None
    next_part = all_parts[index + 1] if index + 1 < len(all_parts) else None
    if prev_part:
        same_doc = prev_part.doc.rel == doc.rel
        label = "Previous part" if same_doc else "Previous"
        strong = (
            f"{prev_part.doc.doc_id} · Part {prev_part.number}"
            if same_doc
            else f"{prev_part.doc.doc_id} · {prev_part.doc.title}"
        )
        pager_parts.append(
            f'<a class="pager-prev" href="{posixpath.basename(prev_part.output)}"><span>{label}</span><strong>{esc(strong)}</strong></a>'
        )
    if next_part:
        same_doc = next_part.doc.rel == doc.rel
        label = "Next part" if same_doc else "Next"
        strong = (
            f"{next_part.doc.doc_id} · Part {next_part.number}"
            if same_doc
            else f"{next_part.doc.doc_id} · {next_part.doc.title}"
        )
        pager_parts.append(
            f'<a class="pager-next" href="{posixpath.basename(next_part.output)}"><span>{label}</span><strong>{esc(strong)}</strong></a>'
        )
    pager = f'<nav class="pager" aria-label="Document navigation">{"".join(pager_parts)}</nav>' if pager_parts else ""

    part_nav = ""
    if part.total > 1:
        links = []
        for p in all_parts:
            if p.doc.rel != doc.rel:
                continue
            if p.number == part.number:
                links.append(f'<span class="part-link is-current" aria-current="page">Part {p.number} <small>{esc(p.range_label)}</small></span>')
            else:
                links.append(f'<a class="part-link" href="{posixpath.basename(p.output)}">Part {p.number} <small>{esc(p.range_label)}</small></a>')
        part_nav = (
            '<nav class="part-nav" aria-label="Document parts"><span class="part-nav-label">This document is published in '
            f'{part.total} parts</span><div class="part-links">{"".join(links)}</div></nav>'
        )

    aside_toc = ""
    if toc:
        aside_toc = f'<aside class="doc-toc" aria-label="On this page"><p class="side-title">On this page</p>{toc_markup(toc)}</aside>'
    mobile_toc = ""
    if toc:
        mobile_toc = f'<details class="toc-mobile"><summary>On this page <span>{len(toc)} sections</span></summary>{toc_markup(toc)}</details>'

    continuation = ""
    if part.number < part.total:
        following = next((p for p in all_parts if p.doc.rel == doc.rel and p.number == part.number + 1), None)
        if following:
            continuation = (
                '<aside class="part-continue"><p class="part-continue-kicker">Continued</p>'
                f'<p>Sections 7.5–12 of {esc(doc.doc_id)} continue in <a href="{posixpath.basename(following.output)}">Part {following.number}</a> — fluid, sample, imaging, optics, measurement, thermal, actuation, compute, process and device classes, followed by extensions, deprecation, generated artefacts and the informative guidance.</p>'
                f'<a class="btn btn-secondary btn-sm" href="{posixpath.basename(following.output)}">Continue to Part {following.number} {ICONS["arrow"]}</a></aside>'
            )
    part_context = ""
    if part.number > 1:
        first = next((p for p in all_parts if p.doc.rel == doc.rel and p.number == 1), None)
        first_link = f'<a href="{posixpath.basename(first.output)}">Part 1</a>' if first else "Part 1"
        part_context = (
            f'<p class="part-context">Part {part.number} of {part.total} · {esc(doc.doc_id)} continues from {first_link}. '
            'The document is split only for page size; the requirements are continuous.</p>'
        )

    missing = ""
    if renderer.pending and doc.rel == "00-architecture.md":
        missing = callout(
            "Links to unpublished documents",
            f"<p>{len(renderer.pending)} cross-reference(s) point to documents or files not present in this build. They are rendered as plain text rather than broken links; each will become a link when the target is published.</p>",
            "note",
            "link",
        )

    part_badge = badge(f"Part {part.number} of {part.total}", "muted") if part.total > 1 else ""
    title_suffix = f" — part {part.number}" if part.number > 1 else ""
    body = f"""
<div class="doc-layout wrap">
  <aside class="doc-sidebar">
    <nav class="doc-nav" aria-label="Specification documents">
      <p class="side-title">Specification <a href="index.html">All docs</a></p>
      <ol>{''.join(nav_items)}</ol>
    </nav>
  </aside>
  <article class="doc-article">
    <nav class="breadcrumb" aria-label="Breadcrumb"><ol><li><a href="{prefix}index.html">Home</a></li><li><a href="index.html">Specification</a></li><li aria-current="page">{esc(doc.doc_id)}{f' · part {part.number}' if part.number > 1 else ''}</li></ol></nav>
    {part_nav}
    <header class="doc-header">
      <div class="doc-badges">{badge(doc.doc_id, "id")}{badge(status_label, badge_tone)}{part_badge}</div>
      <h1>{esc(doc.title)}</h1>
      <div class="doc-status-line"><span>{esc(doc.status)}</span>{f'<span>{esc(part.range_label)}</span>' if part.range_label else ''}<span>{minutes} min read</span><span>{fmt_int(part.words)} words</span></div>
    </header>
    {part_context}
    {mobile_toc}
    {missing}
    <div class="doc-body">{rendered}</div>
    {continuation}
    {pager}
  </article>
  {aside_toc}
</div>
"""
    return page_html(
        path=part.output,
        title=f"{doc.doc_id} · {doc.title}{title_suffix}",
        description=doc.lead[:240] if doc.lead else doc.summary,
        body=body,
        section="spec",
        breadcrumbs=[("Specification", "spec/index.html"), (f"{doc.doc_id}{f' · part {part.number}' if part.number > 1 else ''}", None)],
        og_type="article",
        structured_data={
            "@context": "https://schema.org",
            "@type": "TechArticle",
            "identifier": doc.doc_id,
            "version": MHS_VERSION,
            "proficiencyLevel": "Expert",
        },
    )


# ---------------------------------------------------------------------------
# Pages: registry explorer
# ---------------------------------------------------------------------------


def mode_chips(modes: list[str]) -> str:
    return "".join(
        f'<span class="mode-chip mode-{attr(m)}">{esc(m)}</span>' for m in modes
    ) or '<span class="mode-chip mode-none">unstated</span>'


def tier_badge(tier: str) -> str:
    tone = {"A": "good", "B": "info", "C": "warn", "D": "muted", "X": "bad"}.get(tier, "muted")
    return badge(f"Tier {tier}", tone)


def evidence_label(state: str) -> str:
    return {
        "runtime_tested": "Runtime tested",
        "agent_read": "Agent read",
        "static_scan": "Static scan",
        "declared": "Declared",
        "catalog": "Catalogue only",
    }.get(state, state.replace("_", " ").title())


def registry_explorer_page(ctx) -> str:
    reg = ctx.registry
    p = "../"
    synthetic = callout(
        "Synthetic registry",
        "<p>The real <code>MHS/registry/index.json</code> was not present at build time. This explorer is populated with a deterministic synthetic index so the interface remains testable; every synthetic record is labelled and no upstream links are fabricated.</p>",
        "warn",
        "package",
    ) if reg.synthetic else ""
    family_opts = "".join(
        f'<option value="{attr(name)}">{esc(name)} ({fmt_int(count)})</option>'
        for name, count in reg.family_counts.items()
    )
    license_opts = "".join(
        f'<option value="{attr(name)}">{esc(name)} ({fmt_int(count)})</option>'
        for name, count in reg.license_counts.items()
    )
    tier_opts = "".join(
        f'<option value="{attr(t)}">Tier {esc(t)} ({fmt_int(reg.tier_counts.get(t, 0))})</option>'
        for t in TIERS
        if reg.tier_counts.get(t)
    )
    ring_opts = "".join(
        f'<option value="{attr(r)}">Ring {esc(r)} ({fmt_int(reg.ring_counts.get(r, 0))})</option>'
        for r in RINGS
        if reg.ring_counts.get(r)
    )
    track_opts = "".join(
        f'<option value="{attr(value)}">{esc(label)} ({fmt_int(reg.track_counts.get(value, 0))})</option>'
        for value, label in TRACKS
        if reg.track_counts.get(value)
    )
    mode_opts = "".join(
        f'<option value="{attr(mode)}">{esc(mode)} ({fmt_int(count)})</option>'
        for mode, count in reg.mode_counts.items()
    )
    family_quick = "".join(
        f'<a class="family-chip" href="index.html?family={attr(name)}">{esc(name)} <span>{fmt_int(count)}</span></a>'
        for name, count in list(reg.family_counts.items())[:10]
    )
    body = f"""
<div class="wrap page-hero page-hero-registry">
  {breadcrumbs_html(p, [("Registry", None)])}
  <div class="registry-hero-grid">
    <div>
      <p class="eyebrow">Registry · {esc(human_date(reg.generated_at))}</p>
      <h1>The OpenMHS registry</h1>
      <p class="page-lead">A static, searchable index of packages that can become OpenMHS endpoints — with their bridge family, integration tier, adoption ring, evidence state and next action. A catalogue, not a control plane.</p>
    </div>
    <div class="registry-hero-stats">
      <div><strong>{fmt_int(reg.total)}</strong><span>records</span></div>
      <div><strong>{fmt_int(reg.stats.get('manifests') or 0)}</strong><span>manifests detected</span></div>
      <div><strong>{fmt_int(reg.stats.get('capability_claims') or 0)}</strong><span>capability claims</span></div>
      <div><strong>{len(reg.family_counts)}</strong><span>families</span></div>
    </div>
  </div>
  {synthetic}
  <div class="family-quick" aria-label="Browse by family">{family_quick}<a class="family-chip family-chip-all" href="index.html">All {fmt_int(reg.total)}</a></div>
</div>

<div class="wrap registry-layout">
  <form class="filter-panel" id="registry-filters" aria-label="Filter registry records">
    <div class="filter-head">
      <h2>Filters</h2>
      <button type="reset" class="link-btn" id="registry-reset">Clear all</button>
    </div>
    <div class="filter-field">
      <label for="registry-q">Search records</label>
      <div class="search-input-wrap">
        {ICONS['search']}
        <input id="registry-q" name="q" type="search" placeholder="capability, package, interface…" autocomplete="off" spellcheck="false">
      </div>
      <p class="field-hint">Searches names, descriptions, capabilities, interfaces and licences.</p>
    </div>
    <details class="filter-group" open>
      <summary>Refine <span class="filter-count" id="filter-count"></span></summary>
      <div class="filter-field">
        <label for="registry-track">Track</label>
        <select id="registry-track" name="track"><option value="">All tracks</option>{track_opts}</select>
      </div>
      <div class="filter-field">
        <label for="registry-family">Bridge family</label>
        <select id="registry-family" name="family"><option value="">All families</option>{family_opts}</select>
      </div>
      <div class="filter-field">
        <label for="registry-tier">Integration tier</label>
        <select id="registry-tier" name="tier"><option value="">All tiers</option>{tier_opts}</select>
      </div>
      <div class="filter-field">
        <label for="registry-ring">Adoption ring</label>
        <select id="registry-ring" name="ring"><option value="">All rings</option>{ring_opts}</select>
      </div>
      <div class="filter-field">
        <label for="registry-mode">Mode</label>
        <select id="registry-mode" name="mode"><option value="">All modes</option>{mode_opts}</select>
      </div>
      <div class="filter-field">
        <label for="registry-license">Licence</label>
        <select id="registry-license" name="license"><option value="">All licences</option>{license_opts}</select>
      </div>
    </details>
    <div class="filter-field">
      <label for="registry-sort">Sort by</label>
      <select id="registry-sort" name="sort">
        <option value="relevance">Relevance</option>
        <option value="stars">Stars</option>
        <option value="name">Name</option>
        <option value="tier">Tier</option>
        <option value="ring">Ring</option>
      </select>
    </div>
    <p class="filter-note"><strong>Evidence is not support.</strong> Ring and evidence describe how a record was produced, not whether the package runs or conforms.</p>
  </form>

  <section class="registry-results" aria-labelledby="results-heading">
    <div class="results-toolbar">
      <h2 id="results-heading" class="sr-only">Search results</h2>
      <p class="results-count" id="registry-count" aria-live="polite">Loading registry…</p>
      <div class="active-filters" id="registry-active"></div>
    </div>
    <div class="registry-loading" id="registry-loading">
      <span class="spinner" aria-hidden="true"></span>
      <p>Loading {fmt_int(reg.total)} records…</p>
    </div>
    <ol class="result-list" id="registry-results"></ol>
    <div class="empty-state" id="registry-empty" hidden>
      <h2>No records match those filters</h2>
      <p>Try a broader search or clear the filters. Every record is also addressable directly by its package page.</p>
      <button type="button" class="btn btn-secondary" id="registry-empty-reset">Clear filters</button>
    </div>
    <nav class="pagination" id="registry-pagination" aria-label="Registry pages" hidden></nav>
    <noscript>
      <div class="callout callout-warn"><div><p class="callout-title">JavaScript is required for the interactive explorer</p>
      <div class="callout-body"><p>The full index is available as <a href="../download/index.html">a JSON download</a>, and every record has a static detail page linked from the sitemap. Enable JavaScript for instant filtering and deep-linkable queries.</p></div></div></div>
    </noscript>
  </section>
</div>
<div class="wrap registry-notes">
  <div class="notes-grid">
    <div><h2>How records are made</h2><p>Catalogue fields, bounded static scanning and — for a smaller set — an agent reading the actual source. The registry preserves the difference instead of flattening it into “supported”.</p><a class="text-link" href="../spec/07-registry.html">Registry specification {ICONS['arrow']}</a></div>
    <div><h2>Trust</h2><p>All records are currently unsigned. A trust level is displayed next to every capability; an unsigned claim must never be treated as verified. No record here is a conformance certificate.</p><a class="text-link" href="../spec/07-registry.html">Trust and signing {ICONS['arrow']}</a></div>
    <div><h2>Use the data</h2><p>The explorer is a static projection of the same JSON Lines records. Download the registry bundle, mirror it, or query it offline. No account, no API key, no tracking.</p><a class="text-link" href="../download/index.html">Registry bundle {ICONS['arrow']}</a></div>
  </div>
</div>
<script defer src="../assets/registry-data.js"></script>
<script defer src="../assets/registry.js"></script>
"""
    return page_html(
        path="registry/index.html",
        title="Registry explorer",
        description=f"Explore {fmt_int(reg.total)} packages that can become OpenMHS endpoints: bridge family, integration tier, adoption ring, mode, licence and evidence state.",
        body=body,
        section="registry",
        breadcrumbs=[("Registry", "registry/index.html")],
        og_type="website",
        extra_head='<meta name="robots" content="index,follow">',
    )


# ---------------------------------------------------------------------------
# Pages: registry detail
# ---------------------------------------------------------------------------


def capability_link(prefix: str, cap_id: str, known_caps: dict) -> str:
    if cap_id in known_caps:
        return f'<a class="cap-chip" href="{prefix}capabilities/index.html#{attr(cap_id)}">{esc(cap_id)}</a>'
    return f'<span class="cap-chip cap-chip-unknown" title="Not part of the OpenMHS core catalogue">{esc(cap_id)}</span>'


def adapter_sketch(rec: dict) -> str:
    adapter = rec.get("adapter") or {}
    family = rec.get("family") or "other"
    modes = rec.get("modes") or ["simulated"]
    mode = "hardware" if "hardware" in modes and "simulated" not in modes else modes[0]
    profile = "MHS-Device" if mode == "hardware" else "MHS-Sim"
    caps = rec.get("capabilities_offered") or []
    device_slug = re.sub(r"[^a-z0-9]+", "-", f"{family}-{rec['repo']}".lower()).strip("-")
    sketch = {
        "mhs_adapter": "1.0",
        "adapter_id": f"registry.{rec['package_id']}",
        "family": family,
        "source": {
            "repo": rec.get("repo_url") or "(no upstream recorded)",
            "license": rec.get("license") or "unknown",
        },
        "runtime": {
            "kind": "python" if "Python" in (rec.get("languages") or []) else "process",
            "entry": "record the native module, class or launch command before promoting this adapter",
        },
        "devices": [
            {
                "device_id": f"mhs://localhost/{device_slug}",
                "mode": mode,
                "capabilities": caps[:8] or ["cap.device.describe.v1"],
            }
        ],
        "conformance_target": {"profile": profile, "level": "CL0"},
        "evidence": {
            "state": rec.get("evidence_state") or "declared",
            "source": "generated from registry record; not an attested manifest",
        },
    }
    if mode in ("simulated", "hybrid"):
        sketch["devices"][0]["fidelity"] = {
            "engine": "custom",
            "fidelity_level": "F0",
            "determinism": {"kind": "seeded"},
            "timestep_ms": 1.0,
            "realtime_factor": 0.0,
            "reset": "full",
            "snapshot_restore": False,
            "gaps": ["declare the deployed model's known gaps before claiming F2 or above"],
        }
    return json.dumps(sketch, indent=2, ensure_ascii=False)


def registry_detail_page(ctx, rec: dict, index: int) -> str:
    p = "../../"
    reg = ctx.registry
    known_caps = ctx.caps.by_id
    family_slug = rec["family_slug"]
    family_page = f"../../families/{family_slug}.html"
    caps = rec["capabilities_offered"]
    shown_caps = caps[:28]
    more_caps = len(caps) - len(shown_caps)
    caps_html = "".join(capability_link(p, c, known_caps) for c in shown_caps)
    if more_caps > 0:
        caps_html += f'<span class="cap-more">+{more_caps} more in the record</span>'
    if not caps:
        caps_html = '<p class="muted">No capability classes declared in this record.</p>'
    interfaces_html = pill_list(rec["interfaces"][:16], "pill") or '<span class="muted">Not detected</span>'
    languages_html = pill_list(rec["languages"][:12], "pill pill-quiet") or '<span class="muted">Unknown</span>'
    modes_html = mode_chips(rec["modes"])
    adapter = rec.get("adapter") or {}
    bridge = adapter.get("bridge") or rec["family"]
    adapter_state = rec["adapter_state"]
    integration = rec.get("integration") or {}
    blockers = integration.get("blockers") or []
    if isinstance(blockers, str):
        blockers = [blockers]
    blockers_html = (
        "<ul class=\"blocker-list\">" + "".join(f"<li>{esc(b)}</li>" for b in blockers) + "</ul>"
        if blockers
        else '<p class="muted">No catalog blocker recorded. That is not a guarantee that integration is easy.</p>'
    )
    next_action = rec.get("next_action") or "Inspect the repository and record a precise entry point, then write the adapter manifest."
    effort = integration.get("effort") or rec.get("effort") or "—"
    estimated = integration.get("estimated_days")
    scenario = integration.get("scenario_required")
    hardware_free = rec.get("hardware_free")
    recipe = integration.get("recipe") or f"families/{family_slug}.md"
    upstream = rec.get("repo_url") or ""
    upstream_link = (
        f'<a class="btn btn-secondary btn-sm" href="{attr(upstream)}" rel="noopener">Upstream repository {ICONS["external"]}</a>'
        if upstream and not reg.synthetic
        else '<span class="muted">No upstream URL recorded in this synthetic record.</span>'
    )
    manifest_ref = adapter.get("manifest_ref") or adapter.get("manifest")
    manifest_exists = bool(manifest_ref and (MHS / "registry" / manifest_ref).is_file())
    if manifest_exists:
        manifest_label = f"Adapter manifest at <code>{esc(manifest_ref)}</code>"
        try:
            manifest_text = read_text(MHS / "registry" / manifest_ref)
            manifest_data = json.loads(manifest_text)
            manifest_text = json.dumps(manifest_data, indent=2, ensure_ascii=False)
        except Exception:
            pass
        if len(manifest_text) > 6000:
            manifest_text = manifest_text[:6000] + "\n… truncated in this view"
        manifest_href = p + "registry/" + attr(manifest_ref)
        manifest_link = (
            f'<a class="text-link" href="{manifest_href}">Open the manifest JSON {ICONS["arrow"]}</a>'
            if manifest_ref else ""
        )
        manifest_block = (
            f'<p class="manifest-source">Published manifest detected at <code>{esc(manifest_ref)}</code>. '
            f'{manifest_link}'
            f' This is still an unsigned registry record until a conformance claim is attached.</p>'
            f"{codeblock(manifest_text, 'json', 'mhs-adapter.json')}"
        )
        manifest_state = "published"
    else:
        manifest_block = (
            f'<p class="manifest-source">No attested <code>mhs-adapter.json</code> is present in this build. The sketch below is <strong>generated from the registry fields</strong> to show the shape of the mapping; it is not a manifest, not validated, and must not be treated as one.</p>'
            f"{codeblock(adapter_sketch(rec), 'json', 'declared mapping sketch')}"
        )
        manifest_state = "sketch"
    prev_rec = reg.records[index - 1] if index > 0 else None
    next_rec = reg.records[index + 1] if index + 1 < len(reg.records) else None
    neighbours = []
    if prev_rec:
        neighbours.append(
            f'<a class="pager-prev" href="{prev_rec["slug"]}.html"><span>Previous package</span><strong>{esc(prev_rec["title"])}</strong></a>'
        )
    if next_rec:
        neighbours.append(
            f'<a class="pager-next" href="{next_rec["slug"]}.html"><span>Next package</span><strong>{esc(next_rec["title"])}</strong></a>'
        )
    neighbours_html = f'<nav class="pager" aria-label="Package navigation">{"".join(neighbours)}</nav>' if neighbours else ""
    notes = rec.get("evidence_notes") or "No evidence note recorded."
    provenance = rec.get("provenance_refs") or []
    prov_html = (
        "<ul class=\"plain-list\">" + "".join(f"<li><code>{esc(ref)}</code></li>" for ref in provenance) + "</ul>"
        if provenance
        else '<p class="muted">No provenance references recorded.</p>'
    )
    local = rec.get("local_path") or "—"
    facts = [
        ("Package id", f"<code>{esc(rec['package_id'])}</code>"),
        ("Track", esc(rec["track"].title())),
        ("Bridge family", f'<a href="{family_page}">{esc(rec["family"])}</a>'),
        ("Tier / ring", f"{esc(rec['tier'])} / {esc(rec['ring'])}"),
        ("Modes", modes_html),
        ("Licence", esc(rec["license"])),
        ("Stars", fmt_int(rec["stars"])),
        ("Adapter state", esc(adapter_state)),
        ("Evidence", esc(evidence_label(rec["evidence_state"]))),
        ("Trust", esc(rec["trust"])),
        ("Effort", esc(str(effort))),
        ("Local path", f"<code>{esc(local)}</code>"),
    ]
    if estimated is not None:
        facts.append(("Estimate", f"{esc(estimated)} dev-days"))
    if scenario is not None:
        facts.append(("Scenario", "required" if scenario else "not required"))
    fact_html = "".join(
        f'<div class="fact"><dt>{esc(label)}</dt><dd>{value}</dd></div>' for label, value in facts
    )
    body = f"""
<div class="wrap page-hero page-hero-package">
  {breadcrumbs_html(p, [("Registry", "registry/index.html"), (rec['title'], None)])}
  <div class="package-hero-grid">
    <div>
      <p class="eyebrow">{esc(rec['track'].title())} · {esc(rec['family'])} · ring {esc(rec['ring'])}</p>
      <h1>{esc(rec['title'])}</h1>
      <p class="page-lead">{esc(rec['description']) or 'No description recorded.'}</p>
      <div class="package-badges">{tier_badge(rec['tier'])}{badge(f"Ring {rec['ring']}", "info")}{badge(evidence_label(rec['evidence_state']), "muted")}{badge(f"Adapter: {adapter_state}", "muted")}{badge(rec['license'], "muted")}</div>
      <div class="package-actions">{upstream_link}<a class="btn btn-secondary btn-sm" href="../index.html?family={attr(rec['family'])}">Find similar packages</a></div>
    </div>
    <aside class="package-summary" aria-label="Package summary">
      <p class="package-summary-kicker">At a glance</p>
      <dl>{fact_html}</dl>
    </aside>
  </div>
</div>

<div class="wrap package-layout">
  <article class="package-main">
    <section class="package-section" id="capabilities">
      <h2>Capability surface</h2>
      <p class="section-note">Classes this package can plausibly bind, derived from its catalogue role, interfaces and bounded static scan. A binding is not a claim that the capability is implemented or conformance-tested.</p>
      <div class="cap-chip-list">{caps_html}</div>
      <h3>Interfaces detected</h3>
      <div class="pill-list">{interfaces_html}</div>
      <h3>Languages</h3>
      <div class="pill-list">{languages_html}</div>
    </section>

    <section class="package-section" id="integration">
      <h2>Integration plan</h2>
      <div class="next-action">
        <p class="next-action-kicker">Next action</p>
        <p>{esc(next_action)}</p>
      </div>
      <ol class="steps">
        <li><strong>Read the family recipe.</strong> <a href="{family_page}">{esc(family_slug)} recipe</a> shows the bridge, launch shape, unit handling and typical mapping for this family.</li>
        <li><strong>Pin the native entry point.</strong> Record module/class/function or process invocation; do not rely on undocumented internals. If you must, set <code>stability: fragile</code>.</li>
        <li><strong>Write the adapter manifest.</strong> Validate <code>mhs-adapter.json</code> against <a href="{p}schema/adapter.schema.json">adapter.schema.json</a>; declare units, safety, mode and fidelity gaps honestly.</li>
        <li><strong>Run the bridge and the suite.</strong> Start an endpoint, reach CL0, then run the conformance suite for the declared profile and level.</li>
        <li><strong>Publish evidence.</strong> Attach the report digest to a registry claim. Until then, the record stays <em>{esc(evidence_label(rec['evidence_state'])).lower()}</em>.</li>
      </ol>
      <h3>Blockers</h3>
      {blockers_html}
      <p class="recipe-ref">Registry recipe path: <code>{esc(recipe)}</code> · Profile target: <strong>{esc('MHS-Device' if rec['modes'] == ['hardware'] else 'MHS-Sim')}</strong> · Effort: <strong>{esc(str(effort))}</strong></p>
    </section>

    <section class="package-section" id="adapter">
      <h2>Adapter mapping</h2>
      <div class="manifest-state">{badge('Published manifest' if manifest_exists else 'Generated sketch', 'info' if manifest_exists else 'warn')}</div>
      {manifest_block}
    </section>

    <section class="package-section" id="evidence">
      <h2>Evidence and trust</h2>
      <div class="evidence-grid">
        <div><dt>Evidence state</dt><dd>{esc(evidence_label(rec['evidence_state']))}</dd></div>
        <div><dt>Read by</dt><dd>{esc(rec['evidence_state'])}</dd></div>
        <div><dt>Files read</dt><dd>{esc(rec.get('evidence_files') or '—')}</dd></div>
        <div><dt>Manifest detected</dt><dd>{'yes' if rec.get('has_manifest') else 'no'}</dd></div>
        <div><dt>Trust</dt><dd>{esc(rec['trust'])}</dd></div>
        <div><dt>Generated</dt><dd>{esc(human_date(reg.generated_at))}</dd></div>
      </div>
      <p>{esc(notes)}</p>
      <h3>Provenance references</h3>
      {prov_html}
      {callout("What this record does not mean", "<p>A registry record is a catalogue entry, not a conformance claim, a safety assessment or a statement that the package runs. Runtime-tested and conformance-verified status require separate evidence with a report digest.</p>", "note", "shield")}
    </section>

    {neighbours_html}
  </article>
  <aside class="package-aside">
    <div class="aside-card">
      <h2>Identity</h2>
      <dl class="aside-facts">
        <dt>Owner</dt><dd>{esc(rec['owner'])}</dd>
        <dt>Repository</dt><dd>{esc(rec['repo'])}</dd>
        <dt>Package</dt><dd><code>{esc(rec['package_id'])}</code></dd>
        <dt>Upstream</dt><dd>{f'<a href="{attr(upstream)}" rel="noopener">GitHub {ICONS["external"]}</a>' if upstream and not reg.synthetic else '<span class="muted">not recorded</span>'}</dd>
        <dt>Local path</dt><dd><code>{esc(local)}</code></dd>
        <dt>Last commit</dt><dd>{esc(human_date(rec.get('last_commit_at') or '—'))}</dd>
      </dl>
    </div>
    <div class="aside-card">
      <h2>Related</h2>
      <ul class="aside-links">
        <li><a href="{family_page}">{esc(ctx.family_titles.get(rec['family'], rec['family']))}</a></li>
        <li><a href="../index.html?family={attr(rec['family'])}">All {esc(rec['family'])} packages</a></li>
        <li><a href="../index.html?track={attr(rec['track'])}">All {esc(rec['track'])} records</a></li>
        <li><a href="../index.html?tier={attr(rec['tier'])}">Tier {esc(rec['tier'])} packages</a></li>
      </ul>
    </div>
    <div class="aside-card aside-contribute">
      <h2>Improve this record</h2>
      <p>Records move through <code>declared → packaged → runnable → conformant → certified</code> only when evidence is attached.</p>
      <a class="text-link" href="{p}spec/06-adapters.html">Adapter rules {ICONS['arrow']}</a>
    </div>
  </aside>
</div>
"""
    return page_html(
        path=f"registry/repo/{rec['slug']}.html",
        title=f"{rec['title']} — registry",
        description=(rec["description"] or f"Registry record for {rec['title']}.")[:220],
        body=body,
        section="registry",
        breadcrumbs=[("Registry", "registry/index.html"), (rec["title"], None)],
        og_type="article",
    )


# ---------------------------------------------------------------------------
# Pages: capabilities
# ---------------------------------------------------------------------------

DOMAIN_LABELS = {
    "world": ("World", "Simulated worlds, episodes, snapshots and seeding."),
    "motion": ("Motion", "Joints, Cartesian poses, mobile bases, stops and homing."),
    "manipulation": ("Manipulation", "Grasp, release, pick and place objects."),
    "sensing": ("Sensing", "Scalar sensors, images, point clouds, force/torque and IMUs."),
    "fluid": ("Fluid", "Pipetting, dispensing, transfer, mixing, washing and level sensing."),
    "sample": ("Sample", "Moving, incubating, centrifuging, sealing and storing labware."),
    "imaging": ("Imaging", "Microscope capture, focus and illumination."),
    "optics": ("Optics", "Optical power, shutters and alignment."),
    "measure": ("Measurement", "Electrical, optical, thermal and flow quantities."),
    "thermal": ("Thermal", "Temperature setpoints with explicit units and limits."),
    "actuation": ("Actuation", "GPIO, valves and pumps — small physical actions with real effects."),
    "compute": ("Compute", "Submitting and cancelling bounded computation."),
    "process": ("Process", "Running a bounded local process, always treated as R1+ unless read-only."),
    "device": ("Device", "Describe, calibrate and self-test the device itself."),
}


def capability_card(cap: dict, prefix: str = "") -> str:
    tags = " ".join(cap["_tags"][:8])
    modes = " ".join(cap["_modes"])
    search_blob = " ".join(
        [cap["_slug"], cap["_title"], cap["_summary"], tags, modes, cap["_verb"], cap["_risk"], cap["_status"]]
    ).lower()
    summary = cap["_summary"]
    short = summary[:180].rsplit(" ", 1)[0] + "…" if len(summary) > 180 else summary
    status_badge = (
        ""
        if cap["_status"] == "stable"
        else f'<span class="badge badge-{"warn" if cap["_status"] == "deprecated" else "info"}">{esc(cap["_status"])}</span>'
    )
    return (
        f'<a class="cap-card" id="{attr(cap["_slug"])}" href="#{attr(cap["_slug"])}" '
        f'data-cap="{attr(cap["_slug"])}" data-verb="{attr(cap["_verb"])}" '
        f'data-risk="{attr(cap["_risk"])}" data-search="{attr(search_blob)}">'
        f'<div class="cap-card-top"><code>{esc(cap["_slug"])}</code><span class="cap-risk risk-{attr(cap["_risk"].lower())}">{esc(cap["_risk"])}</span></div>'
        f'<h3>{esc(cap["_title"])}</h3><p>{esc(short)}</p>'
        f'<div class="cap-card-foot"><span class="verb-tag">{esc(cap["_verb"])}</span><span>{len(cap["_modes"])} modes</span><span>{len(cap["_tags"])} tags</span>{status_badge}</div></a>'
    )


def capabilities_page(ctx) -> str:
    caps = ctx.caps
    p = "../"
    verbs = {"read": 0, "write": 0, "invoke": 0}
    risks = {"R0": 0, "R1": 0, "R2": 0, "R3": 0}
    for cap in caps.items:
        verbs[cap["_verb"]] = verbs.get(cap["_verb"], 0) + 1
        risks[cap["_risk"]] = risks.get(cap["_risk"], 0) + 1
    groups = []
    for domain, items in caps.domains:
        label, blurb = DOMAIN_LABELS.get(domain, (domain.title(), ""))
        cards = "".join(capability_card(cap) for cap in items)
        groups.append(
            f'<section class="cap-group" id="domain-{attr(domain)}" data-domain="{attr(domain)}">'
            f'<div class="cap-group-head"><div><p class="eyebrow">{esc(domain)}</p><h2>{esc(label)} <span class="count">{len(items)}</span></h2><p>{esc(blurb)}</p></div>'
            f'<a class="text-link" href="#top">Back to top</a></div>'
            f'<div class="cap-grid">{cards}</div></section>'
        )
    body = f"""
<div class="wrap">
  {breadcrumbs_html(p, [("Capabilities", None)])}
  <header class="page-hero" id="top">
    <p class="eyebrow">{SITE_NAME} {SPEC_VERSION} · capability catalogue</p>
    <h1>What a device can do, in typed terms</h1>
    <p class="page-lead">A capability class is the contract for one class of action: verb, input and output schemas, units, effects, hazards, determinism and risk. Classes are shared; each device binds them to its own resources and declares its own truth.</p>
    <div class="doc-hero-stats">
      <span><strong>{caps.count}</strong> core classes</span>
      <span><strong>{len(caps.domains)}</strong> domains</span>
      <span><strong>{verbs.get('invoke', 0)}</strong> invoke</span>
      <span><strong>{verbs.get('read', 0)}</strong> read</span>
      <span><strong>{verbs.get('write', 0)}</strong> write</span>
    </div>
    <div class="hero-actions">
      {btn("Download capabilities.json", "../download/capabilities.json", "secondary")}
      {btn("Read MHS-003", "../spec/03-capability-registry.html", "ghost")}
    </div>
  </header>
  <div class="cap-toolbar">
    <div class="search-input-wrap cap-search">
      {ICONS['search']}
      <label class="sr-only" for="cap-q">Filter capabilities</label>
      <input id="cap-q" type="search" placeholder="Filter by name, tag, unit or effect…" autocomplete="off" spellcheck="false">
    </div>
    <div class="cap-filter-buttons" role="group" aria-label="Filter by verb">
      <button type="button" class="filter-btn is-active" data-verb="">All verbs</button>
      <button type="button" class="filter-btn" data-verb="read">Read</button>
      <button type="button" class="filter-btn" data-verb="write">Write</button>
      <button type="button" class="filter-btn" data-verb="invoke">Invoke</button>
    </div>
    <p class="cap-filter-count" id="cap-count" aria-live="polite">{caps.count} classes</p>
  </div>
  <noscript><p class="callout callout-note">The filter and schema viewer require JavaScript. The full catalogue is available in <a href="../spec/capabilities.json">capabilities.json</a>.</p></noscript>
  {''.join(groups)}
  <div class="empty-state" id="cap-empty" hidden><h2>No classes match</h2><p>Try a different term or clear the verb filter.</p><button type="button" class="btn btn-secondary" id="cap-clear">Clear filters</button></div>

  <section class="section cap-legend">
    {section_head("Legend", "Verbs, risk classes and semantics", "")}
    <div class="legend-grid">
      <div><h3>Verbs</h3><dl class="legend-list">
        <dt><code>read</code></dt><dd>Observe state or a computed quantity. No physical effect.</dd>
        <dt><code>write</code></dt><dd>Set a declared, persisted parameter. Still a revision-bound mutation.</dd>
        <dt><code>invoke</code></dt><dd>Run a discrete operation with a physical effect; receipted and cancellable.</dd>
        <dt><code>subscribe</code></dt><dd>Receive a sequenced stream; gaps are explicit.</dd>
        <dt><code>compose</code></dt><dd>Run a named, versioned composition of capabilities.</dd>
      </dl></div>
      <div><h3>Risk classes</h3><dl class="legend-list">
        <dt><span class="cap-risk risk-r0">R0</span></dt><dd>Observational. No physical effect; data only.</dd>
        <dt><span class="cap-risk risk-r1">R1</span></dt><dd>Low energy, reversible and bounded.</dd>
        <dt><span class="cap-risk risk-r2">R2</span></dt><dd>High energy, irreversible or destructive if wrong.</dd>
        <dt><span class="cap-risk risk-r3">R3</span></dt><dd>Hazardous to people, environment or irreplaceable samples; permit and human presence.</dd>
      </dl></div>
      <div><h3>Binding, not inheritance</h3><p>Classes do not extend one another. A device binds a class to a resource and supplies its limits, units and native mapping. The catalogue is the shared vocabulary; the device manifest carries vendor truth.</p><p><a class="text-link" href="../spec/03-capability-registry.html#5-binding-a-class-to-a-device">Binding rules {ICONS['arrow']}</a></p></div>
    </div>
  </section>
</div>

<dialog class="cap-dialog" id="cap-dialog" aria-labelledby="cap-dialog-title">
  <div class="dialog-head">
    <div><p class="eyebrow" id="cap-dialog-id">capability class</p><h2 id="cap-dialog-title">Capability</h2></div>
    <button type="button" class="icon-btn dialog-close" id="cap-dialog-close" aria-label="Close">{ICONS['close']}</button>
  </div>
  <div class="dialog-body">
    <p class="dialog-summary" id="cap-dialog-summary"></p>
    <div class="dialog-badges" id="cap-dialog-badges"></div>
    <div class="dialog-meta" id="cap-dialog-meta"></div>
    <div class="schema-viewer">
      <div class="schema-tabs" role="tablist" aria-label="Schema view">
        <button type="button" role="tab" class="schema-tab is-active" data-schema="input" aria-selected="true">Input schema</button>
        <button type="button" role="tab" class="schema-tab" data-schema="output" aria-selected="false">Output schema</button>
        <button type="button" role="tab" class="schema-tab" data-schema="class" aria-selected="false">Class document</button>
        <button type="button" class="copy-btn schema-copy" data-copy-target="cap-schema-code">Copy</button>
      </div>
      <pre tabindex="0" id="cap-schema-pre"><code id="cap-schema-code"></code></pre>
    </div>
    <div class="dialog-extras" id="cap-dialog-extras"></div>
    <p class="dialog-footnote">Class schema is normative data from <code>capabilities.json</code>; where the Markdown catalogue and the JSON disagree, the JSON wins.</p>
  </div>
</dialog>

<script defer src="../assets/capabilities-data.js"></script>
<script defer src="../assets/capabilities.js"></script>
"""
    return page_html(
        path="capabilities/index.html",
        title="Capability catalogue",
        description=f"Browse the {caps.count} core OpenMHS capability classes with input and output JSON Schemas, units, effects, hazards, modes and risk classes.",
        body=body,
        section="capabilities",
        breadcrumbs=[("Capabilities", "capabilities/index.html")],
        og_type="article",
    )


# ---------------------------------------------------------------------------
# Pages: families
# ---------------------------------------------------------------------------


def family_packages(recs: list[dict], limit: int = 18) -> list[dict]:
    ordered = sorted(recs, key=lambda r: (-r["stars"], r["title"].lower()))
    return ordered[:limit]


def family_modes(recs: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for rec in recs:
        for mode in rec["modes"]:
            counts[mode] = counts.get(mode, 0) + 1
    return counts


def families_index_page(ctx) -> str:
    p = "../"
    families = ctx.families
    real = sum(1 for f in families if not f.placeholder)
    cards = []
    for fam in families:
        recs = ctx.family_records.get(fam.name, [])
        modes = family_modes(recs)
        mode_html = "".join(
            f'<span class="mode-chip mode-{attr(m)}">{esc(m)}</span>' for m in modes
        )
        state = (
            badge("Recipe published", "good")
            if not fam.placeholder
            else badge("Recipe in preparation", "warn")
        )
        cards.append(
            f'<a class="family-card" href="{fam.slug}.html">'
            f'<div class="family-card-top"><span class="family-count">{fmt_int(fam.count)} <small>packages</small></span>{state}</div>'
            f"<h2>{esc(fam.title)}</h2><p>{esc(fam.description)}</p>"
            f'<div class="family-modes">{mode_html}</div>'
            f'<span class="family-card-foot">Open family page {ICONS["arrow"]}</span></a>'
        )
    notice = ""
    if real < len(families):
        notice = callout(
            "Recipes are being published progressively",
            f"<p>{real} of {len(families)} family recipes are present in <code>MHS/registry/families/</code>. The remaining pages are generated from the registry index and clearly labelled: they describe the integration shape for that family but are not the published recipe.</p>",
            "warn",
            "book",
        )
    body = f"""
<div class="wrap">
  {breadcrumbs_html(p, [("Families", None)])}
  <header class="page-hero">
    <p class="eyebrow">Adapters and bridges</p>
    <h1>One recipe per family</h1>
    <p class="page-lead">Bridge families are how existing ecosystems join OpenMHS without a rewrite. Each recipe shows the launch shape, the capability mapping, unit and safety handling, the usual blockers, and what “done” means for that family.</p>
    <div class="doc-hero-stats">
      <span><strong>{len(families)}</strong> families</span>
      <span><strong>{fmt_int(sum(f.count for f in families))}</strong> package links</span>
      <span><strong>{real}</strong> recipes published</span>
      <span><strong>{len(families) - real}</strong> in preparation</span>
    </div>
  </header>
  {notice}
  <div class="family-grid">{''.join(cards)}</div>
  <section class="section">
    {section_head("Anatomy", "What every recipe must contain", "")}
    <div class="convention-grid">
      <div><h3>Launch and lifecycle</h3><p>How the process starts, how readiness is probed, how it stops, and which transports it offers. A bridge that cannot start cleanly cannot be conformant above CL0.</p></div>
      <div><h3>Capability mapping</h3><p>Native symbol or route to capability class, argument and result transforms, and the unit conversion performed at the boundary. Undocumented internals are marked fragile.</p></div>
      <div><h3>Safety and mode</h3><p>Limits, interlocks, permits, e-stop independence, and the declared mode and fidelity contract. A recipe never promotes a simulator to hardware.</p></div>
      <div><h3>Evidence and blockers</h3><p>What was read, what is missing, the concrete next command, and the conformance level that is honestly reachable today.</p></div>
    </div>
    <div class="hero-actions">
      {btn("Read the adapter specification", "../spec/06-adapters.html", "primary", icon=True)}
      {btn("Adapter schema", "../schema/adapter.schema.json", "secondary")}
    </div>
  </section>
</div>
"""
    return page_html(
        path="families/index.html",
        title="Bridge families",
        description="OpenMHS bridge families and integration recipes: gymnasium, ROS 2, MuJoCo, VISA, SiLA 2, Opentrons, Micro-Manager, Bluesky, QCoDeS, MADSci and more.",
        body=body,
        section="families",
        breadcrumbs=[("Families", "families/index.html")],
        og_type="article",
    )


def family_placeholder_content(ctx, fam: Family) -> str:
    recs = ctx.family_records.get(fam.name, [])
    top_caps: dict[str, int] = {}
    for rec in recs:
        for cap in rec["capabilities_offered"]:
            top_caps[cap] = top_caps.get(cap, 0) + 1
    cap_items = [c for c, _ in sorted(top_caps.items(), key=lambda kv: (-kv[1], kv[0]))[:12]]
    caps_html = "".join(capability_link("../", c, ctx.caps.by_id) for c in cap_items) or '<p class="muted">No capability classes were recorded for this family.</p>'
    top = family_packages(recs, 16)
    rows = "".join(
        f'<tr><td><a href="../registry/repo/{r["slug"]}.html">{esc(r["title"])}</a></td>'
        f'<td>{esc(r["tier"])}</td><td>{esc(r["ring"])}</td><td>{fmt_int(r["stars"])}</td>'
        f'<td>{mode_chips(r["modes"])}</td></tr>'
        for r in top
    )
    table = (
        f'<div class="table-wrap"><table><thead><tr><th scope="col">Package</th><th scope="col">Tier</th><th scope="col">Ring</th><th scope="col">Stars</th><th scope="col">Modes</th></tr></thead><tbody>{rows}</tbody></table></div>'
        if top
        else '<p class="muted">No packages are indexed in this family yet.</p>'
    )
    return f"""
{callout("Family recipe in preparation", f"<p>The registry has <strong>{fmt_int(fam.count)}</strong> packages in this family, but <code>MHS/registry/families/{esc(fam.slug)}.md</code> was not present at build time. This page is generated from the registry index to keep the family navigable; it is not the published recipe. The integration outline and package list are accurate to the registry snapshot, not a substitute for the recipe.</p>", "warn", "book")}
<p class="lead">{esc(fam.description)}</p>
<h2 id="outline">How packages in this family become endpoints</h2>
<div class="steps-grid">
  <div class="step-card"><span>01</span><h3>Choose the bridge</h3><p>Use the <code>{esc(fam.name)}</code> bridge family where it exists. Otherwise wrap the entry point as Python-object, HTTP or CLI and record the shim explicitly.</p></div>
  <div class="step-card"><span>02</span><h3>Pin the native surface</h3><p>Record module/class/function, launch command or route. Do not rely on undocumented internals; if you must, declare <code>stability: fragile</code>.</p></div>
  <div class="step-card"><span>03</span><h3>Map capabilities and units</h3><p>Bind the classes this package can actually support. Convert to UCUM units at the boundary and declare limits, hazards and idempotency per class.</p></div>
  <div class="step-card"><span>04</span><h3>Declare mode, safety, evidence</h3><p>Write the fidelity contract for simulated devices. Run the suite, publish the report digest, and only then move the record's state.</p></div>
</div>
<h2 id="capabilities">Capability surface seen in this family</h2>
<p class="section-note">Aggregated from package records, not a binding recommendation. A package may offer only a subset.</p>
<div class="cap-chip-list">{caps_html}</div>
<h2 id="packages">Packages in this family</h2>
<p class="section-note">Top {len(top)} of {fmt_int(fam.count)} by stars. Use the <a href="../registry/index.html?family={attr(fam.name)}">registry explorer</a> for the complete, filterable list.</p>
{table}
<h2 id="recipe-checklist">What the published recipe must cover</h2>
<div class="checklist">
  <div><strong>Launch</strong><p>Command, environment, readiness probe, shutdown grace, transport.</p></div>
  <div><strong>Mapping</strong><p>Native symbol to capability id, argument mapping, result mapping, error mapping.</p></div>
  <div><strong>Units</strong><p>Source unit, conversion, target unit — per numeric field, not in names.</p></div>
  <div><strong>Safety</strong><p>Hard limits, interlocks, reset conditions, e-stop independence, risk class.</p></div>
  <div><strong>Mode and fidelity</strong><p>Mode, engine, F-level, determinism, gaps, replay support.</p></div>
  <div><strong>Evidence</strong><p>What was read, what was run, the exact next command, known blockers.</p></div>
</div>
<div class="hero-actions">
  {btn("Explore this family", f"../registry/index.html?family={fam.name}", "primary", icon=True)}
  {btn("Adapter specification", "../spec/06-adapters.html", "secondary")}
</div>
"""


def family_page(ctx, fam: Family) -> str:
    p = "../"
    recs = ctx.family_records.get(fam.name, [])
    modes = family_modes(recs)
    mode_html = "".join(f'<span class="mode-chip mode-{attr(m)}">{esc(m)}</span>' for m in modes)
    tier_counts: dict[str, int] = {}
    for rec in recs:
        tier_counts[rec["tier"]] = tier_counts.get(rec["tier"], 0) + 1
    tier_html = " ".join(f"<span>{esc(t)}: {fmt_int(n)}</span>" for t, n in sorted(tier_counts.items()))
    recipe_html = ""
    toc_html = ""
    if not fam.placeholder:
        renderer = MarkdownRenderer(ctx.known, f"MHS/registry/families/{fam.source.name}", f"families/{fam.slug}.html")
        rendered, toc = renderer.render(fam.body, skip_first_h1=True)
        fam.html = rendered
        fam.toc = toc
        if toc:
            toc_html = f'<details class="toc-mobile" open><summary>On this page <span>{len(toc)} sections</span></summary>{toc_markup(toc)}</details>'
        recipe_html = f'<div class="doc-body recipe-body">{rendered}</div>'
    else:
        recipe_html = family_placeholder_content(ctx, fam)
    top = family_packages(recs, 24)
    rows = "".join(
        f'<tr><td><a href="../registry/repo/{r["slug"]}.html">{esc(r["title"])}</a><br><span class="table-sub">{esc(r["description"][:120])}</span></td>'
        f'<td>{tier_badge(r["tier"])}</td><td>{esc(r["ring"])}</td><td>{esc(r["evidence_state"].replace("_", " "))}</td><td>{fmt_int(r["stars"])}</td></tr>'
        for r in top
    )
    package_table = (
        f'<h2 id="packages">Packages</h2><p class="section-note">Top {len(top)} of {fmt_int(fam.count)} by stars. <a href="../registry/index.html?family={attr(fam.name)}">Filter the full list</a>.</p>'
        f'<div class="table-wrap"><table><thead><tr><th scope="col">Package</th><th scope="col">Tier</th><th scope="col">Ring</th><th scope="col">Evidence</th><th scope="col">Stars</th></tr></thead><tbody>{rows}</tbody></table></div>'
        if top
        else '<p class="muted">No packages are indexed in this family.</p>'
    )
    body = f"""
<div class="wrap">
  {breadcrumbs_html(p, [("Families", "families/index.html"), (fam.title, None)])}
  <header class="page-hero page-hero-family">
    <div class="family-hero-grid">
      <div>
        <p class="eyebrow">Bridge family · {esc(fam.name)}</p>
        <h1>{esc(fam.title)}</h1>
        <p class="page-lead">{esc(fam.description)}</p>
        <div class="package-badges">{badge("Recipe published", "good") if not fam.placeholder else badge("Recipe in preparation", "warn")}{badge(f"{fmt_int(fam.count)} packages", "info")}{''.join(f'<span class="mode-chip mode-{attr(m)}">{esc(m)}</span>' for m in modes)}</div>
      </div>
      <aside class="family-summary">
        <p class="package-summary-kicker">Family snapshot</p>
        <dl>
          <dt>Packages</dt><dd>{fmt_int(fam.count)}</dd>
          <dt>Tiers</dt><dd>{tier_html or '—'}</dd>
          <dt>Modes</dt><dd>{mode_html or '—'}</dd>
          <dt>Registry filter</dt><dd><a href="../registry/index.html?family={attr(fam.name)}">Open in explorer</a></dd>
        </dl>
      </aside>
    </div>
  </header>
  <div class="family-layout">
    <article class="family-main">
      {toc_html}
      {recipe_html}
      {package_table}
    </article>
    <aside class="family-aside">
      <div class="aside-card">
        <h2>Family facts</h2>
        <dl class="aside-facts">
          <dt>Bridge family</dt><dd><code>{esc(fam.name)}</code></dd>
          <dt>Recipe source</dt><dd>{f'<code>{esc(fam.source.name)}</code>' if fam.source else '<span class="muted">not published</span>'}</dd>
          <dt>Packages</dt><dd>{fmt_int(fam.count)}</dd>
          <dt>Agent-read</dt><dd>{fmt_int(sum(1 for r in recs if r['evidence_state'] == 'agent_read'))}</dd>
          <dt>Runtime tested</dt><dd>{fmt_int(sum(1 for r in recs if r['evidence_state'] == 'runtime_tested'))}</dd>
        </dl>
      </div>
      <div class="aside-card">
        <h2>Related</h2>
        <ul class="aside-links">
          <li><a href="../spec/06-adapters.html">Adapters and bridges</a></li>
          <li><a href="../schema/adapter.schema.json">Adapter schema</a></li>
          <li><a href="../capabilities/index.html">Capability catalogue</a></li>
          <li><a href="../conformance/index.html">Conformance ladder</a></li>
          <li><a href="../families/index.html">All families</a></li>
        </ul>
      </div>
      <div class="aside-card aside-contribute">
        <h2>Add a package</h2>
        <p>Registry records are generated from a catalogue and bounded scans, then improved by reading source. A family recipe is how the whole family gets easier.</p>
        <a class="text-link" href="../governance/index.html">Contribution process {ICONS['arrow']}</a>
      </div>
    </aside>
  </div>
</div>
"""
    return page_html(
        path=f"families/{fam.slug}.html",
        title=f"{fam.title} · bridge family",
        description=fam.description,
        body=body,
        section="families",
        breadcrumbs=[("Families", "families/index.html"), (fam.title, None)],
        og_type="article",
        noindex=fam.placeholder,
    )


# ---------------------------------------------------------------------------
# Pages: conformance
# ---------------------------------------------------------------------------

LEVELS = [
    ("cl0", "CL0", "Declared", "Manifests and schemas validate; no runtime is required.",
     ["Valid device and adapter manifests against the OpenMHS schemas", "Capability bindings reference known class MAJOR versions", "Registry record validates if one is published"],
     "A schema-validation report with at least one test result.", "spec/01-conformance.html#3-levels"),
    ("cl1", "CL1", "Observable", "A host can discover and read the device, with stable revisions.",
     ["T1 and/or T2 transport", "hello, devices.list/get, schema.get", "resource.read with state hash", "subscribe and unsubscribe"],
     "Transport transcript and stable revision/state-hash evidence.", "spec/02-wire-protocol.html#3-method-summary"),
    ("cl2", "CL2", "Actuating", "Commands are idempotent, receipted and cancellable.",
     ["session.open/close", "command with command_id and retained receipts", "expected_revision conflicts", "operations.get/cancel and deadlines"],
     "Receipts proving completion, rejection, replay and cancellation.", "spec/02-wire-protocol.html#10-receipts"),
    ("cl3", "CL3", "Governed", "The endpoint refuses unsafe actions before any effect.",
     ["safety.status/estop/reset", "envelope limits and interlocks enforced in order", "risk classes and permits for gated capabilities", "MHS.SAFETY.NOT_CERTIFIED disclosed"],
     "Negative tests: open interlock, stale revision, missing permit.", "spec/04-safety.html"),
    ("cl4", "CL4", "Reproducible", "Outcomes can be reconstructed and evidence verified offline.",
     ["evidence.export and evidence.verify hash chain", "deterministic replay for simulated/replay devices", "same seed ⇒ identical state_hash sequence"],
     "Exported bundle with a verifiable head digest and replay equality.", "spec/05-fidelity.html#5-replay"),
    ("cl5", "CL5", "Orchestrated", "Compositions and multi-device sessions are evidence-bearing.",
     ["composition.run with child receipts", "multi-device sessions", "backpressure and gap semantics", "published conformance report"],
     "Child receipt tree and a published, digest-addressed report.", "spec/00-architecture-part-2.html#10-conformance"),
]

PROFILE_ROWS = [
    ("MHS-Device", "Endpoint", "Hardware-backed endpoint and its devices", "CL0–CL4", "No replay requirement"),
    ("MHS-Sim", "Endpoint", "Simulated or hybrid endpoint", "CL0–CL4", "Fidelity contract required; CL4 replay"),
    ("MHS-Bridge", "Package / adapter", "Adapter manifest plus endpoints a bridge launches", "CL0–CL5", "CL5 needs a published report"),
    ("MHS-Host", "Host", "Agent harness consuming OpenMHS", "CL1–CL5", "Discovery, approvals, evidence ledger"),
    ("MHS-Registry", "Registry", "Records, trust and search", "CL1–CL5", "Digest reproducibility and federation"),
]

MATRIX = [
    ("ADPT", "adapter and manifest", ["●", "◐", "◐", "◐", "◐", "●"]),
    ("CAP", "classes and bindings", ["●", "●", "●", "◐", "◐", "◐"]),
    ("REG", "registry publication", ["●", "—", "—", "—", "◐", "●"]),
    ("PROTO", "framing and methods", ["—", "●", "●", "●", "◐", "◐"]),
    ("TPT", "transports", ["—", "●", "●", "◐", "◐", "◐"]),
    ("SESS", "sessions", ["—", "◐", "●", "●", "◐", "◐"]),
    ("OP", "operations and idempotency", ["—", "—", "●", "●", "◐", "●"]),
    ("MODE", "mode declaration", ["—", "●", "●", "●", "●", "◐"]),
    ("EVT", "subscriptions", ["—", "●", "●", "◐", "●", "●"]),
    ("SAFE", "safety", ["—", "—", "◐", "●", "●", "◐"]),
    ("FID", "fidelity and determinism", ["—", "◐", "◐", "◐", "●", "◐"]),
    ("EVID", "evidence", ["—", "—", "◐", "◐", "●", "●"]),
    ("COMP", "compositions", ["—", "—", "—", "—", "—", "●"]),
    ("CON", "meta and report", ["●", "●", "●", "●", "●", "●"]),
]


def conformance_page(ctx) -> str:
    p = "../"
    st = ctx.status
    ladder = "".join(
        f'<article class="level-card" id="{anchor}"><div class="level-head"><span class="level-badge">{level}</span>'
        f'<div><h2>{esc(name)}</h2><p>{esc(tagline)}</p></div></div>'
        f'<ul class="tick-list">{"".join(f"<li>{esc(req)}</li>" for req in reqs)}</ul>'
        f'<p class="level-evidence"><strong>Evidence:</strong> {esc(evidence)}</p>'
        f'<a class="text-link" href="../{link}">Requirements {ICONS["arrow"]}</a></article>'
        for anchor, level, name, tagline, reqs, evidence, link in LEVELS
    )
    profile_rows = "".join(
        f"<tr><td><strong>{esc(name)}</strong></td><td>{esc(kind)}</td><td>{esc(desc)}</td>"
        f'<td><span class="level-mini">{esc(levels)}</span></td><td>{esc(note)}</td></tr>'
        for name, kind, desc, levels, note in PROFILE_ROWS
    )
    matrix_head = "".join(f"<th scope=\"col\">{lvl}</th>" for lvl in ["CL0", "CL1", "CL2", "CL3", "CL4", "CL5"])
    matrix_rows = "".join(
        f"<tr><th scope=\"row\"><code>{area}</code><span>{esc(label)}</span></th>"
        + "".join(
            f'<td class="matrix-{ "full" if mark == "●" else ("partial" if mark == "◐" else "none")}">'
            f'<span aria-hidden="true">{mark}</span><span class="sr-only">'
            f'{ "required" if mark == "●" else ("subset required" if mark == "◐" else "not required")}</span></td>'
            for mark in marks
        )
        + "</tr>"
        for area, label, marks in MATRIX
    )
    negative = [
        ("SAFE-050", "hello.features omits MHS.SAFETY.NOT_CERTIFIED"),
        ("SAFE-020", "A command proceeds while a required interlock reads open"),
        ("PROTO-040", "A command with a stale expected_revision changes state"),
        ("OP-010", "The same command_id with different input is accepted"),
        ("SESS-010", "A session survives its TTL without a heartbeat"),
        ("MODE-002", "A session opens with a mode other than the device's declared mode"),
        ("EVID-010", "A tampered evidence bundle verifies as valid"),
        ("FID-010", "A simulated device without a fidelity contract claims CL1+"),
    ]
    neg_rows = "".join(f"<tr><td><code>{esc(i)}</code></td><td>{esc(d)}</td></tr>" for i, d in negative)
    suite_note = (
        f'<p class="status-inline"><span class="status-marker status-good"></span> Reference suite present ({st["suite_files"]} modules) with {st["reports_count"]} self-issued reports (CL2–CL4). Reports are issuer-kind <code>self</code>, not third-party verified.</p>'
        if st["suite_present"]
        else '<p class="status-inline"><span class="status-marker status-warn"></span> The conformance suite is specified but a runnable copy is not included in this site build. Commands below show the intended CLI shape; do not claim a level until you have a report.</p>'
    )
    reference_run = ""
    ref_path = MHS / "conformance" / "reports" / "conveyor-cl4.json"
    if ref_path.is_file():
        try:
            ref = json.loads(read_text(ref_path))
        except json.JSONDecodeError:
            ref = {}
        if isinstance(ref, dict) and ref.get("tests"):
            cov = ref.get("coverage") or {}
            env = ref.get("environment") or {}
            subject = ref.get("subject") or {}
            tests = ref.get("tests") or []
            tone_map = {"pass": "good", "fail": "bad", "skip": "warn", "warn": "warn", "error": "bad"}
            test_rows = "".join(
                f'<tr><td><code>{esc(t.get("id") or "")}</code></td><td>{esc(t.get("name") or "")}</td>'
                f'<td><span class="badge badge-{tone_map.get(str(t.get("status")), "muted")}">{esc(str(t.get("status") or "").upper())}</span></td>'
                f'<td>{esc(t.get("level") or "")}</td><td class="test-detail">{esc(t.get("detail") or "")}</td></tr>'
                for t in tests
            )
            limitations = ref.get("limitations") or []
            limits_html = "".join(f"<li>{esc(item)}</li>" for item in limitations) or "<li>No limitations declared.</li>"
            digest = str(ref.get("report_digest") or "")
            reference_run = f"""
  <section class="section" id="quickstart-sdk-run">
    {section_head("Reference run", "A real CL4 report, recomputable from this site", "This is not a mock-up. The report below was produced by running the reference conformance suite against the deterministic conveyor endpoint, and the raw JSON ships with the site.")}
    <div class="report-banner">
      <div>
        <p class="report-kicker">Subject</p>
        <h3>{esc(subject.get("id") or "unknown subject")}</h3>
        <p>{esc(subject.get("kind") or "endpoint")} · wire {esc(subject.get("mhs_version") or MHS_VERSION)} · profile {esc(ref.get("profile") or "")} · suite {esc(ref.get("suite_version") or "")}</p>
      </div>
      <div class="report-level">
        <span class="level-badge">{esc(ref.get("level_achieved") or "")}</span>
        <span>achieved</span>
      </div>
    </div>
    <div class="report-metrics">
      <div><strong>{fmt_int(cov.get("passed", 0))}</strong><span>passed</span></div>
      <div><strong>{fmt_int(cov.get("failed", 0))}</strong><span>failed</span></div>
      <div><strong>{fmt_int(cov.get("skipped", 0))}</strong><span>skipped</span></div>
      <div><strong>{fmt_int(cov.get("required", 0))}</strong><span>required</span></div>
      <div><strong>{esc((env.get("date") or "")[:10])}</strong><span>run date</span></div>
    </div>
    <div class="digest-block">
      <p class="report-kicker">Report digest</p>
      <code class="digest">{esc(digest)}</code>
      <p class="field-hint">This is the report body digest: SHA-256 over the <a href="{p}spec/01-conformance.html#72-report-digest">JCS canonical form with <code>report_digest</code> removed</a>, not the hash of the pretty-printed file. A claim without a matching digest is not evidence.</p>
      <div class="hero-actions">
        <a class="btn btn-secondary btn-sm" href="reports/conveyor-cl4.json" download>Download the raw report</a>
        <a class="btn btn-secondary btn-sm" href="{p}spec/01-conformance.html#7-report-format">Report requirements</a>
      </div>
    </div>
    <div class="table-wrap report-table"><table>
      <thead><tr><th scope="col">Test</th><th scope="col">Requirement</th><th scope="col">Status</th><th scope="col">Level</th><th scope="col">Detail</th></tr></thead>
      <tbody>{test_rows}</tbody>
    </table></div>
    <div class="report-limits">
      <h3>Declared limitations</h3>
      <ul>{limits_html}</ul>
      <p class="field-hint">Skipped tests are displayed, not hidden. This run is self-issued by the reference suite; it is not third-party certification and not safety certification. Environment: {esc(env.get("os") or "unknown OS")} · Python {esc(env.get("python") or "unknown")}.</p>
    </div>
  </section>
"""
    report_json = """{
  "report_version": "1.0",
  "suite_version": "1.0.0",
  "profile": "MHS-Sim",
  "endpoint_id": "mhs://localhost:7400",
  "level_claimed": "CL3",
  "level_achieved": "CL3",
  "tests": [
    {"id": "PROTO-001", "status": "pass",
     "evidence": {"request_digest": "sha256:…", "response_digest": "sha256:…"}},
    {"id": "SAFE-020", "status": "pass", "evidence": {"note": "interlock open ⇒ rejected"}}
  ],
  "environment": {"mhs_version": "1.0", "os": "linux", "date": "2026-10-20T00:00:00Z"},
  "report_digest": "sha256:…",
  "issuer": {"kind": "self", "key_id": null},
  "signature": null
}"""
    claim_json = """{
  "claim_type": "conformance",
  "subject": "gh.example/lab-endpoint",
  "profile": "MHS-Sim",
  "level": "CL3",
  "suite_version": "1.0.0",
  "report_digest": "sha256:…",
  "issued_at": "2026-10-20T00:00:00Z",
  "issuer_kind": "self",
  "trust": "unsigned"
}"""
    body = f"""
<div class="wrap">
  {breadcrumbs_html(p, [("Conformance", None)])}
  <header class="page-hero">
    <p class="eyebrow">{SITE_NAME} {SPEC_VERSION} · executable conformance</p>
    <h1>A claim is a level, not a logo.</h1>
    <p class="page-lead">OpenMHS conformance names a subject, a profile and a level CL0–CL5, and points to a machine-readable report a third party can recompute. Prose, badges without a report, and “MHS-compatible” are not conformance.</p>
    <div class="hero-actions">
      {btn("Read MHS-001", "../spec/01-conformance.html", "primary", icon=True)}
      {btn("Self-certification steps", "#self-certify", "secondary")}
    </div>
    {suite_note}
  </header>

  <section class="section" id="levels">
    {section_head("The ladder", "Six levels, each with evidence", "Each level adds behaviour that must be demonstrated, including negative behaviour. A skipped test is not a passed test.")}
    <div class="level-grid">{ladder}</div>
  </section>

  <section class="section" id="profiles">
    {section_head("Profiles", "Five subjects, five profiles", "A profile fixes what is being tested and which levels are defined. An endpoint subject cannot claim MHS-Host, and a host cannot claim MHS-Device.")}
    <div class="table-wrap"><table class="profile-table"><thead><tr><th scope="col">Profile</th><th scope="col">Subject</th><th scope="col">What is tested</th><th scope="col">Levels</th><th scope="col">Note</th></tr></thead><tbody>{profile_rows}</tbody></table></div>
  </section>

  <section class="section" id="matrix">
    {section_head("Test matrix", "Requirement coverage by level", "● every relevant test must run and pass · ◐ a subset defined by the level's mandatory suite · — not required.")}
    <div class="table-wrap"><table class="matrix-table"><thead><tr><th scope="col">Area</th>{matrix_head}</tr></thead><tbody>{matrix_rows}</tbody></table></div>
    <h3 id="negative-tests">Mandatory negative tests</h3>
    <p>The suite must include tests that prove refusal, not only success. A suite that only exercises the happy path cannot support CL3 or above.</p>
    <div class="table-wrap"><table><thead><tr><th scope="col">Test</th><th scope="col">What must happen</th></tr></thead><tbody>{neg_rows}</tbody></table></div>
  </section>

  <section class="section" id="self-certify">
    {section_head("Self-certification", "How to certify without a certification body", "OpenMHS is designed for self-service. The registry claim plus a reproducible report is the starting point; third-party verification is an additional trust level, not a gate.")}
    <ol class="cert-steps">
      <li><span class="cert-num">01</span><div><h3>Choose the subject and the honest level</h3><p>An endpoint, package, host or registry. Pick the profile that matches the subject and the lowest level that includes the behaviour you actually implement. CL0 is a valid, useful claim.</p></div></li>
      <li><span class="cert-num">02</span><div><h3>Validate every manifest and schema</h3><p>Device manifests, adapter manifests, capability bindings and any registry record must validate against the published JSON Schemas. A simulator without a fidelity contract fails before runtime.</p></div></li>
      <li><span class="cert-num">03</span><div><h3>Run the suite against the endpoint</h3><p>Use the same suite version you cite. Run the negative tests. Do not skip a mandatory test because the endpoint does not implement the failure path.</p><code class="cmd">mhs conform --endpoint mhs://localhost:7400 --profile MHS-Sim --level CL3 --out report.json</code></div></li>
      <li><span class="cert-num">04</span><div><h3>Inspect the report and recompute its digest</h3><p>The report lists every test id with pass, fail or skip. The report digest must be reproducible from the report bytes. A report without the mandatory tests for the claimed level is not a claim.</p></div></li>
      <li><span class="cert-num">05</span><div><h3>Publish the claim</h3><p>Attach profile, level, suite version, report digest, issuer kind and timestamp to the registry record. Unsigned claims are displayed as unsigned; they are never presented as verified.</p></div></li>
      <li><span class="cert-num">06</span><div><h3>Re-run when identity changes</h3><p>A new manifest, fidelity contract, capability set or device instance invalidates the prior report. Re-run, publish a new digest, and keep the old claim addressable.</p></div></li>
    </ol>
  </section>

  {reference_run}
  <section class="section" id="report">
    {section_head("Report", "What a conformance report contains", "The report is data, not a PDF. It validates against conformance-report.schema.json and is addressed by digest.")}
    <div class="example-grid">
      <div><h3>Report</h3>{codeblock(report_json, "json", "conformance-report.json")}</div>
      <div><h3>Registry claim</h3>{codeblock(claim_json, "json", "claim.json")}</div>
    </div>
    <div class="hero-actions">
      <a class="text-link" href="{p}schema/conformance-report.schema.json">conformance-report.schema.json {ICONS['arrow']}</a>
      <a class="text-link" href="{p}schema/registry-record.schema.json">registry-record.schema.json {ICONS['arrow']}</a>
    </div>
  </section>

  <section class="section" id="disclaimer">
    {callout("What conformance does not mean", "<p>OpenMHS conformance means <em>behaviour under test</em>, not safety, quality, clinical validity, regulatory approval or fitness for a particular experiment. A conformance report is not a safety certificate and must never be presented as one. Hardware e-stop protection is required independently of MHS.</p>", "bad", "shield")}
  </section>
</div>
"""
    return page_html(
        path="conformance/index.html",
        title="Conformance",
        description="OpenMHS conformance levels CL0–CL5, five profiles, the test matrix and negative tests, and how to self-certify with a reproducible machine-readable report.",
        body=body,
        section="conformance",
        breadcrumbs=[("Conformance", "conformance/index.html")],
        og_type="article",
    )


# ---------------------------------------------------------------------------
# Pages: SDK
# ---------------------------------------------------------------------------


def sdk_page(ctx) -> str:
    p = "../"
    sdk = ctx.sdk
    st = ctx.status
    if sdk.present:
        status_callout = callout(
            "Reference SDK source and documentation are present",
            f"<p>{st['sdk_modules']} source modules, {st['sdk_tests']} test files and {st['sdk_docs']} guides were present in this build. The interface below is the frozen contract the SDK is built against; no published release package is claimed.</p>",
            "note",
            "package",
        )
    else:
        status_callout = callout(
            "SDK in progress",
            "<p>The reference SDK is being built in parallel and was not present in this build. The interface contract on this page is frozen: distribution <code>openmhs</code>, import <code>mhs</code>, Python 3.10+, standard library only. Treat install commands as the intended distribution shape, not a published package.</p>",
            "warn",
            "package",
        )
    install_from_checkout = "python3 MHS/sdk/tools/sync_data.py\npython3 -m pip install ./MHS/sdk"
    quickstart = """from mhs import connect

with connect("mhs://localhost:7400") as lab:      # one transport
    print(lab.hello())                            # discovery
    for device in lab.devices():
        print(device["device_id"], device["mode"])

    receipt = lab.invoke(                         # one command
        "cap.world.step.v1",
        {"ticks": 120},
        device_id="mhs://localhost:7400/lab/conveyor-workcell",
        expected_revision=7,
    )
    print(receipt["status"], receipt["state_hash_after"])
    bundle = lab.export_evidence()
    print(bundle["head_digest"])"""
    cli_code = """# terminal 1 — a deterministic endpoint, no install required
PYTHONPATH=MHS/sdk/src python3 -m mhs.reference conveyor --port 7400

# terminal 2 — the CLI from the workspace
export PYTHONPATH=MHS/sdk/src
python3 -m mhs.cli devices  --endpoint http://127.0.0.1:7400
python3 -m mhs.cli devices  --endpoint http://127.0.0.1:7400 --device conveyor
python3 -m mhs.cli read     workcell --endpoint http://127.0.0.1:7400
python3 -m mhs.cli call     --endpoint http://127.0.0.1:7400 \
    --capability cap.world.step.v1 --input '{"ticks":120}'
python3 -m mhs.cli session  --endpoint http://127.0.0.1:7400 --ttl 600
python3 -m mhs.cli safety   --endpoint http://127.0.0.1:7400
python3 -m mhs.cli evidence --endpoint http://127.0.0.1:7400 --verify
python3 -m mhs.cli conform  --endpoint http://127.0.0.1:7400 \
    --profile MHS-Sim --level CL4 --output report.json
python3 -m mhs.cli registry --path MHS/registry/index.json \
    --family gymnasium --mode simulated --limit 20

# MCP projection: hand this stdio server to any MCP host
python3 -m mhs.mcp --endpoint http://127.0.0.1:7400"""
    api_rows = [
        ("connect(endpoint, transport=…)", "Open a client; stdio when a command is supplied, otherwise HTTP."),
        ("hello()", "Negotiate the wire revision; return server, devices, limits and features."),
        ("devices() / inspect()", "List device summaries or fetch a full manifest."),
        ("open_session(...) / close()", "Open a least-privilege lease with mode and TTL."),
        ("read(resource_id, …)", "Read a resource state document and its revision/hash."),
        ("invoke(capability_id, input, …)", "Send a command; always returns a receipt, including rejections."),
        ("subscribe(...) / events(...)", "Open a sequenced stream and drain events without blocking."),
        ("cancel(operation_id)", "Best-effort cancellation with safe-state reporting."),
        ("snapshot() / restore()", "Simulated/replay only, when fidelity.snapshot_restore is true."),
        ("safety_status() / estop() / reset()", "Read or change the OpenMHS safety envelope."),
        ("permit(...)", "Issue a scoped, single-use permit after host approvals."),
        ("export_evidence()", "Export the hash-chained receipt bundle for offline verification."),
    ]
    api_html = "".join(f"<tr><td><code>{esc(sig)}</code></td><td>{esc(desc)}</td></tr>" for sig, desc in api_rows)
    api_excerpt = """client = connect("mhs://localhost:7400")            # stdio if command given, else HTTP
client = connect("http://localhost:7400")           # HTTP binding
client.hello() -> dict
client.devices() -> list[dict]
client.inspect(device_id=None) -> dict
client.open_session(device_ids=None, capabilities=None, mode=None, ttl_s=600) -> dict
client.read(resource_id, device_id=None, fields=None) -> dict
client.invoke(capability_id, input=None, *, device_id=None, resource=None,
              expected_revision=None, deadline_ms=30000, permit_id=None,
              command_id=None, session_id=None) -> dict          # receipt
client.cancel(operation_id, deadline_ms=5000) -> dict
client.safety_status(device_id=None) -> dict
client.estop(reason, device_id=None) -> dict
client.reset(device_id=None) -> dict
client.permit(capability_id, input_digest, ttl_s=60, approvals=None) -> dict
client.export_evidence() -> dict
client.close()"""
    readme_html = ""
    if sdk.present:
        renderer = MarkdownRenderer(ctx.known, "MHS/sdk/README.md", "sdk/index.html")
        rendered, _toc = renderer.render(readme_text(sdk), skip_first_h1=True)
        readme_html = f'<section class="section" id="reference-readme"><h2>Reference SDK documentation</h2><div class="doc-body sdk-readme">{rendered}</div></section>'
    docs_html = ""
    if sdk.docs:
        links = "".join(
            f'<li><a href="docs/{esc(doc.stem)}.html">{esc(extract_title(read_text(doc), doc.stem))}</a></li>'
            for doc in sdk.docs
        )
        docs_html = f'<section class="section"><h2>SDK guides</h2><ul class="aside-links">{links}</ul></section>'
    iface_link = (
        f'<a class="text-link" href="INTERFACE.md">Read the frozen interface contract (Markdown) {ICONS["arrow"]}</a>'
        if ctx.interface_copied
        else ""
    )
    body = f"""
<div class="wrap">
  {breadcrumbs_html(p, [("SDK", None)])}
  <header class="page-hero">
    <p class="eyebrow">Reference SDK · Python 3.10+ · stdlib only</p>
    <h1>One client for any OpenMHS endpoint</h1>
    <p class="page-lead">The same host code path drives a Rust conveyor, a Python liquid-handler simulator, a MuJoCo arm or a microscope. Differences live in the adapter plane, not in your agent loop.</p>
    <div class="doc-hero-stats">
      <span><strong>{MHS_VERSION}</strong> protocol</span>
      <span><strong>0</strong> third-party dependencies</span>
      <span><strong>stdio · HTTP · SSE</strong> transports</span>
      <span><strong>MCP</strong> projection</span>
    </div>
    {status_callout}
  </header>

  <section class="section" id="sdk-install">
    {section_head("Install", "Three ways in", "")}
    <div class="install-grid">
      <div class="install-card"><h3>From a checkout, as a package</h3><p>The distribution is <code>openmhs</code>, import name <code>mhs</code>. No release is published; copy the schemas into the package, then install.</p>{codeblock(install_from_checkout, "bash", "shell")}</div>
      <div class="install-card"><h3>From this workspace</h3><p>No build step; the package is pure Python and imports from <code>src/</code>.</p>{codeblock('PYTHONPATH=MHS/sdk/src python3 -c "import mhs; print(mhs.__version__)"', "bash", "shell")}</div>
      <div class="install-card"><h3>Run an endpoint</h3><p>Start the deterministic conveyor and point the CLI or an MCP host at it.</p>{codeblock("PYTHONPATH=MHS/sdk/src python3 -m mhs.reference conveyor --port 7400", "bash", "shell")}</div>
    </div>
    {iface_link}
  </section>

  <section class="section" id="quickstart">
    {section_head("Quickstart", "Connect, read, invoke, export", "")}
    {codeblock(quickstart, "python", "quickstart.py")}
    <div class="quickstart-notes">
      <p><strong>Receipts, not exceptions.</strong> A rejected physical action is a receipt with a stable <code>MHS.*</code> code. <code>MHSError</code> is raised only for transport, protocol or session failures, so a refusal remains evidence.</p>
      <p><strong>Deadlines are mandatory for blocking calls.</strong> The client enforces <code>deadline_ms</code>; a timeout surfaces as <code>MHS.OUTCOME.TIMEOUT</code> rather than hanging. An <code>unknown</code> outcome must be observed before retrying.</p>
    </div>
  </section>

  <section class="section" id="sdk-cli">
    {section_head("CLI", "The same surface from a shell", "Commands are thin wrappers with JSON output, intended for CI, adapters and humans debugging an endpoint.")}
    {codeblock(cli_code, "bash", "mhs")}
  </section>

  <section class="section" id="api">
    {section_head("API", "The frozen client surface", "The complete contract is OpenMHS SDK INTERFACE.md. Add new names; do not change these signatures without an RFC.")}
    <div class="table-wrap"><table><thead><tr><th scope="col">Method</th><th scope="col">Purpose</th></tr></thead><tbody>{api_html}</tbody></table></div>
    <h3>Excerpt from the frozen interface contract</h3>
    {codeblock(api_excerpt, "python", "MHS/sdk/INTERFACE.md")}
  </section>

  <section class="section" id="mcp">
    {section_head("MCP projection", "MCP supplies the tool seam. OpenMHS supplies the contract.", "The projection handles discovery, sessions and safety outside the model, then exposes each bound capability as a tool with the capability's own input schema.")}
    <div class="mcp-grid">
      <div><h3>Tool names</h3><p><code>mhs__&lt;device_slug&gt;__&lt;capability_slug&gt;</code></p><p><code>tools/call</code> maps to <code>mhs.command</code>; errors become <code>isError</code> with <code>structuredContent.mhs_error</code>. Progress maps to MCP progress notifications.</p></div>
      <div><h3>Resources</h3><p>Device resources map to <code>mhs://</code> URIs; reads return state documents, not opaque blobs. Evidence exports are resources too.</p></div>
      <div><h3>What the model sees</h3><p>Mode, risk class, fidelity gaps and trust level are part of the generated description. The projection must keep tool descriptions in sync with schemas.</p></div>
    </div>
    {codeblock("PYTHONPATH=MHS/sdk/src python3 -m mhs.mcp --endpoint http://127.0.0.1:7400", "bash", "stdio MCP server")}
    <p class="field-hint">An MCP host such as OpenAI4S launches the command above as a stdio connector and discovers tools named <code>mhs__&lt;device&gt;__&lt;capability&gt;</code>. No change to the host is required.</p>
  </section>

  <section class="section" id="interface-contract">
    {section_head("Interface contract", "Frozen for parallel build", "These names are stable across the SDK implementation. Python 3.10+, no third-party imports, no network calls in tests.")}
    <div class="convention-grid">
      <div><h3>Package</h3><p><code>MHS/sdk/src/mhs/</code> · distribution <code>openmhs</code> · import <code>mhs</code> · <code>__version__ = "{IDS.SDK_VERSION}"</code> · wire <code>MHS_VERSION = "{MHS_VERSION}"</code>.</p></div>
      <div><h3>Core modules</h3><p><code>mhs.client</code>, <code>mhs.server</code>, <code>mhs.schema</code>, <code>mhs.canonical</code>, <code>mhs.evidence</code>, <code>mhs.registry</code>, <code>mhs.cli</code>.</p></div>
      <div><h3>Bridges</h3><p><code>PythonObjectBridge</code>, <code>GymnasiumBridge</code>, <code>MujocoBridge</code>, <code>SerialBridge</code>, <code>ReplayBridge</code>.</p></div>
      <div><h3>Reference endpoints</h3><p><code>PYTHONPATH=MHS/sdk/src python3 -m mhs.reference conveyor|lab|arm --port 7400</code>; deterministic, pure Python.</p></div>
    </div>
    {docs_html}
    {readme_html}
  </section>

  <section class="section" id="sdk-status">
    {callout("SDK status", f"<p>{ 'SDK README published in this build.' if st['sdk_present'] else 'The SDK implementation is being built in parallel; this page documents the frozen interface.' } No package is presented as production-ready. A device can be exercised through the protocol today with any JSON-RPC client.</p>", "note", "package")}
    <div class="hero-actions">
      {btn("Read the wire protocol", "../spec/02-wire-protocol.html", "primary", icon=True)}
      {btn("Try the playground", "../playground/index.html", "secondary")}
    </div>
  </section>
</div>
"""
    return page_html(
        path="sdk/index.html",
        title="Reference SDK",
        description="Quickstart, CLI, Python API and MCP projection for the OpenMHS reference SDK. Stdlib-only client for stdio, HTTP and SSE endpoints.",
        body=body,
        section="sdk",
        breadcrumbs=[("SDK", "sdk/index.html")],
        og_type="article",
    )


def readme_text(sdk: SdkDocs) -> str:
    return read_text(sdk.readme) if sdk.readme else ""



# ---------------------------------------------------------------------------
# Pages: relation to Anthropic's MHS research preview (secondary page)
# ---------------------------------------------------------------------------


def anthropic_page(ctx) -> str:
    p = "../"
    adopt = [
        ("Integration-cost framing", "Bespoke integration is the bottleneck; a shared driver layer removes the N×M translator problem."),
        ("Physical knowledge as data", "A device's physical characteristics belong in machine-readable metadata, not in manuals or tacit knowledge."),
        ("Natural-language tags", "User-authored tags are first-class data; an agent may interview the operator to elicit them."),
        ("Generated reference view", "Every device gets a generated, model-readable view of what it measures, adjusts and enforces (here: the device profile)."),
        ("Three control surfaces", "MCP, a CLI and a code API are used together (here: transport bindings T4/T5/T6)."),
        ("Code files for long work", "Chaining commands into deterministic code escapes the per-step reasoning loop (here: versioned compositions with child receipts)."),
    ]
    define = [
        ("Wire protocol", "JSON-RPC 2.0, framing, deadlines, cancellation and a stable error taxonomy."),
        ("Receipts and evidence", "Command ids, revisions, canonical state hashes, hash-chained evidence verifiable offline."),
        ("Enforced safety envelope", "Risk classes, limits, interlocks, single-use permits bound to the input digest, latching e-stop."),
        ("Simulation as a mode", "A mandatory declared fidelity contract; no silent sim/hardware switching."),
        ("Adapter and bridge model", "Declarative manifests plus reusable bridges for existing SDKs and simulators."),
        ("Executable conformance", "CL0–CL5, suite-produced digest-addressed reports instead of prose claims."),
    ]
    reject = [
        ("Free-form writable global state dictionary", "breaks least privilege and auditability; mutations stay capability- and receipt-scoped."),
        ("Shared memory as the core transport", "OpenMHS is a supervisory contract, not a real-time bus; memory-speed is a deployment property."),
        ("Auto-published model-authored drivers", "registry admission requires review, evidence and trust."),
        ("Model-side safety claims", "OpenMHS conformance is endpoint behaviour; model evaluations are outside the specification."),
    ]
    claims_table = [
        ("Standardized driver with read/write primitives", "Announcement", "A driver translates the OS to a device and exposes read/write-style primitives. Wire format not stated."),
        ("Standard discovery across networks", "Announcement", "Devices and agents find each other in a standard format. Protocol and scope not stated."),
        ("Tags → automatically generated reference file", "Announcement", "Tags in natural language produce a file describing measures, adjustments and enforced limits. Format not stated."),
        ("Three control mechanisms", "Announcement", "MCP, CLI and code files work together for orchestration via a single line of code."),
        ("Code files chain driver commands", "Announcement", "Long-running work runs in code files without per-step model reasoning."),
        ("Shared-memory dictionary at memory speed", "Announcement (origin)", "The Janelia origin was a shared memory dictionary; its relationship to network discovery is not stated."),
        ("Safety enforced at the hardware interface", "QuEra write-up", "Device-declared bounds, interlocks and e-stops enforced independently of the model. Enforcement code location not specified."),
        ("Out-of-range arm motion refused", "Documentary (chapter 4:30)", "After an operator defines a safe range, an out-of-range command is shown being refused. Timestamp cannot be re-derived (timed captions blocked)."),
        ("Six induced fault conditions blocked", "CMU case study", "Missing plate, e-stop and other conditions blocked before motion. Six conditions are described in prose."),
        ("Devices without a programmable interface unsupported", "Announcement", "Explicit current limitation; GUI-only devices are driven through GUI automation instead."),
    ]
    partners = [
        ("Genentech", "proof-of-concept BCA assay across liquid handler, robotic arm and plate reader; closed-loop flow-rate optimisation"),
        ("HHMI Janelia", "origin rig, shared-memory dictionary, live microscope control"),
        ("QuEra", "laser relock and PID tuning on quantum hardware; strongest written safety statement"),
        ("Tetsuwan", "ResearchOS replaced its scheduler and driver stack with MHS commands; one connector per instrument"),
        ("CMU", "six instruments, drivers built with an agent exploring vendor interfaces, GUI-only plate reader"),
        ("Danaher / Leica", "actively exploring MHS support for smart instruments"),
        ("QIAGEN", "working proof-of-concept on QIAsymphony Connect"),
        ("Tecan", "adding MHS support for Fluent liquid handlers"),
        ("Universal Robots", "early access; plans to add support"),
        ("MBF Bioscience", "building an MHS driver for ScanImage"),
        ("AWS", "will support MHS through Strands Robots (private pre-release)"),
        ("Automata", "adding MHS support to LINQ"),
        ("Doosan Robotics", "testing MHS with robotic arms"),
        ("Hugging Face", "adding MHS support in LeRobot"),
        ("Raspberry Pi", "enabling MHS integration after Camera MHS Driver tests"),
    ]
    claims_html = "".join(
        f"<tr><td>{esc(claim)}</td><td>{esc(source)}</td><td>{esc(detail)}</td></tr>"
        for claim, source, detail in claims_table
    )
    partners_html = "".join(
        f"<tr><td><strong>{esc(name)}</strong></td><td>{esc(claim)}</td></tr>"
        for name, claim in partners
    )
    adopt_html = "".join(f"<li><strong>{esc(title)}</strong> — {esc(text)}</li>" for title, text in adopt)
    define_html = "".join(f"<li><strong>{esc(title)}</strong> — {esc(text)}</li>" for title, text in define)
    reject_html = "".join(f"<li><strong>{esc(title)}</strong> — {esc(text)}</li>" for title, text in reject)
    body = f"""
<div class="wrap">
  {breadcrumbs_html(p, [("Background", None), (ANTHROPIC_PAGE_LABEL, None)])}
  <header class="page-hero">
    <p class="eyebrow">Background · not affiliated with Anthropic</p>
    <h1>{esc(ANTHROPIC_PAGE_LABEL)}</h1>
    <p class="page-lead">Anthropic opened a research preview of its Model Hardware Standard (MHS) in August 2026. OpenMHS is a separate, independent project. This page summarises what the preview's public sources describe — the announcement, the landing page, partner write-ups and the two Anthropic videos — separates verified facts from claims that were never published, and states how OpenMHS relates to it.</p>
    <div class="package-badges">{badge("Research preview", "info")}{badge("Apply-only", "warn")}{badge("No public wire spec", "warn")}{badge("Independently reconstructed", "good")}</div>
  </header>

  <section class="section" id="how">
    <div class="split-head">
      {section_head("How it is described", "A standardized driver, tags, and three control surfaces", "The public description is consistent across the announcement and the videos; the wire-level detail is not published.")}
      <a class="text-link split-link" href="{p}spec/appendix-d-anthropic-mhs.html">Full appendix {ICONS['arrow']}</a>
    </div>
    <div class="grid-3">
      <div class="card"><h3>1 · Standardized driver</h3><p>“Software that translates between a computer’s operating system and a hardware device”, using simple primitives such as <em>read</em> (“get temperature”) and <em>write</em> (“set temperature”).</p></div>
      <div class="card"><h3>2 · Standard discovery</h3><p>Devices become “discoverable in a standard format, so that devices and agents can find each other and communicate across networks” without a bespoke translator.</p></div>
      <div class="card"><h3>3 · Tags become a reference file</h3><p>Users write natural-language tags (or an agent interviews them). The driver “automatically produces a reference file” describing what the device measures, what can be adjusted and which safety limits are enforced.</p></div>
      <div class="card"><h3>4 · Three mechanisms</h3><p>“MCP, the command line interface, and code files (APIs). These work together to enable orchestration across multiple devices via a single line of code.”</p></div>
      <div class="card"><h3>5 · Code files for long work</h3><p>The agent can “chain together driver commands from one or more devices in code files”, so hardware runs without the model reasoning at every step. Learning is captured as a deterministic script.</p></div>
      <div class="card"><h3>6 · Origin: shared memory</h3><p>The collaboration began at HHMI Janelia with a shared memory dictionary that let instruments “communicate … at memory speed”. How this relates to network-wide discovery is not stated.</p></div>
    </div>
  </section>

  <section class="section section-tint" id="video">
    {section_head("What the videos add", "A short film and an 11-minute documentary", "Video facts are cited as video facts. The short film is <code>UxJZrCFzTHY</code> (2:13); the documentary with the demonstrations is <code>P1zBiAQU1IA</code> (11:10), chapters 0:00 · 0:47 · 2:38 · 4:30 · 6:14 · 8:11. Timed captions were not retrievable, so timestamps are chapter-level or approximate.")}
    <div class="table-wrap"><table><thead><tr><th scope="col">Demonstration</th><th scope="col">What it shows</th><th scope="col">Mechanism it illustrates</th></tr></thead><tbody>
      <tr><td>Janelia microscope</td><td>Custom multiphoton rig with lasers, focusers and cameras from different vendors; the first MHS layer is used to control stage and laser remotely.</td><td>Driver + read/write primitives on a heterogeneous rig.</td></tr>
      <tr><td>Robotic arm safe range</td><td>Operator defines the arm’s safe range; an out-of-range command is refused by MHS, then a first-time grasp task is attempted.</td><td>Safety limits enforced below the agent (asserted; location not specified).</td></tr>
      <tr><td>Leica microscope</td><td>Claude focuses, moves around the sample, changes magnification mindful of crashing into the sample, captures and interprets stained tissue.</td><td>Closed-loop read → decide → write on a precision instrument.</td></tr>
      <tr><td>Diatom tracking</td><td>Claude writes a tracking script; after the first attempt fails it adds a live UI and tracks a swimming organism for minutes.</td><td>Agent-synthesized code file becoming the runtime controller.</td></tr>
      <tr><td>Genentech liquid handling</td><td>Claude runs transfers, reads absorbance, detects bubbles in wells and adjusts flow-rate parameters in a closed loop.</td><td>Multi-device read → decide → write; error recovery with human guidance.</td></tr>
    </tbody></table></div>
    <p class="section-note">The videos also use marketing language (“recovered even overnight”, “first time in history”) that the written material qualifies: Genentech reports that bubble failures needed human guidance because the model first treated a physical failure as a software retry.</p>
  </section>

  <section class="section" id="safety">
    {section_head("Safety: asserted vs specified", "A strong claim, a thin specification", "The preview asserts enforcement below the agent; it does not publish the enforcement model.")}
    <div class="table-wrap"><table><thead><tr><th scope="col">Claim</th><th scope="col">Source</th><th scope="col">What is stated</th></tr></thead><tbody>{claims_html}</tbody></table></div>
    {callout("What is not published", "<p>No wire format, no manifest schema, no message set, no reference SDK, no MCP tool naming, no receipt or evidence format, no error taxonomy, no conformance levels, no simulation story, no versioning or governance, and no licence. These are the parts this specification defines rather than inherits.</p>", "warn", "alert")}
  </section>

  <section class="section section-tint" id="ecosystem">
    {section_head("Early ecosystem", "Who was named, and how strongly", "Modality matters: case studies are proof-of-concept, pilots and demos; vendors range from exploring and testing to adding and building.")}
    <div class="table-wrap"><table><thead><tr><th scope="col">Partner</th><th scope="col">As described in the announcement</th></tr></thead><tbody>{partners_html}</tbody></table></div>
  </section>

  <section class="section" id="relationship">
    {section_head("How OpenMHS relates", "Adopt the framing, define the contract, reject the unsafe shortcuts", f"OpenMHS {SPEC_VERSION} starts from the same problem statement and is independent of the preview: it is not a reimplementation, a compatible dialect, or an endorsed continuation.")}
    <div class="grid-3">
      <div class="card"><h3>Adopted</h3><ul class="tick-list">{adopt_html}</ul></div>
      <div class="card"><h3>Defined here</h3><ul class="tick-list">{define_html}</ul></div>
      <div class="card"><h3>Deliberately rejected</h3><ul class="disclaimer-list">{reject_html}</ul></div>
    </div>
  </section>

  <section class="section" id="claims">
    {section_head("Claims this project will not make", "Boundaries that keep the analysis honest", "The preview is closed, apply-only and has no public wire specification; no artefact here may imply otherwise.")}
    <ul class="disclaimer-list">
      <li>Compatibility with, or endorsement by, Anthropic or the MHS research preview.</li>
      <li>Implementing the preview's (unpublished) wire format or driver API.</li>
      <li>Having received preview access, or speaking for any named partner.</li>
      <li>That OpenMHS conformance is a safety evaluation or a safety certification.</li>
      <li>That any vendor named in the preview supports OpenMHS.</li>
      <li>That “memory-speed” or “bare-metal speed” is an OpenMHS guarantee.</li>
    </ul>
  </section>

  <section class="section" id="sources">
    {section_head("Sources", "Fetched and checked on 2026-10-20", "Per-claim quotes, transcript status and gap analysis are kept with the specification sources.")}
    <ul class="aside-links">
      <li><a href="https://www.anthropic.com/news/model-hardware-standard-research-preview" rel="noopener">Anthropic — Previewing the Model Hardware Standard (Aug 27, 2026)</a></li>
      <li>The research-preview landing page operated by Anthropic (its address is cited in the appendix below; it is not this project's site)</li>
      <li><a href="https://www.youtube.com/watch?v=UxJZrCFzTHY" rel="noopener">Short film — Model Hardware Standard: AI operating physical equipment (2:13)</a></li>
      <li><a href="https://www.youtube.com/watch?v=P1zBiAQU1IA" rel="noopener">Documentary — AI models can now help run physical science experiments (11:10)</a></li>
      <li><a href="https://tetsuwan.com/blog/mhs" rel="noopener">Tetsuwan — integrating MHS into ResearchOS</a></li>
      <li><a href="https://www.quera.com/blog-posts/holding-the-light-teaching-an-ai-to-lock-and-tune-our-quantum-computers-lasers" rel="noopener">QuEra — holding the light: AI, lasers and MHS</a></li>
      <li><a href="{p}spec/appendix-d-anthropic-mhs.html">Appendix D — the relationship appendix, with per-claim sources</a></li>
    </ul>
  </section>
</div>
"""
    return page_html(
        path="anthropic-mhs/index.html",
        title=ANTHROPIC_PAGE_LABEL,
        description="How the independent OpenMHS project relates to Anthropic's Model Hardware Standard research preview: what the preview's public sources describe, what OpenMHS adopts, and what it does not claim.",
        body=body,
        section="anthropic",
        breadcrumbs=[("Background", None), (ANTHROPIC_PAGE_LABEL, None)],
        og_type="article",
    )


# ---------------------------------------------------------------------------
# Pages: OpenAI4S host profile
# ---------------------------------------------------------------------------


def host_page(ctx) -> str:
    p = "../../"
    one_call = """from mhs import connect

with connect("mhs://localhost:7400") as lab:              # one transport
    dev = lab.devices[0]                                   # one discovery
    receipt = lab.invoke(                                  # one command
        "cap.world.step.v1", {"ticks": 120}, device_id=dev["device_id"])
    state = lab.read("workcell")                           # one read
    evidence = lab.export_evidence()                       # one ledger
    print(receipt["status"], receipt["state_hash_after"], evidence["head_digest"])"""
    ledger = """receipt_i.evidence.digest =
    sha256( JCS(receipt_i \\ { evidence }) || receipt_(i-1).evidence.digest )

genesis = endpoint genesis record
head    = digest of the latest receipt
verify  = recompute the chain offline; no endpoint trust required"""
    reqs = [
        "Discover endpoints from every configured source and authenticate them.",
        "Open least-privilege sessions and refresh or close them correctly.",
        "Obtain approvals before calling capabilities that require a permit.",
        "Present mode, fidelity gaps, risk class and trust level to the model.",
        "Enforce deadlines and cancellation; never retry an unknown outcome blindly.",
        "Record every receipt in an append-only evidence ledger; export and verify it.",
        "Never claim or imply that OpenMHS replaces hardware safety.",
        "Expose capabilities through MCP tools, native tools or a code API, with schemas in sync.",
    ]
    req_html = "".join(f'<li><span class="tick">{ICONS["check"]}</span>{esc(r)}</li>' for r in reqs)
    mapping_rows = [
        ("<code>openai4s_mhs/config.py</code>", "Settings: <code>enabled</code> (default <code>false</code>), endpoints, hardware gate, evidence log; atomic 0600 writes."),
        ("<code>openai4s_mhs/experimental.py</code>", "Records the experimental <code>skill/mhs</code> capability in OpenAI4S's own capability store so the switch is visible in settings."),
        ("<code>openai4s_mhs/host.py</code>", "<code>MHSHost</code>: discovery, least-privilege sessions, permits, evidence ledger, mode and fidelity disclosure, hardware gate."),
        ("<code>openai4s_mhs/tools.py</code>", "Eight native tools + dispatcher wiring, installed <em>only when enabled</em>; disabled install registers nothing."),
        ("<code>openai4s_mhs/mcpconfig.py</code>", "MCP companion: one stdio connector per endpoint (<code>mhs.mcp</code>), emitted only while the skill is enabled."),
        ("<code>mhs.mcp</code>", "MCP projection of any OpenMHS endpoint; OpenAI4S's existing <code>MCPManager</code> needs no host change."),
    ]
    mapping_html = "".join(f"<tr><td>{a}</td><td>{b}</td></tr>" for a, b in mapping_rows)
    mcp_config = """// OpenAI4S connector settings — one ordinary MCP connector per endpoint
{"connectors": [{
  "id": "mhs-lab",
  "command": ["python3", "-m", "mhs.mcp",
              "--endpoint", "http://127.0.0.1:7401"],
  "transport": "stdio",
  "enabled": false          // experimental: off until the operator enables it
}]}"""
    native_install = """# Optional developer overlay (not the integration path; same switch)
PYTHONPATH=MHS/sdk/src:integration/openai4s python3 -c \
  "import openai4s_mhs as m; m.install(m.MHSConfig(enabled=True))"
python3 -m openai4s_mhs devices --endpoint http://127.0.0.1:7400"""
    gate = """# experimental MCP integration — connector rows are listed, disabled by default
python3 -m openai4s_mhs status    # {"kind": "mcp", "enabled": false, "experimental": true}
python3 -m openai4s_mhs mcp-config --json
#   -> {"connectors": [...], "enabled": false, "transport": "mcp"}
python3 -m openai4s_mhs enable    # operator action: flips the connector rows + settings on
python3 -m openai4s_mhs disable   # and back off again

# while disabled:
#   - the MCP connector is not activated; no projected mhs__* tool is reachable
#   - no endpoint connection is opened by the feature
#   - the rows stay visible in settings with "enabled": false so a human can turn them on
# enabling is the same switch for MCP and for the optional developer overlay."""
    native_tools = [
        ("mhs__devices / mhs__inspect", "Discover endpoints and fetch full device manifests with mode, risk and fidelity gaps."),
        ("mhs__read", "Read a resource revision and state hash."),
        ("mhs__<device>__<capability>", "One tool per bound capability, device-scoped; returns a receipt (rejections included)."),
        ("mhs__permit", "Request a single-use permit bound to the exact input digest."),
        ("mhs__safety / mhs__estop / mhs__reset", "Read status, latch the e-stop, reset once interlocks are clear."),
        ("mhs__operations", "Inspect or cancel an operation without blocking the loop."),
        ("mhs__evidence", "Export and verify the hash-chained evidence bundle."),
    ]
    tools_html = "".join(f"<li><code>{esc(name)}</code><span>{esc(desc)}</span></li>" for name, desc in native_tools)
    body = f"""
<div class="wrap">
  {breadcrumbs_html(p, [("Hosts", None), ("OpenAI4S", None)])}
  <header class="page-hero">
    <p class="eyebrow">Reference host · OpenAI4S</p>
    <h1>One host path. One evidence ledger.</h1>
    <p class="page-lead">The host is where an agent meets the contract. OpenAI4S is the reference host: it discovers endpoints, opens least-privilege sessions, surfaces mode and risk, obtains approvals and records every receipt.</p>
    <div class="package-badges">{badge("Normative mapping", "good")}{badge("MHS-Host profile", "info")}{badge("MCP-first, verified", "good")}</div>
  </header>

  <section class="section" id="paths">
    <div class="split-head">
      {section_head("Integration paths", "Zero-patch MCP today, native tools next", "The integration design deliberately separates an interoperability proof from the first-class host path. Both speak the same contract; neither changes the endpoint.")}
      <a class="text-link split-link" href="DESIGN.md">Read the integration design {ICONS['arrow']}</a>
    </div>
    <div class="path-grid">
      <div class="path-card">
        <div class="path-head"><span class="path-letter">MCP</span><div><h3>Primary integration — MCP projection</h3><p>The SDK ships a stdio MCP server (<code>python -m mhs.mcp</code>). It is registered as an ordinary OpenAI4S connector; tools are generated from bound capabilities and every call goes through OpenMHS sessions, permits and receipts.</p></div></div>
        {codeblock(mcp_config, "json", "mcp.json")}
        <p class="field-hint">The endpoint owns sessions, permits and receipts. MCP only supplies the tool seam.</p>
      </div>
      <div class="path-card">
        <div class="path-head"><span class="path-letter">dev</span><div><h3>Optional developer overlay</h3><p>A stdlib overlay registers the same host surface as native tools for CLI debugging. It is not required for host conformance and is gated by the same experimental switch.</p></div></div>
        {codeblock(native_install, "bash", "install")}
        <ul class="tool-list">{tools_html}</ul>
      </div>
    </div>
  </section>

  <section class="section" id="one-call">
    <div class="split-head">
      {section_head("The one-call property", "The same code path for every endpoint", "No per-repository branches in the host. The differences live in the adapter plane: a Rust conveyor, a Python simulator, a MuJoCo arm or a microscope all arrive through the same client.")}
      <a class="text-link split-link" href="../../spec/09-host-profile.html">Host profile {ICONS['arrow']}</a>
    </div>
    {codeblock(one_call, "python", "openai4s_one_call.py")}
  </section>

  <section class="section section-tint" id="architecture">
    {section_head("Architecture", "Four planes, one loop", "The host owns policy, approvals and the ledger. The endpoint owns enforcement. The adapter owns translation. The equipment is never trusted to interpret intent.")}
    <div class="arch-desktop" role="img" aria-label="Architecture: the OpenAI4S host reaches the OpenMHS contract plane through stdio, HTTP/SSE or the MCP projection; the contract plane reaches equipment through adapters and bridges; receipts flow back into the host evidence ledger.">
      <svg viewBox="0 0 980 330" xmlns="http://www.w3.org/2000/svg">
        <title>OpenMHS host architecture</title>
        <defs>
          <marker id="arrowhead" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="currentColor"/></marker>
        </defs>
        <rect class="diag-bg" x="0" y="0" width="980" height="330" rx="16"/>
        <g class="diag-box diag-host"><rect x="24" y="56" width="238" height="160" rx="10"/><text x="42" y="84" class="diag-kicker">HOST PLANE</text><text x="42" y="110" class="diag-title">OpenAI4S</text><text x="42" y="132" class="diag-text">agent loop · tools · kernel</text><text x="42" y="150" class="diag-text">policy · approvals</text><text x="42" y="168" class="diag-text">evidence ledger</text><rect x="42" y="184" width="200" height="20" rx="4" class="diag-chip"/><text x="50" y="198" class="diag-chip-text">MHS-Host profile · CL1–CL5</text></g>
        <g class="diag-box diag-binding"><rect x="294" y="56" width="180" height="160" rx="10"/><text x="312" y="84" class="diag-kicker">BINDING PLANE</text><text x="312" y="110" class="diag-title">JSON-RPC</text><text x="312" y="132" class="diag-text">stdio · HTTP/SSE · WS</text><text x="312" y="150" class="diag-text">MCP projection</text><text x="312" y="168" class="diag-text">CLI · code API</text></g>
        <g class="diag-box diag-contract"><rect x="504" y="40" width="238" height="192" rx="10"/><text x="522" y="68" class="diag-kicker">CONTRACT PLANE</text><text x="522" y="94" class="diag-title">OpenMHS endpoint</text><text x="522" y="116" class="diag-text">devices · resources · capabilities</text><text x="522" y="134" class="diag-text">sessions · commands · receipts</text><text x="522" y="152" class="diag-text">safety envelope · permits</text><text x="522" y="170" class="diag-text">revisions · state hashes</text><text x="522" y="188" class="diag-text">evidence hash chain</text><rect x="522" y="202" width="202" height="20" rx="4" class="diag-chip"/><text x="530" y="216" class="diag-chip-text">enforced by the endpoint</text></g>
        <g class="diag-box diag-adapter"><rect x="772" y="56" width="184" height="78" rx="10"/><text x="790" y="82" class="diag-kicker">ADAPTER PLANE</text><text x="790" y="104" class="diag-title">Manifest + bridge</text><text x="790" y="122" class="diag-text">declarative mapping</text></g>
        <g class="diag-box diag-equipment"><rect x="772" y="154" width="184" height="78" rx="10"/><text x="790" y="180" class="diag-kicker">EQUIPMENT PLANE</text><text x="790" y="202" class="diag-title">Driver · simulator</text><text x="790" y="220" class="diag-text">SDK · transport · physics</text></g>
        <g class="diag-arrow" color="currentColor"><line x1="262" y1="136" x2="288" y2="136" marker-end="url(#arrowhead)"/><line x1="474" y1="136" x2="498" y2="136" marker-end="url(#arrowhead)"/><line x1="742" y1="112" x2="766" y2="112" marker-end="url(#arrowhead)"/><line x1="742" y1="190" x2="766" y2="190" marker-end="url(#arrowhead)"/><line x1="864" y1="134" x2="864" y2="148" marker-end="url(#arrowhead)"/></g>
        <g class="diag-ledger"><rect x="24" y="254" width="932" height="52" rx="10"/><text x="42" y="276" class="diag-kicker">EVIDENCE LOOP</text><text x="42" y="295" class="diag-text">every receipt → append-only ledger → export → offline verification of the hash chain</text><path d="M623 232 L623 248" class="diag-arrow-line" marker-end="url(#arrowhead)"/><text x="640" y="278" class="diag-chip-text">session summary</text><text x="640" y="295" class="diag-chip-text">receipts · telemetry refs</text></g>
      </svg>
    </div>
    <div class="arch-mobile">
      <div class="arch-stack"><span class="diag-kicker">Host</span><h3>OpenAI4S</h3><p>Agent loop, tools, policy, approvals and the evidence ledger.</p></div>
      <div class="arch-down" aria-hidden="true">↓</div>
      <div class="arch-stack"><span class="diag-kicker">Binding</span><h3>JSON-RPC</h3><p>stdio, HTTP/SSE, WebSocket, MCP projection, CLI and code API.</p></div>
      <div class="arch-down" aria-hidden="true">↓</div>
      <div class="arch-stack arch-stack-contract"><span class="diag-kicker">Contract</span><h3>OpenMHS endpoint</h3><p>Sessions, commands, receipts, safety envelope, revisions and evidence chain — enforced by the endpoint.</p></div>
      <div class="arch-down" aria-hidden="true">↓</div>
      <div class="arch-stack"><span class="diag-kicker">Adapter / equipment</span><h3>Manifest and bridge</h3><p>Declarative mapping to a driver, SDK, simulator or protocol.</p></div>
    </div>
  </section>

  <section class="section" id="evidence">
    <div class="split-head">
      {section_head("Evidence", "The ledger is not optional", "A host that records only successes cannot explain a refusal or an unknown outcome. Every receipt is appended, chained and exportable.")}
      <a class="text-link split-link" href="../../spec/04-safety.html#8-audit-and-evidence-chain">Evidence chain specification {ICONS['arrow']}</a>
    </div>
    <div class="evidence-layout">
      <div>{codeblock(ledger, "text", "hash chain")}</div>
      <div class="evidence-points">
        <div><h3>Receipts, including refusals</h3><p>Accepted, failed, rejected and unknown outcomes are all receipts. A policy refusal is evidence of the envelope working, not an exception to log away.</p></div>
        <div><h3>Offline verification</h3><p>The bundle carries receipts, endpoint metadata and the head digest. A verifier re-derives the chain without trusting the endpoint.</p></div>
        <div><h3>Redaction is declared</h3><p>Adapters declare redaction rules for credentials and PII. Evidence must not contain secrets; telemetry travels by reference, not by copy.</p></div>
        <div><h3>Retention</h3><p>Receipts are retained for at least 30 days by default and are not deletable through the protocol without a truncation marker.</p></div>
      </div>
    </div>
  </section>

  <section class="section" id="experimental">
    <div class="split-head">
      {section_head("Experimental MCP connector", "Off by default, enabled by the operator", "OpenMHS is an experimental MCP integration: the connector rows are listed in settings but disabled, so no projected tool and no endpoint connection exist until a human turns the feature on. Enabling is an explicit, recorded operator action.")}
      <a class="text-link split-link" href="../../spec/09-host-profile.html#82-experimental-surfaces-must-be-off-by-default">HOST-066…069 {ICONS['arrow']}</a>
    </div>
    <div class="dual-panel">
      <div>{codeblock(gate, "bash", "settings")}</div>
      <div class="stack">
        <div class="callout callout-warn"><div class="callout-icon"><strong aria-hidden="true">!</strong></div><div><p class="callout-title">Experimental — not a default capability</p><div class="callout-body"><p>Installation, upgrade, endpoint discovery or first launch never enable MHS. The switch is an explicit operator action recorded in settings (and in OpenAI4S's capability state as <code>skill/mhs</code>).</p></div></div></div>
        <div class="evidence-points">
          <div><h3>Default off, fail closed</h3><p>While disabled the host registers no <code>mhs_*</code> tool, emits no MCP connector and opens no endpoint connection. The model is not told that OpenMHS exists.</p></div>
          <div><h3>MCP companion</h3><p>Enabled, the same switch exposes both surfaces: native tools for code-as-action and an stdio MCP connector per endpoint for a generic MCP harness.</p></div>
          <div><h3>Operator tooling stays explicit</h3><p>The <code>python3 -m openai4s_mhs</code> CLI remains available to a human for diagnostics, but it is never auto-invoked by the agent.</p></div>
        </div>
      </div>
    </div>
  </section>

  <section class="section" id="requirements">
    {section_head("Host requirements", "What MHS-Host actually requires", "A host is conformant on behaviour, not intent. These are the obligations from the host profile, including the experimental-surface rules (HOST-066…069).")}
    <ul class="checklist-list">{req_html}</ul>
  </section>

  <section class="section section-tint" id="mapping">
    {section_head("OpenAI4S mapping", "Where each responsibility lives", "The overlay package sits beside OpenAI4S; the only patch is tool registration. The MCP fallback avoids even that.")}
    <div class="table-wrap"><table><thead><tr><th scope="col">Component</th><th scope="col">Responsibility</th></tr></thead><tbody>{mapping_html}</tbody></table></div>
    <div class="mcp-note">
      <h3>MCP is the integration seam</h3>
      <p>MCP standardises how a model reaches tools; OpenMHS standardises what a tool that moves matter <em>means</em> — mode, units, limits, interlocks, receipts and evidence. The projection maps each bound capability into an MCP tool and maps refusals back to structured OpenMHS codes; sessions, permits and the safety envelope stay inside the endpoint, outside the model.</p>
    </div>
  </section>

  <section class="section" id="host-status">
    {callout("Status", "<p>MHS-009 is host-neutral; its Annex A describes the OpenAI4S mapping informatively. The overlay package is implemented in this repository and verified by its own suite and acceptance demo; this site does not claim it is published to a package index. The playground is a browser reference model of an endpoint, not the host integration.</p>", "note", "package")}
    <div class="hero-actions">
      {btn("Try the endpoint playground", "../../playground/index.html", "primary", icon=True)}
      {btn("Read the host profile", "../../spec/09-host-profile.html", "secondary")}
    </div>
  </section>
</div>
"""
    return page_html(
        path="hosts/openai4s/index.html",
        title="OpenAI4S host",
        description="The OpenAI4S reference host for OpenMHS: one-call client path, plane architecture, MCP projection, approvals and an append-only evidence ledger.",
        body=body,
        section="hosts",
        breadcrumbs=[("Hosts", None), ("OpenAI4S", None)],
        og_type="article",
    )


# ---------------------------------------------------------------------------
# Pages: playground
# ---------------------------------------------------------------------------

DEFAULT_REQUEST = {
    "jsonrpc": "2.0",
    "id": "req-hello",
    "method": "mhs.hello",
    "params": {
        "client": {"name": "mhs-playground", "version": "1.0"},
        "protocol_versions": ["1.0"],
        "features": ["batch"],
    },
}

SCENARIOS = [
    ("hello", "Discovery", "Hello", "Negotiate the protocol and list devices."),
    ("devices", "Discovery", "List devices", "Return the device summaries."),
    ("get", "Discovery", "Get manifest", "Fetch the full device manifest."),
    ("read", "Observe", "Read state", "Read the workcell resource and its state hash."),
    ("step", "Act", "Advance 120 ticks", "Send a receipted command with a fixed command id."),
    ("duplicate", "Act", "Duplicate command id", "Repeat the same command id; the receipt is replayed."),
    ("stale", "Act", "Stale revision", "Expect a revision conflict, with no effect."),
    ("interlock", "Safety", "Open door → command", "Open the safety door outside OpenMHS, then attempt a command."),
    ("safety", "Safety", "Safety status", "Read interlocks, e-stop and the safe state."),
    ("estop", "Safety", "Engage e-stop", "Latch the e-stop through the OpenMHS safety method."),
    ("evidence", "Evidence", "Export evidence", "Export the hash-chained receipt bundle."),
]


def playground_page(ctx) -> str:
    p = "../"
    scenario_buttons = []
    current_group = ""
    for key, group, label, desc in SCENARIOS:
        if group != current_group:
            if current_group:
                scenario_buttons.append("</div>")
            scenario_buttons.append(f'<div class="scenario-group"><p class="scenario-group-label">{esc(group)}</p>')
            current_group = group
        scenario_buttons.append(
            f'<button type="button" class="scenario-btn" data-scenario="{attr(key)}" title="{attr(desc)}">{esc(label)}</button>´'.replace("´", "")
        )
    if current_group:
        scenario_buttons.append("</div>")
    default_json = json.dumps(DEFAULT_REQUEST, indent=2)
    body = f"""
<div class="wrap">
  {breadcrumbs_html(p, [("Playground", None)])}
  <header class="page-hero page-hero-playground">
    <div class="playground-hero-grid">
      <div>
        <p class="eyebrow"><span class="status-dot"></span> Interactive reference model</p>
        <h1>Talk to a mock OpenMHS endpoint</h1>
        <p class="page-lead">A deterministic conveyor workcell in your browser. Send JSON-RPC requests, watch receipts, open an interlock, reuse a command id, latch an e-stop and export the evidence chain. Nothing leaves this page.</p>
        <div class="package-badges">{badge("Reference model — not a real device", "warn")}{badge("No network requests", "info")}{badge("State resets on reload", "muted")}</div>
      </div>
      <div class="playground-notice">
        <strong>This is a teaching model.</strong>
        <p>It implements a deliberately small, readable subset of OpenMHS to show command semantics. It is not conformance-tested, not a safety-rated channel, and not connected to equipment. Do not use it to drive anything physical.</p>
      </div>
    </div>
  </header>

  <div class="playground-workbench">
    <section class="playground-request" aria-labelledby="request-heading">
      <div class="panel-head">
        <h2 id="request-heading">Request</h2>
        <div class="request-actions">
          <button type="button" class="link-btn" id="format-json">Format</button>
          <button type="button" class="link-btn" id="reset-request">Reset</button>
        </div>
      </div>
      <div class="scenario-groups" aria-label="Quick scenarios">{''.join(scenario_buttons)}</div>
      <label class="sr-only" for="request-editor">JSON-RPC request</label>
      <textarea id="request-editor" class="code-editor" spellcheck="false" autocomplete="off" aria-describedby="request-hint">{esc(default_json)}</textarea>
      <p class="field-hint" id="request-hint">Edit the JSON directly. The mock understands <code>mhs.hello</code>, <code>devices.list</code>, <code>devices.get</code>, <code>resource.read</code>, <code>command</code>, <code>safety.status</code>, <code>safety.estop</code>, <code>safety.reset</code>, <code>session.open</code> and <code>evidence.export</code>.</p>
      <div class="request-footer">
        <p class="request-error" id="request-error" role="alert" hidden></p>
        <button type="button" class="btn btn-primary" id="send-request">Send request <span class="kbd">⌘↵</span></button>
      </div>
    </section>

    <section class="playground-response" aria-labelledby="response-heading">
      <div class="panel-head">
        <h2 id="response-heading">Response</h2>
        <p class="response-status" id="response-status" aria-live="polite">Ready.</p>
      </div>
      <div class="response-meta">
        <span id="response-method">mhs.hello</span>
        <span id="response-code">—</span>
        <span id="response-mode">simulated</span>
      </div>
      <pre tabindex="0" class="response-pre"><code id="response-json">{{}}</code></pre>
      <div class="receipt-card" id="receipt-card" hidden>
        <div class="receipt-head"><span>Receipt</span><span id="receipt-status" class="receipt-status">completed</span></div>
        <dl class="receipt-facts">
          <div><dt>Command</dt><dd><code id="receipt-command">—</code></dd></div>
          <div><dt>Revision</dt><dd id="receipt-revision">—</dd></div>
          <div><dt>State hash</dt><dd><code id="receipt-hash">—</code></dd></div>
          <div><dt>Evidence seq</dt><dd id="receipt-seq">—</dd></div>
          <div><dt>Replayed</dt><dd id="receipt-replayed">no</dd></div>
        </dl>
        <p class="receipt-note" id="receipt-note"></p>
      </div>
    </section>
  </div>

  <div class="playground-lower">
    <section class="state-panel" aria-labelledby="state-heading">
      <div class="panel-head"><h2 id="state-heading">Endpoint state</h2><span class="live-dot">live</span></div>
      <div class="state-tiles">
        <div><span class="state-label">Tick</span><strong id="state-tick">0</strong><small>ms simulated</small></div>
        <div><span class="state-label">Revision</span><strong id="state-revision">7</strong><small>monotone uint64</small></div>
        <div><span class="state-label">Door</span><strong id="state-door">closed</strong><small>interlock</small></div>
        <div><span class="state-label">E-stop</span><strong id="state-estop">released</strong><small>latched when engaged</small></div>
        <div><span class="state-label">Parts</span><strong id="state-parts">1</strong><small>on the conveyor</small></div>
        <div><span class="state-label">Evidence</span><strong id="state-evidence">0</strong><small>receipts chained</small></div>
      </div>
      <div class="operator-panel">
        <p class="operator-label">Operator controls <span>(outside OpenMHS)</span></p>
        <div class="operator-actions">
          <button type="button" class="btn btn-secondary btn-sm" id="toggle-door">Open safety door</button>
          <button type="button" class="btn btn-secondary btn-sm" id="reset-model">Reset model</button>
        </div>
        <p class="field-hint">The door is a physical interlock. Toggling it changes the world but is not an OpenMHS command; the next command is refused while it is open.</p>
      </div>
    </section>

    <section class="log-panel" aria-labelledby="log-heading">
      <div class="panel-head"><h2 id="log-heading">Session log</h2><button type="button" class="link-btn" id="clear-log">Clear</button></div>
      <ol class="event-log" id="event-log" aria-live="polite"></ol>
      <p class="field-hint">A local trace of requests and state changes. It is not the evidence chain; use <em>Export evidence</em> for that.</p>
    </section>
  </div>

  <section class="section playground-notes">
    {section_head("What to try", "A five-minute tour of the contract", "")}
    <div class="steps-grid">
      <div class="step-card"><span>01</span><h3>Discover</h3><p>Send <em>Hello</em> and inspect <code>endpoint_id</code>, limits, features and the <code>MHS.SAFETY.NOT_CERTIFIED</code> disclosure.</p></div>
      <div class="step-card"><span>02</span><h3>Observe</h3><p>Read the workcell and compare the revision and <code>state_hash</code> before and after a command.</p></div>
      <div class="step-card"><span>03</span><h3>Refuse</h3><p>Open the door, then send a command. The receipt is <code>rejected</code> with <code>MHS.SAFETY.INTERLOCK_OPEN</code>; the revision does not advance.</p></div>
      <div class="step-card"><span>04</span><h3>Account</h3><p>Export the evidence bundle. Every receipt is chained; a rejected action is evidence, not an exception.</p></div>
    </div>
    {callout("The model's limits", "<p>The playground implements a synchronous subset of the wire protocol. It has no transport, no subscriptions, no concurrency and no real conformance suite. Interlocks are simulated. The actual standard requires independent hardware protection and a report-backed conformance level.</p>", "warn", "shield")}
  </section>
</div>
<script defer src="../assets/playground.js"></script>
"""
    return page_html(
        path="playground/index.html",
        title="Playground",
        description="An interactive, browser-only mock OpenMHS endpoint: discovery, reads, receipts, idempotent replay, interlock rejection, e-stop and evidence export.",
        body=body,
        section="playground",
        breadcrumbs=[("Playground", "playground/index.html")],
        og_type="article",
    )


# ---------------------------------------------------------------------------
# Pages: governance, download, about, search, 404
# ---------------------------------------------------------------------------


def class_status_summary(caps: Capabilities) -> str:
    """"44 <code>stable</code>, 13 <code>experimental</code>, ..." as the catalogue states it; statuses it does not know come last."""
    counts = caps.status_counts
    known = ("stable", "experimental", "deprecated")
    order = [k for k in known if k in counts] + sorted(k for k in counts if k not in known)
    return ", ".join(f"{counts[k]} <code>{esc(k)}</code>" for k in order) or "none are recorded"


def governance_page(ctx) -> str:
    p = "../"
    st = ctx.status
    rfc_steps = [
        ("Proposal", "A written problem statement, the affected requirements, and the proposed change. One concern per RFC; no bundling."),
        ("Discussion", "The editors publish the proposal with a review window. Implementers test the change against real endpoints and the conformance suite."),
        ("Decision", "Accepted, rejected or returned for revision, with the rationale recorded. Silence is not acceptance."),
        ("Amendment", "An accepted RFC amends the normative text, bumps the affected version, and updates schemas, capability classes and tests together."),
    ]
    step_html = "".join(
        f'<li><span class="cert-num">{i:02d}</span><div><h3>{esc(title)}</h3><p>{esc(body)}</p></div></li>'
        for i, (title, body) in enumerate(rfc_steps, start=1)
    )
    licenses = [
        ("Specification text", "the core, the driver profile, MHS-000 to MHS-010 and the appendices", "CC BY 4.0", "Share and adapt with attribution; no endorsement."),
        ("Schemas and code", "JSON Schemas, examples, reference SDK, bridges, site source", "MIT License", "Permissive; redistribution with notice; no trademark grant."),
        ("Registry data", "Package records, index files and claims", "CC BY 4.0", "Attribution to the OpenMHS registry; preserve trust labels."),
    ]
    lic_rows = "".join(
        f"<tr><td><strong>{esc(a)}</strong></td><td>{esc(b)}</td><td><code>{esc(c)}</code></td><td>{esc(d)}</td></tr>"
        for a, b, c, d in licenses
    )
    gov_doc = (
        f'<a class="text-link" href="../spec/10-governance.html">Read MHS-010 · Governance {ICONS["arrow"]}</a>'
        if not any(d.rel == "10-governance.md" and d.placeholder for d in ctx.docs)
        else '<span class="muted">MHS-010 · Governance is in preparation.</span>'
    )
    class_status_note = class_status_summary(ctx.caps)
    body = f"""
<div class="wrap">
  {breadcrumbs_html(p, [("Governance", None)])}
  <header class="page-hero">
    <p class="eyebrow">Project · process and licensing</p>
    <h1>How the standard changes, and how it is licensed</h1>
    <p class="page-lead">OpenMHS is a draft with a versioned change process. The rules are intentionally boring: one concern per proposal, testable requirements, no silent edits, and licences that let vendors and labs implement without asking permission.</p>
    <div class="doc-hero-stats">
      <span><strong>1.0</strong> protocol</span>
      <span><strong>CC BY 4.0</strong> specification text</span>
      <span><strong>MIT</strong> code and schemas</span>
      <span><strong>CC BY 4.0</strong> registry data</span>
    </div>
    {gov_doc}
  </header>

  <div class="governance-layout">
    <div class="governance-main">
      <section class="section" id="rfc">
        {section_head("RFC process", "From proposal to amendment", "The schemas win over the core, the core over the chapters, and a conflict is fixed by an erratum or an accepted RFC. A change that touches behaviour must touch requirements, schemas and tests in the same proposal.")}
        <ol class="cert-steps">{step_html}</ol>
        <div class="convention-grid">
          <div><h3>What belongs in an RFC</h3><p>Wire behaviour, capability classes, safety semantics, conformance tests, registry fields, versioning or licensing. Editorial fixes can be handled as errata, but they never change meaning silently.</p></div>
          <div><h3>What does not</h3><p>Product announcements, driver-specific quirks that belong in an adapter manifest, or changes that make a safety claim without a test. Implementations belong in the registry, not in the standard.</p></div>
          <div><h3>Review evidence</h3><p>A proposal that changes a requirement should include a failing test, an endpoint transcript, or a concrete adapter that cannot be expressed today. “It would be convenient” is not evidence.</p></div>
          <div><h3>Participation</h3><p>Driver authors, instrument vendors, simulation maintainers, lab integrators and host authors are the reviewers that matter. The process is open; no membership tier buys a vote.</p></div>
        </div>
      </section>

      <section class="section" id="versioning">
        {section_head("Versioning", "Three clocks that must not be confused", "The wire protocol, capability classes and registry schemas version independently. That is what lets the vocabulary grow without breaking a host.")}
        <div class="table-wrap"><table><thead><tr><th scope="col">Artefact</th><th scope="col">Version</th><th scope="col">Changes when</th><th scope="col">Compatibility rule</th></tr></thead><tbody>
          <tr><td><strong>Wire protocol</strong></td><td><code>1.0</code></td><td>Framing, method semantics, error model, transport requirements change incompatibly.</td><td>MAJOR mismatch fails closed with <code>MHS.PROTOCOL.VERSION_UNSUPPORTED</code>. MINOR additions are negotiated.</td></tr>
          <tr><td><strong>Capability class</strong></td><td><code>cap.*.v1</code></td><td>An input is removed, retyped, made required; a unit or meaning changes; the verb changes.</td><td>The id carries its MAJOR. Additive changes keep the id; a new MAJOR is a new class.</td></tr>
          <tr><td><strong>Registry schema</strong></td><td><code>1.0.0</code></td><td>Record fields or validation rules change.</td><td>Records validate against the version they cite; the registry publishes its index digest.</td></tr>
          <tr><td><strong>Conformance suite</strong></td><td><code>1.0.0</code></td><td>Tests are added or corrected; a requirement's check changes.</td><td>A claim cites the suite version; a report cannot be recomputed with a different suite.</td></tr>
        </tbody></table></div>
        <p class="status-inline"><span class="status-marker status-warn"></span> Deprecation windows are stated in the RFC that deprecates an artefact. Of the {ctx.caps.count} core classes, {class_status_note}. A deprecated class stays valid and callable; its notes name the protocol method that replaces it.</p>
      </section>

      <section class="section" id="licensing">
        {section_head("Licensing", "Implement without asking", "The licences are chosen so a vendor can ship an adapter, a lab can mirror the registry, and a host can embed the schemas without a commercial negotiation.")}
        <div class="table-wrap"><table><thead><tr><th scope="col">Artefact</th><th scope="col">Covers</th><th scope="col">Licence</th><th scope="col">What it means</th></tr></thead><tbody>{lic_rows}</tbody></table></div>
        <div class="license-notes">
          <div><h3>Attribution</h3><p>When you cite the specification, name “OpenMHS {SPEC_VERSION} (independent draft), The OpenMHS Authors” and link to the source repository. When you reuse registry data, preserve the trust level and evidence state; do not present an unsigned record as verified.</p></div>
          <div><h3>No trademark licence</h3><p>Neither licence grants rights to any name or mark, including those of third parties such as Anthropic. Quoted third-party text, such as the Anthropic quotations in appendix D, is not licensed by this project. A conformance claim must be accurate; it is not an endorsement.</p></div>
          <div><h3>Contributions</h3><p>Contributions to specification text, schemas or code are accepted under the inbound licence of the file being changed (CC BY 4.0 or MIT). No separate CLA is intended.</p></div>
        </div>
      </section>

      <section class="section" id="decisions">
        {section_head("Decision log", "Ten choices that shape the standard", "Alternatives were considered and recorded. They are part of the normative context, not marketing.")}
        <div class="decision-grid">
          <div><strong>D1</strong><p>JSON-RPC 2.0 rather than REST, gRPC-only or MCP-only. It embeds in stdio, HTTP and WebSocket and maps natively to MCP.</p></div>
          <div><strong>D2</strong><p>Sessions as leases rather than stateless calls. Simulators are stateful and cancellation needs a scope.</p></div>
          <div><strong>D3</strong><p>Receipts, revisions and state hashes rather than <code>ok:true</code>. Without them, an agent cannot distinguish “not done” from “unknown”.</p></div>
          <div><strong>D4</strong><p>Endpoint-enforced safety, not host policy. A host is the wrong trust boundary for a laser.</p></div>
          <div><strong>D5</strong><p>Simulation and hardware in one model, with explicit mode and fidelity. Two standards would double the work; silent conflation is unsafe.</p></div>
          <div><strong>D6</strong><p>Declarative adapters plus generic bridges, not a generated driver per repository.</p></div>
          <div><strong>D7</strong><p>Capability classes versioned separately from the wire. Vocabulary evolves faster than framing.</p></div>
          <div><strong>D8</strong><p>Executable self-conformance rather than a certification body as gatekeeper.</p></div>
          <div><strong>D9</strong><p>Natural-language tags attached to typed capabilities, not documentation alone.</p></div>
          <div><strong>D10</strong><p>A static, signed registry rather than a central live broker. Air-gapped labs need a mirror, not a dependency.</p></div>
        </div>
      </section>
    </div>
    <aside class="governance-aside">
      <div class="aside-card">
        <h2>At a glance</h2>
        <dl class="aside-facts">
          <dt>Status</dt><dd>{DRAFT_LABEL}</dd>
          <dt>Authority</dt><dd>Schemas, then core</dd>
          <dt>Change process</dt><dd>Public RFC</dd>
          <dt>Spec text</dt><dd>CC BY 4.0</dd>
          <dt>Code / schemas</dt><dd>MIT</dd>
          <dt>Registry data</dt><dd>CC BY 4.0</dd>
        </dl>
      </div>
      <div class="aside-card">
        <h2>Documents</h2>
        <ul class="aside-links">
          <li><a href="../spec/core.html">MHS-CORE · OpenMHS Core</a></li>
          <li><a href="../spec/00-architecture.html">MHS-000 · Architecture overview</a></li>
          <li><a href="../spec/01-conformance.html">MHS-001 · Conformance</a></li>
          <li><a href="../spec/04-safety.html">MHS-004 · Safety</a></li>
          <li><a href="../spec/10-governance.html">MHS-010 · Governance</a></li>
        </ul>
      </div>
      <div class="aside-card aside-contribute">
        <h2>Contact</h2>
        <p>Questions and RFC proposals go to the project's public issue tracker; vulnerabilities and safety defects are reported privately as described in <code>SECURITY.md</code>.</p>
        <p class="muted">The public repository is being prepared; until it exists there is no project mailbox. This page states the process it will follow.</p>
      </div>
    </aside>
  </div>
</div>
"""
    return page_html(
        path="governance/index.html",
        title="Governance and licensing",
        description="The OpenMHS RFC process, versioning rules and licensing: specification text CC BY 4.0, code and schemas MIT, registry data CC BY 4.0.",
        body=body,
        section="governance",
        breadcrumbs=[("Governance", None)],
        og_type="article",
    )


# ---------------------------------------------------------------------------
# Download bundles
# ---------------------------------------------------------------------------

NOTICE_TEXT = f"""OpenMHS {SPEC_VERSION} — independent development draft
=================================================

{NON_AFFILIATION}

Specification text and registry data: CC BY 4.0 (LICENSE-docs,
https://creativecommons.org/licenses/by/4.0/)
Code, JSON Schemas and examples: MIT License (LICENSE, NOTICE)
Quoted third-party text is not licensed by this project.

Conformance is not safety certification.
"""

# Licence files shipped inside the download bundles when present.
SCHEMA_BUNDLE_LICENCES = ("LICENSE", "NOTICE")
REGISTRY_BUNDLE_LICENCES = ("LICENSE-docs", "NOTICE")


def deterministic_zip(entries: list[tuple[str, bytes]]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for name, data in sorted(entries, key=lambda e: e[0]):
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 20, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, data)
    return buf.getvalue()


def page_source_paths() -> list[Path]:
    """Files the pages are rendered from, beyond the download inputs: the specification text, the SDK guides, the published
    conformance reports, the site assets and deploy files, and this generator. Their digests go into the download manifest so a
    stale build is noticed even when no download changed."""
    found: set[Path] = set()
    for folder, pattern in (
        (MHS / "spec", "*.md"),
        (MHS / "conformance" / "reports", "*.json"),
        (MHS / "sdk" / "docs", "*.md"),
    ):
        found.update(path for path in folder.glob(pattern) if path.is_file())
    for folder in (HERE / "assets", HERE / "deploy"):
        found.update(path for path in folder.rglob("*") if path.is_file())
    for path in (MHS / "sdk" / "README.md", MHS / "sdk" / "INTERFACE.md", WORKSPACE / "integration" / "openai4s" / "DESIGN.md", Path(__file__).resolve()):
        if path.is_file():
            found.add(path)
    return sorted(found)


def prepare_downloads(registry: Registry, caps: Capabilities) -> dict:
    entries = []
    # Every source file that goes into a download, with its digest, so a
    # checker can tell whether the published downloads match the sources.
    inputs: dict[str, str] = {}

    def source(path: Path) -> bytes:
        data = path.read_bytes()
        inputs[path.relative_to(WORKSPACE).as_posix()] = "sha256:" + sha256_hex(data)
        return data

    def licence_entries(names: tuple[str, ...]) -> list[tuple[str, bytes]]:
        return [(name, source(WORKSPACE / name)) for name in names if (WORKSPACE / name).is_file()]

    schema_root = MHS / "schema"
    if schema_root.is_dir():
        schema_entries = []
        for path in sorted(schema_root.rglob("*")):
            if path.is_file():
                rel = path.relative_to(schema_root).as_posix()
                schema_entries.append((f"schema/{rel}", source(path)))
        cap_path = MHS / "spec" / "capabilities.json"
        if cap_path.is_file():
            schema_entries.append(("capabilities.json", source(cap_path)))
        schema_entries.extend(licence_entries(SCHEMA_BUNDLE_LICENCES))
        schema_entries.append(("NOTICE.txt", NOTICE_TEXT.encode()))
        archive = deterministic_zip(schema_entries)
        size = write_bytes(f"download/{BUNDLE_PREFIX}-schema.zip", archive)
        entries.append(
            {
                "key": "schema",
                "name": f"OpenMHS {SPEC_VERSION} schema bundle",
                "file": f"{BUNDLE_PREFIX}-schema.zip",
                "href": f"{BUNDLE_PREFIX}-schema.zip",
                "size": size,
                "sha256": sha256_hex(archive),
                "desc": "All JSON Schemas, worked examples, capabilities.json and the licence files.",
                "contents": f"{len(schema_entries)} files",
            }
        )
    registry_root = MHS / "registry"
    if registry_root.is_dir():
        registry_entries = []
        for name in ("index.json", "index.jsonl", "records.csv", "uncloned.json"):
            path = registry_root / name
            if path.is_file():
                registry_entries.append((f"registry/{name}", source(path)))
        families_dir = registry_root / "families"
        if families_dir.is_dir():
            for path in sorted(families_dir.glob("*.md")):
                registry_entries.append((f"registry/families/{path.name}", source(path)))
        if registry_entries:
            registry_entries.extend(licence_entries(REGISTRY_BUNDLE_LICENCES))
            registry_entries.append(("NOTICE.txt", NOTICE_TEXT.encode()))
            archive = deterministic_zip(registry_entries)
            size = write_bytes(f"download/{BUNDLE_PREFIX}-registry.zip", archive)
            entries.append(
                {
                    "key": "registry",
                    "name": f"OpenMHS {SPEC_VERSION} registry bundle",
                    "file": f"{BUNDLE_PREFIX}-registry.zip",
                    "href": f"{BUNDLE_PREFIX}-registry.zip",
                    "size": size,
                    "sha256": sha256_hex(archive),
                    "desc": "The registry snapshot: JSON, JSON Lines, CSV, uncloned records and any family recipes.",
                    "contents": f"{len(registry_entries)} files",
                }
            )
    cap_path = MHS / "spec" / "capabilities.json"
    if cap_path.is_file():
        data = source(cap_path)
        size = write_bytes("download/capabilities.json", data)
        entries.append(
            {
                "key": "capabilities",
                "name": "Capability catalogue",
                "file": "capabilities.json",
                "href": "capabilities.json",
                "size": size,
                "sha256": sha256_hex(data),
                "desc": f"The machine-readable capability catalogue: {caps.count} classes with normative schemas.",
                "contents": f"{caps.count} classes",
            }
        )
    manifest = {
        "project": SITE_NAME,
        "non_affiliation": NON_AFFILIATION,
        "generated_at": BUILD_DATE,
        "spec_version": SPEC_VERSION,
        "wire_version": MHS_VERSION,
        "registry_records": registry.total,
        "registry_synthetic": registry.synthetic,
        "licences": {
            "specification": "CC-BY-4.0",
            "code_and_schemas": "MIT",
            "registry_data": "CC-BY-4.0",
        },
        "files": [
            {
                "name": e["name"],
                "path": e["file"],
                "bytes": e["size"],
                "sha256": "sha256:" + e["sha256"],
            }
            for e in entries
        ],
        "inputs": [
            {"path": rel, "sha256": digest} for rel, digest in sorted(inputs.items())
        ],
        "page_sources": [
            {"path": path.relative_to(WORKSPACE).as_posix(), "sha256": "sha256:" + sha256_hex(path.read_bytes())}
            for path in page_source_paths()
            if path.relative_to(WORKSPACE).as_posix() not in inputs
        ],
    }
    manifest_bytes = json.dumps(manifest, indent=2, ensure_ascii=False).encode() + b"\n"
    size = write_bytes("download/download-manifest.json", manifest_bytes)
    entries.append(
        {
            "key": "manifest",
            "name": "Download manifest",
            "file": "download-manifest.json",
            "href": "download-manifest.json",
            "size": size,
            "sha256": sha256_hex(manifest_bytes),
            "desc": "Sizes and SHA-256 digests for every file on this page and for every source file it was built from.",
            "contents": "JSON",
        }
    )
    return {"entries": entries, "manifest": manifest}


def download_page(ctx) -> str:
    p = "../"
    entries_html = "".join(
        f'<a class="download-card" href="{attr(e["href"])}" download>'
        f'<div class="download-icon">{ICONS["package"]}</div>'
        f'<div class="download-body"><h2>{esc(e["name"])}</h2><p>{esc(e["desc"])}</p>'
        f'<p class="download-meta"><span>{esc(e["contents"])}</span><span>{fmt_bytes(e["size"])}</span><code>sha256:{esc(e["sha256"][:12])}…</code></p></div>'
        f'<span class="download-arrow">{ICONS["arrow"]}</span></a>'
        for e in ctx.downloads["entries"]
    )
    install = """python3 MHS/sdk/tools/sync_data.py
python3 -m pip install ./MHS/sdk

# or run from the workspace without installing:
PYTHONPATH=MHS/sdk/src python3 -m mhs.cli devices --endpoint http://127.0.0.1:7400
python3 -m mhs.reference conveyor --port 7400"""
    checksum_rows = "".join(
        f'<tr><td><a href="{attr(e["href"])}" download>{esc(e["file"])}</a></td><td>{fmt_bytes(e["size"])}</td><td><code class="sha">{esc(e["sha256"])}</code></td></tr>'
        for e in ctx.downloads["entries"]
    )
    body = f"""
<div class="wrap">
  {breadcrumbs_html(p, [("Downloads", None)])}
  <header class="page-hero">
    <p class="eyebrow">Machine-readable artefacts</p>
    <h1>Take the standard with you</h1>
    <p class="page-lead">Schemas, the capability catalogue and the registry snapshot, packaged for offline use. No account, no telemetry, no external dependencies. Every archive has a SHA-256 digest.</p>
    <div class="doc-hero-stats">
      <span><strong>{len([e for e in ctx.downloads['entries'] if e['key'] in ('schema','registry')])}</strong> bundles</span>
      <span><strong>{ctx.caps.count}</strong> capability classes</span>
      <span><strong>{fmt_int(ctx.registry.total)}</strong> registry records</span>
      <span><strong>{BUILD_DATE}</strong> snapshot</span>
    </div>
  </header>

  <section class="section" id="bundles">
    <div class="download-grid">{entries_html}</div>
  </section>

  <section class="section" id="sdk-install">
    <div class="split-head">
      {section_head("SDK", "Install the reference client", "The client is pure Python with no third-party dependencies. The package is being published in parallel; use the workspace path if the distribution is not available.")}
      <a class="text-link split-link" href="../sdk/index.html">SDK documentation {ICONS['arrow']}</a>
    </div>
    {codeblock(install, "bash", "shell")}
    {callout("Package status", "<p>The SDK distribution is not represented as production-ready in this build. The frozen interface contract is published; the implementation and tests are developed in parallel. The protocol can be exercised today with any JSON-RPC client.</p>", "warn", "package")}
  </section>

  <section class="section" id="checksums">
    {section_head("Integrity", "Verify what you download", "The manifest records the size and SHA-256 of every file. Digests are stable across rebuilds from the same sources.")}
    <div class="table-wrap"><table><thead><tr><th scope="col">File</th><th scope="col">Size</th><th scope="col">SHA-256</th></tr></thead><tbody>{checksum_rows}</tbody></table></div>
    <p class="checksum-hint">Verify with <code>shasum -a 256 &lt;file&gt;</code> (macOS) or <code>sha256sum &lt;file&gt;</code> (Linux).</p>
  </section>

  <section class="section" id="licence">
    {section_head("Licence", "What you may do", "")}
    <div class="license-notes">
      <div><h3>Specification text — CC BY 4.0</h3><p>Share and adapt with attribution. Cite “OpenMHS {SPEC_VERSION} (independent draft), The OpenMHS Authors”. Quoted third-party text is not covered.</p></div>
      <div><h3>Code and schemas — MIT</h3><p>Use, modify and redistribute with the licence notice. No trademark rights.</p></div>
      <div><h3>Registry data — CC BY 4.0</h3><p>Mirror and analyse with attribution. Preserve trust and evidence labels; never present an unsigned record as verified.</p></div>
    </div>
    <div class="hero-actions">
      <a class="text-link" href="../governance/index.html#licensing">Full licensing terms {ICONS['arrow']}</a>
      <a class="text-link" href="../schema/device.schema.json">device.schema.json {ICONS['arrow']}</a>
    </div>
  </section>
</div>
"""
    return page_html(
        path="download/index.html",
        title="Downloads",
        description=f"Download the OpenMHS {SPEC_VERSION} JSON Schema bundle, the capability catalogue and the registry snapshot, with SHA-256 digests and licensing terms.",
        body=body,
        section="download",
        breadcrumbs=[("Downloads", None)],
        og_type="article",
    )


# ---------------------------------------------------------------------------
# Pages: about, search, 404, SDK guides
# ---------------------------------------------------------------------------


def about_page(ctx) -> str:
    p = "../"
    st = ctx.status
    schema_count = len(list((MHS / "schema").rglob("*.json"))) if (MHS / "schema").is_dir() else 0
    status_rows = [
        ("Specification", f"{st['docs_real']} of {st['docs_total']} mapped documents published", DRAFT_LABEL),
        ("JSON Schemas", f"{schema_count} schema files, plus worked examples", "Published"),
        ("Capability catalogue", f"{st['capabilities']} classes across {len(ctx.caps.domains)} domains", "Published"),
        ("Registry", f"{fmt_int(st['registry_total'])} records, {fmt_int(st['registry_manifests'])} manifests detected", "Static snapshot"),
        ("Reference SDK", (
            "Interface frozen; implementation not present in this build" if not st["sdk_present"]
            else f"{st['sdk_modules']} source modules, {st['sdk_tests']} test files, {st['sdk_docs']} guides; no release package claimed"
        ), "Reference source"),
        ("Conformance suite", (
            "Specified; runnable suite not included in this site build" if not st["suite_present"]
            else f"{st['suite_files']} suite modules; {st['reports_count']} self-issued reports (CL2–CL4)"
        ), "Reference evidence"),
        ("Family recipes", f"{st['families_real']} of {st['families']} published", "Published" if st["families_real"] == st["families"] else "In progress"),
        ("Runtime-tested packages", f"{fmt_int(st['runtime_tested'])} registry claims", "Not claimed"),
        ("Safety certification", "OpenMHS is not a safety-rated channel", "Not claimed"),
    ]
    status_html = "".join(
        f"<tr><td><strong>{esc(a)}</strong></td><td>{esc(b)}</td><td>{esc(c)}</td></tr>"
        for a, b, c in status_rows
    )
    principles = [
        ("A1", "One model for simulation and hardware", "The same client, contract and capability vocabulary; mode and fidelity carry the difference."),
        ("A2", "Capabilities, not device types", "A device is a bag of typed capabilities bound to resources, not a vendor category."),
        ("A4", "Fail closed", "A component that cannot be evaluated is a rejection, never an assumption of safety."),
        ("A6", "Fidelity is declared", "A model states what it models, what it does not, and how it was validated."),
        ("A9", "Wrap, do not rewrite", "Existing SDKs join through declarative adapters and generic bridges."),
        ("A10", "Conformance is executable", "A level is backed by a report a third party can recompute."),
    ]
    principle_html = "".join(
        f'<div class="principle"><span>{esc(a)}</span><h3>{esc(title)}</h3><p>{esc(body)}</p></div>'
        for a, title, body in principles
    )
    body = f"""
<div class="wrap">
  {breadcrumbs_html(p, [("About", None)])}
  <header class="page-hero page-hero-about">
    <p class="eyebrow">About the project</p>
    <h1>A contract for the part between reasoning and matter.</h1>
    <p class="page-lead">{esc(DEFINITION)}</p>
    <p class="page-lead">OpenMHS exists because the integration layer for physical AI is rebuilt by every lab, every vendor and every agent harness — and because the safety and evidence semantics that make that layer trustworthy are usually left out.</p>
    <div class="package-badges">{badge(DRAFT_LABEL, "warn")}{badge("Open specification", "info")}{badge("No certification body", "muted")}</div>
  </header>

  <div class="about-layout">
    <div class="about-main">
      <section class="section" id="mission">
        {section_head("Mission", "Make equipment legible to agents, and agents accountable to equipment", "")}
        <p class="dropcap">OpenMHS is an open, versioned, machine-checkable contract between agents that reason and equipment that acts. It lets an AI agent — or a plain Python program — discover a device it has never seen, understand what that device can do and what those actions mean physically, execute under an enforced safety envelope, and obtain verifiable evidence of what actually happened.</p>
        <p>It is model-agnostic and harness-agnostic. It does not assume a particular agent loop, a particular model vendor or MCP. It composes with MCP rather than competing with it: MCP standardises how a model reaches tools; OpenMHS standardises what a tool that moves matter means.</p>
        <div class="audience-grid">
          <div><h3>For driver and bridge authors</h3><p>A target to write against once, instead of a bespoke API per host. The adapter manifest is small; the bridge is reusable across a family.</p></div>
          <div><h3>For instrument vendors</h3><p>A way to describe capabilities, units, limits and provenance without ceding control of the driver or the device.</p></div>
          <div><h3>For labs and integrators</h3><p>A registry of what exists, what evidence backs it, and what the next concrete step is — with the gaps left visible.</p></div>
          <div><h3>For agent-harness authors</h3><p>One client path, one safety model, one evidence format for every physical tool in the loop.</p></div>
        </div>
      </section>

      <section class="section" id="principles">
        {section_head("Design", "The axioms that decide arguments", "When two designs are both plausible, these are the tie-breakers. They are normative context for every other document.")}
        <div class="principle-grid">{principle_html}</div>
        <a class="text-link" href="../spec/00-architecture.html#2-design-axioms">All ten design axioms {ICONS['arrow']}</a>
      </section>

      <section class="section" id="rings">
        {section_head("Adoption rings", "Four rings, and a separate evidence label", "The ring says how far a record has progressed through the adoption plan; evidence says how the record was produced. They are independent, and both are shown on every record. Neither is a quality score, a support commitment or a conformance level.")}
        <div class="ring-model">
          <div class="ring-model-card"><span class="ring-model-num">Ring 0</span><h3>Runtime-verified</h3><p><strong>{fmt_int(ctx.registry.ring_counts.get('0', 0))}</strong> records. A person or agent executed the endpoint locally and captured a report. This is the only ring that can support a runtime claim.</p><code>adoption ring 0</code></div>
          <div class="ring-model-card"><span class="ring-model-num">Ring 1</span><h3>Agent-read source</h3><p><strong>{fmt_int(ctx.registry.ring_counts.get('1', 0))}</strong> records. The actual source was read and a precise entry point, mapping and safety profile were recorded. Still a declared manifest, not an execution.</p><code>adoption ring 1</code></div>
          <div class="ring-model-card"><span class="ring-model-num">Ring 2</span><h3>Static analysis</h3><p><strong>{fmt_int(ctx.registry.ring_counts.get('2', 0))}</strong> records. Catalog fields plus bounded scans produced a manifest skeleton, family recipe and next action.</p><code>adoption ring 2</code></div>
          <div class="ring-model-card"><span class="ring-model-num">Ring 3</span><h3>Family recipe only</h3><p><strong>{fmt_int(ctx.registry.ring_counts.get('3', 0))}</strong> records. The package is mapped to a bridge family and a recipe; individual records may still carry static-scan or agent-read evidence, and the explorer shows which.</p><code>adoption ring 3</code></div>
        </div>
        <p class="muted">Ring and evidence are different axes: a ring-3 record can be agent-read, and a ring-1 record is not automatically conformant. Both labels are shown side by side in the <a href="../registry/index.html">registry explorer</a>; neither implies conformance. Read the model in <a href="../spec/00-architecture-part-2.html#13-adoption-path-for-the-corpus">MHS-000 §13</a>.</p>
      </section>

      <section class="section" id="status">
        {section_head("Status", "Exactly where this build stands", "The site is generated from the source tree; this table reflects the files present when it was built. It is a snapshot, not a roadmap promise.")}
        <div class="table-wrap"><table><thead><tr><th scope="col">Artefact</th><th scope="col">State in this build</th><th scope="col">Claim</th></tr></thead><tbody>{status_html}</tbody></table></div>
        {callout("Not a safety certificate", "<p>No statement on this site certifies a device, a process, an experiment or an organisation. OpenMHS conformance means behaviour under test. Hardware emergency stops and protective functions must exist independently and be validated by the responsible engineers.</p>", "bad", "shield")}
      </section>

      <section class="section" id="disclaimers">
        {section_head("Disclaimers", "What the standard deliberately leaves to others", "")}
        <div class="disclaimer-list">
          <div><h3>Safety and regulation</h3><p>OpenMHS does not provide safety certification, risk assessment, clinical validation or regulatory approval. It is a software interlock layer, not a safety instrumented function.</p></div>
          <div><h3>Fidelity and experiment validity</h3><p>A simulator can be conformant and still be wrong for a particular experiment. Fidelity levels are ordinal claims qualified by declared gaps, not guarantees.</p></div>
          <div><h3>Registry accuracy</h3><p>Records are assembled from a catalogue and bounded scans. Fields can be wrong, incomplete or stale. Evidence state is displayed precisely so you can judge it.</p></div>
          <div><h3>Real-time control</h3><p>OpenMHS is a supervisory contract. It does not replace EtherCAT, CAN, ROS control or vendor real-time APIs underneath a bridge.</p></div>
        </div>
      </section>

      <section class="section" id="colophon">
        {section_head("Colophon", "How this site is made", "")}
        <div class="colophon">
          <p><strong>Static by construction.</strong> The site is generated by a Python standard-library build script. No npm, no bundler, no analytics, no external fonts, no CDN. It works from a local file path and from any static host.</p>
          <p><strong>Accessible and responsive.</strong> System fonts, AA contrast, visible focus, landmarks, a skip link, reduced-motion support and a 360 px layout. The theme toggle stores one preference in <code>localStorage</code>; nothing else is stored.</p>
          <p><strong>Data-driven.</strong> Specification pages are rendered from the normative Markdown. The registry explorer is a static projection of the registry records. The capability viewer reads the same <code>capabilities.json</code> that ships in the schema bundle.</p>
          <p><strong>Written by</strong> {esc(COPYRIGHT_HOLDER)}. Questions go to the project's public issue tracker; security and safety reports follow <code>SECURITY.md</code>. Build date {BUILD_DATE}; specification {SPEC_VERSION}; wire revision {MHS_VERSION}.</p>
        </div>
      </section>
    </div>
    <aside class="about-aside">
      <div class="aside-card">
        <h2>Snapshot</h2>
        <dl class="aside-facts">
          <dt>Protocol</dt><dd>{MHS_VERSION}</dd>
          <dt>Documents</dt><dd>{st['docs_real']} / {st['docs_total']}</dd>
          <dt>Capabilities</dt><dd>{st['capabilities']}</dd>
          <dt>Registry</dt><dd>{fmt_int(st['registry_total'])}</dd>
          <dt>Families</dt><dd>{st['families']}</dd>
          <dt>Build</dt><dd>{BUILD_DATE}</dd>
        </dl>
      </div>
      <div class="aside-card">
        <h2>Go deeper</h2>
        <ul class="aside-links">
          <li><a href="../spec/core.html">OpenMHS Core</a></li>
          <li><a href="../conformance/index.html">Conformance ladder</a></li>
          <li><a href="#rings">Verification rings</a></li>
          <li><a href="../registry/index.html">Registry explorer</a></li>
          <li><a href="../governance/index.html">Governance</a></li>
          <li><a href="../download/index.html">Downloads</a></li>
        </ul>
      </div>
      <div class="aside-card aside-contribute">
        <h2>Cite {SITE_NAME}</h2>
        <p class="cite-block">OpenMHS {SPEC_VERSION} (independent development draft). {esc(COPYRIGHT_HOLDER)}, 2026.</p>
        <p class="muted">Specification text licensed CC BY 4.0.</p>
      </div>
    </aside>
  </div>
</div>
"""
    return page_html(
        path="about/index.html",
        title="About",
        description="The mission, design axioms, verification ring model, honest status and disclaimers of OpenMHS, plus how this static, tracker-free site is built.",
        body=body,
        section="about",
        breadcrumbs=[("About", None)],
        og_type="article",
    )


def search_page(ctx) -> str:
    p = "../"
    body = f"""
<div class="wrap search-page">
  {breadcrumbs_html(p, [("Search", None)])}
  <header class="page-hero search-hero">
    <p class="eyebrow">Search</p>
    <h1>Find a document, capability or family</h1>
    <p class="page-lead">Search the specification, the capability catalogue, bridge families and site pages. Registry records have their own explorer and filter surface.</p>
    <form class="search-form" id="site-search-form" role="search" action="index.html" method="get">
      <label class="sr-only" for="site-search">Search the site</label>
      <div class="search-input-wrap search-input-lg">
        {ICONS['search']}
        <input id="site-search" name="q" type="search" placeholder="Try “interlock”, “world.step”, “gymnasium”…" autocomplete="off" spellcheck="false" autofocus>
        <button type="submit" class="btn btn-primary">Search</button>
      </div>
    </form>
    <div class="search-filters" role="group" aria-label="Filter results by type">
      <button type="button" class="filter-btn is-active" data-type="">All</button>
      <button type="button" class="filter-btn" data-type="spec">Specification</button>
      <button type="button" class="filter-btn" data-type="capability">Capabilities</button>
      <button type="button" class="filter-btn" data-type="family">Families</button>
      <button type="button" class="filter-btn" data-type="site">Site</button>
    </div>
  </header>
  <section class="search-results-wrap" aria-labelledby="search-results-heading">
    <h2 id="search-results-heading" class="sr-only">Search results</h2>
    <p class="results-count" id="search-count" aria-live="polite">Type to search {len(ctx.search_entries)} indexed sections.</p>
    <ol class="search-results" id="search-results"></ol>
    <div class="empty-state" id="search-empty" hidden>
      <h2>No matching sections</h2>
      <p>Try a shorter term, a capability id such as <code>cap.fluid.transfer.v1</code>, or browse the <a href="../registry/index.html">registry explorer</a>.</p>
    </div>
    <div class="search-suggestions" id="search-suggestions">
      <h2>Start here</h2>
      <div class="suggestion-grid">
        <a href="../spec/core.html"><span>Specification</span><strong>OpenMHS Core</strong><p>The object model, limits, e-stop, receipts and the control surfaces.</p></a>
        <a href="../capabilities/index.html"><span>Catalogue</span><strong>Capability classes</strong><p>All {ctx.caps.count} classes with input and output schemas.</p></a>
        <a href="../registry/index.html"><span>Registry</span><strong>{fmt_int(ctx.registry.total)} packages</strong><p>Filter by family, tier, ring, mode and licence.</p></a>
        <a href="../playground/index.html"><span>Interactive</span><strong>Mock endpoint</strong><p>Send a command, trip an interlock and export evidence.</p></a>
      </div>
    </div>
  </section>
</div>
<script defer src="../assets/search.js"></script>
"""
    return page_html(
        path="search/index.html",
        title="Search",
        description="Search OpenMHS specification sections, capability classes, bridge families and site pages.",
        body=body,
        section="search",
        breadcrumbs=[("Search", None)],
        og_type="website",
        noindex=True,
    )


def not_found_page(ctx) -> str:
    p = ""
    body = f"""
<div class="wrap notfound">
  <p class="eyebrow">404 · not found</p>
  <h1>That page is not part of the contract.</h1>
  <p class="page-lead">The URL does not resolve on this site. It may have moved with a document revision, or the link may be mistyped. Nothing about a 404 changes the specification.</p>
  <div class="notfound-grid">
    <a href="spec/index.html"><span>Specification</span><strong>All OpenMHS documents</strong></a>
    <a href="registry/index.html"><span>Registry</span><strong>Explore packages</strong></a>
    <a href="capabilities/index.html"><span>Catalogue</span><strong>Capability classes</strong></a>
    <a href="search/index.html"><span>Search</span><strong>Find a section</strong></a>
  </div>
  <div class="hero-actions">
    {btn("Back to home", "index.html", "primary", icon=True)}
    {btn("Read the core", "spec/core.html", "secondary")}
  </div>
</div>
"""
    return page_html(
        path="404.html",
        title="Page not found",
        description="The requested page was not found on this site.",
        body=body,
        section="",
        noindex=True,
        canonical=False,
    )


def sdk_doc_page(ctx, doc: Path) -> str:
    stem = doc.stem
    title = extract_title(read_text(doc), stem)
    renderer = MarkdownRenderer(ctx.known, f"MHS/sdk/docs/{doc.name}", f"sdk/docs/{stem}.html")
    rendered, toc = renderer.render(read_text(doc), skip_first_h1=True)
    toc_html = f'<details class="toc-mobile" open><summary>On this page</summary>{toc_markup(toc)}</details>' if toc else ""
    body = f"""
<div class="wrap doc-layout-simple">
  {breadcrumbs_html("../", [("SDK", "index.html"), (title, None)])}
  <article class="doc-article">
    <p class="eyebrow">SDK guide</p>
    <h1>{esc(title)}</h1>
    {toc_html}
    <div class="doc-body">{rendered}</div>
    <nav class="pager"><a href="../index.html">← SDK documentation</a></nav>
  </article>
</div>
"""
    return page_html(
        path=f"sdk/docs/{stem}.html",
        title=f"{title} · SDK",
        description=extract_lead(read_text(doc))[:220] or f"OpenMHS SDK guide: {title}.",
        body=body,
        section="sdk",
        breadcrumbs=[("SDK", "sdk/index.html"), (title, None)],
        og_type="article",
    )


# ---------------------------------------------------------------------------
# Build orchestration
# ---------------------------------------------------------------------------


@dataclass
class BuildContext:
    docs: list[Doc]
    registry: Registry
    caps: Capabilities
    families: list[Family]
    sdk: SdkDocs
    status: dict
    known: set[str]
    family_records: dict[str, list[dict]]
    family_titles: dict[str, str]
    downloads: dict
    interface_copied: bool
    search_entries: list = field(default_factory=list)


def write_data_assets(registry: Registry, caps: Capabilities) -> tuple[int, int]:
    fields = [
        "slug", "title", "owner", "repo", "track", "family", "tier", "ring",
        "modes", "license", "stars", "caps", "evidence", "adapter", "desc",
        "search",
    ]
    rows = []
    for rec in registry.records:
        search_blob = " ".join(
            [
                rec["title"], rec["owner"], rec["repo"], rec["description"],
                " ".join(rec["interfaces"]), " ".join(rec["capabilities_offered"]),
                " ".join(rec.get("families") or []), rec["license"],
                rec["license_bucket"], rec["track"], rec["tier"],
            ]
        ).lower()
        rows.append(
            [
                rec["slug"], rec["title"], rec["owner"], rec["repo"], rec["track"],
                rec["family"], rec["tier"], rec["ring"], "+".join(rec["modes"]),
                rec["license_bucket"], rec["stars"], rec["cap_count"],
                rec["evidence_state"], rec["adapter_state"], rec["description"],
                search_blob,
            ]
        )
    payload = {
        "generated_at": registry.generated_at,
        "synthetic": registry.synthetic,
        "fields": fields,
        "total": len(rows),
        "records": rows,
    }
    reg_text = "window.MHS_REGISTRY = " + json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ) + ";\n"
    size_reg = write_text("assets/registry-data.js", reg_text)
    cap_text = "window.MHS_CAPABILITIES = " + json.dumps(
        {"mhs_capabilities": caps.version, "capabilities": caps.items},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ) + ";\n"
    size_cap = write_text("assets/capabilities-data.js", cap_text)
    return size_reg, size_cap


def copy_sources(known: set[str]) -> tuple[bool, int]:
    schema_src = MHS / "schema"
    schema_count = 0
    if schema_src.is_dir():
        for path in sorted(schema_src.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(schema_src).as_posix()
            target = f"schema/{rel}"
            write_bytes(target, path.read_bytes())
            known.add(target)
            schema_count += 1
    cap = MHS / "spec" / "capabilities.json"
    if cap.is_file():
        write_bytes("spec/capabilities.json", cap.read_bytes())
        known.add("spec/capabilities.json")
    interface_copied = False
    iface = MHS / "sdk" / "INTERFACE.md"
    if iface.is_file():
        write_bytes("sdk/INTERFACE.md", iface.read_bytes())
        known.add("sdk/INTERFACE.md")
        interface_copied = True
    reports = MHS / "conformance" / "reports"
    if reports.is_dir():
        for path in sorted(reports.glob("*.json")):
            target = f"conformance/reports/{path.name}"
            write_bytes(target, path.read_bytes())
            known.add(target)
    design = WORKSPACE / "integration" / "openai4s" / "DESIGN.md"
    if design.is_file():
        write_bytes("hosts/openai4s/DESIGN.md", design.read_bytes())
        known.add("hosts/openai4s/DESIGN.md")
    manifest_root = MHS / "registry" / "manifests"
    if manifest_root.is_dir():
        for path in sorted(manifest_root.rglob("*.json")):
            rel = path.relative_to(manifest_root).as_posix()
            target = f"registry/manifests/{rel}"
            write_bytes(target, path.read_bytes())
            known.add(target)
    return interface_copied, schema_count


def copy_assets(known: set[str]) -> None:
    for name in ("style.css", "app.js", "search.js", "playground.js", "registry.js", "capabilities.js"):
        path = ASSETS / name
        if not path.is_file():
            raise SystemExit(f"missing required asset: {path}")
        write_bytes(f"assets/{name}", path.read_bytes())
        known.add(f"assets/{name}")
    write_text("favicon.svg", FAVICON)
    known.add("favicon.svg")


def copy_deploy(known: set[str]) -> None:
    # No CNAME is written: the custom domain, if any, belongs to whoever
    # deploys the site (see deploy/README.md).
    headers = DEPLOY / "_headers"
    if headers.is_file():
        write_bytes("_headers", headers.read_bytes())
        known.add("_headers")
    else:
        write_text(
            "_headers",
            "/*\n  X-Content-Type-Options: nosniff\n  X-Frame-Options: DENY\n"
            "  Referrer-Policy: strict-origin-when-cross-origin\n",
        )
        known.add("_headers")
    write_text(".nojekyll", "")
    known.add(".nojekyll")


def write_robots(known: set[str]) -> None:
    path = DEPLOY / "robots.txt"
    text = read_text(path) if path.is_file() else "User-agent: *\nAllow: /\n"
    text = text.rstrip("\n") + "\n"
    if SITE_URL:
        text += "\nSitemap: " + SITE_URL + "/sitemap.xml\n"
    write_text("robots.txt", text)
    known.add("robots.txt")


def make_search_entries(ctx: BuildContext, pages: list[tuple[str, str]]) -> list[list[str]]:
    entries: list[list[str]] = []
    path_prefix = "../"
    seen: set[tuple[str, str]] = set()

    def add(title: str, path: str, kind: str, desc: str, fragment: str = "") -> None:
        text = re.sub(r"\s+", " ", strip_tags(title)).strip()
        if not text:
            return
        url = path_prefix + path
        if fragment:
            url += "#" + fragment
        key = (url, text)
        if key in seen:
            return
        seen.add(key)
        desc = re.sub(r"\s+", " ", strip_tags(desc)).strip()
        if len(desc) > 180:
            desc = desc[:177].rsplit(" ", 1)[0] + "…"
        entries.append([text, url, kind, desc])

    for path, kind in pages:
        full = OUT / path
        if not full.is_file():
            continue
        html_text = read_text(full)
        title_m = re.search(r"<title>(.*?)</title>", html_text, re.S)
        page_title = html.unescape(title_m.group(1)) if title_m else path
        page_title = re.sub(r"\s+—\s+" + re.escape(SITE_NAME) + "$", "", page_title)
        desc_m = re.search(r'<meta name="description" content="([^"]*)"', html_text)
        desc = html.unescape(desc_m.group(1)) if desc_m else ""
        add(page_title, path, kind, desc)
        main_m = re.search(r"<main[^>]*>(.*?)</main>", html_text, re.S)
        main_html = main_m.group(1) if main_m else html_text
        for m in re.finditer(r'<h([23]) id="([^"]+)"[^>]*>(.*?)</h\1>', main_html, re.S):
            heading = strip_tags(m.group(3)).replace("#", "").strip()
            add(heading, path, kind, page_title, m.group(2))
    for cap in ctx.caps.items:
        add(
            f'{cap["_slug"]} — {cap["_title"]}',
            "capabilities/index.html",
            "Capability",
            cap["_summary"],
            cap["_slug"],
        )
    for fam in ctx.families:
        add(
            f'{fam.title} — bridge family',
            f"families/{fam.slug}.html",
            "Family",
            fam.description,
        )
    entries.sort(key=lambda e: (e[2], e[0].lower(), e[1]))
    return entries


def write_search_index(entries: list[list[str]]) -> int:
    payload = json.dumps(entries, ensure_ascii=False, separators=(",", ":"))
    write_text("assets/search-index.json", payload + "\n")
    return write_text("assets/search-index.js", "window.MHS_SEARCH = " + payload + ";\n")


def write_sitemap(entries: list[tuple[str, str, str]]) -> int:
    """Write sitemap.xml; a sitemap needs absolute URLs, so only with a site URL."""
    if not SITE_URL:
        return 0
    rows = []
    for path, changefreq, priority in entries:
        loc = canonical_url(path)
        rows.append(
            f"<url><loc>{html.escape(loc)}</loc><lastmod>{BUILD_DATE}</lastmod>"
            f"<changefreq>{changefreq}</changefreq><priority>{priority}</priority></url>"
        )
    text = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(rows)
        + "</urlset>\n"
    )
    return write_text("sitemap.xml", text)


def prepare_output_dir(out: Path) -> None:
    """Empty ``out`` for a fresh build, refusing anything that is not ours."""
    out = out.resolve()
    protected = {Path("/").resolve(), Path.home().resolve(), WORKSPACE, MHS, HERE}
    if out in protected or any(out in path.parents for path in (HERE, MHS)):
        raise SystemExit(f"refusing to build into {out}: it contains sources")
    if out.exists():
        if not out.is_dir():
            raise SystemExit(f"refusing to replace {out}: not a directory")
        is_default = out == DEFAULT_OUT.resolve()
        if any(out.iterdir()) and not is_default and not (out / OUT_MARKER).is_file():
            raise SystemExit(
                f"refusing to replace {out}: it is not empty and has no {OUT_MARKER} "
                "marker from a previous site build"
            )
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out / OUT_MARKER).write_text(
        "Generated by MHS/site/build.py; this directory is replaced on every build.\n",
        encoding="utf-8",
    )


def build_site(quiet: bool = False) -> int:
    prepare_output_dir(OUT)

    docs = discover_docs()
    doc_parts = build_doc_parts(docs)
    registry = prepare_registry(load_registry())
    caps = load_capabilities()
    families = load_families(registry)
    sdk = load_sdk()
    status = build_status(docs, registry, caps, families, sdk)

    family_records: dict[str, list[dict]] = {}
    for rec in registry.records:
        for fam in rec.get("families") or ["other"]:
            family_records.setdefault(fam, []).append(rec)
    family_titles = {fam.name: fam.title for fam in families}
    family_titles.setdefault("other", "Other / unclassified")

    downloads = prepare_downloads(registry, caps)

    known: set[str] = set()
    pages: list[str] = [
        "index.html",
        "404.html",
        "spec/index.html",
        "registry/index.html",
        "capabilities/index.html",
        "families/index.html",
        "conformance/index.html",
        "sdk/index.html",
        "hosts/openai4s/index.html",
        "playground/index.html",
        "governance/index.html",
        "download/index.html",
        "about/index.html",
        "search/index.html",
    ]
    pages += [part.output for part in doc_parts]
    pages += [f"registry/repo/{rec['slug']}.html" for rec in registry.records]
    pages += [f"families/{fam.slug}.html" for fam in families]
    sdk_docs = [f"sdk/docs/{doc.stem}.html" for doc in sdk.docs]
    pages += sdk_docs
    pages += [
        "assets/style.css", "assets/app.js", "assets/search.js", "assets/playground.js",
        "assets/registry.js", "assets/capabilities.js", "assets/registry-data.js",
        "assets/capabilities-data.js", "assets/search-index.js", "assets/search-index.json",
        "favicon.svg", "robots.txt", "_headers", ".nojekyll",
    ]
    if SITE_URL:
        pages.append("sitemap.xml")
    pages += [f"download/{e['file']}" for e in downloads["entries"]]
    known.update(pages)
    known.add("spec/capabilities.json")
    known.add("sdk/INTERFACE.md")
    if (MHS / "schema").is_dir():
        for path in (MHS / "schema").rglob("*"):
            if path.is_file():
                known.add("schema/" + path.relative_to(MHS / "schema").as_posix())
    for rec in registry.records:
        ref = (rec.get("adapter") or {}).get("manifest_ref") or (rec.get("adapter") or {}).get("manifest")
        if ref and (MHS / "registry" / ref).is_file():
            known.add("registry/" + ref)

    interface_copied, _schema_count = copy_sources(known)
    copy_assets(known)
    copy_deploy(known)
    write_robots(known)
    size_reg, size_cap = write_data_assets(registry, caps)

    ctx = BuildContext(
        docs=docs,
        registry=registry,
        caps=caps,
        families=families,
        sdk=sdk,
        status=status,
        known=known,
        family_records=family_records,
        family_titles=family_titles,
        downloads=downloads,
        interface_copied=interface_copied,
    )

    noindex_paths: set[str] = {"404.html", "search/index.html"}
    noindex_paths.update(doc.output for doc in docs if doc.placeholder)
    noindex_paths.update(f"families/{fam.slug}.html" for fam in families if fam.placeholder)

    rendered_sizes: dict[str, int] = {}
    searchable: list[tuple[str, str]] = []

    def emit(path: str, html_text: str, search_kind: str | None = None) -> None:
        size = write_text(path, html_text)
        rendered_sizes[path] = size
        if search_kind:
            searchable.append((path, search_kind))

    emit("index.html", home_page(ctx), "Site")
    emit("spec/index.html", spec_index_page(ctx), "Specification")
    for index, part in enumerate(doc_parts):
        emit(
            part.output,
            spec_doc_page(ctx, part, index, doc_parts),
            None if part.doc.placeholder else "Specification",
        )
    emit("registry/index.html", registry_explorer_page(ctx), "Registry")
    for index, rec in enumerate(registry.records):
        emit(f"registry/repo/{rec['slug']}.html", registry_detail_page(ctx, rec, index))
    emit("capabilities/index.html", capabilities_page(ctx), "Capabilities")
    emit("families/index.html", families_index_page(ctx), "Families")
    for fam in families:
        emit(f"families/{fam.slug}.html", family_page(ctx, fam), None if fam.placeholder else "Families")
    emit("conformance/index.html", conformance_page(ctx), "Site")
    emit("sdk/index.html", sdk_page(ctx), "Site")
    for doc in sdk.docs:
        emit(f"sdk/docs/{doc.stem}.html", sdk_doc_page(ctx, doc), "Site")
    emit("hosts/openai4s/index.html", host_page(ctx), "Site")
    emit("anthropic-mhs/index.html", anthropic_page(ctx), "Site")
    emit("playground/index.html", playground_page(ctx), "Site")
    emit("governance/index.html", governance_page(ctx), "Site")
    emit("download/index.html", download_page(ctx), "Site")
    emit("about/index.html", about_page(ctx), "Site")
    emit("404.html", not_found_page(ctx))

    ctx.search_entries = make_search_entries(ctx, searchable)
    emit("search/index.html", search_page(ctx))
    write_search_index(ctx.search_entries)

    sitemap_entries: list[tuple[str, str, str]] = [("index.html", "weekly", "1.0")]
    sitemap_entries.append(("spec/index.html", "monthly", "0.9"))
    for part in doc_parts:
        if not part.doc.placeholder:
            sitemap_entries.append((part.output, "monthly", "0.8"))
    sitemap_entries.append(("registry/index.html", "weekly", "0.9"))
    for rec in registry.records:
        sitemap_entries.append((f"registry/repo/{rec['slug']}.html", "monthly", "0.4"))
    sitemap_entries.append(("capabilities/index.html", "monthly", "0.8"))
    sitemap_entries.append(("families/index.html", "monthly", "0.7"))
    for fam in families:
        if not fam.placeholder:
            sitemap_entries.append((f"families/{fam.slug}.html", "monthly", "0.7"))
    sitemap_entries += [
        ("conformance/index.html", "monthly", "0.8"),
        ("sdk/index.html", "monthly", "0.7"),
        ("hosts/openai4s/index.html", "monthly", "0.6"),
        ("anthropic-mhs/index.html", "monthly", "0.6"),
        ("playground/index.html", "monthly", "0.6"),
        ("governance/index.html", "monthly", "0.6"),
        ("download/index.html", "monthly", "0.7"),
        ("about/index.html", "yearly", "0.5"),
    ]
    for doc in sdk.docs:
        sitemap_entries.append((f"sdk/docs/{doc.stem}.html", "monthly", "0.5"))
    write_sitemap(sitemap_entries)

    # Summary table by top-level area.
    areas: dict[str, list[int]] = {}
    for path, size in rendered_sizes.items():
        area = path.split("/")[0] if "/" in path else "root"
        areas.setdefault(area, []).append(size)
    total_site = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    html_pages = [p for p in rendered_sizes if p.endswith(".html")]
    total_html = sum(rendered_sizes[p] for p in html_pages)
    if not quiet:
        print(f"{SITE_NAME} site build — {BUILD_DATE} — spec {SPEC_VERSION}, wire {MHS_VERSION} — {OUT}")
        print(f"  site url    {SITE_URL + '/' if SITE_URL else '(none: no canonical links, no sitemap)'}")
        print(f"  docs        {len([d for d in docs if not d.placeholder])}/{len(docs)} published, {len([d for d in docs if d.placeholder])} in preparation")
        print(f"  registry    {registry.total:,} records" + (" (SYNTHETIC FALLBACK)" if registry.synthetic else ""))
        print(f"  caps        {caps.count} classes · {len(caps.domains)} domains")
        print(f"  families    {len(families)} pages · {len([f for f in families if not f.placeholder])} recipes published")
        print(f"  sdk         {'README present' if sdk.present else 'no README'}; {len(sdk.docs)} guides")
        print(f"  assets      registry-data {fmt_bytes(size_reg)} · capabilities-data {fmt_bytes(size_cap)}")
        print("  area        pages     HTML")
        for area in sorted(areas):
            sizes = areas[area]
            print(f"  {area:<11} {len(sizes):>5}   {fmt_bytes(sum(sizes)):>9}")
        print(f"  total       {len(html_pages)} pages  {fmt_bytes(total_html)} HTML  {fmt_bytes(total_site)} site")
        over = sorted(
            ((p, s) for p, s in rendered_sizes.items() if p.endswith(".html") and s > 100 * 1024),
            key=lambda kv: -kv[1],
        )
        if over:
            print(f"  note        {len(over)} HTML page(s) over 100KB:")
            for p, s in over[:6]:
                print(f"              {p} ({fmt_bytes(s)})")
        if ctx.search_entries:
            print(f"  search      {len(ctx.search_entries)} indexed sections")
        if any(d.placeholder for d in docs):
            print("  pending     spec: " + ", ".join(d.rel for d in docs if d.placeholder))
        if any(f.placeholder for f in families):
            print(f"  pending     {len([f for f in families if f.placeholder])} family recipes")
    return 0


def main(argv: list[str] | None = None) -> int:
    global OUT, SITE_URL, RELEASE
    parser = argparse.ArgumentParser(
        prog="build.py",
        description="Build the OpenMHS static site.",
        epilog=NON_AFFILIATION,
    )
    parser.add_argument("--out", type=Path, default=None,
                        help=f"output directory (default: {DEFAULT_OUT})")
    parser.add_argument("--site-url", default=None,
                        help="public base URL for canonical links and the sitemap "
                             "(default: $OPENMHS_SITE_URL; no default host)")
    parser.add_argument("--release", action="store_true",
                        help="release build: fail instead of using the synthetic registry fallback")
    parser.add_argument("-q", "--quiet", action="store_true", help="build without the summary log")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    OUT = (args.out.expanduser() if args.out is not None else DEFAULT_OUT).resolve()
    site_url = args.site_url if args.site_url is not None else os.environ.get("OPENMHS_SITE_URL", "")
    SITE_URL = normalize_site_url(site_url)
    RELEASE = bool(args.release)
    return build_site(quiet=args.quiet)


if __name__ == "__main__":
    raise SystemExit(main())
