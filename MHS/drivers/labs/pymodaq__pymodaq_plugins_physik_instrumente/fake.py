"""Fake backend of the PI GCS2 driver: an in-memory stand-in for the upstream PIWrapper.

Gate G7: every public member defined here is a member of
``pymodaq_plugins_physik_instrumente.hardware.pi_wrapper:PIWrapper``.  The wrapper's ``axis_names`` property reads
the controller's ``axes`` list (pi_wrapper.py:84-87); this fake keeps the same names and returns the same shapes.
The values below are test data, not facts about a device, and each is marked ``# placeholder``.  Nothing here talks
to a controller, and no upstream code is imported.
"""


class FakePIWrapper:
    """An in-memory two-axis GCS2 controller with the public surface of PIWrapper."""

    def __init__(self, **_options):
        self._axes = ["1", "2"]                     # placeholder: axis names of the stand-in controller
        self._units = ["um", "um"]                  # placeholder: units the stand-in controller reports
        self._positions = {"1": 12.5, "2": -3.0}    # placeholder: start positions in those units
        self._referenced = {"1": True, "2": False}  # placeholder: referenced state at start
        self._servo = {"1": True, "2": False}       # placeholder: closed-loop state at start
        self._limits = {"1": (0.0, 100.0),          # placeholder: stand-in travel range
                        "2": (-50.0, 50.0)}         # placeholder: stand-in travel range
        self._identity = "fake PI GCS2 controller"  # placeholder: canned identity string
        self._stopped = False
        self._closed = False

    @property
    def axis_names(self):
        return list(self._axes)

    def identify(self):
        return self._identity

    def get_axis_units(self, default="mm"):
        return list(self._units)

    def get_axis_position(self, axis_name):
        return float(self._positions[axis_name])

    def is_referenced(self, axis_name):
        return bool(self._referenced[axis_name])

    def get_servo(self, axis_name):
        return bool(self._servo[axis_name])

    def get_axis_limits(self, axis_name):
        return tuple(float(value) for value in self._limits[axis_name])

    def set_referencing(self, axes):
        if not isinstance(axes, list):
            axes = [axes]
        for axis in axes:
            self._referenced[axis] = True

    def set_servo(self, axis, enable_servo=True):
        self._servo[axis] = bool(enable_servo)

    def move_absolute(self, axis_name, position):
        self._positions[axis_name] = float(position)
        self._stopped = False

    def move_relative(self, axis_name, position):
        self._positions[axis_name] = float(self._positions[axis_name]) + float(position)
        self._stopped = False

    def move_home(self, axis_name):
        self._positions[axis_name] = 0.0            # placeholder: the stand-in home position
        self._referenced[axis_name] = True
        self._stopped = False

    def stop(self):
        self._stopped = True

    def close(self):
        self._closed = True
