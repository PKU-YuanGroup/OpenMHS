"""TH-1 controller over its USB serial device (synthetic vendor SDK of the OpenMHS tutorial)."""

import io  # only the hardware backend ever imports this module

SETPOINT_RANGE_C = (5.0, 80.0)
#: Zone trim limits in kelvin: front -5..5, back -3..3.
TRIM_LIMITS_K = ((-5.0, 5.0), (-3.0, 3.0))


class Controller:
    """One TH-1 controller."""

    def __init__(self, port="/dev/ttyACM0"):
        self.port = port
        self._link = io.open(port, "r+b", buffering=0)

    def _ask(self, command):
        self._link.write((command + "\r").encode("ascii"))
        return self._link.readline().decode("ascii").strip()

    def read_temperature(self):
        return float(self._ask("TEMP?"))

    def get_setpoint(self):
        return float(self._ask("SP?"))

    def set_setpoint(self, celsius):
        self._ask(f"SP {celsius:.1f}")

    def set_zone_trim(self, front_k, back_k):
        self._ask(f"TRIM {front_k:.2f} {back_k:.2f}")

    def set_fan_speed(self, rpm):
        self._ask(f"FAN {int(rpm)}")

    def heater_off(self):
        self._ask("HEAT OFF")

    def emergency_off(self):
        """Cut heater power and latch the controller (released from the front panel)."""
        self._ask("EOFF")

    def lid_is_closed(self):
        return self._ask("LID?") == "CLOSED"

    def close(self):
        self._link.close()
