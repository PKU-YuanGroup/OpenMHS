"""Hardware backend: open the EA-PS 10060-170 through the upstream EAPowerSupply class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored,
unreviewed and R2: the loader refuses its hardware backend until a human sets reviewed_by in driver.lock.json.
The acceptance gate runs the fake backend and never imports this module or the upstream package.

Options: ``port`` (required) is the serial port of the source, for example ``COM4`` or ``/dev/ttyACM0``.
``baud``, ``serial_timeout``, ``write_delay_ms`` and ``query_delay_ms`` override the corresponding BridgeConfig
fields; when omitted the upstream defaults apply.  ``clone`` is the path of the pv-emulator clone root, inserted
into ``sys.path`` so that ``comm.bridge`` and ``config.hardware`` import; alternatively put that root on
PYTHONPATH.  The upstream opens the serial port and sends ``*IDN?`` in EAPowerSupply.open(); after that the factory
enables digital remote control with ``SYST:LOCK ON``, the command SCPIController.connect() uses (comm/scpi.py:128).
"""


def connect(port, *, baud=None, serial_timeout=None, write_delay_ms=None, query_delay_ms=None, clone=None,
            **_options):
    if not isinstance(port, str) or not port.strip():
        raise ValueError("port is required: the serial port of the EA-PS 10060-170 source")
    if clone:
        import sys

        if clone not in sys.path:
            sys.path.insert(0, clone)
    from comm.bridge import BridgeConfig, EAPowerSupply

    cfg = BridgeConfig(serial_port=port.strip())
    if baud is not None:
        cfg.serial_baud = int(baud)
    if serial_timeout is not None:
        cfg.serial_timeout = float(serial_timeout)
    if write_delay_ms is not None:
        cfg.write_delay_ms = float(write_delay_ms)
    if query_delay_ms is not None:
        cfg.query_delay_ms = float(query_delay_ms)
    source = EAPowerSupply(cfg)
    source.open()
    source.write("SYST:LOCK ON")   # SCPIController.connect() does this before any profile command (comm/scpi.py:128)
    return source
