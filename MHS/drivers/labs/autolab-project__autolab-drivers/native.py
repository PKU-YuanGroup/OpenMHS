"""Hardware backend: opens an Anritsu MS2830A through pyvisa and the upstream Driver_VISA class.

Used only with backend="hardware" and allow_hardware=True, an operator decision.  This package is model-authored and
unreviewed, and its risk is R1: the loader of this SDK holds back the hardware backend of an unreviewed
model-written package only at R2 and R3, so nothing here is protected by a review gate -- do not enable this backend
without a person deciding to.  The acceptance gate runs the fake backend and never imports this module, pyvisa or
the upstream package.

The upstream Driver_VISA opens its own pyvisa ResourceManager and VISA resource in ``__init__``
(anritsu_MS2830A/anritsu_MS2830A.py:138-146), so the address below is passed to that constructor unchanged.  The
constructor's remaining keyword arguments are accepted and ignored by the upstream class.

Options of the backend: ``address`` (required) is a VISA resource string such as ``GPIB0::1::INSTR`` or
``TCPIP0::192.168.0.10::inst0::INSTR``.
"""


def connect(address, **options):
    from anritsu_MS2830A.anritsu_MS2830A import Driver_VISA

    return Driver_VISA(address, **options)
