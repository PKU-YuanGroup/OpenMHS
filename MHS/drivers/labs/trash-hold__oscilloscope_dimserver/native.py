"""Hardware backend: opens a Tektronix TDS3054C through the upstream class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This module is
never imported by the acceptance gate, and no hardware run was performed.  The package is R1 and
model-authored; the loader refuses the hardware backend of an unreviewed model-written package at
R2 and R3 only, so at R1 this module is not blocked by the loader and the operator owns the
decision to use it.

The upstream class takes a connection-parameters dict with ``ip`` and ``port`` and opens a TCP
socket to the scope's HTTP server for each command (TDS3054C.py:90-97, 100-111).  Both options
are required here: the clone names no default address or port for a scope, and a default copied
from the exemplar or the profile template would not describe this device.
"""


def connect(ip, port):
    from zmq_server.drivers.TDS3054C import TDS3054C

    return TDS3054C({"ip": ip, "port": port})
