"""Hardware backend: opens a Crazyflie through the upstream CrazyFlyt DroneController.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored and
unreviewed, and it is R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json (the loader does this at R2 and R3 only; an R0 or R1 package must not claim it).  The acceptance gate
runs the fake backend and never imports this module or the CrazyFlyt package; nothing here ran on a drone.

Options of the backend: ``uri`` is the radio URI of the drone (the upstream example uses
``radio://0/10/2M/E7E7E7E7E3``, examples/fly_single.py:25).  ``DroneController`` treats it as required
(CrazyFlyt/drone_controller.py:22).  ``in_swarm`` is passed to the constructor (drone_controller.py:22); it only adds
a start-up delay when false (drone_controller.py:77-78).
"""


def connect(uri=None, in_swarm=False):
    from CrazyFlyt.drone_controller import DroneController

    if not isinstance(uri, str) or not uri.strip():
        raise RuntimeError("the CrazyFlyt DroneController needs the drone URI as the 'uri' backend option")
    return DroneController(uri, in_swarm=in_swarm)
