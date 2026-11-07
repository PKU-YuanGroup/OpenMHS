"""Fake backend of the ISEG HV supply driver: plain attributes instead of the serial line.

Gate G7: every public method here exists on ``basil.HL.iseg_hv:IsegHV`` in the clone.  The numbers are
placeholder values of a configured module, not facts of the device: the channel count, the ramp speed and the
voltages of a real unit come from its init file and its environment.
"""


class FakeIsegHV:
    def __init__(self, **_options):
        self.n_channel = 8          # placeholder: a configured module has some channel count
        self._channel = 1           # placeholder
        self._voltage = 0.0         # placeholder
        self._current = 0.0         # placeholder
        # placeholder; a test may start the fake at a non-zero target to watch the e-stop zero it
        self._source_voltage = float(_options.get("source_voltage", 0.0))
        self._ramp_speed = 100      # placeholder
        self._answer_delay = 1      # placeholder
        self._autostart = True      # placeholder

    def get_voltage(self):
        return self._voltage

    def get_current(self):
        return self._current

    def get_source_voltage(self):
        return self._source_voltage

    def set_voltage(self, voltage):
        self._source_voltage = float(voltage)

    def get_ramp_speed(self):
        return self._ramp_speed

    def set_ramp_speed(self, rs):
        if not 1 <= rs <= 255:
            raise ValueError("Ramp speed must be 1 <= ramp_speed <= 255 V/s")
        self._ramp_speed = int(rs)

    def get_answer_delay(self):
        return self._answer_delay

    def set_answer_delay(self, bt):
        if not 1 <= bt <= 255:
            raise ValueError("answer delay must be 1 <= answer_delay <= 255 ms")
        self._answer_delay = int(bt)

    def get_autostart(self):
        return self._autostart

    def set_autostart(self, state):
        self._autostart = bool(state)

    def get_current_channel(self):
        return self._channel

    def set_current_channel(self, ch):
        if not 1 <= ch <= self.n_channel:
            raise ValueError(f"Channel number must be 1 <= channel <= {self.n_channel}")
        self._channel = ch

    def off(self):
        self.set_voltage(0)
