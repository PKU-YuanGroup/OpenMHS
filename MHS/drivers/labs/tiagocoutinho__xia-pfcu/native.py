"""Hardware backend: opens an XIA PFCU through the upstream connio connection.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored and
unreviewed, and it is R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json (the loader does this at R2 and R3 only; an R0 or R1 package must not claim it).  The acceptance gate
runs the fake backend and never imports this module or the xia_pfcu package.

``url`` (required) is a URL ``connio.connection_for_url`` understands: a serial line or an RFC 2217 / raw TCP bridge
(README.md:12-16).  The connection is opened with ``concurrency="syncio"``, the mode the upstream README uses for the
PFCU object (README.md:122-124), and with the reply terminator ``b";\\r\\n"`` the upstream tango server configures
(xia_pfcu/tango/server/pfcu.py:21-29).  ``module`` is the PFCU module address or ``ALL`` for the broadcast module
(xia_pfcu/protocol.py:25-27); the remaining options go to ``connection_for_url`` (for a serial line the tango server
passes ``baudrate``, ``bytesize`` and ``parity``; xia_pfcu/tango/server/pfcu.py:15-17, 24-27).  A site that needs
another baud rate passes ``baudrate``; this factory assumes no fixed value.
"""


def connect(url, module="ALL", **options):
    """Open the PFCU on ``url`` and return the upstream ``xia_pfcu.pfcu:PFCU`` object."""
    from connio import connection_for_url
    from xia_pfcu import PFCU

    options.setdefault("concurrency", "syncio")
    options.setdefault("eol", b";\r\n")
    connection = connection_for_url(url, **options)
    connection.open()                       # README.md:124 opens the serial connection explicitly
    return PFCU(connection, module=module)
