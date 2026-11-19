"""Hardware backend: opens a JULABO circulator through the upstream labmcp-julabo package.

Used only with backend="hardware" and allow_hardware=True (an operator decision).
This package is model-authored and unreviewed, and it is R2: the loader refuses its
hardware backend until a human sets ``reviewed_by`` in driver.lock.json.

The upstream server (servers/chemistry/julabo-circulator/src/labmcp_julabo/server.py:31-48)
opens a labmcp transport with the RS-232 factory settings from the driver docstring
(driver.py:19-20) and constructs ``JulaboCirculator(transport, command_delay_s=...)``.
This factory does the same through ``labmcp.transports.open_transport``; a ``serial://``
address also accepts query-string overrides.  The upstream package is imported only
when the hardware backend is constructed; the gate never imports this module.
"""


def connect(address, command_delay_s=0.25, **options):
    """Open the transport and return the upstream JulaboCirculator object.

    ``address`` is a labmcp transport address such as ``serial://COM3`` or
    ``tcp://192.168.1.80:4001``.  ``command_delay_s`` is the pause after an OUT
    command before the status query (the upstream server default is 0.25 s).
    """
    from labmcp.transports import open_transport
    from labmcp_julabo.driver import JulaboCirculator

    defaults = {
        "baudrate": 4800,
        "bytesize": 7,
        "parity": "E",
        "stopbits": 1,
        "rtscts": False,
        "read_termination": "\r\n",
        "write_termination": "\r",
        "timeout": 3.0,
    }
    defaults.update(options)
    transport = open_transport(address, **defaults)
    return JulaboCirculator(transport, command_delay_s=float(command_delay_s))
