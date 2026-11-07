"""Fake backend of the tecancavro driver: an in-memory stand-in for ``tecancavro.models:XCaliburD``.

Gate G7: every public method defined here exists on ``tecancavro.models:XCaliburD`` (models.py:25-716), and the one
attribute the driver reads besides the methods, ``microstep``, is set by the upstream ``setMicrostep``
(models.py:707).  Nothing here talks to a pump.

The chain semantics of the upstream class are kept, because the driver depends on them: ``movePlungerAbs``,
``movePlungerRel``, ``changePort``, ``dispense`` and the ``set*`` speed commands only queue a command in
``cmd_chain`` (models.py:456, 486, 509, 527, 536, 545, 554, 565); ``executeChain()`` sends the chain and clears it
(models.py:283-292), and ``setMicrostep`` is sent at once (models.py:701-707).  A move that would leave the plunger
travel is refused as the Cavro refuses an invalid operand, with error code 3 (syringe.py:47).

The starting values are test data, not facts about a pump: each carries ``# placeholder``.  Values never change by
themselves, so reading the state twice gives the same state.
"""


class _Refused(Exception):
    """A command this fake refuses (the upstream raises SyringeError or ValueError instead)."""


class FakeXCaliburD:
    def __init__(self, **_options):
        # the upstream constructor options (models.py:42-43); the values are placeholders
        self.num_ports = int(_options.get("num_ports", 9))            # placeholder
        self.syringe_ul = float(_options.get("syringe_ul", 1000))     # placeholder
        self.waste_port = int(_options.get("waste_port", 9))          # placeholder
        self.microstep = bool(_options.get("microstep", False))       # placeholder
        self._plunger = 3000                                          # placeholder: a filled syringe
        self._port = 1                                                # placeholder
        self._start_speed = 100                                       # placeholder
        self._top_speed = 1000                                        # placeholder
        self._cutoff_speed = 1000                                     # placeholder
        self._slope = 14                                              # placeholder
        self.cmd_chain = ""
        self._chain = []
        self._terminated = 0

    # -- report commands (models.py:631-695) ------------------------------------------------------------------
    def getPlungerPos(self):
        return int(self._plunger)

    def getEncoderPos(self):
        return int(self._plunger)

    def getCurPort(self):
        return int(self._port)

    def getStartSpeed(self):
        return int(self._start_speed)

    def getTopSpeed(self):
        return int(self._top_speed)

    def getCutoffSpeed(self):
        return int(self._cutoff_speed)

    def getBufferStatus(self):
        return 1 if self._chain else 0

    # -- command-set commands (models.py:516-565) -------------------------------------------------------------
    def setSpeed(self, speed_code):
        if not 0 <= speed_code <= 40:                                  # models.py:521
            raise _Refused("speed code outside 0 to 40")
        self.cmd_chain += "S{0}".format(speed_code)
        self._queue(self._apply_speed_code, int(speed_code))

    def setStartSpeed(self, pulses_per_sec):
        self.cmd_chain += "v{0}".format(pulses_per_sec)
        self._queue(self._apply_start_speed, int(pulses_per_sec))

    def setTopSpeed(self, pulses_per_sec):
        self.cmd_chain += "V{0}".format(pulses_per_sec)
        self._queue(self._apply_top_speed, int(pulses_per_sec))

    def setCutoffSpeed(self, pulses_per_sec):
        self.cmd_chain += "c{0}".format(pulses_per_sec)
        self._queue(self._apply_cutoff_speed, int(pulses_per_sec))

    def setSlope(self, slope_code, chain=False):
        if not 1 <= slope_code <= 20:                                  # models.py:560
            raise _Refused("slope code outside 1 to 20")
        self.cmd_chain += "L{0}".format(slope_code)
        self._queue(self._apply_slope, int(slope_code))

    def setMicrostep(self, on=False):
        self.cmd_chain = ""
        self.microstep = bool(on)

    # -- chainable low level functions (models.py:423-510) ----------------------------------------------------
    def changePort(self, to_port, from_port=None, direction="CW"):
        if not 0 < to_port <= self.num_ports:                          # models.py:441
            raise _Refused("port outside 1 to {0}".format(self.num_ports))
        self.cmd_chain += "O{0}".format(to_port)
        self._queue(self._apply_port, int(to_port))

    def movePlungerAbs(self, abs_position):
        limit = 24000 if self.microstep else 3000                      # models.py:473-478
        if not 0 <= abs_position <= limit:
            raise _Refused("absolute position outside 0 to {0}".format(limit))
        self.cmd_chain += "A{0}".format(abs_position)
        self._queue(self._apply_move_abs, int(abs_position))

    def movePlungerRel(self, rel_position):
        self.cmd_chain += ("D{0}" if rel_position < 0 else "P{0}").format(abs(rel_position))
        self._queue(self._apply_move_rel, int(rel_position))

    # -- chainable high level functions (models.py:387-417) --------------------------------------------------
    def dispense(self, to_port, volume_ul):
        self.changePort(to_port)
        steps = int(round(volume_ul * (3000.0 / self.syringe_ul)))     # models.py:866
        self.movePlungerRel(-steps)

    def dispenseToWaste(self, retain_port=True):
        orig_port = self._port
        self.changePort(self.waste_port)
        self.movePlungerAbs(0)
        if retain_port:
            self.changePort(orig_port)

    # -- command chain (models.py:275-325) --------------------------------------------------------------------
    def executeChain(self, minimal_reset=False):
        pending, self._chain = self._chain, []
        self.cmd_chain = ""
        for apply, args in pending:
            apply(*args)
        return 0.0

    def resetChain(self, on_execute=False, minimal_reset=False):
        self._chain = []
        self.cmd_chain = ""

    def terminateCmd(self):
        self._terminated += 1
        self._chain = []
        self.cmd_chain = ""

    # -- internals (not part of the upstream surface) ---------------------------------------------------------
    def _queue(self, apply, *args):
        self._chain.append((apply, args))

    def _apply_speed_code(self, speed_code):
        self._top_speed = speed_code        # placeholder: the code itself, not the pulses/s table

    def _apply_start_speed(self, pulses_per_sec):
        self._start_speed = pulses_per_sec

    def _apply_top_speed(self, pulses_per_sec):
        self._top_speed = pulses_per_sec

    def _apply_cutoff_speed(self, pulses_per_sec):
        self._cutoff_speed = pulses_per_sec

    def _apply_slope(self, slope_code):
        self._slope = slope_code

    def _apply_port(self, to_port):
        self._port = to_port

    def _apply_move_abs(self, abs_position):
        limit = 24000 if self.microstep else 3000
        if not 0 <= abs_position <= limit:
            raise _Refused("absolute position outside 0 to {0}".format(limit))
        self._plunger = abs_position

    def _apply_move_rel(self, rel_position):
        limit = 24000 if self.microstep else 3000
        target = self._plunger + rel_position
        if not 0 <= target <= limit:
            raise _Refused("relative move leaves the plunger travel 0 to {0}".format(limit))
        self._plunger = target
