"""Fake backend of the 8742 driver: an in-memory stand-in for picomotor_terminal_based.Controller.

Gate G7 only sees the public method ``command`` here, and that method exists on the upstream Controller
(picomotor_terminal_based.py:221).  The fake answers the New Focus command strings that this driver sends,
using the same reply shapes the upstream parser accepts: a text line for VE?, one character for QM? and MD?,
and no reply for MC, VA, MV and ST.  The initial values are test data, not device facts.
"""


class FakeController:
    def __init__(self, **_options):
        self._version = "8742 fake"                  # placeholder
        self._motor_type = ["3", "3", "3", "3"]      # placeholder
        self._motion_done = [True, True, True, True]  # placeholder
        self._velocity = [500, 500, 500, 500]        # placeholder

    def command(self, newfocus_command):
        text = str(newfocus_command).strip()
        if text == "MC":
            return None
        if text == "VE?":
            return self._version
        if text == "ST":
            self._motion_done = [True, True, True, True]
            return None
        if len(text) >= 2 and text[0] in "1234":
            index = int(text[0]) - 1
            rest = text[1:]
            if rest == "QM?":
                return self._motor_type[index]
            if rest == "MD?":
                return "1" if self._motion_done[index] else "0"
            if rest == "ST":
                self._motion_done[index] = True
                return None
            if rest.startswith("VA"):
                self._velocity[index] = int(rest[2:])
                return None
            if rest in ("MV+", "MV-"):
                self._motion_done[index] = False
                return None
        raise ValueError(f"unexpected New Focus command {text!r}")
