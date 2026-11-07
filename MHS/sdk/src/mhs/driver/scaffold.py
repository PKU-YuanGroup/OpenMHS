"""Render the driver package templates (``mhs/driver/templates/``, package data).

:func:`render` returns ``{file name: text}`` for one template kind; the
``python -m mhs.driver new`` command writes them into a driver directory.
Placeholders are ``string.Template`` names (see ``templates/README.md``); a
missing one raises ``KeyError``.
"""

from __future__ import annotations

import datetime
import json
import string
from pathlib import Path
from typing import Any, Mapping

from .. import _ids

__all__ = ["DEFAULT_INSTALL", "KINDS", "default_values", "render", "templates_dir"]

#: Template kinds: a decorated Driver and the config-only family drivers.
KINDS = ("direct", "python-object", "serial", "scpi", "gymnasium", "mujoco", "ros")
_COMMON = "common"
#: The lock's ``install`` block when the card says nothing; a card's own ``install`` replaces it (``package.card_values``).
DEFAULT_INSTALL = {"python": ">=3.10", "commands": [], "system_deps": [], "gpu": False, "platform": "any"}
_LOCK_BACKENDS = {
    "direct": {"hardware": ".native:connect", "fake": ".fake:Fake{class_name}"},
    "python-object": {"hardware": ".native:connect", "fake": ".fake:Fake{class_name}"},
    "serial": {"fake": ".fake:Fake{class_name}"},
    "scpi": {"fake": ".fake:Fake{class_name}"},
    "ros": {"fake": ".fake:Fake{class_name}"},
    "gymnasium": {"fake": "gymnasium:make"},
    "mujoco": {"fake": "mujoco"},
}


def templates_dir() -> Path:
    """The directory holding the template kinds."""
    return Path(__file__).resolve().parent / "templates"


def _files(kind: str) -> dict[str, Path]:
    if kind not in KINDS:
        raise ValueError(f"unknown template kind {kind!r}; choose one of {list(KINDS)}")
    root = templates_dir()
    found: dict[str, Path] = {}
    for directory in (root / _COMMON, root / kind):
        for path in sorted(directory.glob("*.tmpl")):
            found[path.name[: -len(".tmpl")]] = path
    return found


def default_values(kind: str = "direct", **values: Any) -> dict[str, str]:
    """Placeholder values with neutral defaults, overridden by ``values``."""
    out: dict[str, Any] = {
        "class_name": "ExampleDevice",
        "device_id": "example-device",
        "device_kind": "world.sim" if kind in ("gymnasium", "mujoco") else "instrument",
        "mode": "simulated" if kind in ("gymnasium", "mujoco") else "hardware",
        "risk": "R0",
        "native": "example.module:ExampleDevice",
        "safe_state": "outputs off, motion stopped",
        "package_id": "gh.example/example-device",
        "repo_url": "https://github.com/example/example-device",
        "commit": "0" * 40,
        "license_spdx": "NOASSERTION",
        "model_id": "unknown-model",
        "run_id": "run-0000",
        "date": datetime.date.today().isoformat(),
        "sdk_version": _ids.SDK_VERSION,
        "schema_base": _ids.SCHEMA_BASE,
        "cap_owner": "example",
        "env_id": "CartPole-v1",
        "model_path": "model.xml",
    }
    out.update({key: value for key, value in values.items() if value is not None})
    module, _, cls = str(out["native"]).partition(":")
    out.setdefault("native_module", module)
    out.setdefault("native_class", cls or module.rsplit(".", 1)[-1])
    if "install" not in out:
        out["install"] = json.dumps(DEFAULT_INSTALL, indent=2).replace("\n", "\n  ")
    if "lock_backends" not in out:
        backends = {name: target.format(class_name=out["class_name"]) for name, target in _LOCK_BACKENDS[kind].items()}
        out["lock_backends"] = json.dumps(backends, indent=2).replace("\n", "\n  ")
    return {key: str(value) for key, value in out.items()}


def render(kind: str, values: Mapping[str, Any]) -> dict[str, str]:
    """``{file name: rendered text}`` of template ``kind`` with ``values`` (see :func:`default_values`)."""
    return {name: string.Template(path.read_text(encoding="utf-8")).substitute(dict(values))
            for name, path in _files(kind).items()}
