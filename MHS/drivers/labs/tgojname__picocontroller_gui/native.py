"""Hardware backend: open a Newport 8742 through the upstream controller class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  The acceptance gate and every
test in this package use the fake backend; this module and the upstream clone were never imported or run here.
The upstream is a set of scripts, not an installed package, so the hardware environment must make
``picomotor_terminal_based`` importable (the clone root on PYTHONPATH, or a copy installed by the operator).

Options: ``idProduct`` and ``idVendor`` are the controller's USB ids, as hexadecimal strings or integers; both are
required because a different 8742 unit may use other ids than the values the clone's UI offers.  The upstream
``Controller`` connects in its constructor (picomotor_terminal_based.py:72-83).
"""


def connect(idProduct, idVendor):
    from picomotor_terminal_based import Controller

    return Controller(_usb_id(idProduct), _usb_id(idVendor))


def _usb_id(value):
    if isinstance(value, int):
        return value
    return int(str(value).strip(), 16)
