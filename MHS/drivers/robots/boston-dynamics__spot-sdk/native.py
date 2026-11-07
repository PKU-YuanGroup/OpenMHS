"""Hardware backend for the Spot driver: opens bosdyn.client.robot:Robot against a robot on the network.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed, and it is R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json (the loader does this at R2 and R3 only).  The acceptance gate runs the fake backend and never
imports this module or the bosdyn package; nothing here ran on a robot.

Options: ``hostname`` is the network-resolvable address of the robot (``create_robot`` takes it,
python/bosdyn-client/src/bosdyn/client/sdk.py:213-217).  ``username`` and ``password`` authenticate directly; when
they are omitted, ``bosdyn.client.util.authenticate`` uses a cached token or the environment
(python/bosdyn-client/src/bosdyn/client/util.py:58-94).  ``name`` is the optional local name of the robot.

The factory starts time sync and waits for it, because commands and state timestamps need a synchronized clock
(python/bosdyn-client/src/bosdyn/client/robot.py:540-556).  It acquires and keeps a body lease, because the power
commands are lease-protected.  It does not power the robot on.  The independent physical E-Stop button remains the
operator's protective function (docs/python/quickstart.md:379), and the robot's software E-Stop service must be
configured by an independent E-Stop client (docs/concepts/estop_service.md:11-19).
"""


def connect(hostname, username=None, password=None, name=None, **options):
    import bosdyn.client
    import bosdyn.client.lease
    import bosdyn.client.util

    if options:
        raise TypeError(f"unknown Spot backend options: {sorted(options)}")
    sdk = bosdyn.client.create_standard_sdk("MHS-Spot")
    robot = sdk.create_robot(hostname, name=name)
    if username is None:
        bosdyn.client.util.authenticate(robot)
    else:
        robot.authenticate(username, password)
    robot.start_time_sync()
    robot.time_sync.wait_for_sync()
    lease_client = robot.ensure_client(bosdyn.client.lease.LeaseClient.default_service_name)
    robot._mhs_lease_keep_alive = bosdyn.client.lease.LeaseKeepAlive(lease_client, must_acquire=True)
    return robot
