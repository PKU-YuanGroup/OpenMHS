"""Hardware factory for the PyLabRobot Incubator front end (never run by the acceptance gate).

The factory is deployment code, not an upstream fact.  It requires the deployed deck geometry, racks and transport
from the operator: this package does not invent a plate carrier, a serial port or a temperature range.  The upstream
Incubator exposes no heater-off command and ``Cytomat.set_temperature`` is not implemented (cytomat.py:370-371).
Model review (2026-11-05): the author's required ``safe_stop`` relay option, an invented stop, was removed.

PyLabRobot is imported only inside ``connect`` so the package module and the gate can load without the clone
installed.  The hardware backend is refused by the loader for this unreviewed model-authored R2 package before this
factory runs.
"""

from __future__ import annotations

from typing import Any


def connect(**options: Any) -> Any:
    """Build the PyLabRobot Incubator front end from deployment options.

    Required options: ``size_x``, ``size_y``, ``size_z``, ``racks`` (a non-empty list of PlateCarrier objects) and
    ``loading_tray_location`` ([x, y, z] in mm).  Provide ``backend`` (an IncubatorBackend) or ``cytomat_model`` and
    ``port`` to construct the clone's Cytomat serial backend.
    """

    from pylabrobot.incubators.incubator import Incubator
    from pylabrobot.resources import Coordinate

    backend = options.get("backend")
    if backend is None:
        from pylabrobot.incubators.cytomat.cytomat import Cytomat

        model = options.get("cytomat_model")
        port = options.get("port")
        if model is None or not port:
            raise RuntimeError("connect needs options['backend'], or options['cytomat_model'] and options['port']")
        backend = Cytomat(model=model, port=port)

    racks = options.get("racks")
    if not isinstance(racks, (list, tuple)) or not racks:
        raise RuntimeError("connect requires a non-empty options['racks'] list of PlateCarrier objects")
    location = options.get("loading_tray_location")
    if not isinstance(location, (list, tuple)) or len(location) != 3:
        raise RuntimeError("connect requires options['loading_tray_location'] = [x, y, z] in mm")
    for key in ("size_x", "size_y", "size_z"):
        if key not in options:
            raise RuntimeError(f"connect requires options[{key!r}] from the deployed deck")

    return Incubator(
        backend=backend,
        name=str(options.get("name") or "incubator"),
        size_x=options["size_x"],
        size_y=options["size_y"],
        size_z=options["size_z"],
        racks=list(racks),
        loading_tray_location=Coordinate(*location),
        category=options.get("category"),
        model=options.get("model"),
    )
