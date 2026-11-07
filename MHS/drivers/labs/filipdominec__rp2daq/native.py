"""Hardware backend: opens one RP2DAQ-firmware board through the upstream rp2daq:Rp2daq class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed, and it is R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json (the loader does this at R2 and R3 only; an R0 or R1 package must not claim it).  The acceptance
gate runs the fake backend and never imports this module or the upstream package.

The upstream module needs the clone directory on PYTHONPATH: it imports ``c_code_parser`` and parses ``rp2daq.c``
and ``include/*.c`` beside the module (rp2daq.py:32, c_code_parser.py:198-202).  It also imports pyserial and
tkinter (rp2daq.py:22-29).  ``required_device_id`` selects the board by its unique USB serial id; the upstream
matches VID:PID 2E8A:000A or 2E8A:0009 (rp2daq.py:246-249).  No installation command is declared because the
upstream has no packaging metadata.
"""


def connect(required_device_id="", verbose=False, **options):
    if options:
        raise TypeError(f"unsupported rp2daq options: {sorted(options)}")
    from rp2daq import Rp2daq

    return Rp2daq(required_device_id=required_device_id, verbose=verbose)
