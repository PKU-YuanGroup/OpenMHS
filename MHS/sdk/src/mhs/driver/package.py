"""Driver package operations behind ``python -m mhs.driver``: reference files, scaffolding, export, catalogue.

* :func:`reference_documents` / :func:`write_reference` -- the generated
  ``reference.json`` (JCS bytes plus a newline) and ``REFERENCE.md`` of a
  driver directory, from the driver class and ``driver.lock.json``
  (``authored_by``, ``reviewed_by``, ``upstream``).  Gate G5 compares the
  committed files with these bytes.
* :func:`scaffold` -- ``new``: render the templates (or copy an exemplar
  structurally, ``--like``) into a driver directory, filled from a task card.
* :func:`export_adapter` -- ``export``: an ``mhs-adapter.json`` (interchange
  format) whose single ``driver`` bridge points back at the directory.
* :func:`find_root` -- the project root (the directory holding ``MHS/sdk``),
  which task cards' ``local_path`` and ``driver_dir`` are relative to.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from .. import _ids
from .. import reference_file as _reference_file
from .loader import LOCK_FILE, driver_class, read_lock
from .spec import DriverDefinitionError

__all__ = [
    "REFERENCE_JSON",
    "REFERENCE_MD",
    "TASK_FILE",
    "card_values",
    "driver_instance",
    "export_adapter",
    "find_root",
    "reference_documents",
    "scaffold",
    "write_reference",
]

TASK_FILE = "task.json"
REFERENCE_JSON = "reference.json"
REFERENCE_MD = "REFERENCE.md"
#: Files ``new --like`` never copies from an exemplar (card-, lock- or run-specific, or generated).
_LIKE_SKIP_FILES = frozenset({TASK_FILE, LOCK_FILE, REFERENCE_JSON, REFERENCE_MD, "RESULT.json", "check-report.json",
                              "facts.md", "test_driver.py", "mhs-adapter.json", "README.md"})
#: Directories ``new --like`` never copies (the tutorial's synthetic upstream, caches).
_LIKE_SKIP_DIRS = frozenset({"vendor", "__pycache__", ".git"})
#: Task-card ``helper`` -> template kind.
# OphydDriver and QcodesDriver are PythonObjectDriver subclasses: `mhs.driver new` scaffolds them from the
# python-object templates (there is no separate "ophyd" or "qcodes" template kind).
HELPER_KINDS = {None: "direct", "OphydDriver": "python-object", "QcodesDriver": "python-object",
                "PythonObjectDriver": "python-object", "SerialDriver": "serial",
                "ScpiDriver": "scpi", "GymnasiumDriver": "gymnasium", "MujocoDriver": "mujoco", "RosDriver": "ros",
                # PyLabRobotDriver is a PythonObjectDriver subclass; McpClientDriver, TagDriver and Sila2Driver are
                # config-only families without a template of their own: with --like, the exemplar's code files are
                # copied and gate G2 names the lock `backends` to set (BACKENDS_DIFFER)
                "PyLabRobotDriver": "python-object", "McpClientDriver": "direct", "TagDriver": "direct",
                "Sila2Driver": "direct"}
#: Template kind / family -> ``mhs-adapter.json`` family.
_ADAPTER_FAMILIES = {"ophyd": "python-object", "python-object": "python-object", "serial": "serial", "scpi": "scpi-visa",
                     "gymnasium": "gymnasium", "mujoco": "mujoco"}


# ---------------------------------------------------------------------------
# root and card
# ---------------------------------------------------------------------------


def find_root(start: str | os.PathLike[str] | None = None) -> Path | None:
    """The nearest directory at or above ``start`` (default: the working directory) that holds ``MHS/sdk``."""
    for base in [Path(start).resolve()] if start is not None else []:
        for candidate in [base, *base.parents]:
            if (candidate / "MHS" / "sdk").is_dir():
                return candidate
    cwd = Path.cwd().resolve()
    for candidate in [cwd, *cwd.parents]:
        if (candidate / "MHS" / "sdk").is_dir():
            return candidate
    return None


def read_json(path: Path) -> tuple[Any, str | None]:
    """``(document, None)`` or ``(None, why)``."""
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, f"{path.name} is missing"
    except (OSError, ValueError) as exc:
        return None, f"{path.name} cannot be read: {exc}"


def _slug(text: str, allowed: str = r"[^a-z0-9]+", joiner: str = "-") -> str:
    out = re.sub(allowed, joiner, text.lower()).strip(joiner)
    return out or "device"


def _camel(text: str) -> str:
    words = [word for word in re.split(r"[^A-Za-z0-9]+", text) if word]
    name = "".join(word[:1].upper() + word[1:] for word in words) or "Device"
    return name if name[0].isalpha() else f"D{name}"


def card_values(card: Mapping[str, Any]) -> dict[str, Any]:
    """Template placeholder values from a task card (``mhs.driver.scaffold.default_values`` keys)."""
    out: dict[str, Any] = {}
    package_id = card.get("package_id")
    owner, repo = "example", "device"
    if isinstance(package_id, str) and package_id.startswith("gh.") and "/" in package_id:
        out["package_id"] = package_id
        owner, _, repo = package_id[3:].partition("/")
    out["device_id"] = _slug(repo)
    out["class_name"] = _camel(repo)
    out["cap_owner"] = _slug(owner, r"[^a-z0-9_-]+", "_")
    upstream = card.get("upstream") if isinstance(card.get("upstream"), Mapping) else {}
    for key, name in (("repo_url", "repo_url"), ("commit", "commit"), ("license_spdx", "license_spdx")):
        if isinstance(upstream.get(key), str) and upstream[key]:
            out[name] = upstream[key]
    install = card.get("install") if isinstance(card.get("install"), Mapping) else None
    if install is not None:
        from . import scaffold as _templates

        platform = install.get("platform")
        out["install"] = json.dumps({
            "python": install["python"] if isinstance(install.get("python"), str) and install["python"] else
            _templates.DEFAULT_INSTALL["python"],
            "commands": [str(item) for item in install.get("commands") or []],
            "system_deps": [str(item) for item in install.get("system_deps") or []],
            "gpu": bool(install.get("gpu")),
            "platform": platform if platform in ("any", "linux", "macos", "windows") else "any",
        }, indent=2).replace("\n", "\n  ")
    symbols = [item for item in card.get("entry_symbols") or [] if isinstance(item, Mapping)
               and isinstance(item.get("symbol"), str) and ":" in item["symbol"]]
    symbols.sort(key=lambda item: {"override": 0, "ast": 1, "recon": 2}.get(str(item.get("confidence")), 3))
    if symbols:
        out["native"] = symbols[0]["symbol"]
    safety = card.get("safety") if isinstance(card.get("safety"), Mapping) else {}
    if safety.get("risk_floor") in ("R0", "R1", "R2", "R3"):
        out["risk"] = safety["risk_floor"]
    if safety.get("expected_mode") in ("hardware", "simulated"):
        out["mode"] = safety["expected_mode"]
    return out


def card_kind(card: Mapping[str, Any] | None) -> str:
    helper = (card or {}).get("helper")
    return HELPER_KINDS.get(helper if isinstance(helper, str) else None, "direct")


# ---------------------------------------------------------------------------
# reference files
# ---------------------------------------------------------------------------


def driver_instance(directory: Path, cls: type, backend: str = "fake") -> Any:
    """An instance for drivers whose contract comes from their backend (simulator families), else ``None``."""
    if not getattr(cls, "_needs_instance", False):
        return None
    backends = dict(getattr(cls, "backends", {}) or {})
    name = backend if backend in backends or backend in ("fake", "sim") else "fake"
    return cls(backend=name, base_dir=directory)


def _lock_inputs(directory: Path) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
    lock, _problems = read_lock(directory)
    if not isinstance(lock, Mapping):
        return None, None
    provenance = {key: lock[key] for key in ("authored_by", "reviewed_by") if key in lock}
    upstream = lock.get("upstream") if isinstance(lock.get("upstream"), Mapping) else None
    pinned = None
    if upstream and upstream.get("repo_url") and upstream.get("commit"):
        pinned = {"repo": str(upstream["repo_url"]), "commit": str(upstream["commit"])}
    return provenance or None, pinned


def reference_documents(directory: str | os.PathLike[str], *, cls: type | None = None,
                        instance: Any = None) -> tuple[bytes, str]:
    """``(reference.json bytes, REFERENCE.md text)`` the driver directory must contain (declared view)."""
    path = Path(directory).resolve()
    klass = cls or driver_class(path)
    provenance, upstream = _lock_inputs(path)
    made = None
    subject: Any = klass
    if getattr(klass, "_needs_instance", False):
        subject = instance if instance is not None else driver_instance(path, klass)
        made = subject if instance is None else None
    try:
        reference = _driver_build().build_reference(subject, provenance=provenance, upstream=upstream)
    finally:
        if made is not None:
            made.close()
    return _reference_file.dump(reference) + b"\n", _reference_file.render_markdown(reference)


def _driver_build() -> Any:
    from . import build

    return build


def write_reference(directory: str | os.PathLike[str]) -> list[Path]:
    """Write ``reference.json`` and ``REFERENCE.md`` into the driver directory; returns the paths written."""
    path = Path(directory).resolve()
    data, markdown = reference_documents(path)
    (path / REFERENCE_JSON).write_bytes(data)
    (path / REFERENCE_MD).write_text(markdown, encoding="utf-8")
    return [path / REFERENCE_JSON, path / REFERENCE_MD]


def stale_references(directory: str | os.PathLike[str]) -> list[str]:
    """The generated files that are missing or differ from what :func:`reference_documents` produces."""
    path = Path(directory).resolve()
    data, markdown = reference_documents(path)
    stale = []
    for name, expected in ((REFERENCE_JSON, data), (REFERENCE_MD, markdown.encode("utf-8"))):
        try:
            current = (path / name).read_bytes()
        except OSError:
            current = None
        if current != expected:
            stale.append(name)
    return stale


# ---------------------------------------------------------------------------
# new
# ---------------------------------------------------------------------------


class ScaffoldError(ValueError):
    """``new`` refused to write (an existing file, an unreadable card or exemplar)."""


def scaffold(directory: str | os.PathLike[str], *, card: str | os.PathLike[str] | None = None,
             like: str | os.PathLike[str] | None = None, kind: str | None = None, force: bool = False,
             values: Mapping[str, Any] | None = None) -> list[Path]:
    """Create a driver package in ``directory`` (see ``python -m mhs.driver new --help``); returns the files written.

    The card is ``card`` or ``<directory>/task.json``.  Without ``like`` the
    files come from the templates of ``kind`` (default: from the card's
    ``helper``); with ``like`` the exemplar's code files are copied and the
    card-specific files (``driver.lock.json``, ``facts.md``,
    ``test_driver.py``) come from the templates.  Existing files are never
    overwritten unless ``force``.
    """
    from . import scaffold as _templates

    target = Path(directory).expanduser().resolve()
    card_doc: Mapping[str, Any] | None = None
    card_path = Path(card).expanduser().resolve() if card is not None else target / TASK_FILE
    if card is not None or card_path.is_file():
        document, problem = read_json(card_path)
        if problem is not None:
            raise ScaffoldError(problem)
        if not isinstance(document, Mapping):
            raise ScaffoldError(f"{card_path} is not a task card (a JSON object)")
        card_doc = document
    chosen = kind or card_kind(card_doc)
    if chosen not in _templates.KINDS:
        raise ScaffoldError(f"unknown template kind {chosen!r}; choose one of {list(_templates.KINDS)}")
    merged = card_values(card_doc or {})
    merged.update({key: value for key, value in (values or {}).items() if value is not None})
    rendered = _templates.render(chosen, _templates.default_values(chosen, **merged))
    companions = (card_doc or {}).get("companions")
    if isinstance(companions, list) and companions:
        # A card's reviewed companion sources (user decision 2026-11-05): the lock repeats {package_id, commit} of
        # each, with the LOCK.json alias of a fetched one (lock), in the card's order (gate G2). A card without them
        # renders the template unchanged.
        lock_doc = json.loads(rendered[LOCK_FILE])
        ordered: dict[str, Any] = {}
        for key, value in lock_doc.items():
            ordered[key] = value
            if key == "upstream":
                ordered["companions"] = [{"package_id": item.get("package_id"), "commit": item.get("commit"),
                                          **({"lock": item.get("lock")} if "lock" in item else {})}
                                         for item in companions if isinstance(item, Mapping)]
        rendered = dict(rendered, **{LOCK_FILE: json.dumps(ordered, indent=2) + "\n"})
    files: dict[str, bytes] = {}
    if like is not None:
        exemplar = Path(like).expanduser().resolve()
        if not (exemplar / "driver.py").is_file():
            raise ScaffoldError(f"--like {like}: not a driver directory (no driver.py)")
        for path in sorted(exemplar.rglob("*")):
            relative = path.relative_to(exemplar)
            if any(part in _LIKE_SKIP_DIRS or part.startswith(".") for part in relative.parts[:-1]):
                continue
            if not path.is_file() or path.is_symlink() or relative.name.startswith("."):
                continue
            if len(relative.parts) == 1 and relative.name in _LIKE_SKIP_FILES:
                continue
            files[relative.as_posix()] = path.read_bytes()
        for name in (LOCK_FILE, "facts.md", "test_driver.py"):
            files[name] = rendered[name].encode("utf-8")
    else:
        files = {name: text.encode("utf-8") for name, text in rendered.items()}
    if card_doc is not None and card_path != target / TASK_FILE:
        files[TASK_FILE] = card_path.read_bytes()
    existing = [name for name, data in files.items()
                if (target / name).exists() and not (name == TASK_FILE and (target / name).read_bytes() == data)]
    if existing and not force:
        raise ScaffoldError(f"{target}: refusing to overwrite {sorted(existing)} (pass --force)")
    written = []
    for name, data in sorted(files.items()):
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_bytes() == data:
            continue
        path.write_bytes(data)
        written.append(path)
    return written


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------


def _family_of(cls: type) -> str:
    from . import families

    from .mcp_client_driver import McpClientDriver
    if issubclass(cls, McpClientDriver):
        return 'mcp-proxy'
    if issubclass(cls, families.RosDriver):
        return "ros1" if cls.ros_version == 1 else "ros2"
    for name, family in (("Sila2Driver", "sila2"), ("HttpDriver", "http-api"), ("OphydDriver", "bluesky-ophyd"), ("PythonObjectDriver", "python-object"), ("SerialDriver", "serial"),
                         ("ScpiDriver", "scpi-visa"), ("GymnasiumDriver", "gymnasium"), ("MujocoDriver", "mujoco")):
        if issubclass(cls, getattr(families, name)):
            return family
    return "other"


def export_adapter(directory: str | os.PathLike[str], *, out: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    """An ``mhs-adapter.json`` document for the driver directory (validated against ``adapter.schema.json``).

    ``out`` is where the document will be written: its single ``driver``
    bridge names the directory relative to it, so ``mhs.adapter.load(out)``
    serves the same driver.
    """
    from ..schema import default_store
    from .build import build_manifest

    path = Path(directory).resolve()
    cls = driver_class(path)
    card, _problem = read_json(path / TASK_FILE)
    card = card if isinstance(card, Mapping) else {}
    lock, _lock_problems = read_lock(path)
    instance = driver_instance(path, cls)
    try:
        manifest = build_manifest(instance if instance is not None else cls, backend=None, instance_id="0" * 26)
        model = (instance._model if instance is not None else cls.driver_model())
    finally:
        if instance is not None:
            instance.close()
    package_id = str(card.get("package_id") or (lock or {}).get("package_id") or f"gh.local/{path.name}")
    adapter_id = re.sub(r"[^a-z0-9_.-]+", ".", package_id.lower().replace("/", ".")).strip(".")[:128]
    if len(adapter_id) < 3:
        adapter_id = f"driver.{adapter_id}"
    upstream = (lock or {}).get("upstream") if isinstance((lock or {}).get("upstream"), Mapping) else {}
    source: dict[str, Any] = {"repo": str(upstream.get("repo_url") or "synthetic (no upstream)"),
                              "license": str(upstream.get("license_spdx") or "NOASSERTION")}
    if upstream.get("commit"):
        source["commit"] = str(upstream["commit"])
    if isinstance(card.get("local_path"), str):
        source["local_path"] = card["local_path"]
    where = Path(out).expanduser().resolve().parent if out is not None else path
    relative = os.path.relpath(path, where).replace(os.sep, "/")
    install = (lock or {}).get("install") if isinstance((lock or {}).get("install"), Mapping) else {}
    runtime: dict[str, Any] = {"kind": "python", "python": str(install.get("python") or ">=3.10"),
                               "entry": "mhs.adapter:load"}
    if install.get("commands"):
        runtime["install"] = [str(item) for item in install["commands"]]
    document: dict[str, Any] = {
        "$schema": _ids.SCHEMA_BASE + "adapter.schema.json",
        "mhs_adapter": _ids.WIRE_VERSION,
        "adapter_id": adapter_id,
        "title": str(manifest.get("display_name") or model.driver)[:160],
        "family": _family_of(cls),
        "source": source,
        "runtime": runtime,
        "devices": [manifest],
        "bridges": [{"bridge_id": "mhs.driver", "kind": "driver", "config": {"path": relative or "."}}],
        "safety": {"risk_class": model.risk},
        "registry": {"package_id": package_id},
    }
    problems = default_store().validate(document, "adapter.schema.json")
    if problems:
        raise DriverDefinitionError([f"exported mhs-adapter.json is invalid: {item}" for item in problems[:5]])
    return document


def relative_to_root(path: Path, root: Path | None) -> str:
    """``path`` relative to ``root`` (POSIX) when inside it, else absolute."""
    if root is not None:
        try:
            return PurePosixPath(path.resolve().relative_to(root.resolve()).as_posix()).as_posix()
        except ValueError:
            pass
    return path.resolve().as_posix()


def copy_tree(source: Path, target: Path) -> None:
    """Copy a driver directory (tests and tutorials), skipping caches."""
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "check-report.json"))
