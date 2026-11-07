"""Hardware backend: opens the Pico serial link through the upstream ``host_nonwireless:Talker`` class.

Used only with backend="hardware" and allow_hardware=True after a human review.  This package is model-authored and
unreviewed; it is R1, so the loader's refusal of model-written hardware packages at R2 and R3 does NOT apply here.
No hardware was attached or run while this package was authored, and the acceptance gate never imports this module
or the upstream package (it checks the fake backend only).

The backend options are the upstream constructor's: ``com`` (the serial port device, required here) and optional
``timeout`` (seconds).  The upstream class opens the port at 115200 baud (src/extra/nonwireless/lib/host_nonwireless.py:9-10).
"""


def connect(com, **options):
    from extra.nonwireless.lib.host_nonwireless import Talker

    return Talker(com=com, **options)
