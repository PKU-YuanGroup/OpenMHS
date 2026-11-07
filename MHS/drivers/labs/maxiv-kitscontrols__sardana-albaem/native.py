"""Hardware backend: opens an ALBA EM2 through the upstream Em2 SCPI/ZMQ client.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored and
unreviewed, and its risk class is R1: the loader refuses the hardware backend of a model-authored package only at R2
and R3, so this package makes no claim that the loader protects an R1 hardware run.  The acceptance gate runs the fake
backend and never imports this module or the sardana_albaem package; no hardware was attached here.

``Em2(host, port, zmq_port)`` creates the SCPI TCP socket and the ZMQ receiver (sardana_albaem/ctrl/em2.py:128-132);
``Em2.open()`` opens the socket (sardana_albaem/ctrl/em2.py:170-171).  The port defaults are the upstream constants
SCPI_CONTROL_PORT and ZMQ_STREAMING_PORT (sardana_albaem/ctrl/em2.py:30-31).
"""


def connect(host, port=None, zmq_port=None):
    from sardana_albaem.ctrl.em2 import SCPI_CONTROL_PORT, ZMQ_STREAMING_PORT, Em2

    if port is None:
        port = SCPI_CONTROL_PORT
    if zmq_port is None:
        zmq_port = ZMQ_STREAMING_PORT
    device = Em2(host, port, zmq_port)
    device.open()
    return device
