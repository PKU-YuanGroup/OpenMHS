"""Hardware backend: open an Agilent AWG33220A through the upstream NetworkDeviceBackend.

Used only with ``backend="hardware"`` and an explicit operator decision.  The package is model-authored, unreviewed
and R1: the loader does not refuse its hardware backend (it refuses an unreviewed model-written package only at R2
and R3), and this path has never been run.  The acceptance gate uses the fake backend and never imports this module.

Options: ``addr`` is an ``"IP:port"`` string (or a ``(host, port)`` tuple) the upstream NetworkDeviceBackend
understands (backend.py:873-925); otherwise ``host`` and ``port`` are combined into one.  ``timeout`` is the socket
timeout in seconds.  The upstream AWG33220A constructor accepts an already opened backend object
(AgilentElectronics.py:20-21, SCPI.py:79-82), so the socket is opened exactly once.
"""


def connect(addr=None, host=None, port=5025, timeout=5.0, **options):
    from pylablib.aux_libs.devices.AgilentElectronics import AWG33220A
    from pylablib.core.devio.backend import NetworkDeviceBackend

    if addr is None:
        if not host:
            raise ValueError("connect() needs addr='IP:port' or host")
        addr = f"{host}:{int(port)}"
    backend = NetworkDeviceBackend(addr, timeout=timeout, term_write="\n", **options)
    return AWG33220A(backend)
