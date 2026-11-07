"""Fake backend of the Opentrons Temp Deck Gen 3 driver: an in-memory stand-in for ``test_utils:Tempdeck``.

Gate G7: every public method defined here exists on the upstream class ``Tempdeck`` in
``stm32-modules/tempdeck-gen3/scripts/test_utils.py``.  The methods return the values the same
M-code exchange returns upstream: ``get_temperatures`` is the M105.D tuple
``(plate1, plate2, heatsink)`` and ``get_thermal_power`` is the M103.D tuple
``(peltier current mA, fan RPM, peltier PWM, fan PWM)`` (``test_utils.py:229-239, 307-324``).  A write
changes the value its own read reports: ``set_fan_power`` updates the fan PWM of M103.D and
``deactivate`` clears it, as M18 does in the firmware (``thermal_task.hpp:233-246``).

The starting temperatures and the peltier and fan values are test data, not facts about a module, and
each is marked ``# placeholder``.  After ``set_temperature`` the fake sets the peltier PWM to a
placeholder proportional response to the target-minus-plate error (clamped to the documented -1 to 1
range), so the M104 target is observable in the M103.D peltier PWM the way the firmware's control loop
makes it observable; the real PID response is not modelled.  Nothing here talks to a device, and the
temperature does not move by itself: reading the state twice gives the same state.
"""


class FakeTempdeck:
    def __init__(self, **_options):
        self._plate_1 = 22.0       # placeholder
        self._plate_2 = 22.0       # placeholder
        self._heatsink = 24.0      # placeholder
        self._current = 0.0        # placeholder
        self._rpm = 0.0            # placeholder
        self._peltier_pwm = 0.0    # placeholder
        self._fan_pwm = 0.0        # placeholder
        self._target = None        # placeholder

    def get_temperatures(self):
        """M105.D: (plate1, plate2, heatsink), as the upstream get_temperatures returns them."""
        return self._plate_1, self._plate_2, self._heatsink

    def get_thermal_power(self):
        """M103.D: (peltier current mA, fan RPM, peltier PWM, fan PWM)."""
        return self._current, self._rpm, self._peltier_pwm, self._fan_pwm

    def set_fan_power(self, power=0):
        """M106 S<power>: the manual fan PWM, 0 to 1."""
        self._fan_pwm = float(power)

    def set_temperature(self, temp):
        """M104 S<temp>: store the target and show it in the peltier PWM (a placeholder response)."""
        self._target = float(temp)  # placeholder
        error = self._target - self._plate_1
        self._peltier_pwm = max(-1.0, min(1.0, error / 100.0))  # placeholder

    def deactivate(self):
        """M18: clear the target, disable the peltier and set fan power 0."""
        self._target = None
        self._peltier_pwm = 0.0
        self._fan_pwm = 0.0
