"""Hardware backend: open an Ismatec pump controller through the upstream class.

Used only with ``backend="hardware"`` and ``allow_hardware=True`` (an operator
decision).  This package is model-authored and unreviewed, and it is R2: the
loader refuses its hardware backend until a human signs ``reviewed_by`` in
``driver.lock.json``, and while the package is blocked (no confirmed stop)
strict start-up also refuses the hardware device (SAFE-045).  The acceptance
gate runs the fake backend and never imports this module or the upstream
``instruments`` package.

``src/instruments/ismatec/ismatec.py`` imports ``Serial`` from ``serial``
(pyserial), ``Instrument`` from ``instruments.instrument`` and ``set_trace``
from ``pdb`` (``ismatec.py:8-10``); it does not import ``lib.helper_functions``.
The clone ships no packaging metadata, so the clone's ``src`` directory must
be on the import path, and pyserial installed (the project image installs it,
``src/project/Dockerfile:6``); the task card declares no install command.

``Ismatec(port)`` only stores ``port`` and creates the request queue
(``instrument.py:24-32``).  ``main()`` then runs ``connect()``, which opens the
port with the line settings hard-coded at ``ismatec.py:39-40`` (baudrate 9600,
bytesize 8, parity N, stopbits 1, timeout 0.5) and writes ``@1`` and ``1M`` to
the pump (``:41-42``; the clone does not say what they set), and starts the
single daemon worker thread (``ismatec.py:86-90``, ``instrument.py:60-63``).
Nothing here starts the pump.  The class has no close method: the port and
the worker stay open until the process ends.

The clone's own deployment (``docker-compose.yml:4-14``, ``src/project/Dockerfile:15``)
runs ``project.ismatec_deltav``, which opens ``/dev/ttyUSB0`` at import and
starts or stops the pump from an OPC UA server (``src/project/ismatec_deltav.py:16-33``);
never run it beside this backend on the same port.
"""


def connect(port, **_options):
    """Return the connected upstream controller; extra options are not used by the upstream class."""
    from instruments.ismatec.ismatec import Ismatec

    instrument = Ismatec(port)
    instrument.main()               # connect() plus _start_threads()
    return instrument
