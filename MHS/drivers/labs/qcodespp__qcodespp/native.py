"""Hardware backend of the Keithley 2450 driver: the upstream QCoDeS instrument over a VISA session.

The gate never imports this module.  ``connect`` runs only when an operator loads the hardware backend
(``mhs.adapter.load_driver(..., backend="hardware", allow_hardware=True, ...)``); it is then the only code that
imports qcodespp, and through it QCoDeS and PyVISA.  The VISA resource address is deployment data and is never
guessed.

Constructing ``Keithley_2450`` opens the VISA session, adds the Parameters listed in its ``__init__`` and calls
``connect_message()`` (Keithley_2450.py:10-120).  It does not turn the output on.  A failure there raises before the
driver serves anything.  QCoDeS keeps a registry of instrument names, so ``name`` must be unique in the process.
Nothing here was run: the package has never opened a VISA session.
"""


def connect(*, address, name="keithley_2450", timeout_s=20):
    """Open the pinned QCoDeS Keithley_2450 instrument at an operator-supplied VISA resource address."""
    if not isinstance(address, str) or not address.strip():
        raise ValueError("address must be the VISA resource name of the Keithley 2450")
    if not isinstance(name, str) or not name.isidentifier():
        raise ValueError("name must be a Python identifier (QCoDeS instrument names are identifiers)")
    if isinstance(timeout_s, bool) or not isinstance(timeout_s, (int, float)) or not 0 < timeout_s <= 60:
        raise ValueError("timeout_s must be a VISA timeout in seconds in (0, 60]")
    from qcodespp.instrument_drivers.tektronix.Keithley_2450 import Keithley_2450

    return Keithley_2450(name, address, timeout=timeout_s)
