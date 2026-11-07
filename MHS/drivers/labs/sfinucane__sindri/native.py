"""Hardware backend: opens a Tektronix BERTScope through the upstream lantz TCP driver.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  ``host`` is the instrument's
network address and ``port`` is its SCPI TCP port; both are required, because the clone states no default for either.
Any other keyword option is forwarded to the upstream constructor.  The upstream class is a
``lantz.network:TCPDriver`` (sindri/tektronix/bertscope.py:35, 464-472), so the factory passes the host and port to
that constructor.

This package is model-authored and unreviewed and declares R1, so the loader does not mechanically refuse its
hardware backend (it does so only for a model-authored R2 or R3 package).  Do not start the hardware backend until a
human sets ``reviewed_by`` in driver.lock.json.  The upstream package is not installed on this machine: this factory
was never imported or run, and nothing in this package ran on an instrument.  The acceptance gate runs the fake
backend and never imports this module.
"""


def connect(host, port, **options):
    from sindri.tektronix.bertscope import BERTScope_TCP

    return BERTScope_TCP(host, int(port), **options)
