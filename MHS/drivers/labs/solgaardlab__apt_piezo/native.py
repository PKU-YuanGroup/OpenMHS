"""Hardware backend: opens a Thorlabs APT controller and returns one piezo Module.

Used only with backend="hardware" and allow_hardware=True (an operator decision).
This package is model-authored and unreviewed; the hardware path has never been
run. The acceptance gate runs the fake backend and never imports this module or
the upstream clone.

The clone is a set of top-level modules, not an installable package: ``apt.py``
imports ``interface`` and ``protocol`` by absolute name (``apt.py:1-3``), and
``interface/controller.py`` imports ``pyftdi`` (``interface/controller.py:1``).
The operator makes the clone root importable and installs pyftdi, then calls
``connect(bay=N, ...)``: the upstream ``APT`` opens the FTDI device, scans the
bays (``apt.py:12-21``) and the function returns the Module of the requested
1-based bay.

A Module does not own the APT lifecycle, and the clone's ``APT.disconnect()``
(``apt.py:23-25``) is not reachable from it, so this factory does not register a
disconnect hook. The driver has no teardown, so nothing in this package calls
``APT.disconnect()``; the acceptance gate never imports this module.
"""


def connect(bay=1, **_options):
    from apt import APT

    controller = APT()
    name = f"module{int(bay)}"
    module = controller.modules.get(name)
    if module is None:
        raise RuntimeError(f"APT found no used bay {name!r}; used bays: {sorted(controller.modules)}")
    return module
