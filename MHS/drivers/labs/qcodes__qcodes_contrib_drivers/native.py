"""Hardware backend of the PM100D driver: the upstream QCoDeS instrument over a VISA session.

The gate never imports this module.  ``connect`` runs only when an operator loads the hardware backend
(``mhs.adapter.load_driver(..., backend="hardware", allow_hardware=True, ...)``); it is then the only code that
imports qcodes_contrib_drivers, and through it QCoDeS and PyVISA.  The VISA resource address is deployment data and is
never guessed.

Constructing ``Thorlab_PM100D`` talks to the meter before it returns (PM100D.py:38-157): it opens the VISA session,
writes STAT:OPER:PTR 512 and STAT:OPER:NTR 0 with sleeps of about 5.4 s in total, sends ``AVER`` (the set_cmd of
``averaging(300)``, which carries no value), writes CONF:POW, asks ABOR;:STAT:OPER?, writes INIT and asks the
identity for the connect message.  A failure there raises before the driver serves anything.  QCoDeS keeps a registry
of instrument names, so ``name`` must be unique in the process.  Nothing here was run: the package has never opened
a VISA session.
"""


def connect(*, address, name="pm100d", timeout_s=20):
    if not isinstance(address, str) or not address.strip():
        raise ValueError("address must be the VISA resource name of the PM100D (for example a USB resource string)")
    if not isinstance(name, str) or not name.isidentifier():
        raise ValueError("name must be a Python identifier (QCoDeS instrument names are identifiers)")
    if isinstance(timeout_s, bool) or not isinstance(timeout_s, (int, float)) or not 0 < timeout_s <= 60:
        raise ValueError("timeout_s must be a VISA timeout in seconds in (0, 60]")
    from qcodes_contrib_drivers.drivers.Thorlabs.PM100D import Thorlab_PM100D

    return Thorlab_PM100D(name, address, timeout=timeout_s)
