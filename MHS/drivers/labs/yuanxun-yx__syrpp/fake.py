"""Fake backend of the syrpp driver: an in-memory stand-in for syrpp.pump_conn:SyrPump.

Gate G7: every public method defined here exists on ``syrpp.pump_conn:SyrPump`` in the clone, and the
signatures follow the upstream methods.  The state lives in private attributes, which the gate does not treat
as fake members.  The starting values are test data, marked ``# placeholder``; the clone never records what a
real pump would answer, so no number here is a Fact or a Limit.  The methods only change in-memory state;
nothing here talks to a device.
"""

#: Test data, not a fact: the prompt texts of the upstream PROMPT table (src/syrpp/pump_conn.py:45-52).
_PROMPT_TEXT = {
    "I": "infusing",                         # placeholder: upstream PROMPT mapping
    "W": "withdrawing",                      # placeholder: upstream PROMPT mapping
    "S": "pumping program stopped",          # placeholder: upstream PROMPT mapping
    "P": "pumping program paused",           # placeholder: upstream PROMPT mapping
    "T": "pause phase",                      # placeholder: upstream PROMPT mapping
    "U": "operational trigger wait (user wait)",  # placeholder: upstream PROMPT mapping
}


#: The human names and codes of the upstream PHASE_FUNCTION table (src/syrpp/pump_conn.py:117-134).
_FUNCTION_CODE = {
    "rate": "RAT", "increment": "INC", "decrement": "DEC", "stop": "STP", "jump": "JMP",
    "loop for": "LOP", "loop start": "LPS", "loop end": "LPE", "pause": "PAS", "if": "IF",
    "event trap": "EVN", "event reset": "EVR", "beep": "BEP", "output": "OUT",
}


class FakeSyrpp:
    """The upstream SyrPump methods over an in-memory pump at one address."""

    def __init__(self, **_options):
        self.calls = []                          # instance data: (method, arguments)
        self._prompt = "S"                       # placeholder: pump stopped at start
        self._firmware = "NE1000V3.934"          # placeholder: README.md:31 example reply
        self._diameter = 1.0                     # placeholder starting diameter
        self._phase = 1                          # placeholder starting phase
        self._function = "rate"                  # placeholder starting phase function
        self._rate = 1.0                         # placeholder starting rate value
        self._rate_volume_unit = "ul"            # placeholder: a VOLUME_UNITS alias
        self._rate_time_unit = "min"             # placeholder: a TIME_UNITS alias
        self._direction = "infuse"               # placeholder starting direction
        self._alarm = False                      # placeholder starting bool
        self._power_fail = False                 # placeholder starting bool
        self._key_beep = False                   # placeholder starting bool
        self._buzzer = False                     # placeholder starting bool
        self._volume = 0.0                       # placeholder starting phase volume
        self._volume_unit = "ul"                 # placeholder: a VOLUME_UNITS alias
        self._infusion = 0.0                     # placeholder dispensed infusion
        self._withdraw = 0.0                     # placeholder dispensed withdrawal

    # -- status, version -----------------------------------------------------------------------------------------
    def get_status(self, address, code=False):
        self.calls.append(("get_status", address, code))
        if code:
            return self._prompt
        return _PROMPT_TEXT[self._prompt]

    def get_firmware_version(self, address):
        self.calls.append(("get_firmware_version", address))
        return self._firmware

    # -- diameter, phase, function -------------------------------------------------------------------------------
    def get_diameter(self, address):
        self.calls.append(("get_diameter", address))
        return self._diameter

    def set_diameter(self, address, diameter):
        self.calls.append(("set_diameter", address, diameter))
        self._diameter = float(diameter)

    def get_phase(self, address):
        self.calls.append(("get_phase", address))
        return self._phase

    def set_phase(self, address, phase):
        self.calls.append(("set_phase", address, phase))
        self._phase = int(phase)

    def get_function(self, address, code=False):
        self.calls.append(("get_function", address, code))
        if code:
            return {"function": _FUNCTION_CODE.get(self._function, self._function)}
        return {"function": self._function}

    def set_function(self, address, function, data=None):
        self.calls.append(("set_function", address, function, data))
        self._function = function

    # -- rate, direction ------------------------------------------------------------------------------------------
    def get_rate(self, address):
        self.calls.append(("get_rate", address))
        return {"value": self._rate, "volume_unit": self._rate_volume_unit,
                "time_unit": self._rate_time_unit}

    def set_rate(self, address, value, volume_unit=None, time_unit=None):
        self.calls.append(("set_rate", address, value, volume_unit, time_unit))
        self._rate = float(value)
        if volume_unit is not None and time_unit is not None:
            self._rate_volume_unit, self._rate_time_unit = volume_unit, time_unit

    def get_direction(self, address):
        self.calls.append(("get_direction", address))
        return self._direction

    def set_direction(self, address, direction):
        self.calls.append(("set_direction", address, direction))
        self._direction = direction

    # -- boolean settings ---------------------------------------------------------------------------------------
    def get_alarm(self, address):
        self.calls.append(("get_alarm", address))
        return self._alarm

    def set_alarm(self, address, buzzer):
        self.calls.append(("set_alarm", address, buzzer))
        self._alarm = bool(buzzer)

    def get_power_fail(self, address):
        self.calls.append(("get_power_fail", address))
        return self._power_fail

    def set_power_fail(self, address, power_fail):
        self.calls.append(("set_power_fail", address, power_fail))
        self._power_fail = bool(power_fail)

    def get_key_beep(self, address):
        self.calls.append(("get_key_beep", address))
        return self._key_beep

    def set_key_beep(self, address, key_beep):
        self.calls.append(("set_key_beep", address, key_beep))
        self._key_beep = bool(key_beep)

    def get_buzzer(self, address):
        self.calls.append(("get_buzzer", address))
        return self._buzzer

    def set_buzzer(self, address, buzzer, n_time=0):
        self.calls.append(("set_buzzer", address, buzzer, n_time))
        self._buzzer = bool(buzzer)

    # -- volume ---------------------------------------------------------------------------------------------------
    def get_volume(self, address):
        self.calls.append(("get_volume", address))
        return {"volume": self._volume, "unit": self._volume_unit}

    def get_volume_dispensed(self, address):
        self.calls.append(("get_volume_dispensed", address))
        return {"infusion": self._infusion, "withdraw": self._withdraw, "unit": self._volume_unit}

    # -- program control ------------------------------------------------------------------------------------------
    def start_program(self, address):
        self.calls.append(("start_program", address))
        self._prompt = "W" if self._direction == "withdraw" else "I"   # placeholder prompt rule

    def stop_program(self, address):
        self.calls.append(("stop_program", address))
        self._prompt = "S"
