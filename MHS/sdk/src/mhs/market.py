"""The OpenMHS device market: every driver package that passed its gate, ready to serve.

``MHS/drivers/market.json`` lists each package whose ``RESULT.json`` says
``"status": "pass"``.  An entry carries a short introduction, what the device
measures, adjusts and does, its upstream source and licence, and the commands
that serve it on its **fake backend** (standard library only, no device, no
upstream checkout).  The website, the OpenAI4S-Playground catalog and
``openai4s lab add`` all read this one file.

Public API::

    from mhs import market

    doc = market.load()                      # the whole market document
    entry = market.find("labs/tiagocoutinho__julabo")
    hits = market.search("microscope", track="labs", limit=10)
    path = market.resolve_package("julabo")  # driver directory, or None

CLI::

    mhs market                         # how many packages, by track and mode
    mhs market search microscope       # find packages
    mhs market show labs/tiagocoutinho__julabo
    mhs market build [--check]         # regenerate MHS/drivers/market.json
    mhs serve labs/tiagocoutinho__julabo --port 7400   # serve one by its market id

A market entry is a *simulation-ready* driver: its gate ran on the fake
backend (``contract_checked``).  That is not a hardware qualification.
Hardware use stays an explicit operator decision (``--backend hardware
--allow-hardware``) and some drivers refuse it until a human review is signed.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Iterable

from . import _ids

MARKET_FORMAT = "openmhs.market/1"
MARKET_FILE = "market.json"
REPO_URL = "https://github.com/PKU-YuanGroup/OpenMHS"
TRACKS = ("labs", "robots")

_DOMAIN_RE = re.compile(r":\s*(?:[^:()]*?)\bfor ([^()]+?) \((?:lab instrumentation|robotics) track\)")


# ---------------------------------------------------------------------------
# locating the drivers
# ---------------------------------------------------------------------------


def drivers_root() -> Path | None:
    """``MHS/drivers`` of an OpenMHS checkout, or ``$MHS_DRIVERS``; ``None`` when absent.

    An installed wheel does not carry the driver packages; set ``MHS_DRIVERS``
    to a checkout's ``MHS/drivers`` in that case.
    """
    explicit = os.environ.get("MHS_DRIVERS", "").strip()
    if explicit:
        root = Path(explicit).expanduser()
        return root if root.is_dir() else None
    root = Path(__file__).resolve().parents[3] / "drivers"
    return root if root.is_dir() else None


def _require_root(root: Path | str | None) -> Path:
    resolved = Path(root) if root is not None else drivers_root()
    if resolved is None or not Path(resolved).is_dir():
        raise FileNotFoundError(
            "OpenMHS driver packages not found: clone " + REPO_URL + " (they live in MHS/drivers) "
            "or set MHS_DRIVERS to that directory"
        )
    return Path(resolved)


def market_path(root: Path | str | None = None) -> Path:
    return _require_root(root) / MARKET_FILE


# ---------------------------------------------------------------------------
# building
# ---------------------------------------------------------------------------


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _names(items: Iterable[dict]) -> list[str]:
    return [str(item.get("name")) for item in items if item.get("name")]


def _join(words: list[str], limit: int = 4) -> str:
    shown = [f"`{w}`" for w in words[:limit]]
    rest = len(words) - len(shown)
    if rest > 0:
        shown.append(f"{rest} more")
    if len(shown) <= 1:
        return "".join(shown)
    return ", ".join(shown[:-1]) + " and " + shown[-1]


def _sentence(text: str) -> str:
    text = " ".join(str(text or "").split()).rstrip(".")
    if len(text) > 1 and text[1].isupper():  # an acronym such as "RF" keeps its case
        return text
    return text[:1].lower() + text[1:]


#: Device kind (prefix) -> market category.  The first matching prefix wins.
CATEGORIES: tuple[tuple[str, str], ...] = (
    ("world.", "Simulation"),
    ("robot.mobile", "Mobile robots"),
    ("robot.", "Robot arms and grippers"),
    ("motion.", "Motion control"),
    ("instrument.microscope", "Optics and microscopy"),
    ("optics.", "Optics and microscopy"),
    ("light.", "Optics and microscopy"),
    ("sensor.optical", "Optics and microscopy"),
    ("instrument.spectro", "Spectroscopy"),
    ("fluid.", "Liquid handling and fluidics"),
    ("actuation.pump", "Liquid handling and fluidics"),
    ("lab.liquid", "Liquid handling and fluidics"),
    ("thermal.", "Thermal and process control"),
    ("lab.thermal", "Thermal and process control"),
    ("instrument.thermometer", "Thermal and process control"),
    ("instrument.incubator", "Thermal and process control"),
    ("process.", "Thermal and process control"),
    ("sensor", "Sensors and cameras"),
    ("instrument", "Electronics and measurement"),
    ("io.", "Electronics and measurement"),
)


def _category(kind: str) -> str:
    for prefix, label in CATEGORIES:
        if kind == prefix.rstrip(".") or kind.startswith(prefix):
            return label
    return "Other devices"


def _topic(record: dict | None) -> str | None:
    """The registry's application domain (e.g. ``UAVs``); used for simulations."""
    if not record:
        return None
    domains = [str(d) for d in record.get("domains") or [] if d and str(d) not in ("sim", "general")]
    if domains:
        return domains[0]
    match = _DOMAIN_RE.search(str(record.get("description") or ""))
    topic = match.group(1).split(";")[0].strip() if match else ""
    return topic if topic and topic not in ("sim", "general") else None


