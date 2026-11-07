"""Hardware backend: opens the uSMU serial port and wraps it in the upstream ``usmu_py.smu:USMU``.

Used only with ``backend="hardware"`` and ``--allow-hardware`` (an operator decision).  The upstream constructor
takes the port name and the optional baud rate, read timeout and command delay and opens a pyserial connection
(usmu_py/smu.py:13-40); this factory passes the backend options through and never invents a port or a setting.
The package is model-authored and unreviewed, but it is R1: the loader refuses the hardware backend of an
unreviewed model-written package only at R2 and R3, so this note does not claim such a refusal for R1.  A human
must review the package before hardware use; the acceptance gate runs the fake backend and never imports this
module, pyserial or the upstream package.

Options: ``port`` (required, for example ``"/dev/ttyUSB0"``) and, when the operator needs to override the upstream
defaults, ``baudrate``, ``timeout`` and ``command_delay``.
"""


def connect(**options):
    from usmu_py.smu import USMU

    port = options.get("port")
    if not port:
        raise ValueError("the uSMU hardware backend needs a 'port' option (for example '/dev/ttyUSB0')")
    settings = {}
    for name in ("baudrate", "timeout", "command_delay"):
        value = options.get(name)
        if value is not None:
            settings[name] = value
    return USMU(port=str(port), **settings)
