"""Hardware backend: opens a GE Druck Pace controller through the upstream connection object.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is
model-authored and unreviewed, and it is R2: the loader refuses its hardware backend until a human
sets ``reviewed_by`` in driver.lock.json (the loader does this at R2 and R3 only; an R0 or R1
package must not claim it).  The acceptance gate runs the fake backend and never imports this
module or the gepace package.

Options of the backend: ``url`` (required) is a URL ``connio.connection_for_url`` understands, such
as ``tcp://host:port``, ``serial:///dev/ttyS0`` or ``rfc2217://host:port``; every other option goes
to ``connection_for_url``.  The upstream tango server builds the connection with
``concurrency="async"`` and passes it to ``Pace`` without an explicit open
(gepace/tango/server/pace.py:54-68); on an asyncio connection the Pace members are coroutine
functions (gepace/pace.py:329-334), which this driver awaits, so the async concurrency is forced.
``modules`` is passed to the Pace constructor (the upstream constructor default is ``(1, 2)``,
gepace/pace.py:329); the driver serves module 1, so it must be included.
"""


def connect(url, **options):
    from connio import connection_for_url
    from gepace.pace import Pace

    options["concurrency"] = "async"
    modules = options.pop("modules", (1, 2))
    connection = connection_for_url(url, **options)
    return Pace(connection, modules=modules)
