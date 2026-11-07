"""Hardware backend: opens a RIGOL DG4202 through the upstream WaveBench SCPI transport.

Used only with backend="hardware" and allow_hardware=True, which is an operator decision.  This package is
model-authored and unreviewed (driver.lock.json ``reviewed_by`` is null); nothing in it ever ran against an
instrument.

Options of the backend:

* ``resource`` (required): the VISA resource of the generator, for example ``TCPIP::192.0.2.10::INSTR`` — the
  builtin DG4000 descriptor lists the ``pyvisa`` backend (src/wavebench/instruments/builtin.py:128-132) and the
  clone builds a ``ConnectionConfig(backend="lan", ...)`` for it before opening ``PyVisaTransport``
  (src/wavebench/instruments/factory.py:275-279);
* ``timeout_ms`` (default 2000) and ``opc_timeout_ms`` (default 2000): the transport timeouts;
* ``check_errors`` (default true): passed as ``check_errors_after_ops`` to ``DG4202Source``
  (src/wavebench/instruments/builtin.py:27-33).

The transport object is the one the upstream class expects (``transport.query`` with the clone's replay policy and
``transport.write``); this module imports the upstream package, which the acceptance gate never instals nor imports.
"""


def connect(resource, *, timeout_ms=2000, opc_timeout_ms=2000, check_errors=True):
    from wavebench.config import ConnectionConfig
    from wavebench.drivers.dg4202 import DG4202Source
    from wavebench.logging import CommandLogger
    from wavebench.transport.pyvisa_transport import PyVisaTransport

    connection = ConnectionConfig(backend="lan", resource=resource, timeout_ms=timeout_ms,
                                  opc_timeout_ms=opc_timeout_ms)
    transport = PyVisaTransport.open(connection, logger=CommandLogger())
    return DG4202Source(transport=transport, check_errors_after_ops=bool(check_errors))
