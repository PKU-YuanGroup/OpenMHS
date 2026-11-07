"""Import a per-repo driver package and read its lock file (used by :mod:`mhs.adapter` and the gate).

A driver directory (``MHS/drivers/<track>/<owner>__<repo>/``) is imported as a
private package whose name is derived from its path and the digest of its
Python files, so ``driver.py`` may use relative imports (``from .fake import
FakeBath``) and ``backends`` entries such as ``".fake:FakeBath"`` resolve
inside it.  Importing never writes ``__pycache__`` into the directory.  The
driver class is the module's ``DRIVER`` attribute, or the single
:class:`~mhs.driver.Driver` subclass defined in ``driver.py``.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import re
import sys
import threading
import types
from pathlib import Path
from typing import Any, Mapping

from .base import Driver
from .spec import DriverDefinitionError

__all__ = ["LOCK_FILE", "driver_class", "import_driver_module", "read_lock", "review_problem"]

LOCK_FILE = "driver.lock.json"
DRIVER_FILE = "driver.py"
_PACKAGE_PREFIX = "_mhs_driver_pkg_"
_IMPORT_LOCK = threading.Lock()


def _package_name(directory: Path) -> str:
    """A private package name from the path and every ``*.py`` file of the package (subpackages included)."""
    digest = hashlib.sha256(str(directory).encode("utf-8"))
    for path in sorted(directory.rglob("*.py")):
        relative = path.relative_to(directory)
        if any(part == "__pycache__" or part.startswith(".") for part in relative.parts[:-1]):
            continue
        try:
            digest.update(relative.as_posix().encode("utf-8") + b"\0" + path.read_bytes() + b"\0")
        except OSError:
            continue
    slug = re.sub(r"[^0-9A-Za-z_]", "_", directory.name)[:40] or "driver"
    return f"{_PACKAGE_PREFIX}{slug}_{digest.hexdigest()[:12]}"


def import_driver_module(directory: str | Path) -> types.ModuleType:
    """Import ``<directory>/driver.py`` as ``<private package>.driver`` (cached while the files are unchanged)."""
    path = Path(directory).expanduser().resolve()
    if not (path / DRIVER_FILE).is_file():
        raise DriverDefinitionError(f"{path} is not a driver directory: it has no {DRIVER_FILE}")
    name = _package_name(path)
    with _IMPORT_LOCK:
        cached = sys.modules.get(f"{name}.driver")
        if cached is not None:
            return cached
        package = types.ModuleType(name)
        package.__path__ = [str(path)]  # type: ignore[attr-defined]
        package.__package__ = name
        package.__file__ = None
        sys.modules[name] = package
        previous = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
        try:
            return importlib.import_module(f"{name}.driver")
        except DriverDefinitionError:
            _forget(name)
            raise
        except Exception as exc:
            _forget(name)
            raise DriverDefinitionError(f"{path / DRIVER_FILE} cannot be imported: {type(exc).__name__}: {exc}") from exc
        finally:
            sys.dont_write_bytecode = previous


def _forget(name: str) -> None:
    for key in [key for key in sys.modules if key == name or key.startswith(name + ".")]:
        sys.modules.pop(key, None)


def driver_class(directory: str | Path) -> type:
    """The Driver class of a driver directory (``DRIVER``, or the one Driver subclass defined in driver.py)."""
    module = import_driver_module(directory)
    declared = getattr(module, "DRIVER", None)
    if declared is not None:
        if not (isinstance(declared, type) and issubclass(declared, Driver)):
            raise DriverDefinitionError(f"{module.__name__}.DRIVER must be a Driver subclass, got {declared!r}")
        return declared
    found = [value for value in vars(module).values()
             if isinstance(value, type) and issubclass(value, Driver) and value.__module__ == module.__name__
             and not value.__dict__.get("_family_base", False)]
    if not found:
        raise DriverDefinitionError(f"{directory}/{DRIVER_FILE} defines no Driver subclass")
    if len(found) > 1:
        names = sorted(item.__name__ for item in found)
        raise DriverDefinitionError(f"{directory}/{DRIVER_FILE} defines several Driver classes {names}; "
                                    "set DRIVER = <the served class>")
    return found[0]


def read_lock(directory: str | Path) -> tuple[dict[str, Any] | None, list[str]]:
    """``(driver.lock.json document or None, problems)``; the document is validated against its schema."""
    path = Path(directory) / LOCK_FILE
    if not path.is_file():
        return None, []
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, [f"{LOCK_FILE} cannot be read: {exc}"]
    if not isinstance(document, dict):
        return None, [f"{LOCK_FILE} must be a JSON object"]
    from ..schema import default_store

    try:
        problems = default_store().validate(document, "driver-lock.schema.json")
    except Exception as exc:  # noqa: BLE001 - no schema: fail closed
        problems = [f"{LOCK_FILE} cannot be validated ({type(exc).__name__}: {exc})"]
    return document, [f"{LOCK_FILE}: {item}" for item in problems]


def review_problem(lock: Mapping[str, Any] | None, lock_problems: list[str], *, risk: str,
                   require_human: bool = False, companion_stop: bool = False) -> str | None:
    """Why a hardware backend at ``risk`` may not start under this lock (``None``: it may).

    A hardware device at R2 or above needs a valid ``driver.lock.json``; a
    model-authored driver additionally needs a human ``reviewed_by``
    signature. ``require_human`` is the ROS and tag-bridge family policy: every
    hardware backend requires a valid human review with scope ``hardware``,
    regardless of risk or authorship. ``companion_stop`` is the same requirement
    for a driver whose e-stop cites a companion (user decision 4, 2026-11-05):
    the citation does not waive the signature, at any risk, and a model does
    not write ``reviewed_by``. An ordinary R1 driver without that declaration
    is unchanged.
    """
    if not require_human and not companion_stop and risk not in ("R2", "R3"):
        return None
    if lock is None:
        return (f"a hardware backend at {risk} needs {LOCK_FILE} (authored_by, reviewed_by); "
                + (lock_problems[0] if lock_problems else "the file is missing"))
    if lock_problems:
        return f"{LOCK_FILE} is invalid: {lock_problems[0]}"
    if companion_stop:
        reviewer = lock.get("reviewed_by")
        if not isinstance(reviewer, Mapping) or reviewer.get("scope") != "hardware":
            return ("this driver's e-stop cites a companion source; a human reviewer must sign reviewed_by with "
                    f"scope hardware in {LOCK_FILE} before a hardware backend may start (the companion citation "
                    "does not waive that signature, at any risk)")
        return None
    if require_human:
        reviewer = lock.get("reviewed_by")
        if not isinstance(reviewer, Mapping) or reviewer.get("scope") != "hardware":
            return (f"a ROS or tag-bridge hardware backend at {risk} needs a human reviewed_by signature with scope "
                    f"hardware in {LOCK_FILE} before it may start (all risk classes and authors)")
        return None
    authored = lock.get("authored_by") if isinstance(lock.get("authored_by"), Mapping) else {}
    if authored.get("kind") == "model" and lock.get("reviewed_by") is None:
        return (f"this driver was written by a model ({authored.get('model_id')}) and is a hardware device at "
                f"{risk}: a human reviewer must sign reviewed_by in {LOCK_FILE} before a hardware backend may start")
    return None
