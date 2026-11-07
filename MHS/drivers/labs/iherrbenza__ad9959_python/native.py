"""Hardware backend: open the upstream AD9959 DDS object for an ESP32 reachable over TCP.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed and is R1; the loader does not add the R2/R3 review gate to it, so the operator must decide before
using real hardware.  The acceptance gate runs the fake backend and never imports this module or the upstream
package.

The upstream clone is not an installed Python package.  Put the pinned clone root (the directory that contains
``DDS_ESP32_lab/``) on PYTHONPATH, and provide the deployment values: the ESP32 address and port, and the DDS core
clock (``clock`` times ``pll``) that the unit actually uses.  The upstream constructor has defaults for these
values (DDS_ESP32_lab/DDS_ESP32.py:34) but they describe one bench, not this device, so they are not used here.
The module imports numpy (DDS_ESP32_lab/DDS_ESP32.py:29).
"""


def connect(ip, port, clock, pll):
    """Return the upstream DDS_ESP32 object for one ESP32; no connection is made until a command is sent."""
    from DDS_ESP32_lab.DDS_ESP32 import DDS_ESP32

    return DDS_ESP32(ip, port=port, clock=clock, pll=pll)
