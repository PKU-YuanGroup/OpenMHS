"""Fake backend of the Newport SMC100 driver.

The fake implements only the public surface of
``pymodaq_plugins_newport.hardware.smc100:SMC100`` (gate G7 reads the clone's
AST).  It talks to nothing: the state lives in plain attributes and every
``write`` mimics the effect of the SMC100 mnemonic on that state.  Every
number and canned reply below is test data, not a device fact; the lines are
marked ``# placeholder``.  The clone's ``query`` strips the first three
characters of a reply, so this fake returns the answer part only.
"""

import time


class FakeSmc100:
    def __init__(self, **_options):
        self._identity = "Newport SMC100PP fake"  # placeholder
        self._position = 0.0  # placeholder
        self._speed = 1.0  # placeholder
        self._acceleration = 1.0  # placeholder
        self._moving = False  # placeholder
        self._enabled = True  # placeholder
        self._referenced = False  # placeholder
        self._last_error = "@"  # placeholder
        self.written = []

    # -- transport -----------------------------------------------------------------
    def write(self, cmd):
        """Record a command and apply its effect to the fake state."""
        self.written.append(cmd)
        if cmd == "OR":
            self._position = 0.0  # placeholder
            self._referenced = True  # placeholder
            self._moving = False  # placeholder
        elif cmd == "ST":
            self._moving = False  # placeholder
        elif cmd == "RS":
            self._referenced = False  # placeholder
            self._moving = False  # placeholder
        elif cmd == "MM0":
            self._enabled = False  # placeholder
        elif cmd == "MM1":
            self._enabled = True  # placeholder
        elif cmd.startswith("PA"):
            self._position = float(cmd[2:])
            self._moving = False  # placeholder
        elif cmd.startswith("PR"):
            self._position += float(cmd[2:])
            self._moving = False  # placeholder
        elif cmd.startswith("VA"):
            self._speed = float(cmd[2:])
        elif cmd.startswith("AC"):
            self._acceleration = float(cmd[2:])
        else:
            self._last_error = "A"  # placeholder: the clone's unknown-message code

    def query(self, cmd):
        """Answer one of the SMC100 queries the upstream class sends."""
        if cmd == "ID?":
            return self._identity
        if cmd == "PA?":
            return str(self._position)
        if cmd == "VA?":
            return str(self._speed)
        if cmd == "AC?":
            return str(self._acceleration)
        if cmd == "TS":
            return "0000" + ("28" if self._moving else "33")  # placeholder
        if cmd == "TE":
            return self._last_error
        raise ValueError(f"the fake does not answer {cmd!r}")

    def close(self):
        pass

    # -- SMC100 surface ------------------------------------------------------------
    @property
    def idn(self):
        return self.query("ID?")

    @property
    def position(self):
        return float(self.query("PA?"))

    @property
    def is_moving(self):
        status = int(self.error_and_controller_status()[1], 16)
        return status == 0x28  # placeholder: the clone's CTRL_STATUS['moving']

    def error_and_controller_status(self):
        reply = self.query("TS")
        return reply[0:4], reply[4:6]

    def get_last_command_error(self):
        return self.query("TE")

    def move_abs(self, position):
        self.write(f"PA{position}")

    def move_rel(self, distance):
        self.write(f"PR{distance}")

    def home(self):
        self.write("PA0")

    def homing(self):
        self.write("OR")

    def reset(self):
        self.write("RS")

    def stop(self):
        self.write("ST")

    def enable(self):
        self.write("MM1")

    def disable(self):
        self.write("MM0")

    def wait_move_finish(self, interval):
        while self.is_moving:
            time.sleep(interval)

    @property
    def speed(self):
        return float(self.query("VA?"))

    @speed.setter
    def speed(self, value):
        self.write(f"VA{value}")

    @property
    def acceleration(self):
        return float(self.query("AC?"))

    @acceleration.setter
    def acceleration(self, value):
        self.write(f"AC{value}")
