"""Hardware backend: opens a ServoControllerStandalone on the SCS servo bus.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored and
unreviewed, and it is R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json.  The acceptance gate runs the fake backend and never imports this module or the upstream module;
nothing here ran on an arm.

Options of the backend:

* ``port_name`` (required): the serial port of the USB-to-serial adapter on the servo bus, for example ``COM12`` on
  Windows or ``/dev/ttyUSB0`` on Linux.  The upstream constructor defaults to COM4 (sources/servo_control_standalone.py
  :289), but a default port is not a statement about this bench, so the operator must name it;
* ``baudrate`` (default 1,000,000), ``timeout`` (default 0.1 s), ``debug`` (default False): passed to the upstream
  constructor, whose defaults are those values (sources/servo_control_standalone.py:289);
* ``upstream_root``: the clone root that contains ``sources/servo_control_standalone.py``.  The default is the
  read-only clone of this task card (robots/itheima1/mcp_robot relative to the package); set it when the clone lives
  elsewhere.
"""

import importlib.util
from pathlib import Path


def _upstream_module(upstream_root=None):
    path = None if upstream_root is None else Path(upstream_root) / "sources" / "servo_control_standalone.py"
    if path is None:
        path = Path(__file__).resolve().parents[4] / "robots" / "itheima1" / "mcp_robot" / "sources" \
            / "servo_control_standalone.py"
    if not path.is_file():
        if upstream_root is not None:
            raise RuntimeError(f"upstream_root {upstream_root!r} does not contain sources/servo_control_standalone.py")
        raise RuntimeError(f"the upstream controller module is not at {path}; pass upstream_root")
    spec = importlib.util.spec_from_file_location("servo_control_standalone", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"the upstream controller module at {path} cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def connect(port_name=None, baudrate=1000000, timeout=0.1, debug=False, upstream_root=None):
    if not port_name:
        raise RuntimeError("port_name is required: name the serial port of the servo bus")
    controller = _upstream_module(upstream_root).ServoControllerStandalone(
        port_name=port_name, baudrate=baudrate, timeout=timeout, debug=debug)
    if not controller.is_open:
        raise RuntimeError(f"the serial port {port_name!r} could not be opened at {baudrate} baud")
    return controller