def _intro(device: dict, measures: list[str], adjusts: list[str], actions: list[dict], mode: str,
           upstream_repo: str) -> str:
    name = str(device.get("name") or "This device")
    source = upstream_repo.removeprefix("https://github.com/")
    parts = [f"{name}, adapted from {source}." if source else f"{name}."]
    can = []
    if measures:
        can.append("reads " + _join(measures))
    if adjusts:
        can.append("sets " + _join(adjusts))
    if actions:
        can.append("runs " + _join(_names(actions)))
    if can:
        parts.append("It " + "; ".join(can) + ".")
    first = next((a for a in actions if a.get("description")), None)
    if first:
        parts.append(f"`{first['name']}`: {_sentence(first['description'])}.")
    if mode == "simulated":
        parts.append("A simulator: the market serves it with a stand-in that needs no simulator install.")
    else:
        parts.append("A hardware driver: the market serves its fake backend, so no instrument is needed.")
    return " ".join(parts)


def _commands(package: str) -> dict[str, str]:
    return {
        "openai4s": f"openai4s lab add {package}",
        "mhs": f"mhs serve {package} --port 7400",
        "mcp": f"mhs serve {package} --mcp",
    }


def build_entry(package_dir: Path, root: Path, registry_dir: Path | None = None) -> dict[str, Any] | None:
    """One market entry for a driver package, or ``None`` when it has not passed its gate."""
    result_path = package_dir / "RESULT.json"
    try:
        result = _read(result_path)
    except (OSError, ValueError):
        return None
    if result.get("status") != "pass":
        return None
    package = package_dir.relative_to(root).as_posix()
    reference = _read(package_dir / "reference.json")
    lock = _read(package_dir / "driver.lock.json")
    task = _read(package_dir / "task.json") if (package_dir / "task.json").is_file() else {}
    record = None
    if registry_dir is not None:
        record_path = registry_dir / "repos" / f"{package}.json"
        if record_path.is_file():
            record = _read(record_path)
    device = reference.get("device") or {}
    upstream = lock.get("upstream") or {}
    measures = _names(reference.get("measures") or [])
    adjusts = _names(reference.get("adjusts") or [])
    actions = list(reference.get("actions") or [])
    mode = str(device.get("mode") or "")
    kind = str(device.get("kind") or "")
    repo_url = str(upstream.get("repo_url") or (device.get("upstream") or {}).get("repo") or "")
    return {
        "id": package,
        "name": device.get("name") or package.split("/", 1)[-1],
        "device_id": device.get("id"),
        "track": package.split("/", 1)[0],
        "category": _category(kind),
        "topic": _topic(record) if kind.startswith("world.") else None,  # the registry domain fits simulations
        "kind": kind,
        "vendor": device.get("vendor"),
        "model": device.get("model"),
        "mode": mode,
        "risk": device.get("risk"),
        "family": task.get("family"),
        "role": task.get("role"),
        "intro": _intro(device, measures, adjusts, actions, mode, repo_url),
        "measures": measures,
        "adjusts": adjusts,
        "actions": [{"name": a.get("name"), "description": a.get("description")} for a in actions if a.get("name")],
        "tags": list(reference.get("tags") or []),
        "backends": sorted(lock.get("backends") or []),
        "served_backend": "fake",
        "evidence": "contract_checked",
        "upstream": {
            "repo_url": repo_url,
            "commit": upstream.get("commit"),
            "license": upstream.get("license_spdx") or (record or {}).get("license_spdx"),
        },
        "stars": (record or {}).get("stars"),
        "install": _commands(package),
    }


