"""Fake backend of the ASI MS-2000-500-CP driver: an in-memory stand-in for the upstream Controller.

Gate G7: every public method defined here exists on ``asi_MS_2000_500_CP:Controller``.  The driver reaches only
``_get_position``, ``_get_motor_moving``, ``move_um``, ``get_pwm_intensity``, ``set_pwm_intensity``,
``set_pwm_state``, ``_get_ttl_in_mode``, ``_get_ttl_out_mode`` and ``close``; this class keeps the same units and the
same TTL-mode vocabulary as the upstream adaptor: positions in micrometres, PWM intensity in percent, and the TTL
input modes ``disabled``/``toggle_ttl_out`` and output modes ``low``/``high``/``pwm``.

The numbers below are test data, not facts about a controller or a stage.  The fake moves immediately and reports
motion complete at once; the upstream adaptor would poll the controller's moving query.  Nothing here talks to a
device.
"""

#: The axis order of the served configuration; the upstream constructor accepts this tuple (asi_MS_2000_500_CP.py:39).
AXES = ("X", "Y", "Z")


class FakeAsiMs2000500Cp:
    def __init__(self, **_options):
        self.axes = AXES
        # placeholder start position (um): a neutral origin, not a fact about any stage
        self.position_um = (0.0, 0.0, 0.0)
        # placeholder wide travel of the fake controller (um): not a real stage envelope
        self.min_position_um = (-1000000.0, -1000000.0, -1000000.0)
        self.max_position_um = (1000000.0, 1000000.0, 1000000.0)
        # placeholder starting motion flag
        self.motor_moving = False
        # placeholder starting LED intensity (percent)
        self.pwm_intensity = 10
        # placeholder TTL modes: the disabled/low pair the upstream constructor programs for the off state
        self._ttl_in_mode = "disabled"
        self._ttl_out_mode = "low"
        self.state = "off"
        self.closed = False

    def _get_position(self):
        return tuple(self.position_um)

    def _get_motor_moving(self):
        return bool(self.motor_moving)

    def _get_ttl_in_mode(self):
        return self._ttl_in_mode

    def _get_ttl_out_mode(self):
        return self._ttl_out_mode

    def _set_ttl_in_mode(self, mode):
        assert mode in ("disabled", "toggle_ttl_out"), f"TTL input mode {mode!r} is not allowed"
        self._ttl_in_mode = mode

    def _set_ttl_out_mode(self, mode):
        assert mode in ("low", "high", "pwm"), f"TTL output mode {mode!r} is not allowed"
        self._ttl_out_mode = mode

    def move_um(self, move_um, relative=True, block=True):
        values = list(move_um)
        if len(values) != len(self.axes):
            raise AssertionError(f"{len(values)} targets for {len(self.axes)} axes")
        if relative:
            values = [position + move for position, move in zip(self.position_um, values)]
        for position, low, high in zip(values, self.min_position_um, self.max_position_um):
            if not low <= position <= high:
                raise AssertionError(f"target {position} um is outside the fake travel [{low}, {high}]")
        self.position_um = tuple(round(position, 3) for position in values)
        # the fake completes every move at once; the motion flag stays false after the call
        self.motor_moving = False if block else True

    def get_pwm_intensity(self):
        return int(self.pwm_intensity)

    def set_pwm_intensity(self, intensity):
        assert type(intensity) is int or type(intensity) is float, "intensity must be a number"
        value = int(intensity)
        assert 1 <= value <= 99, "intensity must be between 1 and 99"
        self.pwm_intensity = value

    def set_pwm_state(self, state):
        assert state in ("off", "on", "pwm", "external"), f"PWM state {state!r} is not allowed"
        if state == "off":
            self._set_ttl_in_mode("disabled")
            self._set_ttl_out_mode("low")
        elif state == "on":
            self._set_ttl_in_mode("disabled")
            self._set_ttl_out_mode("high")
        elif state == "pwm":
            self._set_ttl_in_mode("disabled")
            self._set_ttl_out_mode("pwm")
        else:
            self._set_ttl_in_mode("toggle_ttl_out")
            self._set_ttl_out_mode("low")
        self.state = state

    def close(self):
        if self.state != "off":
            self.set_pwm_state("off")
        self.closed = True
