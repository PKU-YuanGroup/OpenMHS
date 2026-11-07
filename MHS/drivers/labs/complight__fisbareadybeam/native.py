"""Hardware backend: opens a Fisba ReadyBeam module through the upstream class.

Used only with backend="hardware" and allow_hardware=True, which is an operator decision.  This package is
model-authored and unreviewed (driver.lock.json ``reviewed_by`` is null); nothing in it ever ran against an
instrument.

Options of the backend:

* ``port`` (default ``/dev/ttyUSB0``) and ``baud`` (default 57600), ``timeout`` (default 1 s) and ``address``
  (default 0): the keyword arguments of ``FisbaReadyBeam.__init__`` (FisbaReadyBeam/__init__.py:31-57).  The
  constructor opens the serial port itself and enables digital control with parameter 7000
  (FisbaReadyBeam/__init__.py:57, 60-75), so constructing the object is the connection;
* ``debug`` (default 0): the upstream print level.

This module imports the upstream package, which the acceptance gate never instals nor imports.
"""


def connect(port="/dev/ttyUSB0", *, baud=57600, timeout=1.0, address=0, debug=0):
    from FisbaReadyBeam import FisbaReadyBeam

    return FisbaReadyBeam(port=port, baud=baud, timeout=timeout, address=address, debug=debug)
