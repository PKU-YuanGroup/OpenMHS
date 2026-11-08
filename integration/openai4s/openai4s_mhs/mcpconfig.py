"""Generate OpenAI4S MCP connector rows for OpenMHS endpoints.

OpenAI4S already ships a stdio MCP client, so a connector row is configuration,
not code: one row per MHS endpoint whose command is ``python -m mhs.mcp
--endpoint <target> --config <settings>``.  OpenAI4S's ``MCPManager`` then
discovers the endpoint's projected tools and resources and every call goes
through MHS's own server -- sessions, permits and receipts included -- with the
host ``enabled``/``allow_hardware`` policy enforced by the projection
(HOST-001).  The rows work on unpatched OpenAI4S; the governed host route on
top of them (journal, host ledger, trusted e-stop) needs
``openai4s-core.patch`` (:mod:`openai4s_mhs.corepatch`).

This module only builds the dictionaries; it never writes OpenAI4S state.  The
generated shape matches the connector rows OpenAI4S stores (``id``,
``command``, ``transport``, ``enabled``, ``env``) and the ``{"connectors":
[...]}`` configuration file documented in the integration README.

Agent rows never carry ``--operator-tools``: ``mhs__reset`` and ``mhs__permit``
stay hidden from the model.  :func:`operator_argv` is the command line of the
host operator route (:mod:`openai4s_mhs.operator_route`) and is never stored as
a connector row.
"""

from __future__ import annotations

import copy
import os
import re
import shlex
import sys
import sysconfig
from pathlib import Path
from typing import Any, Iterable

from . import connector_registry
from .config import EndpointSpec, MHSConfig

#: The module OpenAI4S spawns. ``mhs.mcp`` is the SDK's stdio MCP projection of
#: one MHS endpoint; it is the whole of Path A.
MCP_MODULE = "mhs.mcp"

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def _slug(value: str, *, limit: int = 40) -> str:
    text = _SLUG_STRIP.sub("-", str(value).lower()).strip("-")
    return text[-limit:] or "endpoint"


def endpoint_target(spec: EndpointSpec) -> str:
    """The MHS transport target for one endpoint.

    HTTP(S) and ``mhs://`` endpoints use their URL.  A stdio endpoint has no
    URL; it is encoded with the ``mhs+stdio://argv,argv`` form that
    ``mhs.connect`` resolves back to a spawned process.
    """
    if spec.command:
        return "mhs+stdio://" + ",".join(str(part) for part in spec.command)
    if spec.url:
        return spec.url
    raise ValueError(f"endpoint {spec.id!r} has neither url nor command")


def connector_argv(
    spec: EndpointSpec, *, python: str | None = None, config_path: str | None = None
) -> list[str]:
    """The connector command array: one stdio MCP server fronting the endpoint.

    ``mhs.mcp`` takes ``--endpoint URL`` for a running HTTP endpoint and
    ``--command "<argv>"`` for a stdio endpoint it spawns itself; both keep the
    connector a plain stdio server, which is all OpenAI4S requires.

    ``--config <settings JSON>`` carries the host deployment policy
    (``enabled``, ``allow_hardware``) into the projection.  It is always added:
    dropping it was HOST-001, where enabling the connector silently discarded
    the documented hardware restriction.
    """
    launcher = source_launcher()
    argv = [python or sys.executable, launcher] if launcher else [python or sys.executable, "-m", MCP_MODULE]
    if spec.command:
        argv.extend(["--command", shlex.join([str(part) for part in spec.command])])
    elif spec.url:
        argv.extend(["--endpoint", spec.url])
    else:
        raise ValueError(f"endpoint {spec.id!r} has neither url nor command")
    argv.extend(["--config", str(_resolve_policy_path(config_path))])
    return argv


