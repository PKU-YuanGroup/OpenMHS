"""Hardware backend of the pyagilis driver: open the upstream AGUC2 serial controller.

Used only with ``backend="hardware"`` and ``allow_hardware=True`` (an operator decision).  This package is
model-authored and unreviewed; because it declares R1, the loader does not itself refuse the hardware backend (it
does so at R2 and R3 only), so a human must review driver.lock.json before any hardware use.  The acceptance gate
runs the fake backend and never imports this module or the pyagilis package.

``port`` is the serial device of the controller; the remaining options (``axis1alias``, ``axis2alias``, ``stepAmp1``,
``stepAmp2``, ``testRead``) are the arguments of ``AGUC2.__init__`` (pyagilis/controller.py:21).  The upstream
``AGUC2.stop`` calls ``Thread.isAlive`` (pyagilis/controller.py:100), which Python 3.9 removed, so this factory
returns a thin controller wrapper whose ``stop`` sends ``ST`` to each axis directly (pyagilis/channel.py:45-47);
every other call is delegated to the upstream object.
"""


class _Controller:
    """The subset of AGUC2 the driver uses, with a stop that does not touch the removed isAlive API."""

    def __init__(self, controller):
        self._controller = controller

    def __getattr__(self, name):
        return getattr(self._controller, name)

    def stop(self):
        for alias in self._controller.aliases:
            self._controller.axis[alias].stop()


def connect(port=None, **options):
    """Open the controller on ``port`` and return the upstream object behind the stop wrapper."""
    from pyagilis.controller import AGUC2

    if not port:
        raise ValueError("the pyagilis hardware backend needs the serial port option 'port'")
    controller = AGUC2(port, **options)
    if controller.port.amInull():
        raise RuntimeError(f"the Agilis controller on {port!r} did not open")
    return _Controller(controller)
