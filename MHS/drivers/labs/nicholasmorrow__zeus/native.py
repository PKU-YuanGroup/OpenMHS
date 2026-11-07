"""Hardware backend: opens one ZEUS module through the upstream ``zeus.ZeusModule``.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed, and it is R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json (the loader does this at R2 and R3 only; an R0 or R1 package must not claim it).  The acceptance gate
runs the fake backend and never imports this module or the upstream package.

The upstream class hard-codes the SocketCAN interface ``socketcan_ctypes`` on channel ``can0`` (``zeus.py:506-511``)
and imports python-can at module import time (``zeus.py:1``).  The operator must therefore install python-can, bring
the USB2CAN interface up with the clone's ``init_can.sh`` (``README:1``) and make the clone importable, for example
with PYTHONPATH pointing at the clone root.  The upstream ``setup.py`` and ``requirements.txt`` are empty, so
``pip install .`` alone does not install the package or python-can.

The hardware path was never run.  The upstream clone is Python 2-era in places: ``sendDataObject`` calls
``data.encode('hex')`` (``zeus.py:468``) and constructs ``can.Message(extended_id=False, ...)``
(``zeus.py:469-472``), both of which modern Python 3/python-can no longer accept.  A reviewer must resolve that
before the hardware backend is used.

Options: ``module_id`` (required; the upstream module id 1 to 31), ``init_module`` (default True) and
``auto_response`` (default True) are passed to ``ZeusModule``.
"""


def connect(module_id, init_module=True, auto_response=True, **_options):
    import zeus

    return zeus.ZeusModule(module_id, init_module=init_module, auto_response=auto_response)
