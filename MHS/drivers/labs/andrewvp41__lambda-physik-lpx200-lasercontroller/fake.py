"""Fake backend of the LPX 200 driver: an in-memory stand-in for the LPX200:Control command builder.

Gate G7: the only public method defined here, ``evaluate``, exists on LPX200.Control in the pinned clone, which
stores the ``commRes`` query function as ``self.evaluate`` (LPX200.py:92, 98 and 283).  Like ``commRes`` it answers a
query and returns ``None`` after a command (LPX200.py:251-258), but it keeps the state in plain attributes and never
opens a VISA resource.  The starting values are
arbitrary test data (each marked ``# placeholder``), not claims about a real LPX 200.  Nothing here talks to a
device.

The reply formats follow the clone: OPMODE? answers ON/OFF (LPX200.py:108), TRIGGER? answers INT/EXT (LPX200.py:
115), MODE? answers one of the mode names (LPX200.py:86), and Menu? answers the gas menu number, the wavelength and
the gas mixture, whose last field the display prints (LPX200.py:61).  A command outside this small surface raises,
like a line the instrument would not accept.
"""


class FakeLpx200:
    def __init__(self, **_options):
        self._operating_mode = "OFF"        # placeholder
        self._trigger_mode = "INT"          # placeholder
        self._mode = "HV"                   # placeholder
        self._repetition_rate = 100.0       # placeholder
        self._high_voltage = 20.0           # placeholder
        self._energy = 10.0                 # placeholder
        self._pressure = 1500.0             # placeholder
        self._gas_menu = "1 248 RARE"       # placeholder
        self.sent = []

    def evaluate(self, line):
        text = str(line).strip()
        self.sent.append(text)
        if text == "OPMODE?":
            return self._operating_mode
        if text == "TRIGGER?":
            return self._trigger_mode
        if text == "MODE?":
            return self._mode
        if text == "REPRATE?":
            return f"{self._repetition_rate:g}"
        if text == "HV?":
            return f"{self._high_voltage:g}"
        if text == "EGY?":
            return f"{self._energy:g}"
        if text == "PRESSURE?":
            return f"{self._pressure:g}"
        if text == "Menu?":
            return self._gas_menu
        if text == "OPMODE=ON":
            self._operating_mode = "ON"
            return None
        if text == "OPMODE=OFF":
            self._operating_mode = "OFF"
            return None
        if text.startswith("REPRATE="):
            self._repetition_rate = float(text.split("=", 1)[1])
            return None
        if text.startswith("HV="):
            self._high_voltage = float(text.split("=", 1)[1])
            return None
        if text.startswith("EGY="):
            self._energy = float(text.split("=", 1)[1])
            return None
        if text.startswith("MODE="):
            self._mode = text.split("=", 1)[1]
            return None
        if text.startswith("TRIGGER="):
            self._trigger_mode = text.split("=", 1)[1]
            return None
        raise ValueError(f"the fake does not accept the command {text!r}")