def build(root: Path | str | None = None) -> dict[str, Any]:
    """Scan ``MHS/drivers/*/*`` and return the market document (deterministic order)."""
    base = _require_root(root)
    registry_dir = base.parent / "registry"
    entries = []
    for track in TRACKS:
        for package_dir in sorted((base / track).glob("*/")):
            entry = build_entry(package_dir, base, registry_dir if registry_dir.is_dir() else None)
            if entry is not None:
                entries.append(entry)
    stats: dict[str, dict[str, int]] = {"track": {}, "mode": {}}
    for entry in entries:
        for key in stats:
            stats[key][entry[key]] = stats[key].get(entry[key], 0) + 1
    return {
        "format": MARKET_FORMAT,
        "project": _ids.PROJECT_NAME,
        "website": _ids.SITE_URL,
        "repository": REPO_URL,
        "sdk_version": _ids.SDK_VERSION,
        "count": len(entries),
        "stats": stats,
        "note": "Every entry passed its gate on the fake backend (contract_checked). That is not a hardware "
                "qualification; hardware use is an explicit operator decision.",
        "packages": entries,
    }


def render(document: dict[str, Any]) -> str:
    """Stable text: the header indented, then one package per line (small, diff-friendly)."""
    head = {k: v for k, v in document.items() if k != "packages"}
    lines = json.dumps(head, indent=1, ensure_ascii=False)[:-2].rstrip()
    rows = ",\n".join(json.dumps(p, ensure_ascii=False, separators=(",", ":")) for p in document["packages"])
    return lines + ',\n "packages": [\n' + rows + "\n ]\n}\n"


