"""Hardware backend: open the upstream ``labinstruments.agilent:AgilentE8257D`` over its TCP socket.

Used only with ``backend="hardware"`` (never by the acceptance gate, which runs the fake backend and does not import
this module).  The upstream class inherits ``GenericInstrument.__init__(ip_address, port=5025, timeout=None,
verbose=False)`` (labinstruments/generic.py:27), which opens the socket and reads the identity; this factory passes
the backend options through:

* ``host`` (or ``ip_address``): the instrument address, required;
* ``port``: the TCP port, defaulting to the upstream's 5025 (labinstruments/generic.py:27);
* ``timeout_s``: the socket timeout in seconds when given (the upstream default is no timeout).

This package is model-authored and unreviewed.  It is R1, so the loader refuses the hardware backend of an
unreviewed model-written package only at R2 and R3; this note does not claim such a refusal for R1.  A human must
review the package before hardware use.
"""


def connect(**options):
    host = options.get("host") or options.get("ip_address")
    if not host:
        raise ValueError("the Agilent E8257D hardware backend needs a 'host' (or 'ip_address') option")
    port = int(options.get("port", 5025))
    timeout = options.get("timeout_s")
    kwargs = {}
    if timeout is not None:
        kwargs["timeout"] = float(timeout)
    from labinstruments.agilent import AgilentE8257D

    return AgilentE8257D(str(host), port, **kwargs)
