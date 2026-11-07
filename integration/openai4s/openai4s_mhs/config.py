"""Configuration for the OpenAI4S x OpenMHS reference host.

Configuration sources, in priority order:

1. explicit ``MHSConfig`` passed to :class:`MHSHost` / :func:`install`;
2. ``MHS_CONFIG=/path/to/mhs.json``;
3. ``~/.openai4s/mhs.json``;
4. the ``MHS_ENDPOINTS`` environment variable (comma-separated endpoint URLs).

The file format is JSON and deliberately boring::

    {
      "enabled": false,
      "endpoints": [
        {"id": "lab",      "url": "http://127.0.0.1:7401", "label": "lab simulator"},
        {"id": "conveyor", "command": ["python3", "-m", "mhs.reference", "conveyor", "--stdio"],
         "label": "conveyor workcell"}
      ],
      "evidence_log": "~/.openai4s/mhs-evidence.jsonl",
      "allow_hardware": false,
      "auto_permit_risk": ["R0", "R1"],
      "session_ttl_s": 900,
      "command_timeout_ms": 60000,
      "estop_devices": ["mhs://lab.local/liquid-handler"],
      "command_journal": "~/.openai4s/mhs-commands.jsonl",
      "host_ledger": "~/.openai4s/mhs-host-ledger.jsonl",
      "operator_token_file": "~/.openai4s/mhs-operator.token"
    }

``enabled=false`` is the default and the most important line: the MHS **MCP
connector** is experimental and disabled until the operator turns it on in
settings (``python -m openai4s_mhs enable``, ``MHS_ENABLED=1``, or
``"enabled": true`` in this file).  A disabled setting means the generated MCP
connector rows stay disabled and no endpoint connection is opened by the agent;
OpenAI4S still lists them in settings so the operator can enable them there.

``allow_hardware=false`` means a device whose manifest declares
``mode: "hardware"`` is discovered but sessions are refused unless the operator
flips the flag: a research agent should not accidentally drive a real
instrument because a config file listed it.  Only a JSON ``true`` turns
``enabled`` or ``allow_hardware`` on (the rule ``mhs.mcp`` applies to the same
document); a quoted ``"true"``/``"false"`` or ``1`` reads as false and is listed
in :attr:`MHSConfig.notices`.

The same document is the ``--config`` of every agent connector row, so it must
not set ``operator_tools`` (that would list ``mhs__reset``/``mhs__permit`` to the
model; :attr:`MHSConfig.warnings` reports it and the host route refuses both
tools anyway).  Resets and permits go through the host operator route
(:mod:`openai4s_mhs.operator_route`), which launches ``mhs.mcp --operator-tools``
and, when ``operator_token_file`` is set, authenticates with that token.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_PATH = Path.home() / ".openai4s" / "mhs.json"

#: Risk classes a host may approve automatically for *simulated* devices when
#: no human approval channel exists.  Hardware sessions never auto-approve R2+.
DEFAULT_AUTO_PERMIT = ("R0", "R1")


@dataclass(frozen=True)
class EndpointSpec:
    """One MHS endpoint the host may connect to.

    Either ``url`` (``http://`` / ``https://`` / ``mhs://``) or ``command`` (a
    local stdio-launched endpoint, the MHS T1 binding) must be present.  ``id``
    is the short name used by tools and the CLI.
    """

    id: str
    url: str | None = None
    command: list[str] | None = None
    label: str = ""
    env: dict[str, str] = field(default_factory=dict)

    def to_mhs_target(self):
        """Return the value passed to ``mhs.connect``."""
        if self.command:
            return list(self.command)
        if self.url:
            return self.url
        raise ValueError(f"endpoint {self.id!r} has neither url nor command")

    def public(self) -> dict:
        return {
            "id": self.id,
            "label": self.label or self.id,
            "transport": "stdio" if self.command else "http",
            "target": self.url or " ".join(self.command or []),
        }


@dataclass
class MHSConfig:
    #: Experimental feature switch.  False by default: MHS does not exist for the
    #: agent until an operator enables it in settings.
    enabled: bool = False
    #: Register/update the MCP connector rows in OpenAI4S's connector store when
    #: enabling/disabling, so the switch appears in its settings surface.
    sync_openai4s: bool = True
    endpoints: list[EndpointSpec] = field(default_factory=list)
    evidence_log: str = "~/.openai4s/mhs-evidence.jsonl"
    allow_hardware: bool = False
    auto_permit_risk: tuple[str, ...] = DEFAULT_AUTO_PERMIT
    session_ttl_s: int = 900
    command_timeout_ms: int = 60000
    max_output_chars: int = 20000
    #: Explicit emergency-stop device allow-list.  Entries may be full device
    #: ids, short device names, ``endpoint_id:device_id`` or ``endpoint_id:*``.
    #: Empty means "every device discovered on a configured endpoint", which is
    #: still endpoint-bound: an arbitrary connector/URL can never be selected.
    estop_devices: tuple[str, ...] = ()
    #: Durable pre-dispatch journal and host evidence ledger (HOST-003/HOST-004).
    command_journal: str = "~/.openai4s/mhs-commands.jsonl"
    host_ledger: str = "~/.openai4s/mhs-host-ledger.jsonl"
    #: Bearer token file of the human operator, used only by the host operator
    #: route (``mhs.mcp --operator-tools --token-file``) for HTTP endpoints.
    operator_token_file: str | None = None
    #: Settings problems found while loading (never secrets).  Each one weakens
    #: the agent connector rows, so agent rows are refused while any is present.
    warnings: tuple[str, ...] = ()
    #: Settings values that were ignored (a policy flag that is not a JSON
    #: boolean reads as false).  Reported by ``status``; they block nothing.
    notices: tuple[str, ...] = ()
    #: The settings file this config was loaded from (``None`` for an explicit
    #: in-memory config).  The generated MCP connector passes it as ``--config``.
    config_path: str | None = None

    # ---------------------------------------------------------------- loading
    @classmethod
    def load(cls, path: str | Path | None = None) -> "MHSConfig":
        """Load configuration from disk/env without ever raising on absence."""
        raw: dict = {}
        candidate = None
        if path is not None:
            candidate = Path(path).expanduser()
        elif os.environ.get("MHS_CONFIG"):
            candidate = Path(os.environ["MHS_CONFIG"]).expanduser()
        elif DEFAULT_CONFIG_PATH.exists():
            candidate = DEFAULT_CONFIG_PATH
        if candidate is not None and candidate.exists():
            with open(candidate, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            if not isinstance(raw, dict):
                raise ValueError(f"MHS settings document {str(candidate)!r} must be a JSON object")
        config = cls(
            enabled=_read_enabled(raw),
            sync_openai4s=bool(raw.get("sync_openai4s", raw.get("declare_in_openai4s", True))),
            endpoints=[_endpoint_from_dict(item) for item in raw.get("endpoints", [])],
            evidence_log=str(raw.get("evidence_log", "~/.openai4s/mhs-evidence.jsonl")),
            allow_hardware=_read_flag(raw, "allow_hardware"),
            auto_permit_risk=tuple(raw.get("auto_permit_risk", DEFAULT_AUTO_PERMIT)),
            session_ttl_s=int(raw.get("session_ttl_s", 900)),
            command_timeout_ms=int(raw.get("command_timeout_ms", 60000)),
            max_output_chars=int(raw.get("max_output_chars", 20000)),
            estop_devices=tuple(str(item) for item in raw.get("estop_devices", [])),
            command_journal=str(raw.get("command_journal", "~/.openai4s/mhs-commands.jsonl")),
            host_ledger=str(raw.get("host_ledger", "~/.openai4s/mhs-host-ledger.jsonl")),
            operator_token_file=(
                str(raw["operator_token_file"]) if raw.get("operator_token_file") else None
            ),
            warnings=_settings_warnings(raw),
            notices=_settings_notices(raw),
            config_path=str(candidate) if candidate is not None else None,
        )
        config.enabled = _env_override() if _env_override() is not None else config.enabled
        if not config.endpoints:
            config.endpoints = endpoints_from_env()
        return config

    # ------------------------------------------------------------ experimental
    @property
    def experimental(self) -> bool:
        """The MCP integration is always experimental in this release."""
        return True

    @property
    def declare_in_openai4s(self) -> bool:
        """Backwards-compatible alias for :attr:`sync_openai4s`."""
        return self.sync_openai4s

    def to_settings(self) -> dict:
        """The operator-facing view of the switch (what settings shows)."""
        settings = {
            "feature": "mhs",
            "kind": "mcp",
            "experimental": True,
            "enabled": bool(self.enabled),
            "default_enabled": False,
            "transport": "mcp",
            "note": (
                "The OpenMHS MCP integration is experimental and disabled by "
                "default; enable it explicitly in settings."
            ),
        }
        if self.warnings:
            settings["warnings"] = list(self.warnings)
        if self.notices:
            settings["notices"] = list(self.notices)
        return settings

    # --------------------------------------------------------------- helpers
    def endpoint(self, endpoint_id: str | None) -> EndpointSpec:
        if not self.endpoints:
            raise LookupError(
                "no MHS endpoints configured; set MHS_ENDPOINTS, write "
                f"{DEFAULT_CONFIG_PATH}, or call MHSHost with an explicit config"
            )
        if endpoint_id is None:
            if len(self.endpoints) == 1:
                return self.endpoints[0]
            raise LookupError(
                "multiple MHS endpoints configured; name one of: "
                + ", ".join(ep.id for ep in self.endpoints)
            )
        for ep in self.endpoints:
            if ep.id == endpoint_id:
                return ep
        raise LookupError(
            f"unknown MHS endpoint {endpoint_id!r}; configured: "
            + ", ".join(ep.id for ep in self.endpoints)
        )

    @property
    def evidence_path(self) -> Path:
        return Path(self.evidence_log).expanduser()

    @property
    def command_journal_path(self) -> Path:
        return Path(self.command_journal).expanduser()

    @property
    def host_ledger_path(self) -> Path:
        return Path(self.host_ledger).expanduser()


def _endpoint_from_dict(item: dict) -> EndpointSpec:
    command = item.get("command")
    if isinstance(command, str):
        command = command.split()
    base = item.get("label") or item.get("id") or ""
    return EndpointSpec(
        id=str(item.get("id") or _slug(item.get("url") or base or "endpoint")),
        url=item.get("url"),
        command=list(command) if command else None,
        label=str(base),
        env={str(k): str(v) for k, v in (item.get("env") or {}).items()},
    )


def endpoints_from_env(value: str | None = None) -> list[EndpointSpec]:
    raw = value if value is not None else os.environ.get("MHS_ENDPOINTS", "")
    specs: list[EndpointSpec] = []
    for token in str(raw or "").split(","):
        token = token.strip()
        if not token:
            continue
        if token.startswith("stdio:"):
            argv = token[len("stdio:") :].split()
            specs.append(EndpointSpec(id=_slug(" ".join(argv[1:3]) or "stdio"), command=argv))
        else:
            specs.append(EndpointSpec(id=_slug(token), url=token, label=token))
    return specs


# ---------------------------------------------------------------------------
# Experimental-skill setting (default off)
# ---------------------------------------------------------------------------

#: Environment override understood by every entry point: ``MHS_ENABLED=1``
#: enables the experimental MCP integration for this process without editing settings.
ENV_ENABLED = "MHS_ENABLED"
_TRUTHY = {"1", "true", "yes", "on", "enable", "enabled"}
_FALSEY = {"0", "false", "no", "off", "disable", "disabled"}


def _env_override() -> bool | None:
    raw = os.environ.get(ENV_ENABLED)
    if raw is None or not str(raw).strip():
        return None
    value = str(raw).strip().lower()
    if value in _TRUTHY:
        return True
    if value in _FALSEY:
        return False
    return None


def _read_flag(raw: dict, key: str) -> bool:
    """Only a JSON ``true`` turns a policy flag on (the same rule as ``mhs.mcp.MCPPolicy.load``).

    ``"false"``, ``"true"`` and ``1`` all read as false, so a quoted value can never open the
    hardware gate in one parser while ``mhs.mcp`` keeps it shut.
    """
    return raw.get(key, False) is True


def _read_enabled(raw: dict) -> bool:
    """Only a JSON ``true`` enables the integration (the same rule as ``mhs.mcp.MCPPolicy.load``)."""
    return _read_flag(raw, "enabled")


#: Policy flags read with :func:`_read_flag`; a non-boolean value is reported in ``notices``.
_POLICY_FLAGS = ("enabled", "allow_hardware", "operator_tools", "allow_external_sessions")


def _settings_notices(raw: dict) -> tuple[str, ...]:
    """Settings values that were ignored because they are not JSON booleans (never secrets).

    They do not weaken anything (every such flag reads as false), so unlike
    :func:`_settings_warnings` they never block agent connector rows.
    """
    found: list[str] = []
    for key in _POLICY_FLAGS:
        if key in raw and not isinstance(raw[key], bool):
            found.append(
                f"{key}={json.dumps(raw[key])[:40]} is not a JSON boolean and reads as false; "
                f"write {key}: true or {key}: false"
            )
    return tuple(found)


def _settings_warnings(raw: dict) -> tuple[str, ...]:
    """Settings that weaken the agent connector rows that share this document."""
    found: list[str] = []
    if raw.get("operator_tools") is True:
        found.append(
            "operator_tools=true lists mhs__reset/mhs__permit on every agent connector "
            "row; remove it (the host operator route passes --operator-tools itself)"
        )
    if raw.get("allow_external_sessions") is True:
        found.append(
            "allow_external_sessions=true lets the model name sessions the connector "
            "did not open; remove it"
        )
    return tuple(found)


def resolve_config_path(path: str | Path | None = None) -> Path:
    """$MHS_CONFIG, then the explicit path, then ``~/.openai4s/mhs.json``."""
    if path is not None:
        return Path(path).expanduser()
    env = os.environ.get("MHS_CONFIG")
    if env:
        return Path(env).expanduser()
    return DEFAULT_CONFIG_PATH


def read_raw_config(path: str | Path | None = None) -> dict:
    """Read the settings file as-is (empty dict when it does not exist)."""
    target = resolve_config_path(path)
    if not target.exists():
        return {}
    with open(target, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data if isinstance(data, dict) else {}


def write_raw_config(raw: dict, path: str | Path | None = None) -> Path:
    """Persist settings atomically with owner-only permissions."""
    target = resolve_config_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    with open(temporary, "w", encoding="utf-8") as fh:
        json.dump(raw, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(temporary, target)
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass
    return target


def update_settings(path: str | Path | None = None, **updates: Any) -> dict:
    """Merge ``updates`` into the settings file and return the new document."""
    raw = read_raw_config(path)
    raw.update(updates)
    write_raw_config(raw, path)
    return raw


def set_enabled(enabled: bool, path: str | Path | None = None) -> dict:
    """Turn the experimental MHS skill on or off in the settings file."""
    return update_settings(
        path,
        enabled=bool(enabled),
        experimental=True,
        default_enabled=False,
        transport="mcp",
    )


def is_enabled(path: str | Path | None = None) -> bool:
    """Effective setting: environment override, then the settings file, then off."""
    override = _env_override()
    if override is not None:
        return override
    return _read_enabled(read_raw_config(path))


def _slug(value: str) -> str:
    out = []
    for char in str(value).lower():
        if char.isalnum() or char in "-_":
            out.append(char)
        elif out and out[-1] != "-":
            out.append("-")
    slug = "".join(out).strip("-")
    return slug[-40:] or "endpoint"
