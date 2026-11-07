"""Fake backend of the tutorial thermostat.

Gate G7: every public method here exists on thermo.controller:Controller
(vendor/thermo/controller.py); the state lives in plain attributes.
"""


class FakeController:
    def __init__(self, **_options):
        self.temperature = 21.0
        self.setpoint = 20.0
        self.trim = (0.0, 0.0)
        self.fan = 0
        self.heating = True
        self.lid = True

    def read_temperature(self):
        return self.temperature

    def get_setpoint(self):
        return self.setpoint

    def set_setpoint(self, celsius):
        self.setpoint = float(celsius)

    def set_zone_trim(self, front_k, back_k):
        self.trim = (float(front_k), float(back_k))

    def set_fan_speed(self, rpm):
        self.fan = int(rpm)

    def heater_off(self):
        self.heating = False

    def emergency_off(self):
        self.heating = False

    def lid_is_closed(self):
        return self.lid
