"""Hardware backend of the Lake Shore 336 driver: the upstream QCoDeS instrument over a VISA session.

The gate never imports this module.  ``connect`` runs only when an operator loads the hardware backend
(``mhs.adapter.load_driver(..., backend="hardware", allow_hardware=True, ...)``); it is then the only code that imports
``instruments.lakeshore_336`` and through it QCoDeS and PyVISA.  The VISA resource address is deployment data and is
never guessed.

Constructing ``LakeShore336`` opens the VISA session and writes ``*CLS``; the upstream class deliberately does not send
``*RST`` (instruments/lakeshore_336.py:22-26, 95-110).  A failure there raises before the driver serves anything.
QCoDeS keeps a registry of instrument names, so ``name`` must be unique in the process.  Nothing here was run: the
package has never opened a VISA session.
"""


def connect(*, address, name="lakeshore_336"):
    if not isinstance(address, str) or not address.strip():
        raise ValueError("address must be the VISA resource name of the Lake Shore 336")
    if not isinstance(name, str) or not name.isidentifier():
        raise ValueError("name must be a Python identifier (QCoDeS instrument names are identifiers)")
    from instruments.lakeshore_336 import LakeShore336

    return LakeShore336(name=name, address=address)