def operator_argv(
    spec: EndpointSpec,
    config: MHSConfig,
    *,
    python: str | None = None,
    config_path: str | None = None,
) -> list[str]:
    """The command line of the host operator route for one endpoint.

    The agent row's command plus ``--operator-tools`` (``mhs__reset`` and
    ``mhs__permit`` are listed), and ``--token-file`` with the operator's token
    when ``operator_token_file`` is configured and the endpoint is HTTP.  It is
    only ever launched by :class:`openai4s_mhs.operator_route.OperatorRoute`.
    """
    argv = connector_argv(spec, python=python, config_path=config_path or config.config_path)
    argv.append("--operator-tools")
    token_file = getattr(config, "operator_token_file", None)
    if token_file and spec.url and not spec.command:
        argv.extend(["--token-file", str(Path(str(token_file)).expanduser())])
    return argv


def _sdk_source_root() -> str | None:
    """The ``sys.path`` entry ``mhs`` was imported from, when it is a source tree.

    OpenAI4S starts each MCP connector with a least-privilege environment (no
    ``PYTHONPATH``), so a row whose ``mhs.mcp`` must come from a source checkout
    has to name it in its own ``env``.  An installed ``openmhs`` (site-packages)
    needs nothing.
    """
    try:
        import mhs  # noqa: PLC0415 - optional at import time
    except Exception:  # noqa: BLE001 - the row is still generated; the child reports it
        return None
    root = Path(str(getattr(mhs, "__file__", "") or "")).resolve().parents[1]
    installed = {
        str(Path(path).resolve())
        for key in ("purelib", "platlib")
        for path in [sysconfig.get_paths().get(key)]
        if path
    }
    if str(root) in installed or root.name in ("site-packages", "dist-packages"):
        return None
    return str(root)


#: The self-locating stdio launcher of this checkout (see the file's docstring).
LAUNCHER = Path(__file__).resolve().parents[1] / "launch" / "mhs.mcp"


def source_launcher() -> str | None:
    """``launch/mhs.mcp`` when ``mhs`` is imported from this checkout's source tree, else ``None``.

    With it a generated row needs no ``env`` (no ``PYTHONPATH``); an installed
    ``openmhs``, or an SDK from another tree, keeps ``-m mhs.mcp``.
    """
    root = _sdk_source_root()
    if not root or not LAUNCHER.is_file():
        return None
    own_src = Path(__file__).resolve().parents[3] / "MHS" / "sdk" / "src"
    return str(LAUNCHER) if Path(root).resolve() == own_src.resolve() else None


def connector_env() -> dict[str, str]:
    """``env`` of a generated row: ``PYTHONPATH`` when the SDK is a source tree.

    A source tree also gets the caller's ``PYTHONDONTWRITEBYTECODE``, so a
    checkout run without bytecode stays without it in the connector children.
    """
    root = _sdk_source_root()
    if not root:
        return {}
    env = {"PYTHONPATH": root}
    if os.environ.get("PYTHONDONTWRITEBYTECODE"):
        env["PYTHONDONTWRITEBYTECODE"] = os.environ["PYTHONDONTWRITEBYTECODE"]
    return env


def _resolve_policy_path(config_path: str | None) -> str:
    if config_path:
        return str(config_path)
    from .config import resolve_config_path

    return str(resolve_config_path(None))


def connector_id(spec: EndpointSpec) -> str:
    """A stable, provider-portable connector id for one endpoint."""
    return "mhs-" + _slug(spec.id)


def connector_entry(
    spec: EndpointSpec,
    *,
    python: str | None = None,
    enabled: bool = False,
    config_path: str | None = None,
) -> dict:
    """One OpenAI4S stdio MCP connector entry for an MHS endpoint.

    ``enabled`` defaults to False: the MHS integration is experimental and must
    be turned on in settings, so the generated connector row is listed but off.
    The row always carries the settings path as ``--config``; the projection
    then enforces ``enabled``/``allow_hardware`` from that document.  An
    explicitly enabled row built without an explicit config path (the demo and
    focused tests) also sets ``MHS_ENABLED=1`` in the child environment, the
    documented one-process override for "this caller explicitly enabled MHS";
    generated deployment rows always pass the path and never need the override.
    A source checkout runs ``launch/mhs.mcp`` (:func:`source_launcher`) and
    needs no ``env``; ``env.PYTHONPATH`` names the SDK source tree only when
    ``mhs`` comes from another source tree (:func:`connector_env`).
    """
    entry = {
        "id": connector_id(spec),
        "name": spec.label or spec.id,
        "command": connector_argv(spec, python=python, config_path=config_path),
        "transport": "stdio",
        "enabled": bool(enabled),
    }
    # The launcher finds the SDK itself; only `-m mhs.mcp` from a source tree needs PYTHONPATH.
    env = {} if source_launcher() else connector_env()
    if enabled and config_path is None:
        env["MHS_ENABLED"] = "1"
    if env:
        entry["env"] = env
    return entry


