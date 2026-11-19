"""Hardware backend: opens the AutoProber GRBL CNC through the upstream wrapper.

Used only with ``backend="hardware"`` and ``allow_hardware=True``, and only after a human signs
``driver.lock.json`` ``reviewed_by``: this package is model-authored and R2, so the loader refuses its hardware
backend until then.  The acceptance gate never imports this module and never ran it.

Options of the factory: ``port`` and ``baud`` are handed to ``autoprober.cnc.CNC``.  When they are omitted the
upstream constructor keeps its own environment/default selection (``AUTOPROBER_CNC_PORT`` and
``AUTOPROBER_CNC_BAUD``, autoprober/cnc.py:49-53) and ``connect`` opens the serial line (autoprober/cnc.py:55-64).
The upstream class also waits for the controller after opening; this factory adds nothing to the transport.
"""


def connect(port=None, baud=None):
    from autoprober.cnc import CNC

    device = CNC(port=port, baud=baud)
    device.connect()
    return device
