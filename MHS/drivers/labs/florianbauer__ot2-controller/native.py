"""Hardware backend: construct the repository's SSH feature implementation for one OT-2.

Used only with backend="hardware" and allow_hardware=True.  This package is model-authored and unreviewed, and it
is R2: the loader refuses the hardware backend until a human sets ``reviewed_by`` in driver.lock.json.  The
acceptance gate never imports this module or the upstream package.  The package is blocked (model review,
2026-11-05): the upstream has no stop for a running protocol.

Options of the backend (any other option is refused, so a misspelt key path never falls back to the default key):

``device_ip``
    Required.  The OT-2 address the upstream CLI takes with ``-o/--ot2-ip-address``
    (``ot2_controller/__main__.py:14``).
``pkey_path``
    Optional.  The SSH private key file; the upstream constructor uses its own
    ``~/.ssh/ot2_ssh_key`` default when this is omitted
    (``ot2_controller/feature_implementations/ot2controller_impl.py:16,34-37``).

The constructor loads the key, adds unknown host keys automatically (``AutoAddPolicy``) and opens the SSH
connection as ``root`` without a timeout argument (``ot2controller_impl.py:17,29-45``), so construction is
deployment I/O.  The upstream package is installed with ``pip install .`` (``setup.py:5-17``); the gate never
installs or imports it.
"""

from __future__ import annotations


def connect(device_ip: str, pkey_path: str | None = None):
    from ot2_controller.feature_implementations.ot2controller_impl import Ot2ControllerImpl

    return Ot2ControllerImpl(device_ip=device_ip, pkey_path=pkey_path)
