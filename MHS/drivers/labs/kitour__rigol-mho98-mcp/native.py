"""Hardware backend of the RIGOL MHO98 driver: one upstream ``Session`` over PyVISA.

The gate never imports this module (it serves the fake backend), and no hardware is attached in
this package's acceptance run.  The operator installs the pinned upstream package with its own
``pip install .`` and provides the deployment configuration the upstream reads:

* USB: ``RIGOL_USB=1`` and, when several Rigol instruments are visible, ``RIGOL_USB_SERIAL``;
* LAN: ``RIGOL_IP=<instrument-address>`` when USB is not enabled.

The upstream opens the transport lazily on the first query (session.py:235-267) and validates the
MHO98 identity on ``idn()`` (session.py:324-338); this driver's ``setup`` calls ``idn()``.  The
operator must supply a finite positive ``timeout_ms``. The upstream default is ``None``
(session.py:23, 83-100), which selects an infinite VISA timeout; this factory refuses that default.
``output_dir``, ``lock_path`` and ``resource_manager`` are forwarded to ``Session``.
This package is model-authored and unreviewed;
no hardware run was performed.
"""


def connect(timeout_ms, **options):
    """Open the upstream MHO98 session and return it to the driver."""
    if isinstance(timeout_ms, bool) or not isinstance(timeout_ms, int) or timeout_ms <= 0:
        raise ValueError("hardware deployment requires an explicit finite positive timeout_ms")
    from rigol_mcp.mho98.session import Session

    return Session(timeout_ms=timeout_ms, **options)
