"""Hardware backend: connects the upstream Tecan Fluent SiLA2 client to a running SilaFluentServer.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed, and it is R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json.  The acceptance gate runs the fake backend and never imports this module or the upstream package.

The upstream wrapper's constructor builds a ``sila2.client.SilaClient`` for a SilaFluentServer and requires the
``SilaFluentController`` feature (Python/src/tecan/__Fluent.py:20-34).  The wrapper does not start FluentControl
itself; ``start_fluent()`` forwards ``StartFluentOrAttach``/``StartFluentAndLogin``/``StartFluentInSimulationMode``
(Python/src/tecan/__Fluent.py:262-287).  This factory therefore only connects to an already running SilaFluentServer;
the operator's deployment supplies the host, port and TLS options (the README's ``Fluent("127.0.0.1", 50052,
insecure=True)`` is one example, not a device fact).  The wrapper's ``shutdown(timeout)`` is not called: stopping the
OpenMHS endpoint must not shut down FluentControl.
"""


def connect(server_ip="127.0.0.1", server_port=50052, **options):
    from tecan import Fluent

    return Fluent(server_ip=server_ip, server_port=server_port, **options)
