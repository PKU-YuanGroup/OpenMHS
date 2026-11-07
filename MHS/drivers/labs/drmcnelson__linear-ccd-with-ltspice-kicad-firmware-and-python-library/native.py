"""Hardware backend: opens a TCD1304 controller through the upstream serial class.

Used only with ``backend="hardware"`` and ``allow_hardware=True`` (an operator decision).  This package is
model-authored and unreviewed, and nothing here was run: the acceptance gate uses the fake backend and never imports
this module or the upstream package.

``portspec`` (or the option ``port``) is the serial device the upstream constructor opens with
``serial.Serial(portspec, ...)`` (TCD1304Rev2_Python/TCD1304Rev2Controller.py:521).  The clone must already be
importable: put the clone root and its ``TCD1304Rev2_Python`` directory on ``PYTHONPATH``, because the controller
uses bare imports for its sibling modules (``Accumulators``, ``GUIWindow``, ``GraphicsWindow``, lines 61-84) and
imports pyserial, numpy, scipy and matplotlib.  The remaining options go to the upstream constructor.

The constructor starts a reader process and, with ``graphics=False``, the upstream reader still dereferences
``self.GraphicsWindow.queue`` when it records a frame (line 901), which is a known upstream limitation of that mode;
a real hardware run has not been tried from this package.
"""


def connect(portspec=None, **options):
    """Open the upstream controller and return the LCCDCONTROLLER object."""
    if portspec is None:
        portspec = options.pop("port", None)
    if not portspec:
        raise ValueError("connect() needs the serial port of the device (portspec=...)")
    from TCD1304Rev2_Python.TCD1304Rev2Controller import LCCDCONTROLLER

    return LCCDCONTROLLER(portspec, graphics=False, monitor=False, gui=False, **options)
