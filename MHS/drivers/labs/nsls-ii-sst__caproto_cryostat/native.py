"""Hardware transport factory for the NSLS-II SST ADR EPICS IOC.

This module is imported only for a reviewed hardware backend.  The acceptance
gate never imports it, and the TagDriver refuses the hardware backend until a
human signs ``reviewed_by`` with scope ``hardware`` in ``driver.lock.json``.

``connect`` builds a Channel Access client with caproto's threaded client (the
library the upstream IOC itself imports) and adapts it to the TagBridge
transport interface:

* ``read_point`` reads one PV and returns its scalar value (a string for a
  string PV, otherwise the numeric element the IOC publishes);
* ``write_point`` issues a wait-for-put-completion write and returns ``True``
  only when the IOC's CA reply status is success.

The PV suffix comes from the declaration; the operator supplies the deployment
prefix (the module's argument-parser default is not a device fact).  A PV that
does not connect within the request timeout is ``TagRefused``: nothing was sent.
A failure after the request was sent propagates, which the bridge reports as an
unknown outcome.  There is no shared bus lock: Channel Access handles concurrent
requests, so a stop is not queued behind an ordinary read or write.

The reviewer must supply the installed prefix and CA address configuration
(``EPICS_CA_ADDR_LIST`` and related environment) before signing.  Model review
(2026-11-05): the package declares read points only, so the bridge never calls
``write_point``; it remains here only because it is part of the transport
interface.  The upstream module docstring's CA environment uses a facility
broadcast address (cryostat.py:1-6), which is deployment data.
"""

import threading

from mhs.bridge.tags import TagRefused


def connect(prefix, **_options):
    """Open a Channel Access client for the deployment's PV ``prefix``."""
    if not isinstance(prefix, str) or not prefix:
        raise ValueError("connect needs the deployment's non-empty EPICS PV prefix")
    return CaprotoTransport(prefix)


class CaprotoTransport:
    """One Channel Access client cache for the configured PV prefix."""

    def __init__(self, prefix):
        import caproto.threading.client as client  # vendor library: imported only at hardware time

        self._client = client
        self._prefix = prefix
        self._context = client.Context()
        self._pvs = {}
        self._lock = threading.Lock()

    def _name(self, request):
        pv = request.get("pv") if isinstance(request, dict) else None
        if not isinstance(pv, str) or not pv:
            raise ValueError("an epics-ca request needs a PV suffix")
        return self._prefix + pv

    def _pv(self, name, timeout_s):
        with self._lock:
            pv = self._pvs.get(name)
        if pv is None:
            pv = self._context.get_pvs(name, timeout=float(timeout_s))[0]
            with self._lock:
                self._pvs[name] = pv
        try:
            pv.wait_for_connection(timeout=float(timeout_s))
        except Exception as exc:  # noqa: BLE001 - no channel: nothing was sent
            raise TagRefused(f"the PV {name!r} is not connected", code="disconnected") from exc
        return pv

    def read_point(self, request, *, timeout_s):
        pv = self._pv(self._name(request), timeout_s)
        response = pv.read(timeout=float(timeout_s))
        return _scalar(response.data)

    def write_point(self, request, raw, *, timeout_s):
        pv = self._pv(self._name(request), timeout_s)
        response = pv.write(raw, wait=True, timeout=float(timeout_s))
        status = getattr(response, "status", 1)
        if status != 1:
            raise TagRefused(f"the IOC refused the put to {pv.name!r} with status {status}", code=status)
        return True

    def close(self):
        self._context.disconnect(wait=True)


def _scalar(data):
    """One Python value from a Channel Access read payload."""
    if isinstance(data, (bytes, bytearray)):
        return bytes(data).decode("ascii")
    if isinstance(data, str):
        return data
    if not hasattr(data, "__iter__"):
        return data
    values = list(data)
    if len(values) == 1:
        value = values[0]
        return bytes(value).decode("ascii") if isinstance(value, (bytes, bytearray)) else value
    if all(isinstance(value, str) for value in values):
        return "".join(values)
    if all(isinstance(value, (bytes, bytearray)) for value in values):
        return b"".join(bytes(value) for value in values).decode("ascii")
    return values
