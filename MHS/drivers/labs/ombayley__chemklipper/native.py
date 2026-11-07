"""Hardware backend: opens the ChemKlipper gantry through a Moonraker WebSocket.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed, and it is R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json (the loader does this at R2 and R3 only).  The acceptance gate runs the fake backend and never
imports this module or the chem_klipper package.

Options of the backend: ``host`` (required) is the Moonraker host and ``port`` (default 7125) its port; ``name``
names the upstream Gantry object and ``request_timeout`` is the per-request timeout in seconds of
``MoonrakerConfig`` (src/chem_klipper/config.py:14-23).  The client opens ``ws://<host>:<port>/websocket``
(src/chem_klipper/moonraker.py:45-47) and the upstream Gantry validates the connection
(src/chem_klipper/devices/moonraker_device.py:24-29).
"""


async def connect(host, port=7125, request_timeout=10.0, name="Gantry"):
    from chem_klipper.config import MoonrakerConfig
    from chem_klipper.devices.gantry import Gantry
    from chem_klipper.moonraker import MoonrakerClient

    config = MoonrakerConfig(host=host, port=port, request_timeout=request_timeout)
    gantry = Gantry(client=MoonrakerClient(config), name=name)
    await gantry.connect()
    return gantry
