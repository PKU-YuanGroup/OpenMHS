"""Fake backend of the syringe-pump driver: an in-memory stand-in for ctrl_syringe_pumps.control:Control.

Gate G7: every public method defined here exists on the upstream class (``ctrl_syringe_pumps/interface.py`` and
``control.py``).  The state lives in plain attributes, which the gate does not treat as fake members.  The reply
lines are test data (marked ``# placeholder``); the clone never prints what a real pump answers.  The diameter check
and the rate-unit check copy the upstream's own conditions (``interface.py:39-43`` and ``63-66``), so an input the
real class refuses is refused here too.  Nothing here talks to a device.
"""

#: Test data, not a fact: the clone does not state what a pump answers.
_REPLY_OK = "OK"                     # placeholder
_REPLY_VERSION = "ctrl-syringe-pumps fake"  # placeholder


class FakeControl:
    """The upstream Control object's methods, over an in-memory pump."""

    def __init__(self, **_options):
        self.adr1, self.adr2 = 0, 1   # the upstream Interface defaults (interface.py:4-6)
        self.port = "fake"
        self.baud_rate = 9600          # placeholder copied from control.py:9
        self.timeout = 0.5             # placeholder copied from control.py:11
        self.diameter = 1.0            # placeholder starting value
        self.direction = "INF"         # placeholder starting value
        self.rate = 1.0                # placeholder starting value
        self.rate_unit = "UM"          # placeholder starting value
        self.running = False
        self.calls = []

    def _reply(self, name):
        self.calls.append(name)
        return _REPLY_OK

    def test_pump(self, adr):
        self.calls.append("test_pump")
        return _REPLY_VERSION

    def set_diameter(self, adr, val):
        lower, upper = 0.1, 50.0       # interface.py:10
        if not lower < val < upper:
            raise ValueError("The inside diameter must be within the range [0.1, 50] mm.")
        self.diameter = val
        return self._reply("set_diameter")

    def set_direction_infuse(self, adr):
        self.direction = "INF"
        return self._reply("set_direction_infuse")

    def set_direction_withdraw(self, adr):
        self.direction = "WDR"
        return self._reply("set_direction_withdraw")

    def set_direction_reverse(self, adr):
        self.direction = "REV"
        return self._reply("set_direction_reverse")

    def set_pumping_rate(self, adr, val, rate_unit):
        if rate_unit not in ("UM", "MM", "UH", "MH"):
            raise ValueError("Value error for the rate units.")
        self.rate, self.rate_unit = val, rate_unit
        return self._reply("set_pumping_rate")

    def run_pump(self, adr):
        self.running = True
        return self._reply("run_pump")

    def stop_pump(self, adr):
        self.running = False
        return self._reply("stop_pump")
