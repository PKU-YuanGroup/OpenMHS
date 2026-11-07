"""Hardware backend: opens a Tektronix DPO70000 through the upstream instrumentkit transport.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  The acceptance gate runs the fake
backend and never imports this module or the upstream package.  Nothing here was run and this package is
model-authored and unreviewed.  The driver is R0, so the loader's rule that refuses the hardware backend of an
unreviewed model-written package at R2/R3 does not apply to it; no hardware was attached for this package.

``uri`` is an instrumentkit URI.  ``open_from_uri`` dispatches ``tcpip://host:port`` to ``open_tcpip`` and
``serial:///dev/ttyS0?baud=...`` to ``open_serial`` (src/instruments/abstract_instruments/instrument.py:339-431).
"""


def connect(uri):
    from instruments.tektronix import TekDPO70000

    return TekDPO70000.open_from_uri(uri)
