"""Hardware backend: opens the CHEMYX pump through the upstream ``Connection`` object over pyserial.

Used only with ``backend="hardware"`` and ``allow_hardware=True`` (an operator decision).  The acceptance gate runs
the fake backend and never imports this module or the upstream clone.  This package is model-authored and
unreviewed; it is R2, so the loader refuses its hardware backend until a human sets ``reviewed_by`` in
driver.lock.json.

The upstream examples import the serial module as ``from core import connect`` and put the ``python_dist`` package
directory next to the run script (singlestep.py:15, documentation/instructions/python_instructions.md:15), so an
operator must put the clone's ``python_dist/CHEMYX_python`` directory on PYTHONPATH before using this backend.

Options of the backend are the upstream constructor's: ``port`` (for example ``/dev/tty.usbserial-10``), ``baudrate``
(must match the pump's System Settings, connect.py:56-57), ``multipump`` (default False) and ``verbose`` (default
False).
"""


def connect(port, baudrate, multipump=False, verbose=False):
    """Open the upstream serial connection and return it (Connection.openConnection is called here)."""
    from core import connect as core_connect

    connection = core_connect.Connection(port=port, baudrate=baudrate, multipump=multipump, verbose=verbose)
    connection.openConnection()
    return connection
