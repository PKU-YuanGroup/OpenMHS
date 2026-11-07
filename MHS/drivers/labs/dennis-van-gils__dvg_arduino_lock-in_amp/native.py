"""Hardware backend: opens a DvG Arduino lock-in amplifier through the upstream Alia serial class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored and
unreviewed, and it is R1: the loader refuses the hardware backend of an unreviewed model-written package only at R2
and R3, so this R1 package gets no such protection.  The driver's only stop is the native ``turn_off()`` (the ``off``
command); it is not an independent hardware stop.  The acceptance gate runs the fake backend and never imports this
module or the upstream package, and no hardware run was made.

Options are the Alia constructor's: ``name``, ``long_name``, ``connect_to_specific_ID``, ``baudrate``,
``read_timeout`` and ``write_timeout`` (Alia_protocol_serial.py:139-147).  The connection is found by the upstream
``auto_connect()`` port scan (DvG_Arduino_lockin_amp.py:383-385), and ``begin()`` reads the firmware constants and
turns the lock-in off (Alia_protocol_serial.py:168-185).  The read timeout is capped at 1 s so the e-stop's
``turn_off()`` wait is bounded.

The upstream repository is a collection of top-level modules with no packaging metadata, so the deployment must make
``Alia_protocol_serial`` importable (for example by putting the clone root on ``PYTHONPATH`` or running from it); this
module does not add the clone to ``sys.path``.
"""


def connect(**options):
    from Alia_protocol_serial import Alia

    options["read_timeout"] = min(float(options.get("read_timeout", 1.0)), 1.0)
    options.setdefault("write_timeout", 1.0)
    device = Alia(**options)
    device.auto_connect()
    if not device.is_alive:
        raise RuntimeError("Alia.auto_connect() found no lock-in amplifier")
    if not device.begin():
        raise RuntimeError("Alia.begin() failed")
    return device
