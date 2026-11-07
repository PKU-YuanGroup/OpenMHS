"""Hardware backend factory of the GP350 package: open the upstream serial client for one controller.

The factory is imported only when the hardware backend is built; the gate never imports it.  ``SerialClient`` opens
a pyserial port in its constructor (collectors/serial_client.py:9-31), so the controller's port and line settings
are the options of this backend.  Nothing here is tested: no hardware was attached.
"""

from collectors.serial_client import SerialClient

DEFAULTS = {
    # The line settings are options with the constructor's defaults, not device limits: the module fitted to a
    # GP350 may be the RS-232 module (300 7N2, CRLF) or the Digital Interface (9600 8N1, CR)
    # (docs/operations/gp350-wiring.md:22-31, 49-59).
    "bytesize": 8,
    "parity": "N",
    "stopbits": 1,
    "line_terminator": "\r\n",
    "timeout": 1.0,
    "write_timeout": 1.0,
}


def connect(*, port: str, baudrate: int, **options):
    """Open a ``SerialClient`` on ``port`` with the line settings of the installed module."""
    settings = dict(DEFAULTS)
    settings.update({key: value for key, value in options.items() if key in DEFAULTS})
    return SerialClient(port=port, baudrate=baudrate, **settings)
