"""In-memory fake backend of the OpenLH driver.

Gate G7: every public method defined here exists on the upstream class named by ``native``
(``pyuf.uf.wrapper.swift_with_ultrasonic:SwiftWithUltrasonic``) or on its base ``SwiftAPI`` in
``pyuf/uf/wrapper/swift_api.py``: get_position, get_polar, get_servo_angle, get_ultrasonic, get_limit_switch,
get_is_moving, set_position, set_servo_angle, set_pump and set_gripper.  The fake keeps plain instance data and does
not define any other public member.

The starting position, polar coordinate, servo angles, ultrasonic distance and limit switch state are test data,
not facts; each is marked ``# placeholder``.  The clone has no simulator, mock or recorded session (its tests import
the real API and need the arm), so this is a small recording-style fake: a call returns a value and a write changes
the state that the matching read returns.  Nothing here talks to a device.
"""


class FakeSwiftWithUltrasonic:
    def __init__(self, **_options):
        #: Starting state of the fake; every number on these lines is a placeholder, not a device fact.
        self._position = [150.0, 0.0, 150.0]          # placeholder
        self._polar = [0.0, 150.0, 150.0]             # placeholder
        self._servo = [90.0, 90.0, 90.0, 90.0]        # placeholder
        self._ultrasonic = 30                          # placeholder
        self._limit_switch = False                     # placeholder
        self._moving = False                           # placeholder
        self._pump = False                             # placeholder
        self._gripper = False                          # placeholder
        self._calls = []

    # -- reads ------------------------------------------------------------------------------------------------
    def get_position(self):
        self._calls.append(("get_position", (), {}))
        return list(self._position)

    def get_polar(self):
        self._calls.append(("get_polar", (), {}))
        return list(self._polar)

    def get_servo_angle(self, servo_id=None):
        self._calls.append(("get_servo_angle", (servo_id,), {}))
        if servo_id is None:
            return list(self._servo)
        return float(self._servo[servo_id])

    def get_ultrasonic(self):
        self._calls.append(("get_ultrasonic", (), {}))
        return self._ultrasonic

    def get_limit_switch(self):
        self._calls.append(("get_limit_switch", (), {}))
        return self._limit_switch

    def get_is_moving(self):
        self._calls.append(("get_is_moving", (), {}))
        return self._moving

    # -- writes -------------------------------------------------------------------------------------------------
    def set_position(self, x=None, y=None, z=None,
                     speed=None, relative=False,
                     wait=False, timeout=10, e=None, change_x_by=0, change_y_by=0, change_z_by=0):
        self._calls.append(("set_position", (x, y, z), {"speed": speed, "relative": relative, "wait": wait,
                                                         "timeout": timeout, "e": e}))
        target = [x + change_x_by if x is not None else None,
                  y + change_y_by if y is not None else None,
                  z + change_z_by if z is not None else None]
        if relative:
            for index, value in enumerate(target):
                if value is not None:
                    self._position[index] += float(value)
        else:
            for index, value in enumerate(target):
                if value is not None:
                    self._position[index] = float(value)
        self._moving = False
        return True

    def set_servo_angle(self, servo_id, angle, wait=False, timeout=10):
        self._calls.append(("set_servo_angle", (servo_id, angle), {"wait": wait, "timeout": timeout}))
        self._servo[servo_id] = float(angle)
        self._moving = False
        return True

    def set_pump(self, on, timeout=None):
        self._calls.append(("set_pump", (bool(on),), {"timeout": timeout}))
        self._pump = bool(on)
        return True

    def set_gripper(self, catch, timeout=None):
        self._calls.append(("set_gripper", (bool(catch),), {"timeout": timeout}))
        self._gripper = bool(catch)
        return True
