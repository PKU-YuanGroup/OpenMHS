"""Hardware backend: opens a Hantek 1008C through the upstream ``hantek1008.Hantek1008`` class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed, but it is R1: the loader refuses the hardware backend of an unreviewed model-written package only
at R2 and R3, so this note does not claim such a refusal for R1.  A human must review the package before hardware
use; the acceptance gate runs the fake backend and never imports this module or the ``hantek1008`` package.

The upstream constructor only stores the configuration (hantek1008.py:58-101); ``connect`` finds the USB device by
vendor id 0x0783 and product id 0x5725 and binds its endpoints (hantek1008.py:103-132), and ``init`` sends the
initialization sequence, measures the zero offsets and applies the configuration (hantek1008.py:268-400).  The
upstream application does the same three steps in ``csvexport.py``: construct, ``connect()``, ``init()``
(csvexport.py:195-215).  The factory passes every backend option through unchanged to the constructor:
``ns_per_div``, ``vertical_scale_factor``, ``active_channels``, ``correction_data``,
``zero_offset_shift_compensation_channel``, ``zero_offset_shift_compensation_function`` and
``zero_offset_shift_compensation_function_time_offset_sec`` (hantek1008.py:689-695).
"""


def connect(**options):
    from hantek1008 import Hantek1008

    device = Hantek1008(**options)
    device.connect()
    device.init()
    return device