def write(root: Path | str | None = None) -> Path:
    path = market_path(root)
    path.write_text(render(build(root)), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# reading
# ---------------------------------------------------------------------------


def load(root: Path | str | None = None) -> dict[str, Any]:
    """The market document; built in memory when ``market.json`` is missing."""
    path = market_path(root)
    if path.is_file():
        return _read(path)
    return build(root)


def _keys(entry: dict[str, Any]) -> set[str]:
    package = str(entry["id"])
    folder = package.split("/", 1)[-1]
    keys = {package.lower(), folder.lower()}
    if "__" in folder:
        owner, repo = folder.split("__", 1)
        keys.update({repo.lower(), f"{owner}/{repo}".lower(), f"gh.{owner}/{repo}".lower()})
    return keys


def find(name: str, root: Path | str | None = None, *, document: dict | None = None) -> dict[str, Any] | None:
    """An entry by market id (``labs/owner__repo``), folder, ``owner/repo`` or a unique repo name."""
    wanted = str(name or "").strip().strip("/").lower()
    if not wanted:
        return None
    if wanted.startswith("mhs/drivers/"):
        wanted = wanted[len("mhs/drivers/"):]
    packages = (document or load(root))["packages"]
    exact = [e for e in packages if str(e["id"]).lower() == wanted]
    if exact:
        return exact[0]
    matches = [e for e in packages if wanted in _keys(e)]
    return matches[0] if len(matches) == 1 else None


def search(query: str = "", *, track: str | None = None, mode: str | None = None, limit: int | None = None,
           root: Path | str | None = None, document: dict | None = None) -> list[dict[str, Any]]:
    """Entries whose id, name, category, kind, vendor or tags contain every query word."""
    words = [w for w in str(query or "").lower().split() if w]
    hits = []
    for entry in (document or load(root))["packages"]:
        if track and entry["track"] != track:
            continue
        if mode and entry["mode"] != mode:
            continue
        haystack = " ".join(str(v) for v in (entry["id"], entry["name"], entry["category"], entry.get("topic"), entry["kind"],
                                              entry.get("vendor"), entry.get("model"), " ".join(entry["tags"]))).lower()
        if all(w in haystack for w in words):
            hits.append(entry)
    hits.sort(key=lambda e: (-(e.get("stars") or 0), e["id"]) if words else (e["id"],))
    return hits[:limit] if limit else hits


def resolve_package(target: str, root: Path | str | None = None) -> Path | None:
    """The driver directory for a market id or name, or ``None``."""
    try:
        base = _require_root(root)
        entry = find(target, base)
    except (FileNotFoundError, OSError, ValueError):
        return None
    if entry is None:
        return None
    path = base / entry["id"]
    return path if path.is_dir() else None


# ---------------------------------------------------------------------------
# CLI (``mhs market``)
# ---------------------------------------------------------------------------


def _print_entry(entry: dict[str, Any]) -> None:
    print(f"{entry['id']}\n  {entry['name']}")
    print(f"  {entry['category']} · {entry['mode']} · risk {entry['risk']} · licence {entry['upstream']['license']}")
    print(f"  {entry['intro']}")
    print(f"  OpenAI4S:  {entry['install']['openai4s']}")
    print(f"  MHS:       {entry['install']['mhs']}")
    print(f"  MCP:       {entry['install']['mcp']}")
    print(f"  Upstream:  {entry['upstream']['repo_url']} @ {str(entry['upstream']['commit'] or '')[:12]}")


def run_cli(verb: str, query: str, *, track: str | None, mode: str | None, limit: int, as_json: bool,
            check: bool) -> int:
    if verb == "build":
        base = _require_root(None)
        text = render(build(base))
        path = base / MARKET_FILE
        current = path.read_text(encoding="utf-8") if path.is_file() else ""
        if check:
            if current != text:
                print(f"mhs market: {path} is stale; run `mhs market build`")
                return 1
            print(f"mhs market: {path} is current")
            return 0
        path.write_text(text, encoding="utf-8")
        print(f"mhs market: wrote {path} ({json.loads(text)['count']} packages)")
        return 0
    document = load()
    if verb == "show":
        entry = find(query, document=document)
        if entry is None:
            hits = search(query, document=document, limit=5)
            print(f"mhs market: no single package named {query!r}"
                  + ("; did you mean: " + ", ".join(h["id"] for h in hits) if hits else ""))
            return 1
        print(json.dumps(entry, indent=2, ensure_ascii=False)) if as_json else _print_entry(entry)
        return 0
    if verb == "search" or query:
        hits = search(query, track=track, mode=mode, limit=limit, document=document)
        if as_json:
            print(json.dumps(hits, indent=2, ensure_ascii=False))
            return 0
        for entry in hits:
            print(f"{entry['id']:<58} {entry['mode']:<9} {entry['risk']:<3} {entry['name'][:70]}")
        total = len(search(query, track=track, mode=mode, document=document))
        print(f"\n{len(hits)} of {total} shown. Details: mhs market show <id>   Serve: mhs serve <id>")
        return 0
    summary = {k: document[k] for k in ("count", "stats", "website", "sdk_version")}
    if as_json:
        print(json.dumps(summary, indent=2))
    else:
        stats = document["stats"]
        print(f"OpenMHS market: {document['count']} packages "
              f"({', '.join(f'{v} {k}' for k, v in sorted(stats['track'].items()))}; "
              f"{', '.join(f'{v} {k}' for k, v in sorted(stats['mode'].items()))})")
        print("Find one:   mhs market search <words>\nServe one:  mhs serve <id> --port 7400"
              f"\nBrowse:     {document['website'].rstrip('/')}/market/")
    return 0
