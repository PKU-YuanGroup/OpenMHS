"""Hardware backend: opens a CryoCon temperature controller through the connio connection factory.

Used only with backend="hardware" and allow_hardware=True, an operator decision, and never by the acceptance gate
(which runs the fake backend and never imports this module).  This package is read-only and R0, so the loader's
refusal of an unreviewed model-written hardware backend (R2 and R3 only) does not apply here; this module must not
claim it.  The hardware path was never opened by this work; use it only with a person at the instrument.

The upstream tango server builds the connection with ``connection_for_url(url, concurrency="async", ...)`` and
constructs ``CryoCon(conn, channels=..., loops=...)`` (cryocon/tango/server/cryocon.py:113-125 and
cryocon/tango/server/cryocon.py:146-148).  On an async connection the member descriptors return coroutines, which
is what the driver awaits (cryocon/cryocon.py:297-305).  The README's async example uses the same class over
``sockio.aio.TCP`` (README.md:48-54).

Options: ``url`` (required) is a URL connio's ``connection_for_url`` understands, for example ``tcp://host:port``
or a serial URL; ``channels`` and ``loops`` are passed to the ``CryoCon`` constructor only when given (its
constructor defaults are at cryocon/cryocon.py:246); ``channel`` and ``loop`` select which channel and loop the
direct driver reads and are consumed here; every other option goes to ``connection_for_url``.
"""


def connect(url, channel=None, loop=None, channels=None, loops=None, **options):
    from connio import connection_for_url
    from cryocon import CryoCon

    connection_options = {"concurrency": "async"}
    connection_options.update(options)
    connection = connection_for_url(url, **connection_options)
    device_options = {}
    if channels is not None:
        device_options["channels"] = channels
    if loops is not None:
        device_options["loops"] = loops
    return CryoCon(connection, **device_options)
