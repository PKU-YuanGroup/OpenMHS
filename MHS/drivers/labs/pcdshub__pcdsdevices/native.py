"""Hardware backend of the TPR trigger driver: the upstream ophyd Device over EPICS Channel Access.

The gate never imports this module.  ``connect`` runs only when an operator loads the hardware backend
(``mhs.adapter.load_driver(..., backend="hardware", allow_hardware=True, ...)``); it is then the only code that
imports pcdsdevices, and through it ophyd and pyepics.

The operator supplies the TPR PV prefix and the channel number; the upstream class formats ``:CHnn_`` and ``:TRGnn_``
from the channel and selects ``SYS0_`` for LCLS1 or ``SYS2_`` for LCLS2 (``pcdsdevices/tpr.py:137-152``).  The channel
is documented as 0 through 11 (``pcdsdevices/tpr.py:71-72``).  There is no default prefix here: a wrong or empty prefix
would connect to nothing or to another device, so the factory refuses an empty one.  After construction it waits for
the Device's Signals once, for at most ``connection_timeout_s`` seconds.

Nothing here was run: the package has never connected to an IOC, and the package is model-authored and unreviewed.
"""


def connect(*, prefix, channel, timing_mode="LCLS2", name="tpr", connection_timeout_s=5.0):
    if not isinstance(prefix, str) or not prefix.strip():
        raise ValueError("prefix must be the non-empty EPICS PV prefix of the TPR")
    if isinstance(channel, bool) or not isinstance(channel, int) or not 0 <= channel <= 11:
        raise ValueError("channel must be an integer from 0 through 11 (pcdsdevices/tpr.py:71-72)")
    if timing_mode not in ("LCLS1", "LCLS2"):
        raise ValueError("timing_mode must be 'LCLS1' or 'LCLS2' (pcdsdevices/tpr.py:19-21)")
    if not isinstance(name, str) or not name.isidentifier():
        raise ValueError("name must be a Python identifier (it names the ophyd Device and its Signals)")
    if (isinstance(connection_timeout_s, bool) or not isinstance(connection_timeout_s, (int, float))
            or not 0 < connection_timeout_s <= 60):
        raise ValueError("connection_timeout_s must be a number of seconds in (0, 60]")
    from pcdsdevices.tpr import TprTrigger

    device = TprTrigger(prefix=prefix, channel=channel, timing_mode=timing_mode, name=name)
    device.wait_for_connection(timeout=connection_timeout_s)
    return device
