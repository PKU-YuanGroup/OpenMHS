"""Hardware backend: opens a JULABO circulator through the upstream asyncio connection.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed, and it is R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json (the loader does this at R2 and R3 only; an R0 or R1 package must not claim it).  The
acceptance gate runs the fake backend and never imports this module or the julabo package.

Options of the backend: ``url`` (required) is a URL ``julabo.connection_for_url`` understands -- ``tcp://host:port``,
``serial:///dev/ttyS0``, ``rfc2217://host:port`` or ``serial-tcp://host:port`` (julabo/connection.py:43-70) -- and any
other option goes to ``connection_for_url``; for a serial line the tango server passes ``baudrate`` (default 9600),
``bytesize`` (8) and ``parity`` ("N") (julabo/tango/server/device.py:17-19, 26-28).  The connection is asyncio, the
default of ``connection_for_url`` (julabo/connection.py:45), so the device is the coroutine-based JulaboCF.
"""


async def connect(url, **options):
    from julabo import JulaboCF, connection_for_url

    connection = connection_for_url(url, **options)
    device = JulaboCF(connection)
    await connection.open()                 # as in the upstream README example (README.md:38-40)
    return device
