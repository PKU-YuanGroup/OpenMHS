"""Hardware backend: open a Sartorius balance through the upstream ``open_device`` factory.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  The upstream factory opens the
serial transport, resolves the protocol and returns the Balance facade (src/sartoriuslib/devices/factory.py:58-68);
the facade is asynchronous, so this factory is asynchronous too.

This package is model-authored and unreviewed, and it is R1: the loader refuses the hardware backend of an
unreviewed model-written package only at R2 and R3, so an operator can select it here.  The acceptance gate runs the
fake backend and never imports this module, the upstream package or anyserial.  Nothing here ran on hardware.

``port`` is required.  ``protocol`` accepts the upstream values ``"xbpi"``, ``"sbi"`` or ``"auto"``; the defaults for
baudrate, parity and stopbits are the upstream SerialSettings defaults (9600, odd, one), and an operator must pass
the framing its own balance is configured for.  No default here is a statement that the instrument uses it.
"""


async def connect(port, *, protocol="auto", baudrate=None, parity=None, stopbits=None, timeout=1.0, **options):
    """Open ``port`` and return the upstream Balance."""
    from sartoriuslib import open_device
    from sartoriuslib.protocol import ProtocolKind
    from sartoriuslib.transport.base import SerialSettings

    settings = None
    if baudrate is not None or parity is not None or stopbits is not None:
        fields = {"port": port}
        if baudrate is not None:
            fields["baudrate"] = int(baudrate)
        if parity is not None:
            fields["parity"] = parity
        if stopbits is not None:
            fields["stopbits"] = stopbits
        settings = SerialSettings(**fields, **options)
    return await open_device(port, protocol=ProtocolKind(protocol), serial_settings=settings, timeout=float(timeout))
