"""Live ``sim`` backend: a bounded client of MVSim's own ZMQ/protobuf services (package code; never run by the gate).

This is the package's own client, with its own declared dependency (pyzmq, in driver.lock.json ``install``); the SDK
does not depend on it, and nothing here is imported until the ``sim`` backend is opened. It offers the two members of
the upstream Python client the driver uses, ``callService(serviceName, inputSerializedMsg) -> bytes`` and
``shutdown()`` (modules/comms/python/generated-sources-pybind/mvsim/Comms/Client.cpp:64-87).

Why not the upstream client itself: its ``connect``, ``callService`` and ``shutdown`` wait on ZMQ receives with no
timeout (common.cpp:63-73; Client.cpp:233-259, 735-808), and the pybind11 binding calls them without releasing the
GIL (generated Client.cpp:74-87), so a simulator that stops answering would stall the whole Python process, e-stop
included. The client (``mvsim_wire.MvsimServiceClient``) speaks the same wire protocol, and every socket operation is
bounded by one deadline per call:

1. ``GetServiceInfoRequest`` (serviceName) to the server's main REP socket at ``tcp://<host>:<port>`` (the port defaults
   to MVSIM_SERVER_PORT or 23700, ports.h:20-49); the answer names the service's endpoint (Client.cpp:745-778,
   Server.cpp:416-438). Endpoints are cached per service as the upstream client caches them, and dropped after any
   failed call so the next call asks again.
2. ``CallService`` (serviceName, serializedInput) to the configured host at the port of that endpoint; the answer is
   the service's own message, returned unframed as the upstream client returns it (Client.cpp:781-805; the serving
   side, Client.cpp:545-590). The simulator binds its service socket to ``tcp://0.0.0.0:*`` and reports that wildcard
   endpoint (Client.cpp:166-167, 462); the upstream client connects to it verbatim (Client.cpp:775, 783), this client
   never follows a host the server names. An answer must be the service's answer type (``mvsim_wire.ANSWER_TYPES``) or
   a ``GenericAnswer`` whose success is false (an unknown service, Client.cpp:565-580); anything else raises.

Every message is MVSim's envelope (``mvsim_wire.frame``). A fresh REQ socket serves each request (closed with linger 0
afterwards), so a timed-out request never blocks the next one and concurrent calls (an e-stop during a command) do not
share a socket. A call that does not finish in time raises ``TimeoutError``; the driver then reports the outcome as
unknown (or the e-stop as unreached). This client has not been run against an MVSim server.
"""

from __future__ import annotations

import os

from .mvsim_wire import MvsimServiceClient

_DEFAULT_PORT = 23700  # MVSIM_PORTNO_MAIN_REP, modules/comms/include/mvsim/Comms/ports.h:20


def _port(port):
    """The server port: ``port``, else MVSIM_SERVER_PORT when it holds a valid port, else 23700 (ports.h:26-49).

    ``mvsim launch`` may serve on one of the next nine ports when 23700 is taken (ports.h:22-24): the operator then
    passes that port.
    """
    if port is not None:
        value = int(port)
        if not 1 <= value <= 65535:
            raise ValueError("the MVSim server port must be 1..65535")
        return value
    text = os.environ.get("MVSIM_SERVER_PORT", "")
    if text.isdigit() and 1 <= int(text) <= 65535:
        return int(text)
    return _DEFAULT_PORT


def connect(*, host="localhost", port=None, timeout_s=2.0, **_options):
    """The ``sim`` backend factory: a client for the MVSim server at ``host``/``port`` (no I/O until the first call)."""
    import zmq  # the package's declared dependency (pyzmq); never imported by the gate or the SDK

    if not isinstance(host, str) or not host or any(char in host for char in "/:@ "):
        raise ValueError("host must be a bare host name or address")
    timeout_s = float(timeout_s)
    if not 0.05 <= timeout_s <= 30.0:
        raise ValueError("timeout_s must be between 0.05 and 30 seconds")
    return MvsimServiceClient(zmq, host, _port(port), timeout_s)
