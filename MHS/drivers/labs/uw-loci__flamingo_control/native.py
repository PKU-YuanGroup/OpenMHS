"""Hardware backend: connects a Flamingo microscope and returns its PositionController.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed, and it is R1: the loader does not refuse its hardware backend on review grounds (that refusal is
for a model-authored R2 or R3 driver).  The acceptance gate runs the fake backend and never imports this module or
the upstream py2flamingo package, so the hardware path below was never executed.

The backend builds the upstream core objects the application's component factory uses: a TCPConnection, a
ProtocolEncoder and a QueueManager wrapped in MVCConnectionService (services/component_factory.py:21-25, 82-87).
It connects to the microscope with a ConnectionConfig (models/connection.py:28-43) and then constructs the
PositionController with a shared ConfigurationService (services/component_factory.py:172-176).  The configuration
service discovers the project root by walking up from the current directory until it finds
``microscope_settings/`` (services/configuration_service.py:46-70), so the operator starts the process where that
directory is reachable.

Options: ``host`` and ``port`` are required; ``live_port`` defaults to port + 1 and ``timeout`` to 2.0 s, both as
ConnectionConfig does (models/connection.py:44-60).  Any other option is rejected so a typo cannot silently change
the transport.
"""


def connect(host, port, live_port=None, timeout=2.0, **options):
    if options:
        raise TypeError(f"unknown connection option(s): {', '.join(sorted(options))}")
    from py2flamingo.controllers.position_controller import PositionController
    from py2flamingo.core import ProtocolEncoder, QueueManager, TCPConnection
    from py2flamingo.models.connection import ConnectionConfig
    from py2flamingo.services.configuration_service import ConfigurationService
    from py2flamingo.services.connection_service import MVCConnectionService

    connection = MVCConnectionService(TCPConnection(), ProtocolEncoder(), QueueManager())
    connection.connect(ConnectionConfig(host, int(port), live_port, float(timeout)))
    return PositionController(connection, config_service=ConfigurationService())
