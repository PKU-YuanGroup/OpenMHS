"""Hardware backend: opens a RIGOL oscilloscope through the upstream ScopeDriver.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  The factory imports the pinned
upstream package inside the call, so neither the fake backend nor the acceptance gate imports or runs
the clone. Adapter-only tests import this module without calling connect().  A LAN SCPI connection is a host and port (the upstream raw-socket default is 5555, lan.py:20); a USB
connection is the VISA resource string the upstream UsbTransport expects.  When ``profile`` is omitted, the factory
follows the upstream connection sequence: open the transport, drain the error queue, identify with *IDN? and
resolve the model profile (connection.py:169-172).

The session transport serializes each complete query/response with an RLock because the upstream transports
share one reply buffer and have no such lock (lan.py:96-102; usb.py:130-138). A stop can wait for one in-flight
query's timeout; the endpoint reports an unreached safe state if its stop budget expires. Teardown closes the link.

This package is model-authored and unreviewed.  It is R1, so the loader does not gate its hardware backend on a
``reviewed_by`` signature; nothing in this package ran on an instrument.
"""

import threading


class _SerializedTransport:
    """Keep text and binary query responses on the request that sent them."""

    def __init__(self, link):
        self._link = link
        self._lock = threading.RLock()

    def open(self):
        with self._lock:
            return self._link.open()

    def close(self):
        with self._lock:
            return self._link.close()

    @property
    def is_open(self):
        with self._lock:
            return self._link.is_open

    def write(self, command):
        with self._lock:
            return self._link.write(command)

    def query(self, command, timeout_s=None):
        with self._lock:
            return self._link.query(command, timeout_s)

    def query_binary(self, command, timeout_s=None):
        with self._lock:
            return self._link.query_binary(command, timeout_s)

    def query_lines(self, command, timeout_s=None):
        with self._lock:
            return self._link.query_lines(command, timeout_s)


def connect(host=None, port=5555, resource_name=None, timeout_s=5.0, profile=None, **options):
    from rigol_oscilloscope_mcp.driver.scope import ScopeDriver
    from rigol_oscilloscope_mcp.driver.session import ScpiSession
    from rigol_oscilloscope_mcp.profiles import load_profile, resolve_profile

    if resource_name is not None:
        from rigol_oscilloscope_mcp.transport.usb import UsbTransport

        link = UsbTransport(str(resource_name), float(timeout_s))
    elif host is not None:
        from rigol_oscilloscope_mcp.transport.lan import LanTransport

        link = LanTransport(str(host), int(port), float(timeout_s))
    else:
        raise ValueError("connect needs host (LAN) or resource_name (USB)")

    link.open()
    try:
        session = ScpiSession(_SerializedTransport(link), float(timeout_s))
        session.drain_error_queue()
        if profile is None:
            idn = ScopeDriver(session, load_profile("rigol-generic")).identify()
            selected = resolve_profile(idn).profile
        else:
            selected = load_profile(str(profile))
        return ScopeDriver(session, selected)
    except BaseException:
        link.close()
        raise
