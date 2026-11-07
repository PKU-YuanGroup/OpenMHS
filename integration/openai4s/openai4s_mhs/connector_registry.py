"""Process-local resolution of an OpenAI4S connector row to its MHS settings.

The stock host route receives a connector row (``connector_id``, ``command``,
``env``), not an ``MHSConfig``.  The durable link is the row's
``--config <settings.json>`` argument, which the generated row always carries.
This registry is a fallback for the one supported case where that path is not
readable from the host process -- an explicitly constructed ``MHSConfig`` whose
connector row was generated in memory (the probe/test path) -- so the route does
not have to guess or silently fall back to the ungoverned transport.

It is deliberately process-local and advisory: the file named by ``--config``
wins whenever it exists, because that is the operator's durable policy.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Iterable

from .config import MHSConfig

_LOCK = threading.Lock()
_BY_CONNECTOR: dict[str, MHSConfig] = {}
_BY_PATH: dict[str, MHSConfig] = {}


def register(
    config: MHSConfig,
    connector_ids: Iterable[str],
    *,
    config_path: str | os.PathLike[str] | None = None,
) -> None:
    path = str(config_path or config.config_path or "")
    normalised = str(Path(path).expanduser()) if path else ""
    with _LOCK:
        if normalised:
            _BY_PATH[normalised] = config
        for connector_id in connector_ids:
            _BY_CONNECTOR[str(connector_id)] = config


def resolve(connector_id: str, config_path: str | None = None) -> MHSConfig | None:
    normalised = str(Path(config_path).expanduser()) if config_path else ""
    with _LOCK:
        if normalised and normalised in _BY_PATH:
            return _BY_PATH[normalised]
        return _BY_CONNECTOR.get(str(connector_id))


def clear() -> None:
    """Test hook: forget process-local registrations."""
    with _LOCK:
        _BY_CONNECTOR.clear()
        _BY_PATH.clear()


__all__ = ["clear", "register", "resolve"]
