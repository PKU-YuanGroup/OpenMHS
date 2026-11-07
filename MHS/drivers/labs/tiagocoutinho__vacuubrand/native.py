"""Hardware backend: opens a Vacuubrand DCP 3000 through the upstream connection object.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored and
unreviewed at R1: the loader refuses the hardware backend of a model-authored package only at R2 and R3, so this R1
package does not rely on that refusal.  The acceptance gate runs the fake backend and never imports this module or
the vacuubrand package.

The upstream README connects through ``connection_for_url('serial:///dev/ttyS0')`` and wraps the result in
``DCP3000`` (README.md:34-48).  The Tango server passes ``concurrency="async"`` and adds ``baudrate``, ``bytesize``
and ``parity`` for serial and rfc2217 URLs (vacuubrand/tango/server/dcp3000.py:41-55); this factory always requests
the asyncio connection because the driver awaits the upstream methods (protocol.py:179-182).  The Tango server
device properties default to 9600 baud, 8 data bits and no parity (tango/server/dcp3000.py:34-37), and the README
documents 19200 baud for its serial line (README.md:57-60); this module sets neither, so the site passes the settings
of its own line.  Every option other than ``url`` goes to ``connection_for_url``.
"""


async def connect(url, **options):
    from connio import connection_for_url
    from vacuubrand.dcp3000 import DCP3000

    options["concurrency"] = "async"
    connection = connection_for_url(url, **options)
    return DCP3000(connection)
