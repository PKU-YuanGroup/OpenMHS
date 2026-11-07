"""Fake backend of the CrazyFlie driver: an in-memory stand-in for CrazyFlyt.drone_controller:DroneController.

Gate G7: every public member defined here is a method of ``DroneController``
(CrazyFlyt/drone_controller.py at the pinned commit 85d99afa21cb5b90fd130cd480f0589a2b700b58), with the upstream
parameter names.  The fake stores the setpoint and the mode flag exactly as the upstream methods do, and it keeps a
list of the calls it received so a test can see what reached the "drone".

All numbers in this file are test data, not device facts.  The fake does not fly: it does not integrate a trajectory,
it does not update ``position_estimate``, and it does not open a radio link.  ``position_estimate`` stays at the
upstream constructor's zero array.
"""


class FakeDroneController:
    """An in-memory DroneController: ``start``/``stop`` toggle ``running`` and the setters store their value."""

    def __init__(self, URI="radio://0/10/2M/E7E7E7E7E0", in_swarm=False):  # placeholder URI
        self._uri = URI
        self._in_swarm = in_swarm
        self.period = 1 / 40.0                                  # placeholder: the upstream control period
        self.running = False
        self.flow_deck_attached = False
        self.position_estimate = [0.0, 0.0, 0.0, 0.0]           # placeholder: four zero values
        self.setpoint = [0.0, 0.0, 0.0, 0.0]                    # placeholder: four zero values
        self.pos_control = False
        self._calls = []

    # -- members of DroneController ---------------------------------------------------------------
    def start(self):
        self._calls.append(("start", ()))
        self.running = True

    def stop(self):
        self._calls.append(("stop", ()))
        self.running = False

    def end(self):
        self._calls.append(("end", ()))
        self.running = False

    def set_pos_control(self, setting):
        self._calls.append(("set_pos_control", (bool(setting),)))
        self.pos_control = bool(setting)

    def set_setpoint(self, setpoint):
        values = [float(value) for value in setpoint]
        self._calls.append(("set_setpoint", (list(values),)))
        self.setpoint = values

    # -- hooks for test_driver.py (not DroneController members, never used by the driver) ---------
    def _called(self, name):
        return [args for call_name, args in self._calls if call_name == name]

    def _move_position_estimate(self, x, y, z, yaw):
        """Place the reported state estimate (test data for a read)."""
        self.position_estimate = [float(x), float(y), float(z), float(yaw)]
