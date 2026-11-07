"""Register the MHS MCP connectors in OpenAI4S's connector store.

OpenAI4S persists MCP connectors as rows (``connectors`` table) and its Web
settings surface toggles them.  The MHS integration is therefore an ordinary MCP
connector: one row per endpoint, ``enabled=false`` by default, turned on by an
explicit operator action.  This module keeps that registration best-effort: it
must never make the CLI or the SDK depend on OpenAI4S being importable.
"""

from __future__ import annotations

import os
from typing import Any

from .config import MHSConfig
from .mcpconfig import connector_entries, refuse_unsafe_agent_rows

#: Environment escape hatch for tests/headless CI: never touch the host DB.
SKIP_ENV = "MHS_SKIP_OPENAI4S_SYNC"

#: Description shown in OpenAI4S's connector settings.
DESCRIPTION = (
    "OpenMHS endpoint via `mhs.mcp` (experimental; disabled by default — enable "
    "the MHS integration in settings to use it)."
)


def _store(config: MHSConfig):
    if os.environ.get(SKIP_ENV):
        return None
    if not config.sync_openai4s:
        return None
    try:
        from openai4s.config import get_config  # type: ignore
        from openai4s.store import get_store  # type: ignore
    except Exception:  # noqa: BLE001 - OpenAI4S absent is a supported mode
        return None
    try:
        return get_store(get_config().db_path)
    except Exception:  # noqa: BLE001
        return None


def sync_connectors(
    config: MHSConfig | None = None, *, enabled: bool | None = None
) -> list[dict[str, Any]] | None:
    """Upsert one connector row per configured MHS endpoint.

    ``enabled`` defaults to the integration switch (``config.enabled``): off by
    default, on only after the operator enables the feature.  Returns the rows
    it wrote, or ``None`` when the host store is unavailable.
    """
    effective = config if config is not None else MHSConfig.load()
    target_enabled = bool(effective.enabled if enabled is None else enabled)
    if target_enabled:
        refuse_unsafe_agent_rows(effective)
    store = _store(effective)
    if store is None:
        return None
    saved: list[dict[str, Any]] = []
    for entry in connector_entries(effective):
        try:
            row = store.upsert_connector(
                connector_id=entry["id"],
                name=entry.get("name") or entry["id"],
                command=entry["command"],
                description=DESCRIPTION,
                args=entry.get("args") or [],
                env=entry.get("env") or {},
                enabled=target_enabled,
            )
        except Exception:  # noqa: BLE001 - a broken host DB is not our failure
            return saved or None
        saved.append(
            {
                "connector_id": str(row.get("connector_id") or entry["id"]),
                "enabled": bool(row.get("enabled", target_enabled)),
            }
        )
    return saved


def set_connectors_enabled(
    enabled: bool, config: MHSConfig | None = None
) -> list[dict[str, Any]] | None:
    """Flip every MHS connector row on or off without rewriting its command."""
    effective = config if config is not None else MHSConfig.load()
    if enabled:
        refuse_unsafe_agent_rows(effective)
    store = _store(effective)
    if store is None:
        return None
    rows: list[dict[str, Any]] = []
    for entry in connector_entries(effective):
        connector_id = entry["id"]
        try:
            store.patch_connector(connector_id, enabled=bool(enabled))
        except Exception:  # noqa: BLE001
            return rows or None
        rows.append({"connector_id": connector_id, "enabled": bool(enabled)})
    return rows


def list_connectors(config: MHSConfig | None = None) -> list[dict[str, Any]] | None:
    """List the MHS connector rows currently registered in OpenAI4S."""
    effective = config if config is not None else MHSConfig.load()
    store = _store(effective)
    if store is None:
        return None
    ids = {entry["id"] for entry in connector_entries(effective)}
    try:
        rows = store.list_connectors()
    except Exception:  # noqa: BLE001
        return None
    return [
        {
            "connector_id": str(row.get("connector_id")),
            "enabled": bool(row.get("enabled")),
            "command": row.get("command"),
        }
        for row in rows
        if str(row.get("connector_id")) in ids
    ]


__all__ = [
    "DESCRIPTION",
    "SKIP_ENV",
    "list_connectors",
    "set_connectors_enabled",
    "sync_connectors",
]
