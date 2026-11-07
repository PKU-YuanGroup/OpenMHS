"""Hardware backend: builds the upstream TEMClient for a running DTMicroscope TEMServer.

Used only with ``backend="hardware"`` and ``allow_hardware=True`` (an operator decision).  The upstream client opens one
socket per call to the JSON-RPC server (``DTMicroscope/base/twisted_client.py:36-46``); the server in turn owns the
AutoScript connection to the microscope (``DTMicroscope/server/twisted_server.py:137-156``).  This factory only
constructs the client: it does not start the server, install the upstream package or contact a device.

The package is R1.  The loader refuses the hardware backend of an unreviewed model-written package only at R2 and R3,
so no review gate protects this R1 backend: a human must review the package before pointing it at a microscope.  Nothing
in this module, and no part of the package, was run against hardware.

Options: ``host`` is the address of the running TEMServer (default ``127.0.0.1``, the address the server's own
``connect_to_as`` uses for AutoScript, twisted_server.py:154-156), ``port`` its JSON-RPC port (the server's main listens
on 9093, twisted_server.py:389-392) and ``timeout`` the socket timeout in seconds.  These are connection options, not
device bounds.
"""


def connect(host="127.0.0.1", port=9093, timeout=30):
    from DTMicroscope.base.twisted_client import TEMClient

    return TEMClient(host=host, port=port, timeout=timeout)
