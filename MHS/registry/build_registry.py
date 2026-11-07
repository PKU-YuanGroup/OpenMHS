#!/usr/bin/env python3
"""OpenMHS registry generator (stdlib only, deterministic, offline).

Joins the OpenAI4S backend catalogue, the analyst profiles, the recon notes,
the corpus lock and two bounded static scans of the local clones (the
catalogue classifier's ``scan_corpus.py`` and the AST scan ``source_scan.py``),
runs the eleven ordered triage rules (``triage.py``, curated overrides win),
reads the per-repo driver packages as overlays (``overlays.py``) and writes:

  repos/<track>/<owner>__<repo>.json     one registry record per clone
  tasks/<track>/<owner>__<repo>.json     one task card per clone (taskcards.py)
  tasks/pilot-candidates.json            the pilot pool for MHS/handoff/pilot-20.json
  families/<family>.md                   one recipe per family present (recipes.py)
  README.md coverage.md uncloned.json    documentation and gaps (docs.py)
  index.json index.jsonl records.csv     aggregates (build_index.py; git-ignored, CI builds them)

Run:   python3 MHS/registry/build_registry.py [--jobs N] [--cache DIR]
Date:  fixed (MHS_REGISTRY_DATE, default DEFAULT_DATE); output is byte-stable.  SOURCE_DATE_EPOCH is
       ignored on purpose: CI systems export it for their own reproducible builds, and it must not
       change the registry's dates (``build --check`` would fail).

Inputs that are never written: the corpus clones, ``MHS/drivers/**`` and
``MHS/registry/overrides/**``.  Skeleton adapter manifests are no longer
generated; the former ones are archived in
``_archive/registry/manifests-skeleton-2026-10/``.  Nothing here executes a
repo, installs anything or touches the network.
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
from collections import Counter, OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

import catalog_view as CV         # noqa: E402  (risk floors and verbs from mhs.catalog)
import family_data as FD          # noqa: E402
import licenses as LIC            # noqa: E402
import overlays as OV             # noqa: E402
import scan_corpus as SC          # noqa: E402
import taskcards as TC            # noqa: E402
import triage as T                # noqa: E402
from mhs import _ids              # noqa: E402  (catalog_view put the SDK source tree on sys.path)

REGISTRY_VERSION = "0.9.0"
REGISTRY_ID = _ids.REGISTRY_ID
DEFAULT_DATE = "2026-10-20T00:00:00Z"
CATALOG_DIR = os.path.join(WORKSPACE, "openai4s_backend_catalog_all_sources")
CATALOG_CSV = os.path.join(CATALOG_DIR, "openai4s_backend_catalog.csv")
CAPS_CSV = os.path.join(CATALOG_DIR, "backend_capabilities.csv")
CORE_CAPS_JSON = os.path.join(WORKSPACE, "MHS", "spec", "capabilities.json")
ALIASES_CSV = os.path.join(CATALOG_DIR, "aliases.csv")
ANALYSIS_DIR = os.path.join(WORKSPACE, "work", "analysis")
PROFILES_JSONL = os.path.join(ANALYSIS_DIR, "repo_profiles.jsonl")
ANALYSIS_REPORT = os.path.join(ANALYSIS_DIR, "REPORT.md")
RECON_ROOT = os.path.join(WORKSPACE, "work", "recon")
RECIPES_LABS = os.path.join(RECON_ROOT, "labs", "adapter_recipes.md")
RECIPES_ROBOTS = os.path.join(RECON_ROOT, "robots", "adapter_recipes.md")
CLONE_AUDIT = os.path.join(WORKSPACE, "clone_audit_2026-10-12", "baseline.jsonl")

OUT = HERE
REPOS_DIR = os.path.join(OUT, "repos")
TASKS_DIR = os.path.join(OUT, "tasks")
FAMILIES_DIR = os.path.join(OUT, "families")
UNCLONED_JSON = os.path.join(OUT, "uncloned.json")
COVERAGE_MD = os.path.join(OUT, "coverage.md")
README_MD = os.path.join(OUT, "README.md")
LOCK_PATH = os.path.join(OUT, "corpus.lock.jsonl")
ARCHIVED_MANIFESTS = "_archive/registry/manifests-skeleton-2026-10"

TRACK_EN = {"labs": "lab instrumentation", "robots": "robotics", "shared": "shared infrastructure"}

# Analyst profile taxonomy -> MHS adapter family (work/analysis/repo_profiles.jsonl)
PROFILE_FAMILY_MAP = {
    "gym-env": "gymnasium", "task-env": "gymnasium", "dm-env": "dm-env",
    "mujoco": "mujoco", "pybullet": "pybullet", "ros2": "ros2", "ros1": "ros1",
    "gazebo": "gazebo", "isaac-sim": "isaac-sim", "isaac-lab": "isaac-lab",
    "isaac-gym": "isaac-gym", "unity": "unity", "airsim": "airsim",
    "sapien": "sapien", "drake": "drake", "brax-mjx": "brax-mjx",
    "habitat": "habitat", "webots": "webots", "coppelia": "other",
    "engine-only": "other", "protocol-bridge": "http-api",
    "mcp-server": "mcp-proxy", "lab-serial": "serial",
    "lab-visa-scpi": "scpi-visa", "lab-micromanager": "micromanager",
    "lab-qcodes-ophyd": "qcodes", "lab-bluesky": "bluesky-ophyd",
    "lab-opentrons": "opentrons", "lab-pylabrobot": "pylabrobot",
    "lab-sila2": "sila2", "lab-flowchem": "flowchem",
    "lab-madsci": "madsci", "lab-orchestrator": "other",
    "http-api": "http-api", "sdk-library": "python-object",
    "measurement-model": "python-object", "lerobot-real": "lerobot-real",
    "tooling": "other", "docs-only": "other", "assets": "other", "other": "other",
}
PROFILE_INTERFACE_LABELS = {
    "cli": "CLI", "gazebo": "Gazebo", "http_rest": "HTTP/REST",
    "gymnasium": "Gymnasium", "mujoco": "MuJoCo", "ros2": "ROS 2",
    "ros1": "ROS 1", "grpc": "gRPC", "pyserial": "Serial", "isaac": "Isaac Sim",
    "websocket": "WebSocket", "pybullet": "PyBullet", "pyvisa": "SCPI/VISA",
    "zeromq": "ZeroMQ", "unity": "Unity", "lerobot": "LeRobot", "mcp": "MCP",
    "brax": "Brax/MJX", "mavlink": "MAVLink", "epics": "EPICS",
    "airsim": "AirSim", "dm_env": "dm_env", "sapien": "SAPIEN",
    "opentrons": "Opentrons", "modbus": "Modbus", "opcua": "OPC UA",
    "bluesky": "Bluesky/Ophyd", "micromanager": "Micro-Manager", "mqtt": "MQTT",
    "sila2": "SiLA 2", "pylabrobot": "PyLabRobot", "qcodes": "QCoDeS",
    "drake": "Drake", "habitat": "Habitat", "webots": "Webots",
}
PROFILE_MARKER_BY_FEATURE = {
    "ros2_package": "ros2", "ros1_package": "ros1", "has_gazebo_world": "gazebo",
    "has_mjcf": "mujoco", "has_unity_project": "unity",
    "has_unreal_project": "unreal", "has_webots_world": "webots",
    "has_coppelia_scene": "other", "has_openapi_file": "http",
    "has_mcp_manifest": "mcp", "has_docker": "docker",
}
PROFILE_MARKER_BY_DEP = {
    "mujoco": "mujoco", "pybullet": "pybullet", "gymnasium": "gymnasium",
    "gym": "gymnasium", "dm_env": "dm_env", "dm-control": "dm_env",
    "rclpy": "ros2", "rclcpp": "ros2", "ament_cmake": "ros2",
    "ament-cmake": "ros2", "catkin": "ros1", "rospy": "ros1", "roscpp": "ros1",
    "pyvisa": "scpi_visa", "pyserial": "serial", "serial": "serial",
    "opentrons": "opentrons", "pylabrobot": "pylabrobot", "qcodes": "qcodes",
    "ophyd": "bluesky_ophyd", "bluesky": "bluesky_ophyd", "sila2": "sila2",
    "mcp": "mcp", "fastapi": "http", "flask": "http", "requests": "http",
    "micromanager": "micromanager", "pymmcore": "micromanager",
    "isaacgym": "isaac_gym", "isaaclab": "isaac_lab", "sapien": "sapien",
    "pyrep": "other", "coppeliasim": "other", "habitat": "habitat",
    "drake": "drake", "webots": "webots", "airsim": "airsim",
    "lerobot": "lerobot", "brax": "brax_mjx", "mjx": "brax_mjx",
    "madsci": "madsci", "flowchem": "flowchem", "epics": "epics",
    "opcua": "opcua", "pymodbus": "serial",
}
# tier rules whose output is a generic fallback: a content-based analyst tier
# may replace them (never the other way round)
FALLBACK_TIER_RULES = {"B7-entry-detected", "C5-code-no-entry",
                       "C6-unknown-code", "D3-peripheral-fallback"}
FALLBACK_FAMILY_RULES = {"role-fallback", "language-fallback", "default",
                         "marker-fallback"}


def profile_catalog_row(profile, by_key, by_master_id):
    """Resolve the catalog row(s) a clone maps to, using the analyst profile.

    Returns (primary_row, extra_rows).  Extra rows are the catalog rows that
    share a master_id with the primary row (duplicate catalog entries); they
    are claimed so ``uncloned.json`` does not report a false gap.
    """
    if not profile:
        return None, []
    cat = profile.get("catalog") or {}
    primary = None
    url = cat.get("repo_url")
    if url:
        key = repo_key_from_url(url)
        primary = by_key.get(key)
    if primary is None:
        for mid in (cat.get("master_ids") or []):
            rows = by_master_id.get(mid)
            if rows:
                primary = rows[0]
                break
    extras = []
    for mid in (cat.get("master_ids") or []):
        for row in by_master_id.get(mid, []):
            if primary is None or row["_row"] != primary["_row"]:
                if row not in extras:
                    extras.append(row)
    return primary, extras


def enrich_scan(scan: dict, profile, caps_rows) -> dict:
    """Merge the analyst profile's static-scan facts into our scan feature dict.

    Only structural evidence is merged (files/deps/entry markers); it does not
    change the evidence state, which stays `static_scan`.
    """
    if not profile:
        return scan
    out = dict(scan or {})
    markers = dict(out.get("markers") or {})
    features = ((profile.get("features") or {}))
    for feat, marker in PROFILE_MARKER_BY_FEATURE.items():
        if features.get(feat):
            markers[marker] = markers.get(marker, 0) + 1
    deps = ((profile.get("dependencies") or {}).get("top") or [])
    for dep in deps:
        name = str(dep.get("name", "")).lower()
        marker = PROFILE_MARKER_BY_DEP.get(name)
        if marker:
            markers[marker] = markers.get(marker, 0) + 1
    out["markers"] = dict(sorted(markers.items()))
    # languages from the profile (their `languages` is a dict with a dominant)
    languages = list(out.get("languages") or [])
    profile_langs = profile.get("languages") or {}
    dominant = profile_langs.get("dominant") if isinstance(profile_langs, dict) else None
    if dominant and dominant not in languages:
        languages.insert(0, dominant)
    out["languages"] = languages[:8]
    # build systems from the profile when our scan missed them
    if not out.get("build_systems"):
        sys_map = {"python-pyproject": "python", "python-requirements": "python",
                   "python-setuptools": "python", "cargo": "cargo", "npm-node": "node",
                   "docker": "docker", "cmake": "cmake", "make": "make",
                   "julia": "julia", "r": "r"}
        found = []
        for item in (profile.get("build_systems") or []):
            name = item.get("name") if isinstance(item, dict) else str(item)
            mapped = sys_map.get(name)
            if mapped and mapped not in found:
                found.append(mapped)
        out["build_systems"] = found
    # entry-point evidence: only trustworthy kinds (main scripts / launch files /
    # compiled binaries), not Makefile-derived "console_script" names.
    evidence = list(out.get("entry_evidence") or [])
    for ep in (profile.get("entry_points") or []):
        kind = (ep or {}).get("kind")
        path = (ep or {}).get("path")
        if kind in {"main_script", "rust_bin", "dotnet_main", "ros_launch"} and path:
            item = f"analyst scan entry: {kind} {path}"[:200]
            if item not in evidence:
                evidence.append(item)
    out["entry_evidence"] = evidence[:12]
    return out


def profile_interface_names(profile, scan):
    """Interfaces detected with strong evidence by the analyst scan."""
    if not profile:
        return []
    out = []
    for name, info in (profile.get("interfaces") or {}).items():
        if not isinstance(info, dict) or not info.get("detected"):
            continue
        if info.get("strength") == "weak":
            continue
        label = PROFILE_INTERFACE_LABELS.get(name)
        if label:
            out.append(label)
    return dedupe(out)

FAMILY_ENUM = [
    "python-object", "gymnasium", "dm-env", "mujoco", "pybullet", "isaac-sim",
    "isaac-lab", "isaac-gym", "gazebo", "ros2", "ros1", "webots", "unity",
    "sapien", "drake", "brax-mjx", "habitat", "airsim", "lerobot-real",
    "http-api", "mcp-proxy", "scpi-visa", "serial", "sila2", "opentrons",
    "micromanager", "flowchem", "madsci", "pylabrobot", "bluesky-ophyd",
    "qcodes", "cli-process", "docker", "replay", "other",
]

TRUTHY_PREFIXES = ("yes", "true", "是", "partial", "部分", "通过", "依赖",
                   "可用", "支持", "some", "limited")
FALSY_PREFIXES = ("no", "false", "否", "无", "不适用", "unknown", "未知",
                  "none", "not ")


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def build_date() -> str:
    """The registry's generation date: ``$MHS_REGISTRY_DATE`` or ``DEFAULT_DATE`` (never SOURCE_DATE_EPOCH)."""
    date = os.environ.get("MHS_REGISTRY_DATE")
    if date:
        return date
    return DEFAULT_DATE


