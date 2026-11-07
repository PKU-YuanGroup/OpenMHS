"""Hardware backend of the AD75019 crosspoint switch: the upstream QCoDeS ``Muxi`` over pyVISA.

The gate never imports this module.  ``connect`` runs only when an operator loads the hardware backend; it is then the
only code that imports ``qcdrivers`` and, through it, QCoDeS, pyVISA and matplotlib (mux.py:1-8).  The VISA resource
name is deployment data; the baud rate defaults to the upstream constructor's own 9600 (mux.py:37), which the
firmware also opens with (firmware.ino:19).

Constructing ``Muxi`` talks to the switch before it returns: it opens the VISA session, sets the baud rate, the
newline/CRLF terminators and a 2000 ms VISA timeout, calls QCoDeS ``connect_message()`` (Muxi overrides ``get_idn``
with a hard-coded dictionary, mux.py:237-256, so no identity query is sent; QCoDeS prints the connect message to
stdout, which an MHS server talking over stdio must isolate), clears the VISA handle and allocates a local 32 x 32
matrix (src/qcdrivers/squad/mux/mux.py:50-68).  It does not reset the switch: routes set before the driver opened
stay set until the first *RST.  A failure in that sequence raises before the driver serves anything.  Nothing here
was run: this package has never opened a serial port, and the fake backend has never touched hardware.
"""


def connect(*, address, name="muxi", baud_rate=9600):
    if not isinstance(address, str) or not address.strip():
        raise ValueError("address must be the VISA resource name of the Muxi serial port")
    if not isinstance(name, str) or not name.isidentifier():
        raise ValueError("name must be a Python identifier (QCoDeS instrument names are identifiers)")
    if isinstance(baud_rate, bool) or not isinstance(baud_rate, int) or baud_rate <= 0:
        raise ValueError("baud_rate must be a positive integer")
    from qcdrivers.squad.mux.mux import Muxi

    return Muxi(name, address, baud_rate=baud_rate)
