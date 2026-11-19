"""Hardware backend: constructs the upstream ``levylabinst.MCLockin:MCLockin`` instrument.

Used only with ``backend="hardware"`` and ``allow_hardware=True`` (an operator decision); the acceptance gate runs the
fake backend and never imports this module or the ``levylabinst`` package.

Options:

* ``address`` (required) is the ZMQ server address of the lock-in, e.g. ``tcp://localhost:29170``
  (levylabinst/MCLockin.py:24-27).
* ``config`` (required) is the deployment's channel configuration mapping each label to its lead number, e.g.
  ``{"source": 1, "drain": 2, "gate": 3}`` (levylabinst/MCLockin.py:31-36); the served field names are the upstream
  ``<label>_<X|Y|R|Theta|Mean>`` names built from it (lines 79-85).
* ``name`` is the local QCoDeS instrument name (default ``mclockin``).
* any further keyword goes to the upstream constructor (``timeout``, ``metadata``, ...).

The upstream repository has no packaging: its ``setup.py`` is empty and its modules import ``qcodes``, ``zmq``,
``numpy`` and ``tkinter``.  A hardware deployment therefore has to provide those dependencies and put the pinned clone
on ``PYTHONPATH`` before this factory is called; the package does not install it.
"""


def connect(address, config, name="mclockin", **options):
    from levylabinst.MCLockin import MCLockin

    return MCLockin(name=name, address=address, config=dict(config), **options)
