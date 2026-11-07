"""Fake x-axis of the liquid-handling robot: an in-memory stand-in for the upstream Axis object.

The fake implements only the attributes of ``lhrhost.robot.x_axis:Axis`` that this driver uses: the two position
properties (both coroutines, as they are upstream) and the two coroutine methods ``move_by_physical_delta`` and
``set_motor_limits``.  The sensor position and the physical position move together with a 1:1 calibration: that is
test data, not a calibration of any assembled robot.  Nothing here talks to an Arduino.
"""


class FakeXAxis:
    def __init__(self, **_options):
        self._sensor_position = 0.0        # placeholder
        self._physical_position = 0.0      # placeholder
        self.motor_limits = (0.0, 0.0, 0.0, 0.0)   # placeholder: forwards max/min, backwards max/min

    @property
    async def sensor_position(self):
        """Return the fake raw sensor position."""
        return self._sensor_position

    @property
    async def physical_position(self):
        """Return the fake physical position."""
        return self._physical_position

    async def move_by_physical_delta(self, physical_delta):
        """Move both fake positions by the displacement and return it."""
        self._physical_position += physical_delta
        self._sensor_position += physical_delta    # placeholder: the fake uses a 1:1 calibration
        return physical_delta

    async def set_motor_limits(
        self, forwards_max=None, forwards_min=None, backwards_max=None, backwards_min=None
    ):
        """Store the duty limits the driver sets and return the previous values."""
        previous = self.motor_limits
        values = list(previous)
        for index, value in enumerate((forwards_max, forwards_min, backwards_max, backwards_min)):
            if value is not None:
                values[index] = value
        self.motor_limits = tuple(values)
        return previous