class UnsafeAgentSettings(ValueError):
    """The shared settings document would weaken every agent connector row (``MHS.HOST.CONFIG_REQUIRED``)."""

    code = "MHS.HOST.CONFIG_REQUIRED"


def refuse_unsafe_agent_rows(config: MHSConfig) -> None:
    """Refuse to write or enable agent connector rows while the settings document they pass to ``mhs.mcp``
    as ``--config`` sets ``operator_tools`` or ``allow_external_sessions``.

    On stock OpenAI4S (connector rows only, no patched host route) such a row would list ``mhs__reset`` and
    ``mhs__permit`` to the model, or let it name foreign sessions. The host operator route passes
    ``--operator-tools`` itself and never needs the setting.
    """
    if config.warnings:
        raise UnsafeAgentSettings(
            "MHS.HOST.CONFIG_REQUIRED: refusing to write or enable agent connector rows: "
            + "; ".join(config.warnings)
        )


def connector_entries(
    config: MHSConfig | None = None,
    *,
    python: str | None = None,
    endpoints: Iterable[EndpointSpec] | None = None,
    enabled: bool | None = None,
) -> list[dict]:
    """One connector entry per configured MHS endpoint."""
    effective = config if config is not None else MHSConfig.load()
    source = list(endpoints) if endpoints is not None else effective.endpoints
    target_enabled = bool(effective.enabled if enabled is None else enabled)
    policy_path = effective.config_path or str(_resolve_policy_path(None))
    entries = [
        connector_entry(
            spec, python=python, enabled=target_enabled, config_path=policy_path
        )
        for spec in source
    ]
    # A stored row is only a command line.  Remember which settings document
    # produced it so the real host route can resolve policy without guessing
    # when an in-memory config's ``--config`` path is not readable.
    connector_registry.register(
        effective,
        [entry["id"] for entry in entries],
        config_path=policy_path,
    )
    return entries


def connector_config(
    config: MHSConfig | None = None,
    *,
    python: str | None = None,
    endpoints: Iterable[EndpointSpec] | None = None,
    enabled: bool | None = None,
) -> dict:
    """The MCP connector document an operator can merge or persist into OpenAI4S.

    Rows are always listed — that is how the feature appears in settings — but
    ``enabled`` is false unless the experimental integration has been switched on.
    """
    effective = config if config is not None else MHSConfig.load()
    target_enabled = bool(effective.enabled if enabled is None else enabled)
    return {
        "connectors": connector_entries(
            effective, python=python, endpoints=endpoints, enabled=target_enabled
        ),
        "enabled": target_enabled,
        "experimental": True,
        "transport": "mcp",
        "note": (
            "OpenMHS endpoints are reached through the MCP projection: one stdio "
            "`mhs.mcp` server per endpoint. The integration is experimental and "
            "disabled until an operator enables it in settings."
        ),
        "settings_path": str(_settings_path(effective)),
    }


def _settings_path(config):
    from .config import resolve_config_path

    return resolve_config_path(None)


def mcp_server_config(entry: dict) -> dict:
    """Convert one generated entry to OpenAI4S's ``MCPManager`` config shape.

    ``MCPManager.list_tools/call_tool`` take ``(connector_id, config)`` where
    ``config`` is the stored connector row.  The row's command is a list, which
    ``MCPManager._argv`` appends ``args`` to, so this is already compatible.
    """
    return copy.deepcopy(entry)


__all__ = [
    "MCP_MODULE",
    "connector_argv",
    "UnsafeAgentSettings",
    "connector_config",
    "connector_entries",
    "refuse_unsafe_agent_rows",
    "connector_entry",
    "connector_env",
    "source_launcher",
    "connector_id",
    "endpoint_target",
    "mcp_server_config",
    "operator_argv",
]
