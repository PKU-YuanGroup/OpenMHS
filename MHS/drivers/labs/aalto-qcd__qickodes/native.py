"""Hardware backend of the QICKoDeS driver: the upstream QCoDeS instrument over a Pyro4 connection.

The gate never imports this module.  ``connect`` runs only when an operator loads the hardware backend, and it is then
the only code that imports qickodes; constructing ``QickInstrument`` reaches the QICK server through
``make_proxy(ns_host, ns_port)`` (src/qickodes/instrument_v2.py:102).  The board address is deployment data and is
never guessed.  The upstream constructor also asserts exactly one tProc of type qick_processor and builds the DAC,
ADC and DDR4 objects from the remote configuration (instrument_v2.py:107-142); a board with another tProc type or an
unreachable nameserver raises before the driver serves anything.

The install block of the task card is ``pip install .`` with qick>=0.2.255, qcodes and pyro4 (pyproject.toml:22-26).
This module was never run: the package is model-authored and unreviewed, and it is checked on the fake backend only.
"""


def connect(*, ns_host, ns_port=8888, name="QickInstrument", **options):
    """Open the upstream QICKoDeS QickInstrument on the Pyro4 nameserver of the QICK board."""
    if not isinstance(ns_host, str) or not ns_host.strip():
        raise ValueError("ns_host must be the address of the Pyro4 nameserver of the QICK board")
    if isinstance(ns_port, bool) or not isinstance(ns_port, int) or not 0 < ns_port <= 65535:
        raise ValueError("ns_port must be a TCP port in 1..65535")
    if not isinstance(name, str) or not name.isidentifier():
        raise ValueError("name must be a Python identifier (QCoDeS instrument names are identifiers)")
    from qickodes.instrument_v2 import QickInstrument

    return QickInstrument(ns_host, ns_port=ns_port, name=name, **options)
