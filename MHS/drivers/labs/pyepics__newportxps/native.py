"""Hardware backend: opens a Newport XPS controller through the upstream class.

Used only with ``backend="hardware"`` and ``allow_hardware=True`` (an operator
decision).  The upstream ``NewportXPS.__init__`` opens the TCP connection, logs
in and calls ``read_systemini`` immediately
(newportxps/newportxps.py:53-84, 138-160), so ``connect`` returns a controller
that has already read its ``system.ini``.

Options of the backend:

* ``host`` (required) is the controller's host name or IP address.
* ``username``, ``password``, ``port``, ``timeout``, ``extra_triggers`` and
  ``outputs`` are passed to ``NewportXPS`` and keep its defaults
  (newportxps/newportxps.py:53-58).  They configure the transport; they are not
  device bounds.
* ``stage`` and ``group`` are the driver's binding options, not constructor
  arguments.  The upstream ``group`` argument names the trajectory (PVT) group
  and calls ``set_trajectory_group``, which accepts only a multiple-axis group
  (newportxps/newportxps.py:444-496); it is not the group this driver enables,
  homes or aborts.  This factory therefore accepts both options and does not
  pass them to the constructor.  The driver selects the stage and group after
  the connection from the controller's own ``stages`` and ``groups``.

The low-level transport sets a 3600 s socket timeout before each command
(newportxps/XPS_C8_drivers.py:90-94), so a lost network path can block a call
for a long time; a hardware deployment must supervise the link.

This package is model-authored and unreviewed (``driver.lock.json``
``reviewed_by`` is null).  It is R1: the loader refuses the hardware backend of
an unreviewed model-written package only at R2 and R3, so at R1 that loader
rule does not protect this driver.  A human must review it and sign
``reviewed_by`` before any hardware use.  The acceptance gate runs the fake
backend and never imports this module or the newportxps package.
"""


def connect(host, stage=None, group=None, **options):
    """Connect to the controller at ``host``; ``stage``/``group`` are binding options."""
    from newportxps.newportxps import NewportXPS

    return NewportXPS(host, **options)
