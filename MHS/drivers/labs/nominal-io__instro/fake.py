"""Fake backend of the Siglent SPD3303 driver: an in-memory stand-in for the upstream VISA class.

Gate G7: every public method defined here exists on
``instro.psu.drivers.siglent_spd3303:SiglentSPD3303`` in the clone
(``instro/psu/drivers/siglent_spd3303.py:11-158``).  The driver reaches no other attribute of the backend.
The upstream class sends one SCPI command per method and returns a float, a bool or the decoded status dict;
this fake keeps the same method signatures and return shapes.

Every starting value, measured value and status string below is test data, not a statement about a device;
each is marked ``# placeholder``.  The fake models a single resistive load per channel so that a measurement
moves with the set points; that is a placeholder model, not a calibration.  Nothing here talks to a device.
"""


class FakeSiglentSPD3303:
    def __init__(self, **_options):
        # all values below are placeholders (test data), not device facts or limits
        self._open = False
        self._voltage_setpoint = [0.0, 0.0]      # placeholder
        self._current_setpoint = [0.0, 0.0]      # placeholder
        self._output_enabled = [False, False]    # placeholder
        self._load_ohms = 1000.0                 # placeholder
        self._psu_mode = "INDEPENDENT"           # placeholder

    def _index(self, channel: int) -> int:
        if channel not in (1, 2):
            raise ValueError("SiglentSPD3303 channel must be 1 or 2 for a programmed output")
        return channel - 1

    def open(self) -> None:
        self._open = True

    def close(self) -> None:
        self._output_enabled = [False, False]    # placeholder: close leaves both outputs off
        self._open = False

    def set_voltage(self, voltage: float, channel: int) -> None:
        self._voltage_setpoint[self._index(channel)] = round(float(voltage), 3)

    def get_voltage(self, channel: int) -> float:
        index = self._index(channel)
        if not self._output_enabled[index]:
            return 0.0                            # placeholder: no output, no measured voltage
        return self._voltage_setpoint[index]

    def set_current_limit(self, current_limit: float, channel: int) -> None:
        self._current_setpoint[self._index(channel)] = round(float(current_limit), 3)

    def get_current(self, channel: int) -> float:
        index = self._index(channel)
        if not self._output_enabled[index]:
            return 0.0                            # placeholder: no output, no measured current
        drawn = self._voltage_setpoint[index] / self._load_ohms
        return round(min(drawn, self._current_setpoint[index]), 3)

    def get_voltage_setpoint(self, channel: int) -> float:
        return self._voltage_setpoint[self._index(channel)]

    def get_current_setpoint(self, channel: int) -> float:
        return self._current_setpoint[self._index(channel)]

    def output_enable(self, enable: bool, channel: int) -> None:
        self._output_enabled[self._index(channel)] = bool(enable)

    def get_output_status(self, channel: int) -> bool:
        return self._output_enabled[self._index(channel)]

    def query_status(self) -> dict:
        # The upstream decoder returns CC/CV, the tracking mode and the two enable bits
        # (instro/psu/drivers/siglent_spd3303.py:151-158).
        modes = []
        for index in range(2):
            limited = (self._output_enabled[index]
                       and self._current_setpoint[index] > 0.0
                       and self.get_current(index + 1) >= self._current_setpoint[index])
            modes.append("CC" if limited else "CV")   # placeholder model of the regulation bit
        return {
            "ch1_mode": modes[0],
            "ch2_mode": modes[1],
            "psu_mode": self._psu_mode,
            "ch1_enable": self._output_enabled[0],
            "ch2_enable": self._output_enabled[1],
        }
