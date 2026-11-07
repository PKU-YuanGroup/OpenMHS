"""Hardware backend: opens a scope through the upstream pyvisa transport and KeysightScope class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  The factory
imports the pinned upstream package inside the call, so the fake backend of this package and the
acceptance gate never import or run the clone.

``resource`` is the VISA resource string the upstream transport expects -- for example
``TCPIP0::192.168.0.50::inst0::INSTR``, ``TCPIP0::192.168.0.50::5025::SOCKET``,
``USB0::...::INSTR`` or ``ASRL3::INSTR`` (README.md:184-190).  ``backend`` selects the pyvisa
resource manager (``"auto"`` tries the system VISA first and then pyvisa-py, transport.py:64-77);
``timeout_ms`` is the VISA timeout (default 5000 ms, transport.py:47) and the other keyword
arguments (``read_termination`` and ``write_termination``) go to VisaTransport unchanged.

The upstream class does not expose a close method; the driver's teardown closes the transport
attribute ``t`` (keysight.py:37-40, transport.py:100-104).

This package is model-authored and unreviewed and is R1, so the loader does not gate its hardware
backend on a ``reviewed_by`` signature (that refusal applies to model-authored R2 and R3 packages).
Nothing in this package ran on an instrument.
"""


def connect(resource, *, backend="auto", timeout_ms=5000, **options):
    from ece_suite.instruments.keysight import KeysightScope
    from ece_suite.instruments.transport import VisaTransport

    transport = VisaTransport(resource, backend=backend, timeout_ms=int(timeout_ms), **options)
    return KeysightScope(transport)
