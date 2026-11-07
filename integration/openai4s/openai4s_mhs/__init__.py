"""OpenAI4S x OpenMHS reference host — MCP-first, experimental, disabled by default.

OpenMHS is an independent open-source project, not affiliated with or endorsed
by Anthropic.

The integration path is **MCP**:

    OpenAI4S agent
        └── MCPManager (stock OpenAI4S; the governed route needs openai4s-core.patch)
              └── stdio MCP server  `python -m mhs.mcp --endpoint …`
                    └── MHS endpoint (device / simulator / replay)

One connector row per MHS endpoint; OpenAI4S discovers the projected tools
(``mhs__<device>__<capability>`` plus discovery/safety/evidence tools) and every
call goes through MHS's own server — sessions, safety envelope, permits,
receipts and the evidence chain included.

The feature is **experimental and disabled by default**.  The generated
connector rows carry ``enabled: false`` until an operator turns the feature on in
settings (:func:`enable`, ``MHS_ENABLED=1`` for one process, or
``"enabled": true`` in ``~/.openai4s/mhs.json``).  While disabled no MHS tool is
reachable and no endpoint connection is opened by the agent.

A native-tool overlay (:func:`install`) exists as a *developer preview* for
debugging the same host API outside MCP; it is not the integration path and is
gated by the same switch.

The generated connector always carries ``--config <settings path>`` so
``mhs.mcp`` enforces the same ``enabled``/``allow_hardware`` policy
(HOST-001), and never ``--operator-tools``: ``mhs__reset``/``mhs__permit`` are
for the host operator route (:mod:`openai4s_mhs.operator_route`) only.  The
governed path is wired into the host route by ``openai4s-core.patch`` (two
OpenAI4S core files, :mod:`openai4s_mhs.corepatch`): for an MHS connector row,
``openai4s/host/mcp.py`` calls ``openai4s_mhs.hostroute`` from
``MCPService.call``, so an ordinary ``CallMCPTool`` capability call runs
through the durable journal and host ledger, and the named
``mhs_emergency_stop`` action plus the device-bound ``mcp_call`` e-stop
exemption are on the real ``HostDispatcher`` route.  The same capabilities
remain available as direct entry points (no core patch needed):

* :func:`emergency_stop` -- trusted, device-bound software e-stop that bypasses
  the ordinary tool-approval prompt but not connector authorization
  (HOST-002);
* :func:`invoke` / :func:`reconcile` -- durable command-id journal, pre-send vs
  post-send distinction, ``MHS.OUTCOME.UNKNOWN`` and idempotent replay
  (HOST-003);
* :class:`HostLedger` / :func:`export_package` / :func:`verify_package` -- the
  append-only host chain and portable host+endpoint evidence package
  (HOST-004);
* :class:`OperatorRoute` -- the operator's reset and permits over a dedicated
  ``mhs.mcp --operator-tools`` connection, audited in the host ledger.

Non-MHS connectors and MHS discovery/read tools keep the ordinary
approval-gated transport path unchanged.

CLI::

    python3 -m openai4s_mhs status            # experimental MCP integration, off by default
    python3 -m openai4s_mhs enable            # operator enables it in settings
    python3 -m openai4s_mhs mcp-config --json # connector rows for OpenAI4S
    python3 -m openai4s_mhs disable
    python3 -m openai4s_mhs core-patch check  # the OpenAI4S core patch applies at its base
"""

from __future__ import annotations

#: Tracks the OpenMHS SDK release line (``mhs._ids.SDK_VERSION``).
__version__ = "0.9.0.dev0"

from .config import (  # noqa: E402,F401
    DEFAULT_CONFIG_PATH,
    EndpointSpec,
    MHSConfig,
    is_enabled,
    read_raw_config,
    resolve_config_path,
    set_enabled,
)
from .emergency import EmergencyStopError, emergency_stop  # noqa: E402,F401
from .host import MHSHost  # noqa: E402,F401
from .host_evidence import (  # noqa: E402,F401
    HostLedger,
    HostLedgerError,
    export_package,
    verify_package,
)
from .mcp_invoke import (  # noqa: E402,F401
    CommandJournal,
    MCPConnector,
    MCPInvokeError,
    MCPOutcomeUnknown,
    invoke,
    invoke_via,
    reconcile,
)
from .operator_route import OperatorRoute, OperatorRouteError  # noqa: E402,F401


