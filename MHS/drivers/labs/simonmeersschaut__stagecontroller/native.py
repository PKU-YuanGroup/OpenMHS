"""Hardware backend: the upstream ``stage.Serial`` over the fixed serial line the clone opens.

Used only with backend="hardware" and allow_hardware=True (an operator decision); the gate never imports this
module and never opens the device.  The upstream constructor opens /dev/ttyUSB0 at 9600 8N1 and retries until the
port is available (stage.py:21-42), so the clone root must be importable (put it on PYTHONPATH) and the upstream
dependencies ``serial``, ``numpy`` and ``gpiozero`` must be installed (stage.py:1-6).  The constructor takes no
options; there is no configurable port in the clone.
"""


def connect(**options):
    if options:
        raise TypeError("stage.Serial takes no options; the clone fixes /dev/ttyUSB0 at 9600 8N1 (stage.py:25-31)")
    from stage import Serial

    return Serial()