def truthy(value: str) -> bool:
    v = (value or "").strip().lower()
    if not v:
        return False
    for p in FALSY_PREFIXES:
        if v.startswith(p):
            return False
    for p in TRUTHY_PREFIXES:
        if v.startswith(p):
            return True
    return False


def slugify(text: str, maxlen: int = 120) -> str:
    s = text.strip().lower()
    s = re.sub(r"[^a-z0-9_.-]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-._")
    if not s:
        s = "x"
    return s[:maxlen]


def tagify(text: str, maxlen: int = 60) -> str:
    s = text.strip().lower()
    s = re.sub(r"[^a-z0-9 -]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip(" -")
    if not s or not s[0].isalnum():
        s = "x " + s
    return s[:maxlen].rstrip(" -")


def package_id_for(owner: str, repo: str) -> str:
    """Stable package id: gh.<owner>/<repo>, lowercase (MHS-007 REG-004)."""
    package_id = "gh." + slugify(owner, 60) + "/" + slugify(repo, 80)
    if not re.match(r"^gh\.[a-z0-9_.-]+/[a-z0-9_.-]+$", package_id):
        package_id = "gh." + slugify(f"{owner}-{repo}", 120) + "/" + slugify(repo or "repo", 80)
    return package_id.lower()


def dedupe(items):
    seen = set()
    out = []
    for item in items:
        key = item if isinstance(item, str) else json.dumps(item, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def split_multi(value: str, seps=r"\s*[;|]\s*"):
    if not value:
        return []
    return [p.strip() for p in re.split(seps, value) if p.strip()]


CJK_RE = TC.CJK_RE   # CJK ideographs, punctuation and full-width forms


def en_field(zh: str):
    """Glossary-translate one catalog field; return None unless fully English."""
    if not zh or is_unknown(zh):
        return None
    rendered = FD.translate_zh(zh)
    rendered = re.sub(r"\s*\[zh\]\s*$", "", rendered).strip()
    if not rendered or CJK_RE.search(rendered):
        return None
    return rendered


def is_unknown(value: str) -> bool:
    return (value or "").strip().lower() in {"", "unknown", "none", "无", "不适用", "未知"}


def file_sha256(path: str) -> str:
    import hashlib
    h = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
    except OSError:
        return "sha256:unavailable"
    return "sha256:" + h.hexdigest()


# ---------------------------------------------------------------------------
# inputs
# ---------------------------------------------------------------------------
def load_catalog():
    with open(CATALOG_CSV, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for i, row in enumerate(rows):
        row["_row"] = i + 2  # CSV record number incl. header (catalog convention)
    return rows


def load_capabilities():
    caps = {}
    if not os.path.exists(CAPS_CSV):
        return caps
    with open(CAPS_CSV, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            url = (row.get("canonical_repo_url") or row.get("repo_url") or "").strip()
            key = repo_key_from_url(url)
            if not key:
                continue
            caps.setdefault(key, []).append(row)
    return caps


def load_core_capabilities():
    """MHS core capability catalogue: id -> class document (MHS/spec/capabilities.json)."""
    if not os.path.exists(CORE_CAPS_JSON):
        raise SystemExit(f"[registry] missing core capability catalogue: {CORE_CAPS_JSON}")
    with open(CORE_CAPS_JSON, encoding="utf-8") as fh:
        doc = json.load(fh)
    caps = {}
    for entry in doc.get("capabilities", []):
        cid = entry.get("capability_id")
        if cid:
            caps[cid] = entry
    return caps


def repo_key_from_url(url: str):
    m = re.match(r"https?://github\.com/([^/]+)/([^/#?]+)", url or "", re.IGNORECASE)
    if not m:
        return None
    return (m.group(1).lower(), m.group(2).lower().rstrip("."))


def load_aliases():
    alias = {}
    if not os.path.exists(ALIASES_CSV):
        return alias
    with open(ALIASES_CSV, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if (row.get("applied") or "").lower() != "true":
                continue
            a = repo_key_from_url(row.get("alias_url", ""))
            b = repo_key_from_url(row.get("canonical_repo_url", ""))
            if a and b:
                alias[a] = b
    return alias


def load_profiles():
    """Optional catalog-analyst output: work/analysis/repo_profiles.jsonl.

    Accepted keys per line (all optional): owner, repo, repo_url, family,
    tier, ring, evidence_state/evidence.read_by, entry_points, files_read,
    description, notes, blockers.  Unknown keys are ignored.
    """
    profiles = {}
    if not os.path.exists(PROFILES_JSONL):
        return profiles
    with open(PROFILES_JSONL, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            key = None
            if obj.get("owner") and obj.get("repo"):
                key = (str(obj["owner"]).lower(), str(obj["repo"]).lower())
            elif obj.get("repo_url"):
                key = repo_key_from_url(str(obj["repo_url"]))
            if key:
                profiles[key] = obj
    return profiles


def load_recon():
    """Per-repo recon notes written by the recon agent: work/recon/<track>/<owner>__<repo>.md"""
    notes = {}
    for track in ("labs", "robots"):
        d = os.path.join(RECON_ROOT, track)
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            if not name.endswith(".md") or name.endswith("adapter_recipes.md"):
                continue
            stem = name[:-3]
            if "__" not in stem:
                continue
            owner, repo = stem.rsplit("__", 1)
            path = os.path.join(d, name)
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    text = fh.read(200_000)
            except OSError:
                continue
            notes[(owner.lower(), repo.lower())] = {
                "track": track, "path": os.path.relpath(path, WORKSPACE),
                "text": text,
            }
    return notes


def load_scan_summary():
    """Optional catalog-analyst availability notes for uncloned catalog rows."""
    path = os.path.join(ANALYSIS_DIR, "scan_summary.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}
    notes = {}
    for item in (data.get("catalog_rows_without_clone") or []):
        url = item.get("repo_url")
        if url:
            notes[url.lower()] = {"status": item.get("status"),
                                  "note": item.get("note")}
    return notes


def load_recipe_notes():
    """Optional work/recon/{labs,robots}/adapter_recipes.md, split by ## heading."""
    notes = []
    for path in (RECIPES_LABS, RECIPES_ROBOTS):
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read(400_000)
        except OSError:
            continue
        notes.append({"path": os.path.relpath(path, WORKSPACE), "text": text})
    return notes


# ---------------------------------------------------------------------------
# feature derivation
# ---------------------------------------------------------------------------
def catalog_index(rows, aliases):
    by_key = {}
    for row in rows:
        key = (row["owner"].lower(), row["repo_name"].lower())
        by_key[key] = row
    by_repo_name = {}
    for key, row in by_key.items():
        by_repo_name.setdefault(key[1], []).append(key)
    return by_key, by_repo_name


def pair_clone_with_catalog(track, owner, repo, by_key, by_repo_name, aliases,
                            profile_row=None):
    """Return (catalog_row|None, join_kind)."""
    key = (owner.lower(), repo.lower())
    if key in by_key:
        return by_key[key], "exact"
    if profile_row is not None:
        return profile_row, "analyst_catalog"
    if key in aliases and aliases[key] in by_key:
        return by_key[aliases[key]], "alias"
    # conservative fallback: repo_name is unique in the catalog and the local
    # clone name matches exactly.  Documented in coverage.md.
    candidates = by_repo_name.get(key[1], [])
    if len(candidates) == 1:
        return by_key[candidates[0]], "repo_name_unique"
    return None, "none"


def family_haystacks(row, scan, caps_rows, recon):
    """Weighted text sources for family scoring."""
    sources = []  # (weight, text)
    if row is not None:
        sources.append((10, row.get("backend_family", "")))
        sources.append((7, row.get("integration_interfaces", "")))
        sources.append((2, row.get("repo_name", "") + " " + row.get("description_zh", "") + " " + row.get("category", "") + " " + row.get("adapter_role", "")))
        sources.append((5, row.get("minimal_adapter_entry", "") + " " + row.get("recommended_integration", "") + " " + row.get("blockers", "") + " " + row.get("reusable_adapter_group", "")))
    if caps_rows:
        text = " ".join(" ".join(str(v) for k, v in c.items()
                                 if k in ("backend_or_environment", "device_or_robot",
                                          "initialization_api", "action_api",
                                          "observation_api", "observation_types",
                                          "state_query", "stop_cancel_reset",
                                          "integration_notes"))
                        for c in caps_rows)
        sources.append((5, text))
    if recon:
        sources.append((8, recon.get("text", "")))
    if scan:
        sources.append((3, scan.get("readme_head", "")))
        sources.append((4, " ".join(sorted(scan.get("markers", {})))))
    return sources


def classify_family(row, scan, caps_rows, recon):
    """Score adapter families with an explicit, source-weighted rule table.

    The winning family is the one matched in the *strongest* evidence source
    (catalog backend_family = 10, catalog interfaces = 7, capability-table API
    hints = 5, scan markers = 4, README = 3, repo name/description = 2); ties
    are broken by the rule-table order (most specific family first).  Summing
    keyword hits across sources would let README keyword spam outvote the
    catalog's explicit backend family, so we deliberately do not sum.
    """
    sources = family_haystacks(row, scan, caps_rows, recon)
    best = None  # (weight, -rule_index, family, patterns)
    for index, (family, patterns) in enumerate(FD.FAMILY_RULES):
        best_weight = 0
        hits = []
        for weight, text in sources:
            if not text or weight <= best_weight:
                continue
            for rx in patterns:
                found = rx.findall(text)
                if found:
                    hits.append(rx.pattern)
                    best_weight = max(best_weight, weight)
                    break
        if best_weight:
            candidate = (best_weight, -index, family, hits)
            if best is None or candidate[:2] > best[:2]:
                best = candidate
    if best:
        weight, _neg, family, hits = best
        return _task_env_preference(family, weight, hits, row, scan), weight, hits[:6], "scored"
    # deterministic fallbacks (no rule matched anywhere)
    role = (row or {}).get("adapter_role", "")
    markers = set((scan or {}).get("markers", {}))
    for marker, family in (("gymnasium", "gymnasium"), ("mujoco", "mujoco"),
                            ("pybullet", "pybullet"), ("ros2", "ros2"),
                            ("gazebo", "gazebo"), ("mcp", "mcp-proxy"),
                            ("scpi_visa", "scpi-visa"), ("micromanager", "micromanager"),
                            ("http", "http-api"), ("serial", "serial")):
        if marker in markers:
            return family, 1, [f"scan-marker:{marker}"], "marker-fallback"
    if "任务环境" in role:
        return "gymnasium", 0, ["role:task-environment"], "role-fallback"
    if "设备SDK" in role or "设备 SDK" in role:
        return "python-object", 0, ["role:device-sdk"], "role-fallback"
    if "协议桥接" in role:
        return "http-api", 0, ["role:protocol-bridge"], "role-fallback"
    lang = (row or {}).get("language", "")
    build = (scan or {}).get("build_systems", [])
    if "Python" in lang or "python" in build:
        return "python-object", 0, ["language:python"], "language-fallback"
    return "other", 0, ["default:other"], "default"


# Families whose bridge is a raw engine, so a Gym/dm_env API on a task-env
# repo is better wrapped by the task-env bridge.  Isaac/Habitat/AirSim have
# their own task APIs and dedicated bridge families, so they are not rewritten.
ENGINE_FAMILIES = {"mujoco", "pybullet", "gazebo", "webots", "unity", "sapien",
                   "drake", "brax-mjx"}


def _task_env_preference(family, weight, hits, row, scan):
    """Prefer the task-environment bridge when a repo exposes a Gym/dm_env API.

    A repo whose catalog backend says `MuJoCo` but whose role is a task
    environment and whose scan finds `gymnasium`/`dm_env` is more directly
    wrapped by the gymnasium/dm-env bridge (reset/step contract) than by the
    raw engine bridge; the engine remains the fidelity backend.
    """
    if family not in ENGINE_FAMILIES:
        return family
    markers = set((scan or {}).get("markers", {}))
    role = (row or {}).get("adapter_role", "")
    interfaces = ((row or {}).get("integration_interfaces") or "").lower()
    gym_api = ("gymnasium" in markers or "gym" in markers
               or "gymnasium" in interfaces or "gym" in interfaces)
    backend_family = ((row or {}).get("backend_family") or "").lower()
    # dm_env is only authoritative when the catalog says so; a README token is
    # not strong enough to override an explicit engine family.
    dm_api = ("dm_env" in interfaces or "dm_control" in interfaces
              or "dm_env" in backend_family or "dm_control" in backend_family
              or "dm-control" in backend_family)
    tasky = ("任务环境" in role or "直接模拟后端" in role or "完整环境" == (row or {}).get("category", ""))
    if dm_api and not gym_api:
        return "dm-env"
    if gym_api and tasky:
        return "gymnasium"
    return family


def parse_effort(row, tier):
    raw = ((row or {}).get("adaptation_effort") or "").strip()
    if raw.startswith("低"):
        return "E1"
    if raw.startswith("中高") or raw.startswith("中"):
        return "E2"
    if raw.startswith("高"):
        return "E3"
    return {"A": "E1", "B": "E2", "C": "E3", "D": "E4", "X": "EX"}.get(tier, "E2")


EFFORT_DAYS = {"E1": 1, "E2": 3, "E3": 8, "E4": 20, "EX": 0}


def parse_modes(row, family, scan):
    sim = truthy((row or {}).get("simulation_available", ""))
    hw_free = truthy((row or {}).get("hardware_free", ""))
    role = (row or {}).get("adapter_role", "")
    family_sim = family in FD.SIM_FAMILIES
    family_hw = family in FD.HARDWARE_FAMILIES
    markers = set((scan or {}).get("markers", {}))
    modes = []
    if sim or family_sim or "world" in (row or {}).get("integration_interfaces", "").lower():
        if family != "replay":
            modes.append("simulated")
    if (family_hw or not hw_free or "设备SDK" in role or "测量模型" in role
            or "控制器" in role or "hardware" in (row or {}).get("supported_platforms", "").lower()):
        if family not in FD.SIM_FAMILIES or not sim:
            modes.append("hardware")
    if family == "replay":
        modes.append("replay")
    if not modes:
        if family in FD.SIM_FAMILIES:
            modes = ["simulated"]
        elif family == "replay":
            modes = ["replay"]
        else:
            modes = ["hardware"]
    return dedupe(modes)


def classify_tier(row, family, scan, caps_rows, recon, modes):
    """Ordered explicit rule table.  Returns (tier, rule_id)."""
    if not scan or scan.get("files", 0) == 0:
        return "X", "X1-empty-clone"
    role = (row or {}).get("adapter_role", "")
    category = (row or {}).get("category", "")
    build = scan.get("build_systems", [])
    has_code = bool(scan.get("ext_counts")) or bool(build)
    entry = bool(scan.get("entry_evidence"))
    catalog_entry = not is_unknown((row or {}).get("minimal_adapter_entry", ""))
    recon_entry = bool(recon)
    entry_ev = entry or catalog_entry or recon_entry
    sim = truthy((row or {}).get("simulation_available", "")) or family in FD.SIM_FAMILIES
    role_direct = "直接模拟后端" in role
    role_task = "任务环境" in role
    role_sdk = "设备SDK" in role or "设备 SDK" in role
    role_bridge = "协议桥接" in role
    role_ctrl = "控制器" in role
    role_engine = "物理引擎" in role
    role_asset = "场景资产" in role
    role_measure = "测量模型" in role
    role_periph = "外围工具" in role or "辅助工具" in role
    periph_cat = category in {"辅助工具", "自动分类/发现", "数据集", "策略/算法"}
    sim_declared_no = (row or {}).get("simulation_available", "").lower().startswith(("no", "false", "否"))

    if role_periph and not (role_sdk or role_bridge or role_direct or role_task):
        return "D", "D1-peripheral-role"
    if periph_cat and not (role_sdk or role_bridge or role_direct or role_task or role_ctrl):
        return "D", "D2-peripheral-category"
    if role_direct and entry_ev and has_code:
        return "A", "A1-direct-backend-entry"
    if role_task and family in FD.SIM_FAMILIES and entry_ev and has_code:
        return "A", "A2-task-env-entry"
    if role_sdk and (has_code or build):
        return "B", "B1-device-sdk"
    if role_bridge and (has_code or build):
        return "B", "B2-protocol-bridge"
    if role_measure and (has_code or build):
        return "B", "B3-measurement-model"
    if role_ctrl and (has_code or build) and family in FD.SIM_FAMILIES | FD.HARDWARE_FAMILIES:
        return "B", "B4-controller"
    if role_task:
        return "B", "B5-task-env-wrap"
    if role_engine:
        return "C", "C1-physics-engine"
    if role_asset:
        return "C", "C2-scene-asset"
    if role_direct or role_task:
        return "C", "C3-backend-needs-scenario"
    if role_sdk or role_bridge or role_ctrl or role_measure:
        return "B", "B6-role-without-entry"
    if entry_ev and has_code and not sim_declared_no:
        return "B", "B7-entry-detected"
    if sim and has_code:
        return "C", "C4-sim-needs-scenario"
    if role_periph:
        return "D", "D3-peripheral-fallback"
    if has_code:
        return "C", "C5-code-no-entry"
    return "C", "C6-unknown-code"


def ring_for(tier, evidence_state):
    if tier in ("A", "B"):
        return 1 if evidence_state == "agent_read" else 2
    return 3


def extract_latin_keywords(description_zh: str, limit: int = 6) -> list[str]:
    if not description_zh:
        return []
    stop = {
        "python", "api", "sdk", "gui", "readme", "gpu", "cpu", "mhs", "ros",
        "http", "https", "github", "com", "www", "the", "and", "for", "with",
        "of", "on", "in", "to", "an", "is", "are", "be", "by", "or", "as",
        "at", "from", "into", "via", "using", "use", "based", "implementation",
        "implements", "framework", "library", "package", "project", "tool",
        "tools", "toolkit", "support", "supports", "provide", "provides",
        "including", "include", "example", "examples", "code", "open", "source",
        "new", "all", "its", "this", "that", "which", "can", "not", "non",
    }
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9_.+\-]{1,40}", description_zh)
    out = []
    for token in tokens:
        low = token.lower().strip(".")
        if low in stop or len(low) < 2:
            continue
        if token not in out:
            out.append(token)
        if len(out) >= limit:
            break
    return out


def make_description(row, track, family, tier, evidence_state, scan, owner, repo, plan=None):
    """Short, factual English summary built only from catalog fields.

    The Chinese catalog text is never machine-translated beyond the fixed
    glossary in family_data.py; fields that cannot be rendered completely in
    English are omitted rather than leaking mixed-language fragments.
    """
    cat = en_field((row or {}).get("category", ""))
    role = en_field((row or {}).get("adapter_role", ""))
    dom = en_field((row or {}).get("domain", ""))
    backend = en_field((row or {}).get("backend_family", ""))
    lang = (row or {}).get("language", "")
    if is_unknown(lang):
        detected = (scan or {}).get("languages", [])
        lang = ", ".join(detected[:3]) if detected else "unknown"
    lead = f"{owner}/{repo}: "
    if cat:
        lead += cat
    else:
        lead += "repository"
    if dom:
        lead += f" for {dom}"
    lead += f" ({TRACK_EN.get(track, track)} track)."
    parts = [lead]
    if role and tier in ("A", "B", "C"):
        parts.append(f"Catalog role: {role}.")
    if backend:
        parts.append(f"Declared backend: {backend}.")
    parts.append(f"Language: {lang}.")
    keywords = extract_latin_keywords((row or {}).get("description_zh", ""))
    if keywords:
        parts.append("Catalog keywords: " + ", ".join(keywords) + ".")
    if plan is None:
        if tier in ("D", "X"):
            plan = (f"OpenMHS plan: not targeted as a device (tier {tier}); "
                    f"evidence {evidence_state}.")
        else:
            plan = f"OpenMHS plan: {family} family, tier {tier}, evidence {evidence_state}."
    parts.insert(1, plan)    # the plan sentence survives the length cut below
    parts = [p for p in parts if not CJK_RE.search(p)]
    desc = " ".join(parts).replace("[zh]", "")
    desc = re.sub(r"\s{2,}", " ", desc).strip()
    if len(desc) > 300:
        cut = desc[:300]
        # prefer a sentence boundary, else a word boundary; never end mid-word
        boundary = max(cut.rfind(". "), cut.rfind("; "), cut.rfind(", "))
        if boundary >= 200:
            desc = cut[:boundary + 1]
        else:
            desc = cut.rsplit(" ", 1)[0].rstrip(" ,;") + "."
    if not desc.endswith("."):
        desc += "."
    return desc


def make_next_action(row, family, tier, evidence_state, blockers, scan, recon):
    bridge = FD.FAMILY_BRIDGE.get(family, "shim")
    if tier == "X":
        return ("Clone is empty; re-clone the repository at a pinned commit or "
                "exclude it from the corpus before attempting an adapter.")
    if tier == "D":
        return ("Not targeted as a device (peripheral/tooling). Optionally reuse "
                "as test tooling; no MHS adapter planned.")
    if tier == "C":
        return (f"Pick a concrete scenario/task for this {family} asset or engine, then "
                f"write an adapter manifest binding {bridge} to a device with "
                f"world.*/motion.* capabilities and a fidelity contract.")
    if tier == "B":
        target = "the native SDK entry point"
        if recon:
            target = "the entry points cited in the recon notes"
        elif (scan or {}).get("entry_evidence"):
            target = "a detected entry point"
        return (f"Write a thin {bridge} shim for {target}, add an mhs-adapter.json "
                f"(declared here), then package and run it; resolve: "
                f"{'; '.join(blockers[:3]) if blockers else 'no catalog blocker recorded'}.")
    # tier A
    entry = "detected entry point"
    if recon:
        entry = "agent-read entry points"
    elif not is_unknown((row or {}).get("minimal_adapter_entry", "")):
        entry = "catalog minimal_adapter_entry"
    return (f"Start the {bridge} bridge on the {entry}, bind world.*/motion.* "
            f"capabilities against the declared adapter manifest, and record a CL2 "
            f"run; then close: {'; '.join(blockers[:3]) if blockers else 'no catalog blocker recorded'}.")


def collect_blockers(row, scan, family, tier):
    blockers = []
    if tier == "X":
        return ["local clone is empty (no files beyond VCS metadata)"]
    cat_blockers = (row or {}).get("blockers", "")
    if cat_blockers and not is_unknown(cat_blockers) and cat_blockers.strip() not in {"无", "none"}:
        blockers.append(cat_blockers.strip()[:240])
    if not scan or not scan.get("build_files"):
        blockers.append("no standard build file detected in bounded scan")
    if scan and not scan.get("readme"):
        blockers.append("no README in repo root; entry point unverified")
    if scan and scan.get("files") and not scan.get("entry_evidence"):
        blockers.append("no entry point detected in bounded scan")
    lic = (row or {}).get("license", "")
    if is_unknown(lic) or lic.startswith(("NOASSERTION", "unknown")):
        blockers.append("license unknown or NOASSERTION; confirm reuse terms")
    elif scan and not scan.get("license_file") and not is_unknown(lic):
        blockers.append("no LICENSE file at repo root; license from catalog only")
    runtime = (row or {}).get("runtime_requirements", "")
    if re.search(r"gpu|cuda|nvidia|rtx|vulkan", runtime, re.IGNORECASE):
        blockers.append("catalog declares GPU/accelerator requirements")
    if (row or {}).get("archived", "").lower() == "true":
        blockers.append("upstream repository archived")
    if (row or {}).get("simulation_available", "").lower().startswith("no"):
        blockers.append("catalog declares no simulation path")
    if tier == "C":
        blockers.append("needs a concrete scenario/model before it is a device")
    if family == "other":
        blockers.append("no v1.0 MHS bridge family; requires a shim")
    return dedupe(blockers)[:6]


# ---------------------------------------------------------------------------
# records
# ---------------------------------------------------------------------------
INTERFACE_LABELS = {
    "ros2": "ROS 2", "ros1": "ROS 1", "gazebo": "Gazebo", "mujoco": "MuJoCo",
    "pybullet": "PyBullet", "gymnasium": "Gymnasium", "dm_env": "dm_env",
    "isaac_sim": "Isaac Sim", "isaac_lab": "Isaac Lab", "isaac_gym": "Isaac Gym",
    "webots": "Webots", "unity": "Unity", "unreal": "Unreal",
    "airsim": "AirSim", "sapien": "SAPIEN", "drake": "Drake",
    "brax_mjx": "Brax/MJX", "habitat": "Habitat", "opentrons": "Opentrons",
    "pylabrobot": "PyLabRobot", "flowchem": "Flowchem", "madsci": "MADSci",
    "sila2": "SiLA 2", "mcp": "MCP", "scpi_visa": "SCPI/VISA",
    "qcodes": "QCoDeS", "bluesky_ophyd": "Bluesky/Ophyd",
    "micromanager": "Micro-Manager", "http": "HTTP/REST", "serial": "Serial",
    "mqtt": "MQTT", "zeromq": "ZeroMQ", "opcua": "OPC UA", "epics": "EPICS",
    "tango": "Tango", "mavlink": "MAVLink", "docker": "Docker",
    "replay": "Replay", "lerobot": "LeRobot", "cli": "CLI",
}


def collect_interfaces(row, scan, profile=None):
    interfaces = []
    if row:
        for item in split_multi(row.get("integration_interfaces", "")):
            item = item.strip()
            if item and not is_unknown(item):
                interfaces.append(item[:80])
    for marker in sorted((scan or {}).get("markers", {})):
        label = INTERFACE_LABELS.get(marker)
        if label:
            interfaces.append(label)
    interfaces.extend(profile_interface_names(profile, scan))
    return dedupe(interfaces)[:12]


def recon_entry_points(text: str, limit: int = 8) -> list:
    """Extract entry-point bullets from the recon notes' (a) section only."""
    sections = re.split(r"(?m)^(?=#{2,4}\s)", text or "")
    picked = []
    for section in sections:
        heading = section.splitlines()[0] if section.splitlines() else ""
        if not re.search(r"\(a\)|entry[ _-]?points?", heading, re.IGNORECASE):
            continue
        for line in section.splitlines()[1:]:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if not re.search(r"`[^`]+`|\.(py|rs|cpp|hpp|c|h|toml|cfg|yaml|yml|json|xml):\d+", stripped):
                continue
            picked.append("recon (a): " + stripped.lstrip("-* ")[:220])
            if len(picked) >= limit:
                return picked
    return picked


def make_record(track, owner, repo, row, join_kind, scan, caps_rows, recon, profile):
    family, score, matched, family_rule = classify_family(row, scan, caps_rows, recon)
    package_id = package_id_for(owner, repo)
    profile_class = (profile or {}).get("classification") or {}
    analyst_family = PROFILE_FAMILY_MAP.get(str(profile_class.get("family", "")))
    analyst_family_conf = float(profile_class.get("family_confidence") or 0.0)
    analyst_source = str(profile_class.get("family_source") or "")
    hardware_family_override = (
        analyst_family in FD.HARDWARE_FAMILIES
        and analyst_family_conf >= 0.9
        and "catalog" in analyst_source
        and family != analyst_family
    )
    if (analyst_family in FAMILY_ENUM
            and (family_rule in FALLBACK_FAMILY_RULES or hardware_family_override)
            and analyst_family_conf >= 0.6):
        family = analyst_family
        score = int(analyst_family_conf * 100)
        matched = ["analyst-profile:" + str(profile_class.get("family"))]
        family_rule = "analyst-profile"
    modes, mode_override = FD.apply_mode_override(package_id, parse_modes(row, family, scan))
    tier, tier_rule = classify_tier(row, family, scan, caps_rows, recon, modes)
    if tier in ("D", "X"):
        modes = []
    analyst_tier = str(profile_class.get("tier", ""))
    analyst_tier_conf = float(profile_class.get("tier_confidence") or 0.0)
    if (analyst_tier in {"A", "B", "C", "D", "X"} and tier_rule in FALLBACK_TIER_RULES
            and analyst_tier_conf >= 0.6):
        tier = analyst_tier
        tier_rule = "analyst-profile"
        if tier in ("D", "X"):
            modes = []
    evidence_state = "static_scan"
    read_by = "static_analysis"
    files_read = 0
    prov = []
    ev_notes = ""
    if scan and scan.get("files", 0) > 0:
        files_read = (len(scan.get("build_files", []))
                      + (1 if scan.get("readme") else 0)
                      + (1 if scan.get("license_file") else 0))
        ev_notes = (f"bounded static scan: {scan['files']} files enumerated (max depth 3), "
                    f"{files_read} opened (README head <=16 KiB, build files <=32 KiB)")
    if recon:
        evidence_state, read_by = "agent_read", "agent"
        refs = re.findall(r"(?:[\w./-]+)\.(?:py|rs|cpp|hpp|c|h|md|toml|cfg|yaml|yml|json|xml)(?::\d+)?", recon["text"])
        files_read = max(files_read, min(len(set(refs)), 200))
        prov.append(recon["path"])
        ev_notes = (ev_notes + "; " if ev_notes else "") + \
                   f"agent-read source notes in {recon['path']} (entry points with file:line; not executed)"
    if profile:
        p_state = str(profile.get("evidence_state") or (profile.get("evidence") or {}).get("state") or "")
        if p_state in ("static_scan", "agent_read"):
            evidence_state = p_state
            read_by = "agent" if p_state == "agent_read" else "static_analysis"
        if profile.get("notes"):
            ev_notes = (ev_notes + "; " if ev_notes else "") + str(profile["notes"])[:400]
    if tier == "X":
        evidence_state, read_by = "declared", "catalog"
    elif evidence_state == "declared":
        evidence_state, read_by = "declared", "catalog"
    if profile and profile.get("files_read"):
        try:
            files_read = max(files_read, int(profile["files_read"]))
        except (TypeError, ValueError):
            pass
    ring = ring_for(tier, evidence_state)

    caps = []   # capabilities_offered comes from the task card (code-derived candidate classes)
    adapter_state = "none"
    bridge = FD.FAMILY_BRIDGE.get(family, "shim")

    blockers = collect_blockers(row, scan, family, tier)
    if recon and not blockers:
        blockers = ["runtime not executed; only source reading evidence"]
    effort = parse_effort(row, tier)
    next_action = make_next_action(row, family, tier, evidence_state, blockers, scan, recon)
    if profile and profile.get("next_action"):
        next_action = str(profile["next_action"])[:500]

    license_raw = (row or {}).get("license", "") or "unknown"
    languages = []
    if row and not is_unknown(row.get("language", "")):
        languages.extend(split_multi(row["language"], seps=r"\s*[,;|]\s*"))
    languages.extend((scan or {}).get("languages", [])[:4])
    languages = [x for x in dedupe(languages) if not is_unknown(x)][:6]
    build_systems = list((scan or {}).get("build_systems", []))
    interfaces = collect_interfaces(row, scan, profile)

    stars = 0
    try:
        stars = max(0, int((row or {}).get("stars", "0") or 0))
    except (TypeError, ValueError):
        stars = 0
    last_commit = (row or {}).get("last_commit_at", "")
    if is_unknown(last_commit):
        last_commit = ""

    repo_url = (row or {}).get("repo_url") or f"https://github.com/{owner}/{repo}"
    entry_points = list((scan or {}).get("entry_evidence", []))[:8]
    if row and not is_unknown(row.get("minimal_adapter_entry", "")):
        entry_points.append("catalog minimal_adapter_entry: " + row["minimal_adapter_entry"][:220])
    if recon:
        entry_points.extend(recon_entry_points(recon["text"]))
    entry_points = dedupe(entry_points)[:12]

    package_id = package_id_for(owner, repo)
    domains = [d for d in (FD.translate_zh((row or {}).get("domain", "")) or "").replace("/", " ").split("; ")
               if d and d != "unknown"]
    tags = [tagify(TRACK_EN.get(track, track)), tagify(family), tagify(bridge + " bridge")]
    cat_tag = tagify(FD.translate_zh((row or {}).get("category", "")))
    if cat_tag:
        tags.append(cat_tag)
    role_tag = tagify(FD.translate_zh((row or {}).get("adapter_role", "")))
    if role_tag:
        tags.append(role_tag)
    if any(m == "simulated" for m in modes):
        tags.append("simulated")
    if any(m == "hardware" for m in modes):
        tags.append("hardware interface")
    tags = [t for t in dedupe(tags) if t][:12]

    description = make_description(row, track, family, tier, evidence_state, scan, owner, repo)
    if profile and profile.get("description"):
        description = str(profile["description"])[:1200]

    record = OrderedDict()
    record["record_type"] = "package"
    record["id"] = package_id
    record["registry_id"] = REGISTRY_ID
    record["package_id"] = package_id
    record["repo_url"] = repo_url
    record["track"] = track
    record["owner"] = owner
    record["repo"] = repo
    record["title"] = f"{owner}/{repo}"
    record["description"] = description
    record["tags"] = tags
    record["domains"] = domains[:6]
    record["families"] = [family]
    record["tier"] = tier
    record["ring"] = ring
    record["modes"] = modes
    record["languages"] = languages
    record["build_systems"] = build_systems
    record["interfaces"] = interfaces
    record["license"] = license_raw
    record["simulation"] = truthy((row or {}).get("simulation_available", "")) or family in FD.SIM_FAMILIES
    record["hardware_free"] = truthy((row or {}).get("hardware_free", ""))
    record["stars"] = stars
    record["last_commit_at"] = last_commit
    adapter_obj = {
        "present": bool((scan or {}).get("has_mhs_adapter_file")),
        "manifest_ref": None,
        "state": adapter_state,
        "bridge": bridge,
        "entry_points": entry_points,
    }
    record["adapter"] = adapter_obj
    record["capabilities_offered"] = caps
    record["integration"] = {
        "recipe": f"families/{family}.md",
        "effort": effort,
        "estimated_days": EFFORT_DAYS.get(effort, 3),
        "blockers": blockers,
        "next_action": next_action[:500],
        "scenario_required": tier == "C",
    }
    record["evidence"] = {
        "state": evidence_state,
        "read_by": read_by,
        "files_read": int(files_read),
        "notes": ev_notes[:800] if ev_notes else "catalog fields only",
        "verified_at": BUILD_TS,
        "provenance_refs": prov[:6],
    }
    links = {"repo": repo_url}
    evidence_urls = split_multi((row or {}).get("evidence_urls", ""), seps=r"\s*[;|]\s*")
    for url in evidence_urls:
        # an API endpoint is not documentation (REGQ-12)
        if url.startswith("http") and "/blob/" not in url and "api.github.com" not in url:
            links["docs"] = url[:300]
            break
    record["links"] = links
    record["trust"] = "unsigned"
    record["local_path"] = f"{track}/{owner}/{repo}"
    catalog_refs = []
    if row:
        if not is_unknown(row.get("master_id", "")):
            catalog_refs.append(row["master_id"])
        catalog_refs.append(row["repo_url"])
    record["catalog_refs"] = dedupe(catalog_refs)[:4]
    record["updated_at"] = BUILD_TS
    record["x-vendor"] = {
        "mhs_registry": {
            "generator": "MHS/registry/build_registry.py",
            "registry_version": REGISTRY_VERSION,
            "generated_at": BUILD_TS,
        },
        "catalog": {
            "join": join_kind,
            "row": (row or {}).get("_row"),
            "track_raw": (row or {}).get("track", ""),
            "category_zh": (row or {}).get("category", ""),
            "adapter_role_zh": (row or {}).get("adapter_role", ""),
            "backend_family_raw": (row or {}).get("backend_family", ""),
            "description_zh": (row or {}).get("description_zh", ""),
            "priority": (row or {}).get("priority", ""),
            "scope": (row or {}).get("scope", ""),
            "verification_level": (row or {}).get("verification_level", ""),
            "mhs_support_raw": (row or {}).get("mhs_support", ""),
            "archived": (row or {}).get("archived", ""),
        },
        "analyst_profile": ({
            "merged": True,
            "catalog_mapped_via": ((profile or {}).get("catalog") or {}).get("mapped_via"),
            "catalog_status": ((profile or {}).get("catalog") or {}).get("catalog_status"),
            "family": profile_class.get("family"),
            "family_confidence": profile_class.get("family_confidence"),
            "family_source": profile_class.get("family_source"),
            "tier": profile_class.get("tier"),
            "tier_confidence": profile_class.get("tier_confidence"),
            "priority_score": ((profile or {}).get("priority") or {}).get("score"),
            "quality_flags": ((profile or {}).get("quality") or {}).get("flags", []),
        } if profile else {"merged": False}),
        "classification": {
            "family_rule": family_rule,
            "family_score": score,
            "family_matches": matched[:6],
            "tier_rule": tier_rule,
            "catalog_family": family,
            "catalog_tier": tier,
        },
        "scan": {
            "files": (scan or {}).get("files", 0),
            "build_systems": build_systems,
            "markers": (scan or {}).get("markers", {}),
            "entry_evidence_count": len((scan or {}).get("entry_evidence", [])),
        },
    }
    if mode_override:
        record["x-vendor"]["classification"]["mode_override"] = mode_override
    return record




# ---------------------------------------------------------------------------
# triage, licences, overlays and the final record
# ---------------------------------------------------------------------------

#: triage integration family -> registry family (``families[0]``; one vocabulary for
#: records, recipes and the site).  ``ros`` and ``http`` keep a more specific
#: catalogue family when it already is one of theirs.
TRIAGE_FAMILY = {
    "python-object": "python-object", "serial": "serial", "scpi": "scpi-visa", "gymnasium": "gymnasium",
    "mujoco": "mujoco", "pylabrobot": "pylabrobot", "sila2": "sila2", "qcodes": "qcodes", "ophyd": "bluesky-ophyd",
    "pymmcore-plus": "micromanager", "lerobot": "lerobot-real", "mcp-client": "mcp-proxy", "mavlink": "mavlink",
    "tag-bridge": "tag-bridge",
}
ROS_REGISTRY_FAMILIES = ("ros2", "ros1", "gazebo")
HTTP_REGISTRY_FAMILIES = ("http-api", "opentrons", "madsci", "flowchem")
#: structural markers a simulator family needs (an engine import, a model or project file);
#: a README or name match alone never keeps one (REGQ-08, MISSED-7)
SIM_MARKER_IMPORTS = {
    "gymnasium": {"gym", "gymnasium"}, "dm-env": {"dm_env", "dm_control"},
    "mujoco": {"mujoco", "mujoco_py", "dm_control"}, "pybullet": {"pybullet", "pybullet_envs", "pybullet_data"},
    "isaac-sim": {"isaacsim", "omni", "omni_isaac"}, "isaac-lab": {"isaaclab", "isaaclab_tasks", "isaaclab_assets"},
    "isaac-gym": {"isaacgym", "isaacgymenvs", "legged_gym"}, "gazebo": {"gazebo_msgs", "gz", "ignition"},
    "webots": {"controller", "deepbots"}, "unity": {"mlagents", "mlagents_envs"},
    "sapien": {"sapien", "mani_skill", "mani_skill2"}, "drake": {"pydrake"}, "brax-mjx": {"brax"},
    "habitat": {"habitat", "habitat_sim", "habitat_lab", "habitat_baselines", "igibson", "omnigibson"},
    "airsim": {"airsim", "cosysairsim"},
}


#: when the catalogue's simulator family has no marker, the first family the code does show
#: (engine-specific families before the generic task-environment APIs)
SIM_FALLBACK_ORDER = ("isaac-lab", "isaac-gym", "isaac-sim", "habitat", "sapien", "airsim", "unity", "webots",
                      "drake", "pybullet", "brax-mjx", "dm-env", "mujoco", "gymnasium", "gazebo")


def structural_sim_marker(family, facts):
    """Why a simulator family is structurally present (None when nothing in the code says so)."""
    if facts.scan is None:
        return "no scan"
    hit = sorted(facts.all_imports & SIM_MARKER_IMPORTS.get(family, set()))
    if hit:
        return f"imports {hit[0]}"
    markers = facts.markers
    tree = (facts.scan or {}).get("tree") or []
    if family == "gymnasium" and facts.python.get("gym_ids"):
        return "gym env registration"
    if family == "mujoco" and T.mjcf_models(facts):
        return "MJCF model"
    if family == "gazebo" and (int(markers.get("package_xml", 0)) or int(markers.get("launch_files", 0))
                               or any(p.endswith((".world", ".sdf")) for p in tree)):
        return "ROS/Gazebo package, launch or world files"
    if family == "webots" and any(p.endswith(".wbt") for p in tree):
        return "Webots world file"
    if family == "unity" and markers.get("unity_project"):
        return "Unity project"
    return None


def final_family(base, decision, facts, analyst_family):
    """(families[0], note): the triage family where one exists, else the catalogue family
    with simulator families kept only on a structural marker."""
    fam = decision.family
    if fam == "ros":
        if base in ROS_REGISTRY_FAMILIES:
            return base, None
        chosen = analyst_family if analyst_family in ("ros1", "ros2") else "ros2"
        return chosen, f"triage family ros (catalogue family {base})"
    if fam == "http":
        if base in HTTP_REGISTRY_FAMILIES:
            return base, None
        return "http-api", f"triage family http (catalogue family {base})"
    if fam in TRIAGE_FAMILY:
        mapped = TRIAGE_FAMILY[fam]
        return mapped, (None if mapped == base else f"triage family {fam} (catalogue family {base})")
    if base in FD.SIM_FAMILIES and structural_sim_marker(base, facts) is None:
        for other in SIM_FALLBACK_ORDER:
            marker = structural_sim_marker(other, facts) if other != base else None
            if marker and marker != "no scan":
                return other, f"catalogue family {base} has no structural marker; the code shows {other} ({marker})"
        return "other", f"catalogue family {base} dropped: no structural marker in the code"
    return base, None


def final_tier(tier, decision):
    """Registry tier reconciled with the triage decision (a skipped or reference repo is not a device)."""
    if decision.reason_code == "skip:empty":
        return "X"
    if decision.strategy == "reference" or (decision.strategy == "skip" and not decision.variant_of):
        return "D"
    if decision.strategy in T.DISPATCHABLE and tier in ("D", "X"):
        return "B"
    return tier


MODE_ORDER = {"hardware": 0, "hybrid": 1, "simulated": 2, "replay": 3}
#: families whose driver drives a simulator; a twin in one of them is a simulated device even when the repo also
#: carries code for the real robot (that hardware is a separate driver task)
SIMULATOR_FAMILIES = frozenset({"gymnasium", "mujoco"})
#: simulation environment and process-simulator classes (by class name or base class name)
_SIM_BASE = re.compile(r"(?:Env|Environment|Gym)$|^Simulator")


def hardware_evidence(facts):
    """Why the code drives real hardware: a ranked class with device API that uses a hardware transport
    (``triage.hardware_transport``), not a mock or simulator of the device and not a simulation environment
    class (an ``Env`` or ``Gym`` class, or a subclass of a ``Simulator`` class, that talks to a process simulator
    over COM, for example). None when nothing does."""
    for cls in facts.python.get("entry_classes") or []:
        hit = sorted(set(cls.get("transport") or []) & T.HARDWARE_TRANSPORTS)
        name = str(cls.get("symbol") or "").rsplit(":", 1)[-1]
        env_like = any(_SIM_BASE.search(n) for n in [name] + [str(b).rsplit(".", 1)[-1] for b in cls.get("bases") or []])
        if hit and int(cls.get("api", 0)) >= 2 and not T.is_mock_class(cls) and not env_like:
            return f"class {cls['symbol']} uses the hardware transport {hit[0]}"
    return None


def final_modes(record, decision, facts, mode_override):
    """Hardware first: a dual-mode repo is a hardware device plus a simulated device that models it.

    A repo whose code drives real hardware (:func:`hardware_evidence`) is never recorded as simulated only,
    unless its driver is a simulator family (gymnasium, mujoco) or its role is a simulation environment with
    a decided strategy.  A recon (``untriaged``) card is hardware first whatever its role: the recon confirms
    or drops the hardware mode.
    """
    if record["tier"] in ("D", "X"):
        return []
    base = list(record["modes"])
    if mode_override:
        return sorted(dict.fromkeys(base), key=MODE_ORDER.get)
    role = decision.role
    upstream_sim = any(TC._device_mock(m) for m in ((facts.scan or {}).get("mocks") or []))
    hardware = bool(hardware_evidence(facts))
    # a repo the catalogue calls a model or a simulation is hardware-capable only when its code uses a
    # hardware transport (curated overrides keep the role they set)
    no_hardware = decision.rule != "override" and bool(T.sim_catalogue(facts)) and not T.hardware_transport(facts)
    if role == "sim-env":
        modes = ["simulated"]
        if hardware and decision.strategy == "untriaged":
            # a recon card for a simulation repo that also carries real-robot code (deploy controllers, a
            # leader arm's motor bus, a serial sensor board) says so; a decided gymnasium or MuJoCo
            # family-config keeps the simulator as its driver and stays simulated
            modes = ["hardware", "simulated"]
    elif role == "twin-candidate":
        # a model of a real device. It is dual-mode, hardware first, when the code also drives the device: a
        # direct driver whose catalogue row or code shows hardware, or a protocol, lab-framework or ROS family
        # (or a recon card) whose code uses a hardware transport. A MuJoCo or Gymnasium twin is a simulated
        # device whose hardware is driven by another repo.
        drives = "hardware" in base or bool(T.hardware_transport(facts))
        if (drives and decision.strategy == "direct-driver") or (hardware and decision.family not in SIMULATOR_FAMILIES):
            modes = ["hardware", "simulated"]
        else:
            modes = ["simulated"]
    elif role in ("device-driver", "driver-pack"):
        modes = ["hardware"]
        if "simulated" in base or upstream_sim:
            modes.append("simulated")
        if "replay" in base:
            modes.append("replay")
    else:
        modes = sorted(dict.fromkeys(base), key=MODE_ORDER.get)
        if hardware and decision.strategy == "untriaged" and "hardware" not in modes:
            # a recon card for code that drives hardware says so: the recon confirms or drops the hardware mode
            modes = ["hardware"] + modes
    if no_hardware:
        modes = [m for m in modes if m != "hardware"] or ["simulated"]
    return modes or ["hardware"]


def english_items(items, limit):
    """List items rendered in English (glossary), dropping what stays Chinese or carries a [zh] marker."""
    out = []
    for item in items:
        text = str(item or "").strip()
        if CJK_RE.search(text):
            text = re.sub(r"\s*\[zh\]\s*$", "", FD.translate_zh(text)).strip()
        if not text or CJK_RE.search(text) or "[zh]" in text:
            continue
        if text not in out:
            out.append(text[:120])
    return out[:limit]


def clean_tags(tags, strategy):
    out = []
    for tag in list(tags) + [tagify(strategy.replace("-", " "))]:
        if not tag or re.search(r"(?:^|\s)zh(?:\s|$)", tag) or tag.endswith(" bridge"):
            continue
        if tag not in out:
            out.append(tag)
    return out[:12]


def blocker_codes(card, decision, record):
    """Enumerated English blocker codes (REGQ-07); the catalogue's own blocker prose stays in x-vendor."""
    codes = []
    if decision.reason_code == "skip:empty":
        codes.append("EMPTY_CLONE: the local clone has no files")
    if decision.quarantine:
        codes.append("QUARANTINE: download lure or binary-only content; never dispatched")
    if decision.variant_of:
        codes.append(f"DUPLICATE_OF: {decision.variant_of}")
    elif decision.strategy == "skip" and decision.reason_code != "skip:empty" and not decision.quarantine:
        codes.append(f"NOT_A_DEVICE: {card['skip_reason']}"[:240])
    if decision.strategy == "reference":
        codes.append(f"REFERENCE_ONLY: role {decision.role}")
    if decision.strategy == "bridge-runtime":
        codes.append("SDK_BRIDGE_TASK: a framework or transport behind a helper, not a per-repo driver")
    for item in card["blocked_on"]:
        if item == "QUARANTINE":
            continue
        if item.startswith("helper:"):
            codes.append(f"HELPER_MISSING: {item}")
        elif item == TC.RECON_BLOCK:
            codes.append(f"NEEDS_RECON: {item}; no entry symbol and no candidate classes, a recon pass names them "
                         "before a driver task is dispatched")
        else:
            codes.append(item)
    lic_class = card["upstream"]["license_class"]
    if lic_class == "unknown":
        codes.append("LICENSE_UNKNOWN: no SPDX id in the catalogue, the LICENSE file or the package metadata")
    elif card["publish_review"] == "required":
        codes.append(f"LICENSE_REVIEW: {lic_class}; the user decides before a driver is published")
    if card["install"]["gpu"]:
        codes.append("NEEDS_GPU: an import or the catalogue requires a GPU")
    if card["install"]["platform"] == "windows":
        codes.append("PLATFORM_WINDOWS: Windows-only imports")
    if decision.strategy in T.DISPATCHABLE + ("untriaged",):
        if not card["entry_symbols"] and card["family"] != "mujoco":
            codes.append("NO_ENTRY_SYMBOL: no AST device class or env registration found")
        if not card["install"]["commands"]:
            codes.append("NO_INSTALL_FILE: no root pyproject.toml, setup.py, requirements.txt or package.xml")
    if str((record.get("x-vendor") or {}).get("catalog", {}).get("archived", "")).lower() == "true":
        codes.append("ARCHIVED: the upstream repository is archived")
    return list(dict.fromkeys(codes))[:8]


def next_action_for(card, decision, overlay=None):
    """One actionable English sentence built from the card and the driver package's overlay (REGQ-07)."""
    path = TC.card_path_for(card)
    status = card["package_status"]
    if status == "pass":
        state = (overlay.evidence_state() if overlay else None) or "contract_checked"
        text = (f"Maintain {card['driver_dir']}: its RESULT.json passed the gate ({state}); re-run "
                f"`{card['acceptance']}` and review the package when the upstream commit or the SDK changes. "
                "Not dispatched again.")
        return text[:500]
    if status == "blocked":
        codes = ", ".join(card["blocked_on"]) or "no codes"
        text = (f"Review {card['driver_dir']}/RESULT.json: the package is blocked on {codes}; clear the codes "
                f"before {path} is dispatched again.")
        return text[:500]
    if status == "skip-proposed":
        codes = ", ".join(card["blocked_on"]) or "no codes"
        text = (f"Review {card['driver_dir']}/RESULT.json: the package proposes a skip ({codes}); record the skip "
                f"as a curated override in MHS/registry/overrides/ or clear the codes before {path} is dispatched "
                "again.")
        return text[:500]
    if TC.dispatchable_now(card) or (card["wave"] == TC.WAVE_EXEMPLAR and decision.strategy in T.DISPATCHABLE):
        like = f", copying {card['exemplar']}" if card["exemplar"] else ""
        text = (f"Write the {card['helper']} driver package {card['driver_dir']} from {path} (wave {card['wave']}, "
                f"rank {card['rank']}){like}; done when `{card['acceptance']}` exits 0.")
    elif decision.strategy in T.DISPATCHABLE and card["blocked_on"] == [TC.RECON_BLOCK]:
        text = (f"Recon first (wave {card['wave']}): name an entry class and candidate capability classes for "
                f"{card['local_path']} and record them in {card['driver_dir']}/RESULT.json; {path} is dispatched "
                "once the card has them.")
    elif decision.strategy in T.DISPATCHABLE:
        text = (f"Wait for {', '.join(card['blocked_on'])}; {path} is wave {card['wave']} and is dispatched once "
                f"blocked_on is empty.")
    elif decision.strategy == "untriaged":
        text = (f"Recon only (wave {card['wave']}): confirm an entry symbol and a decision for {card['local_path']} "
                f"and record them in {card['driver_dir']}/RESULT.json; card {path}.")
    elif decision.strategy == "bridge-runtime":
        target = f"the {decision.family} helper" if decision.family else "a future engine bridge"
        text = f"SDK bridge task: this {decision.role} backs {target}; it is not a per-repo driver task."
    elif decision.strategy == "reference" and decision.role == "prior-art":
        text = "Reference only: an earlier MHS implementation to compare with, not a device to integrate."
    elif decision.strategy == "reference":
        text = ("Reference only: a host, orchestrator or MCP wrapper of a covered backend; integrate the backend "
                "instead.")
    else:
        text = f"Not integrated: {card['skip_reason']}"
    return text[:500]


def plan_sentence(card, decision):
    if decision.strategy in T.DISPATCHABLE:
        helper = card["helper"] or f"{card['family']} helper (planned)"
        return f"OpenMHS plan: {decision.strategy} with {helper}, wave {card['wave']}."
    if decision.strategy == "untriaged":
        return f"OpenMHS plan: recon card, wave {card['wave']}."
    if decision.strategy == "bridge-runtime":
        return "OpenMHS plan: SDK bridge runtime, not a per-repo driver."
    if decision.strategy == "reference":
        return f"OpenMHS plan: reference only ({decision.role})."
    return f"OpenMHS plan: not integrated ({decision.reason_code})."


def resources_for(caps):
    """Candidate classes grouped by a resource kind each class declares (kind_ok by construction)."""
    groups = OrderedDict()
    anywhere = []
    for cap in caps:
        entry = CV.catalog().get(cap) or {}
        kinds = [k for k in entry.get("resource_kinds") or [] if isinstance(k, str)]
        if not kinds or kinds == ["*"]:
            anywhere.append(cap)
            continue
        groups.setdefault(kinds[0], []).append(cap)
    if anywhere:
        target = next(iter(groups)) if groups else "device"
        groups.setdefault(target, []).extend(anywhere)
    return [OrderedDict((("kind", kind), ("capabilities", list(capabilities))))
            for kind, capabilities in groups.items()]


def device_plan(record, card):
    """Planned devices: the hardware device first, then a simulated (or replay) device linked by ``models``."""
    modes = list(record.get("modes") or [])
    if not modes:
        return []
    track, owner, repo = record["local_path"].split("/")[:3]
    base = f"mhs://{REGISTRY_ID}/{track}/{owner}__{repo}"
    candidates = list(card["hints"]["candidate_classes"])
    devices = []
    hardware_id = None
    for mode in modes:
        caps = [c for c in candidates if mode in ((CV.catalog().get(c) or {}).get("modes") or [mode])]
        floor = CV.risk_floor(caps)
        device = OrderedDict()
        device["device_id"] = f"{base}/{mode}"
        device["mode"] = mode
        if mode in ("simulated", "replay") and hardware_id:
            device["models"] = [hardware_id]
        device["risk_floor"] = floor
        device["resources"] = resources_for(caps)
        if mode == "hardware":
            hardware_id = device["device_id"]
            device["estop_required"] = CV.RISK_ORDER.index(floor) >= 1
            device["safe_state"] = "the native stop or disable path; the driver author cites it from the upstream code"
        else:
            device["backend"] = "upstream-sim" if card["mock_strategy"]["preferred"] == "upstream-sim" else "fake"
        devices.append(device)
    return devices


def finalize_record(record, decision, facts, lock, lic, overlay, analyst_family):
    """Apply the triage decision, the corpus lock, the licence facts and the overlay (cards come next)."""
    vendor = record["x-vendor"]
    cls = vendor["classification"]
    family, note = final_family(record["families"][0], decision, facts, analyst_family)
    if note:
        cls["family_note"] = note
    record["families"] = [family]
    tier = final_tier(record["tier"], decision)
    if tier != record["tier"]:
        cls["tier_note"] = f"tier {record['tier']} -> {tier}: triage {decision.strategy} ({decision.reason_code})"
    record["tier"] = tier
    record["modes"] = final_modes(record, decision, facts, cls.get("mode_override"))
    if decision.modes:
        # A reviewer's reading of the source beats the README scan and the role defaults (overrides README, modes),
        # but it may only correct a record towards hardware: it never removes a hardware mode the scan found.
        if record["tier"] in ("D", "X"):
            raise ValueError(f"{decision.package_id}: override modes {decision.modes} on a record of tier "
                             f"{record['tier']}, which plans no device and has no modes")
        scanned = list(record["modes"])
        if "hardware" in scanned and "hardware" not in decision.modes:
            raise ValueError(f"{decision.package_id}: override modes {decision.modes} drop the hardware mode the scan "
                             f"found ({scanned}); a modes override never removes hardware")
        record["modes"] = list(decision.modes)
        cls["mode_override"] = OrderedDict((("rule", "override:modes"), ("modes", list(decision.modes)),
                                            ("scanned_modes", scanned),
                                            ("evidence", decision.evidence[0] if decision.evidence else "")))
    if decision.served_mode:
        # The card serves the simulated form. Hardware stays on the record (a served_mode never drops it and
        # never makes the card a hardware card). expected_mode() reads the same condition.
        modes = list(record["modes"])
        if (decision.served_mode != "simulated" or not modes or modes[0] != "hardware"
                or "simulated" not in modes):
            raise ValueError(f"{decision.package_id}: served_mode {decision.served_mode!r} requires modes that keep "
                             f"hardware and simulated with hardware first (got {modes}); it serves the simulated "
                             "form and never drops or serves the hardware path")
        cls["served_mode"] = OrderedDict((("rule", "override:served-mode"), ("mode", "simulated"),
                                          ("evidence", decision.evidence[0] if decision.evidence else "")))
    record["simulation"] = "simulated" in record["modes"]
    record["hardware_free"] = bool(set(record["modes"]) & {"simulated", "replay"})
    remote = (lock or {}).get("repo_url")
    if remote and remote.startswith("https://") and remote != record["repo_url"]:
        vendor["catalog"]["repo_url"] = record["repo_url"]
        record["repo_url"] = remote
        record["links"]["repo"] = remote
    source = OrderedDict((("repo_url", remote or record["repo_url"]),))
    if (lock or {}).get("commit"):
        source["commit"] = lock["commit"]
    record["source"] = source
    vendor["catalog"]["license_raw"] = record["license"]
    record["license"] = lic["license_spdx"]
    record["license_spdx"] = lic["license_spdx"]
    record["license_class"] = lic["license_class"]
    vendor["license"] = OrderedDict((k, lic[k]) for k in ("source", "catalog_spdx", "file_spdx", "file",
                                                           "declared_spdx", "agrees", "review"))
    record["quarantine"] = bool(decision.quarantine)
    record["variant_of"] = decision.variant_of
    triage_info = OrderedDict()
    triage_info["version"] = T.TRIAGE_VERSION
    triage_info["rule"] = decision.rule
    triage_info["reason_code"] = decision.reason_code
    triage_info["family"] = decision.family
    triage_info["helper"] = decision.helper
    triage_info["evidence"] = [TC.english(e) for e in decision.evidence][:8]
    if decision.justification:
        triage_info["justification"] = decision.justification
    if decision.partner:
        triage_info["partner"] = decision.partner
    if decision.flagship:
        triage_info["flagship"] = True
    hardware = hardware_evidence(facts)
    if hardware:
        # validate.py checks hardware first against this evidence without the corpus
        triage_info["hardware_transport"] = TC.english(hardware)
    vendor["triage"] = triage_info
    if overlay is not None:
        vendor["overlay"] = overlay.to_vendor()
    return record


def complete_record(record, card, decision, overlay, row, scan, track, owner, repo):
    """Copy the card's wave, rank, blockers and hints into the record and render the English fields."""
    raw_blockers = (row or {}).get("blockers", "")
    if raw_blockers and not is_unknown(raw_blockers):
        record["x-vendor"]["catalog"]["blockers_raw"] = raw_blockers[:600]
    integration = OrderedDict()
    integration["strategy"] = decision.strategy
    integration["role"] = decision.role
    integration["reason_code"] = decision.reason_code
    if decision.strategy not in ("skip", "reference"):
        integration["recipe"] = f"families/{record['families'][0]}.md"
    integration["effort"] = {"family-config": "E1", "direct-driver": "E3" if decision.role == "driver-pack" else "E2",
                             "untriaged": "E3", "bridge-runtime": "E3"}.get(decision.strategy, "EX")
    integration["blockers"] = blocker_codes(card, decision, record)
    integration["next_action"] = next_action_for(card, decision, overlay)
    integration["scenario_required"] = record["tier"] == "C"
    record["integration"] = integration
    record["blocked_on"] = list(card["blocked_on"])
    record["wave"] = card["wave"]
    record["rank"] = card["rank"]
    record["capabilities_offered"] = [] if record["tier"] in ("D", "X") else list(card["hints"]["candidate_classes"])
    adapter = OrderedDict()
    adapter["present"] = bool(record["adapter"].get("present"))
    adapter["manifest_ref"] = None
    adapter["state"] = (overlay.adapter_state() if overlay else None) or "none"
    adapter["bridge"] = decision.family or "none"
    adapter["entry_points"] = [f"{s['symbol']} ({s['file']}:{s['line']})" for s in card["entry_symbols"]]
    record["adapter"] = adapter
    state = overlay.evidence_state() if overlay else None
    if state:
        record["evidence"]["state"] = state
        record["evidence"]["read_by"] = "runtime"
        record["evidence"]["provenance_refs"] = [overlay.path + "/RESULT.json"] + (
            [overlay.path + "/check-report.json"] if "check-report.json" in overlay.committed_files() else [])
    record["ring"] = (0 if state == "hardware_checked" else 1 if state == "contract_checked"
                      else 2 if (TC.dispatchable_now(card) or card["wave"] == TC.WAVE_EXEMPLAR) else 3)
    record["interfaces"] = english_items(record["interfaces"], 12)
    record["domains"] = english_items(record["domains"], 6)
    record["languages"] = english_items(record["languages"], 6)
    record["build_systems"] = english_items(record["build_systems"], 8)
    catalog_family_tag = tagify(record["x-vendor"]["classification"]["catalog_family"])
    record["tags"] = clean_tags([tagify(record["families"][0])] + [t for t in record["tags"] if t != catalog_family_tag],
                                decision.strategy)
    record["description"] = make_description(row, track, record["families"][0], record["tier"],
                                             record["evidence"]["state"], scan, owner, repo,
                                             plan=plan_sentence(card, decision))
    if CJK_RE.search(record["evidence"].get("notes") or ""):
        record["x-vendor"].setdefault("analyst_profile", {})["notes_raw"] = record["evidence"]["notes"]
        record["evidence"]["notes"] = "analyst notes kept in x-vendor.analyst_profile.notes_raw"
    record["x-vendor"]["device_plan"] = device_plan(record, card)
    return record


# ---------------------------------------------------------------------------
# output
# ---------------------------------------------------------------------------

def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


class Output:
    """Writes generated files, or (``check=True``) only reports which would change."""

    def __init__(self, check: bool = False):
        self.check = check
        self.changed: list[str] = []
        self.written = 0

    def text(self, path: str, text: str) -> None:
        try:
            with open(path, encoding="utf-8", newline="") as fh:
                if fh.read() == text:
                    return
        except OSError:
            pass
        self.changed.append(os.path.relpath(path, WORKSPACE))
        if self.check:
            return
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        self.written += 1

    def prune(self, directory: str, keep: set, pattern: str = "*.json") -> None:
        """Remove generated files under ``directory`` that the current build did not produce."""
        import glob as _glob
        for path in sorted(_glob.glob(os.path.join(directory, "*", pattern))):
            if os.path.abspath(path) not in keep:
                self.changed.append(os.path.relpath(path, WORKSPACE) + " (stale)")
                if not self.check:
                    os.remove(path)


def read_jsonl(path):
    out = []
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return out


BUILD_TS = build_date()


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Regenerate the OpenMHS registry, task cards, recipes and docs.")
    parser.add_argument("--jobs", type=int, default=int(os.environ.get("MHS_REGISTRY_JOBS", "1") or 1),
                        help="parallel source-scan workers (default 1, or $MHS_REGISTRY_JOBS)")
    parser.add_argument("--cache", default=os.environ.get("MHS_TRIAGE_CACHE"),
                        help="cache of source-scan facts keyed by commit and scanner version")
    parser.add_argument("--records-only", action="store_true", help="write records and cards only")
    parser.add_argument("--check", action="store_true",
                        help="write nothing; exit 1 when a committed generated file differs")
    parser.add_argument("--companions-root", default=os.environ.get("MHS_DRIVER_GATE_COMPANIONS") or None,
                        help="directory whose LOCK.json is the fetched-companion lock "
                             "(default: $MHS_DRIVER_GATE_COMPANIONS when set). "
                             "Clone files stay at each entry's path under the workspace.")
    args = parser.parse_args(list(argv) if argv is not None else None)
    global BUILD_TS
    BUILD_TS = build_date()
    out = Output(check=args.check)
    guarded = OV.tree_digests(OV.DRIVERS_DIR, OV.OVERRIDES_DIR)

    print(f"[registry] workspace: {WORKSPACE}")
    catalog_rows = load_catalog()
    caps = load_capabilities()
    core_caps = load_core_capabilities()
    aliases = load_aliases()
    profiles = load_profiles()
    availability_notes = load_scan_summary()
    recon_notes = load_recon()
    recipe_notes = load_recipe_notes()
    print(f"[registry] catalog rows: {len(catalog_rows)}; core capability classes: {len(core_caps)}; "
          f"aliases: {len(aliases)}; profiles: {len(profiles)}; recon notes: {len(recon_notes)}")

    by_key, by_repo_name = catalog_index(catalog_rows, aliases)
    by_master_id = {}
    for row in catalog_rows:
        mid = row.get("master_id") or ""
        if mid and not is_unknown(mid):
            by_master_id.setdefault(mid, []).append(row)
    scans = SC.scan_corpus(WORKSPACE)
    print(f"[registry] scanned clones: {len(scans)}; empty: "
          f"{sum(1 for s in scans.values() if s.get('files', 0) == 0)}")

    records, rows, recon_scans = [], {}, {}
    for (track, owner, repo) in sorted(scans, key=lambda k: (k[0], k[1].lower(), k[2].lower(), k[1], k[2])):
        key = (owner.lower(), repo.lower())
        profile = profiles.get(key)
        profile_row, extra_rows = profile_catalog_row(profile, by_key, by_master_id)
        row, join_kind = pair_clone_with_catalog(track, owner, repo, by_key, by_repo_name, aliases, profile_row)
        if row is not None and profile_row is not None and row["_row"] == profile_row["_row"]:
            extra_rows = [r for r in extra_rows if r["_row"] != row["_row"]]
        caps_rows = caps.get(key, [])
        recon = recon_notes.get(key)
        scan = enrich_scan(scans[(track, owner, repo)], profile, caps_rows)
        record = make_record(track, owner, repo, row, join_kind, scan, caps_rows, recon, profile)
        if row is not None:
            all_rows = [row] + list(extra_rows)
            if profile_row is not None:
                all_rows.append(profile_row)
            rows_all = [row["_row"]] + sorted({r["_row"] for r in all_rows if r["_row"] != row["_row"]})
            record["x-vendor"]["catalog"]["rows_all"] = rows_all
            for extra in all_rows:
                if extra["_row"] != row["_row"] and extra["repo_url"] not in record["catalog_refs"]:
                    record["catalog_refs"].append(extra["repo_url"])
        records.append(record)
        rows[record["local_path"]] = row
        recon_scans[record["local_path"]] = scan

    # deterministic package_id uniqueness; the envelope id tracks package_id
    seen = {}
    for record in records:
        pid = record["package_id"]
        if pid in seen:
            seen[pid] += 1
            record["package_id"] = f"{pid}-{seen[pid]}"
        else:
            seen[pid] = 1
        record["id"] = record["package_id"]
        record["registry_id"] = REGISTRY_ID

    # --- triage (same inputs as `python3 MHS/registry/triage.py`) ---------------
    locks = {e["local_path"]: e for e in read_jsonl(LOCK_PATH)}
    audits = {str(o.get("directory_slug") or "").lower(): o for o in read_jsonl(CLONE_AUDIT) if o.get("directory_slug")}
    notes = T.load_catalog_notes(CATALOG_CSV)
    commits = {lp: e.get("commit") for lp, e in locks.items()}
    source_scans = T.scan_corpus(WORKSPACE, [r["local_path"] for r in records], jobs=args.jobs,
                                 cache_dir=args.cache, commits=commits)
    facts = {}
    for record in records:
        _t, owner, repo = record["local_path"].split("/")[:3]
        facts[record["package_id"]] = T.facts_from_record(
            record, profiles.get((owner.lower(), repo.lower())), locks.get(record["local_path"]),
            source_scans.get(record["local_path"]), notes, audits.get(f"{owner}/{repo}".lower()))
    overrides = T.load_overrides()
    stale = T.unknown_overrides(overrides, facts)
    if stale:
        for pid in stale:
            print(f"[registry] ERROR override for {pid}, which is not a registry record", file=sys.stderr)
        return 2
    decisions = T.triage(list(facts.values()), overrides)
    print(f"[registry] triage: {len(decisions)} decisions; "
          + ", ".join(f"{k} {v}" for k, v in T.summarize(decisions)["by_strategy"].items()))

    # --- overlays (read-only) ------------------------------------------------------
    overlays = OV.load()
    keys = {OV.key_for(r["local_path"]) for r in records}
    for key in sorted(set(overlays) - keys):
        print(f"[registry] ERROR driver package MHS/drivers/{key} has no registry record", file=sys.stderr)
    if set(overlays) - keys:
        return 2

    # --- records, cards, waves ------------------------------------------------------
    cards = OrderedDict()
    by_pid = {r["package_id"]: r for r in records}
    for record in records:
        pid = record["package_id"]
        decision = decisions[pid]
        f = facts[pid]
        lscan = (f.scan or {}).get("license") or {}
        lic = LIC.resolve(record["license"], lscan.get("spdx"), lscan.get("file"),
                          ((f.scan or {}).get("install") or {}).get("declared_license") or [])
        overlay = overlays.get(OV.key_for(record["local_path"]))
        analyst_family = ((profiles.get((record["owner"].lower(), record["repo"].lower())) or {})
                          .get("classification") or {}).get("family")
        finalize_record(record, decision, f, locks.get(record["local_path"]), lic, overlay,
                        PROFILE_FAMILY_MAP.get(str(analyst_family)))
        row = rows.get(record["local_path"]) or {}
        cards[pid] = TC.build_card(record, decision, f, locks.get(record["local_path"]), lic,
                                   overlay.blocked_on() if overlay else (), row.get("runtime_requirements", ""),
                                   overlay.package_status() if overlay else "none")
    companion_errors = attach_companions(cards, decisions, by_pid, locks, args.companions_root)
    if companion_errors:
        for msg in companion_errors[:20]:
            print(f"[registry] ERROR {msg}", file=sys.stderr)
        return 2
    waves = TC.assign_waves(cards, decisions, facts, {pid: r["stars"] for pid, r in by_pid.items()})
    for record in records:
        pid = record["package_id"]
        track, owner, repo = record["local_path"].split("/")[:3]
        complete_record(record, cards[pid], decisions[pid], overlays.get(OV.key_for(record["local_path"])),
                        rows.get(record["local_path"]), recon_scans.get(record["local_path"]), track, owner, repo)

    # fail fast instead of publishing an unresolved core capability referent
    cap_errors = [f"{r['package_id']}: unknown core capability {cap}" for r in records
                  for cap in r["capabilities_offered"] if cap.startswith("cap.") and cap not in core_caps]
    if cap_errors:
        for msg in cap_errors[:20]:
            print(f"[registry] ERROR {msg}", file=sys.stderr)
        return 2

    keep = set()
    for record in records:
        path = os.path.join(REPOS_DIR, record["track"], f"{record['owner']}__{record['repo']}.json")
        keep.add(os.path.abspath(path))
        out.text(path, dumps(record))
    out.prune(REPOS_DIR, keep)
    keep = set()
    for card in cards.values():
        path = os.path.join(WORKSPACE, TC.card_path_for(card))
        keep.add(os.path.abspath(path))
        out.text(path, TC.dumps(card))
    out.prune(TASKS_DIR, keep)
    out.text(TC.PILOT_PATH, TC.dumps(TC.pilot_document(waves["pilot"], cards, BUILD_TS)))
    print(f"[registry] {len(records)} records, {len(cards)} task cards, "
          f"{len(waves['pilot'])} pilot candidates")

    uncloned = build_uncloned(by_key, records, availability_notes)
    out.text(UNCLONED_JSON, dumps({"generated_at": BUILD_TS, "count": len(uncloned), "rows": uncloned}))
    if not args.records_only:
        import build_index as BI
        import docs as DOCS
        import recipes as RECIPES
        summary = TC.summarize(cards)
        for path, text in RECIPES.render_recipes(records, cards, recipe_notes, FAMILIES_DIR, BUILD_TS).items():
            out.text(path, text)
        out.prune(FAMILIES_DIR, {os.path.abspath(p) for p in RECIPES.recipe_paths(records, FAMILIES_DIR)}, "*.md")
        stats = BI.compute_stats(records)
        manifest = source_manifest(catalog_rows, core_caps, aliases, profiles, recon_notes, recipe_notes)
        for path, text in DOCS.render_docs(records, cards, summary, stats, uncloned, manifest, BUILD_TS, OUT,
                                           decisions_summary=T.summarize(decisions)).items():
            out.text(path, text)
        if not args.check:
            BI.build(records=records, generated_at=BUILD_TS)
    after = OV.tree_digests(OV.DRIVERS_DIR, OV.OVERRIDES_DIR)
    if after != guarded:
        print("[registry] ERROR MHS/drivers/** or MHS/registry/overrides/** changed during the build",
              file=sys.stderr)
        return 2
    if args.check:
        for path in out.changed[:40]:
            print(f"[registry] stale: {path}")
        print(f"[registry] check: {len(out.changed)} generated file(s) differ")
        return 1 if out.changed else 0
    print(f"[registry] wrote {out.written} changed file(s); done")
    return 0


def attach_companions(cards, decisions, by_pid, locks, companions_root=None):
    """Copy each reviewed override's companions onto its card with the clone's local_path and repo_url (corpus lock)
    and the companion record's licence; the errors stop the build. Cards without companions are left untouched.

    A companion with ``lock`` is a clone fetched under work/companions (DESIGN-2): its local_path, repo_url, ref and
    licence come from LOCK.json, read once (a licence that is not an SPDX expression becomes NOASSERTION with the
    LOCK.json text as licence_note). ``companions_root`` selects that file (:func:`triage.read_companion_lock`);
    clone paths stay under the workspace."""
    lock_by_pid = {line.get("package_id"): line for line in locks.values()}
    companion_lock, lock_problem = None, None
    if any(T.COMPANION_LOCK_KEY in entry for decision in decisions.values()
           for entry in getattr(decision, "companions", None) or []):
        companion_lock, lock_problem = T.read_companion_lock(WORKSPACE, companions_root)
    errors = [lock_problem] if lock_problem else []
    for pid, decision in decisions.items():
        entries = list(getattr(decision, "companions", None) or [])
        if not entries:
            continue
        problems = T.companion_problems(pid, entries, by_pid, lock_by_pid, WORKSPACE, companion_lock)
        if problems:
            errors.extend(problems)
            continue
        out = []
        for entry in entries:
            head = (
                ("alias", entry["alias"]),
                ("package_id", entry["package_id"]),
                ("commit", entry["commit"]),
                ("profile", entry["profile"]),
                ("reason", entry["reason"]),
                ("version_evidence", [OrderedDict((("side", item["side"]), ("ref", item["ref"]),
                                                   ("token", item["token"]))) for item in entry["version_evidence"]]),
            )
            if entry.get(T.COMPANION_HARDWARE_STOP_KEY) is True:
                head = head + (("hardware_stop", True),)
            if T.COMPANION_LOCK_KEY in entry:
                line = companion_lock[entry[T.COMPANION_LOCK_KEY]]
                spdx, note = T.lock_licence(line.get("licence"))
                out.append(OrderedDict(head + (
                    ("lock", entry[T.COMPANION_LOCK_KEY]),
                    ("ref", line.get("ref")),
                    ("local_path", line["path"]),
                    ("repo_url", line.get("repo_url")),
                    ("license_spdx", spdx),
                ) + ((("licence_note", note),) if note else ())))
                continue
            line = lock_by_pid[entry["package_id"]]
            companion = by_pid[entry["package_id"]]
            out.append(OrderedDict(head + (
                ("local_path", line["local_path"]),
                ("repo_url", line.get("repo_url") or companion.get("repo_url")),
                ("license_spdx", companion.get("license_spdx")),
            )))
        cards[pid]["companions"] = out
    return errors


def source_manifest(catalog_rows, core_caps, aliases, profiles, recon_notes, recipe_notes):
    """Provenance of this build (repository-relative paths only, no workspace path; OSS-05)."""
    return OrderedDict((
        ("generator", "MHS/registry/build_registry.py"),
        ("registry_version", REGISTRY_VERSION),
        ("registry_id", REGISTRY_ID),
        ("generated_at", BUILD_TS),
        ("catalog", {"path": os.path.relpath(CATALOG_CSV, WORKSPACE), "sha256": file_sha256(CATALOG_CSV),
                     "rows": len(catalog_rows)}),
        ("capabilities", {"path": os.path.relpath(CORE_CAPS_JSON, WORKSPACE), "classes": len(core_caps),
                          "sha256": file_sha256(CORE_CAPS_JSON)}),
        ("aliases", {"path": os.path.relpath(ALIASES_CSV, WORKSPACE), "applied": len(aliases)}),
        ("analyst_profiles", {"path": os.path.relpath(PROFILES_JSONL, WORKSPACE), "rows": len(profiles)}),
        ("recon_notes", {"dir": os.path.relpath(RECON_ROOT, WORKSPACE), "per_repo_files": len(recon_notes),
                         "recipe_files": [n["path"] for n in recipe_notes]}),
        ("corpus_lock", {"path": "MHS/registry/corpus.lock.jsonl", "sha256": file_sha256(LOCK_PATH)}),
        ("overrides", {"dir": "MHS/registry/overrides", "files": sorted(
            os.path.basename(p) for p in __import__("glob").glob(os.path.join(OV.OVERRIDES_DIR, "*.json")))}),
        ("archived_manifests", ARCHIVED_MANIFESTS),
    ))


def _english_value(text):
    """Glossary English of a catalogue value, or "" when it stays Chinese."""
    items = english_items([text], 1) if text else []
    return items[0] if items else ""


def build_uncloned(by_key, records, availability_notes=None):
    """Catalogue rows without a local clone; English fields, the Chinese originals in each row's x-vendor."""
    claimed = set()
    for r in records:
        cat = r["x-vendor"]["catalog"]
        if cat.get("row"):
            claimed.add(cat["row"])
        for extra in (cat.get("rows_all") or []):
            claimed.add(extra)
    rows = []
    for key in sorted(by_key, key=lambda k: (k[1], k[0])):
        row = by_key[key]
        if row["_row"] in claimed:
            continue
        note = (availability_notes or {}).get((row.get("repo_url") or "").lower(), {})
        status, note_text = note.get("status"), note.get("note")
        vendor = OrderedDict()
        for field, value in (("category_zh", row.get("category", "")), ("adapter_role_zh", row.get("adapter_role", "")),
                             ("priority_zh", row.get("priority", "")), ("analyst_note_zh", note_text)):
            if value and CJK_RE.search(str(value)):
                vendor[field] = value
        if note_text and CJK_RE.search(note_text):
            note_text = (f"The analyst recorded the upstream repository as {status or 'unchecked'}; the original "
                         "note is in x-vendor.analyst_note_zh.")
        out = OrderedDict((
            ("owner", row["owner"]),
            ("repo", row["repo_name"]),
            ("repo_url", row["repo_url"]),
            ("track_raw", _english_value(row.get("track", ""))),
            ("category", _english_value(row.get("category", ""))),
            ("adapter_role", _english_value(row.get("adapter_role", ""))),
            ("backend_family_raw", _english_value(row.get("backend_family", ""))),
            ("language", _english_value(row.get("language", ""))),
            ("license", _english_value(row.get("license", ""))),
            ("stars", row.get("stars", "")),
            ("priority", _english_value(row.get("priority", ""))),
            ("reason", "catalog row without a local clone in labs/ or robots/"),
            ("catalog_row", row["_row"]),
            ("analyst_status", status),
            ("analyst_note", note_text),
        ))
        if vendor:
            out["x-vendor"] = vendor
        rows.append(out)
    return rows


if __name__ == "__main__":
    sys.exit(main())