def install(config: MHSConfig | None = None) -> bool:
    """Developer preview: register the native MHS tools **only when enabled**.

    Not the OpenAI4S integration path — use the MCP connector
    (:func:`mcp_config` / :func:`sync_connectors`) instead.  With the switch off
    this registers nothing and returns False.
    """
    effective = config if config is not None else MHSConfig.load()
    if not effective.enabled:
        _deactivate_if_installed()
        return False
    from .tools import install as _install

    return _install(effective)


def _deactivate_if_installed() -> bool:
    """Remove an in-process native surface without requiring OpenAI4S to import."""
    try:
        from .tools import deactivate
    except Exception:  # noqa: BLE001 - OpenAI4S absent: nothing to deactivate
        return True
    try:
        return bool(deactivate())
    except Exception:  # noqa: BLE001
        return False


def install_if_enabled(config: MHSConfig | None = None) -> bool:
    """Same as :func:`install`; reads the persisted setting when no config given."""
    return install(config)


def mcp_config(config: MHSConfig | None = None, *, python: str | None = None) -> dict:
    """The MCP connector document for the configured endpoints (one row each)."""
    from .mcpconfig import connector_config

    return connector_config(config, python=python)


def sync_connectors(
    config: MHSConfig | None = None, *, enabled: bool | None = None
) -> list[dict] | None:
    """Register/update the MHS connector rows in OpenAI4S's connector store.

    Best-effort and idempotent: returns ``None`` when OpenAI4S (or its store) is
    not importable, so the same code runs in CI and from a plain CLI.
    """
    from .mcp_register import sync_connectors as _sync

    return _sync(config, enabled=enabled)


def enable(path: str | None = None) -> dict:
    """Operator action: enable the experimental MCP integration in settings.

    Refused (``MHS.HOST.CONFIG_REQUIRED``, nothing changed) while the settings document sets
    ``operator_tools`` or ``allow_external_sessions``: every agent connector row passes it to ``mhs.mcp``.
    """
    from .mcpconfig import refuse_unsafe_agent_rows

    refuse_unsafe_agent_rows(MHSConfig.load(path))
    document = set_enabled(True, path)
    config = MHSConfig.load(path)
    config.enabled = True
    connectors = sync_connectors(config, enabled=True)
    return {
        **config.to_settings(),
        "settings_path": str(resolve_config_path(path)),
        "connectors": connectors,
        "next": "restart OpenAI4S (or reload its connector settings) to activate the MCP tools",
    }


def disable(path: str | None = None) -> dict:
    """Operator action: disable the integration and the MHS connector rows."""
    document = set_enabled(False, path)
    _deactivate_if_installed()
    config = MHSConfig.load(path)
    config.enabled = False
    connectors = sync_connectors(config, enabled=False)
    return {
        **config.to_settings(),
        "settings_path": str(resolve_config_path(path)),
        "connectors": connectors,
    }


def status(path: str | None = None) -> dict:
    """Report the experimental switch, settings path and registered connectors."""
    from .mcp_register import list_connectors

    config = MHSConfig.load(path)
    return {
        **config.to_settings(),
        "settings_path": str(resolve_config_path(path)),
        "settings_present": resolve_config_path(path).exists(),
        "connectors": list_connectors(config),
        "connector_document": mcp_config(config),
    }


__all__ = [
    "CommandJournal",
    "DEFAULT_CONFIG_PATH",
    "EmergencyStopError",
    "EndpointSpec",
    "HostLedger",
    "HostLedgerError",
    "MCPConnector",
    "MCPInvokeError",
    "MCPOutcomeUnknown",
    "MHSConfig",
    "MHSHost",
    "OperatorRoute",
    "OperatorRouteError",
    "__version__",
    "disable",
    "emergency_stop",
    "enable",
    "export_package",
    "install",
    "install_if_enabled",
    "invoke",
    "invoke_via",
    "is_enabled",
    "mcp_config",
    "read_raw_config",
    "reconcile",
    "resolve_config_path",
    "set_enabled",
    "status",
    "sync_connectors",
    "verify_package",
]
