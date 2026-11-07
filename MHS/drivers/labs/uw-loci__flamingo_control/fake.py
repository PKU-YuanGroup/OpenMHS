"""Fake backend of the Flamingo stage driver: an in-memory stand-in for PositionController.

Gate G7: every public method defined here exists on
``py2flamingo.controllers.position_controller:PositionController``.  The driver reaches only
``get_current_position``, ``get_home_position``, ``set_home_position``, ``is_position_within_bounds``,
``move_to_position``, ``emergency_stop``, ``clear_emergency_stop`` and the ``connection`` attribute that the upstream
``__init__`` assigns (position_controller.py:63, 98-99).  The fake keeps the same units as the upstream Position
model: X, Y and Z in millimetres and R in degrees.

The starting coordinates below are test data, not facts about any stage (each is marked ``# placeholder``).  The
fake moves immediately and does not model the upstream's asynchronous motion-complete tracker or its movement lock;
it is an in-memory stand-in, not a recording.  Nothing here talks to a device.
"""


class _Point:
    """The x, y, z, r attributes that the upstream Position dataclass carries."""

    __slots__ = ("x", "y", "z", "r")

    def __init__(self, x, y, z, r):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)
        self.r = float(r)


class _FakeConnection:
    """The connection object a real controller owns; the driver only disconnects it."""

    def __init__(self):
        self.connected = True

    def disconnect(self):
        self.connected = False


class FakeFlamingoControl:
    def __init__(self, **_options):
        self.connection = _FakeConnection()
        # Placeholders: the first four are the tracked position, the second four are the stored home position.
        self._position = _Point(0.0, 0.0, 0.0, 0.0)          # placeholder start position
        self._home = _Point(5.0, 5.0, 5.0, 45.0)             # placeholder home position
        self._emergency_stop_active = False
        # Placeholders: wide test limits for the fake, not the limits of a real stage.
        self._limits = {
            "x": {"min": -1000.0, "max": 1000.0},
            "y": {"min": -1000.0, "max": 1000.0},
            "z": {"min": -1000.0, "max": 1000.0},
            "r": {"min": -720.0, "max": 720.0},
        }

    def get_current_position(self):
        return _Point(self._position.x, self._position.y, self._position.z, self._position.r)

    def get_home_position(self):
        return _Point(self._home.x, self._home.y, self._home.z, self._home.r)

    def set_home_position(self, position):
        valid, errors = self.is_position_within_bounds(position)
        if not valid:
            raise ValueError("Cannot set home position outside stage limits:\n" + "\n".join(errors))
        self._home = _Point(position.x, position.y, position.z, position.r)

    def is_position_within_bounds(self, position):
        errors = []
        for axis, value in (("x", position.x), ("y", position.y), ("z", position.z), ("r", position.r)):
            limit = self._limits[axis]
            if not (limit["min"] <= value <= limit["max"]):
                errors.append(f"{axis.upper()}={value} outside limits [{limit['min']}, {limit['max']}]")
        return (len(errors) == 0, errors)

    def move_to_position(self, position, validate=True):
        if self._emergency_stop_active:
            raise RuntimeError("Movement blocked - emergency stop active. Clear emergency stop first.")
        if validate:
            position = _Point(
                min(max(position.x, self._limits["x"]["min"]), self._limits["x"]["max"]),
                min(max(position.y, self._limits["y"]["min"]), self._limits["y"]["max"]),
                min(max(position.z, self._limits["z"]["min"]), self._limits["z"]["max"]),
                min(max(position.r, self._limits["r"]["min"]), self._limits["r"]["max"]),
            )
        self._position = _Point(position.x, position.y, position.z, position.r)

    def emergency_stop(self):
        self._emergency_stop_active = True

    def clear_emergency_stop(self):
        self._emergency_stop_active = False
