"""Hardware backend: opens a Lake Shore Model 218 through the upstream DeviceConnection.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed, and it is R1: the loader does not refuse an R1 hardware backend for a model-authored package, so
the hardware backend stays an operator decision; no hardware or network access was used to write or check this
package.  The acceptance gate runs the fake backend and never imports this module or the clone.

The clone is a soft-IOC device library shipped as the top-level package ``devices`` (there is no setup.py or
``__init__.py``; README-less repository, but the modules import one another as ``devices.*``).  A deployment must
put the clone root on ``PYTHONPATH`` so ``from devices.ls218 import DeviceConnection`` resolves, or mount the clone
as the ``devices`` package.  The card's install block only installs the requirements (PyYAML, softioc, aioca,
numpy, screenutils and pyModbusTCP), not the device package.

``DeviceConnection(host, port, timeout)`` constructs a ``TelnetConnection``, which opens ``telnetlib.Telnet(host,
port, timeout)`` in its constructor and stores it as ``self.tn`` (devices/ls218.py:25-26,
devices/telnet_base.py:30-36).  The upstream settings carry ``ip`` as a string, ``port: '23'`` as a string and
``timeout: 2`` (settings.yaml:9-15); this factory converts the port and timeout to the numeric types telnetlib
needs.  The constructor catches connection errors and leaves no ``tn`` attribute, so the factory raises instead of
returning a half-open object.
"""


def connect(host, port, timeout=2.0, **_options):
    """Open the upstream DeviceConnection and return it."""
    from devices.ls218 import DeviceConnection

    device = DeviceConnection(str(host), int(port), float(timeout))
    if getattr(device, "tn", None) is None:
        raise OSError(f"cannot open the Lake Shore 218 connection to {host}:{port}")
    return device
