"""Hardware backend: opens the upstream ScanImage TCP/IP JSON client.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed; it is R1, so the loader does not refuse the hardware backend (the reviewed_by refusal is R2 and
R3 only, and this package must not claim it).  The acceptance gate runs the fake backend and never imports this
module or the upstream client; nothing here ran on a ScanImage server.

The upstream client is one module at the clone root (py_json_client.py, module name ``py_json_client``) with no
packaging, so a deployment puts that directory on PYTHONPATH (driver.lock.json install.notes).  Its constructor
opens the TCP socket immediately and sets a 100 ms timeout (py_json_client.py:26-33).  ``address`` and ``port``
are required options: the constructor defaults 127.0.0.1 and 5555 (py_json_client.py:26) describe the upstream
example, not the operator's ScanImage host.
"""


def connect(address, port, **options):
    """Open the upstream client against the ScanImage JSON server at ``address:port``."""
    from py_json_client import ScanimageTcpipClient

    return ScanimageTcpipClient(address=address, port=port)
