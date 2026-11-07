"""Hardware transport factory for the caproto-rpi hat IOC's state PV (reviewed backend only).

The acceptance gate never imports this module.  The TagDriver refuses the
hardware backend until a human signs ``reviewed_by`` with scope ``hardware`` in
``driver.lock.json``, at every risk class and for every author.  ``connect``
builds a caproto Channel Access client (the client half of the library the
upstream ``requirements.txt`` already installs) and adapts it to the TagBridge
transport interface:

* ``read_point`` returns the value of the declared PV suffix;
* ``write_point`` returns ``True`` only after the caproto put completion
  (``wait=True``) arrived from the IOC.

Deployment data.  The PV name is the operator's prefix plus the pvproperty
attribute name declared upstream: ``state`` at ``iocs/hat.py:34``.  The shipped
supervisor configuration starts the hat IOC with a templated prefix
(``--prefix=hat{{ prefix }}:``, ``supervisor_config/hat.conf:2``), so the prefix
is a deployment option.  ``prefix`` must include the trailing colon; there is
no safe default because the deployment may rename it.

Fresh reads.  ``read_point`` calls ``PV.get(use_monitor=False)`` so a stop
confirmation is a new Channel Access read, never the latest monitor cache.
``write_point`` waits for the put completion; a lost reply therefore raises
and the bridge records an unknown outcome instead of assuming the write.

The stop is ``state = 0`` confirmed by that fresh read.  It does not call the
IOC shutdown hook: the upstream hook drives the GPIO pins LOW and calls
``GPIO.cleanup`` (``iocs/hat.py:43-47``); this transport only writes the PV.

The reviewer must, before signing: confirm the deployed prefix, the pins the
IOC was started with and what is wired to them, the caproto client version and
the pyepics-compatible ``get``/``put`` signatures, and run this against the IOC
under supervision, including a put whose reply is lost.
"""


class CaprotoCaTransport:
    """One caproto Channel Access context for the declared PV."""

    def __init__(self, context, pvs):
        self._context = context
        self._pvs = dict(pvs)

    def _pv(self, request):
        try:
            return self._pvs[request["pv"]]
        except KeyError as exc:  # only the declared suffix is served
            raise ValueError(f"undeclared PV suffix {request.get('pv')!r}") from exc

    def read_point(self, request, *, timeout_s):
        pv = self._pv(request)
        value = pv.get(timeout=float(timeout_s), use_monitor=False)
        if value is None:
            raise TimeoutError(f"no fresh value from {pv.pvname} within {float(timeout_s)} s")
        return value

    def write_point(self, request, raw, *, timeout_s):
        pv = self._pv(request)
        pv.put(raw, wait=True, timeout=float(timeout_s))
        return True

    def close(self):
        self._context.disconnect()


def connect(prefix, connect_timeout_s=5.0, **_options):
    """Build the Channel Access transport for the operator's hat IOC prefix."""
    from caproto.threading.client import Context
    from caproto.threading.pyepics_compat import get_pv

    names = {"state": str(prefix) + "state"}
    context = Context()
    pvs = {}
    try:
        for suffix, name in names.items():
            pvs[suffix] = get_pv(name, context=context, connect=True, timeout=float(connect_timeout_s))
    except BaseException:
        context.disconnect()
        raise
    return CaprotoCaTransport(context, pvs)
