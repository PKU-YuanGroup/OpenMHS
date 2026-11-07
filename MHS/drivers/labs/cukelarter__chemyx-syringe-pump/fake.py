"""Fake backend of the CHEMYX syringe pump driver: an in-memory pump, not upstream code.

The driver is a direct ``Driver`` over the upstream ``Connection`` object, so this fake implements only the public
methods of that class (gate G7 checks them against the clone's AST).  It keeps the pump state in private attributes
and answers the query methods with the reply lists the clone's ``getResponse`` would return.  It does not import or
run the upstream clone and it does not talk to an instrument.

Every number below is test data for the fake, not a device fact or a safety limit: each is marked ``# placeholder``
and none is copied into a Fact, a Limit or the reference.
"""


class FakeConnection:
    """A stand-in for ``python_dist.CHEMYX_python.core.connect:Connection``."""

    def __init__(self, **options):
        self._open = False
        self._multipump = bool(options.get("multipump", False))
        self._current_pump = 1
        self._running = False
        self._units = "mL/min"                 # placeholder
        self._diameter = 28.6                  # placeholder, mm
        self._rate = 1.0                       # placeholder, selected unit
        self._volume = 1.0                     # placeholder, selected unit
        self._delay = 0.5                      # placeholder, s
        self._time = 0.0                       # placeholder
        self._displaced = 0.0                  # placeholder
        self._elapsed = 0.0                    # placeholder
        self._pending = []
        self._sent = []

    # -- the public methods of the upstream Connection ---------------------------
    def openConnection(self):
        self._open = True

    def closeConnection(self):
        self._open = False

    def sendCommand(self, command):
        self._sent.append(command)
        self._pending = [self._answer(str(command).strip())]
        return self.getResponse()

    def getResponse(self):
        reply = list(self._pending)
        self._pending = []
        return reply

    def startPump(self, mode=0, multistep=False):
        command = "start "
        if self._multipump and mode > 0:
            command = f"{mode} {command}"
        if multistep:
            command = f"{command} {int(multistep)}"
        return self.sendCommand(command)

    def stopPump(self, mode=0):
        command = "stop "
        if self._multipump and mode > 0:
            command = f"{mode} {command}"
        return self.sendCommand(command)

    def pausePump(self, mode=0):
        command = "pause "
        if self._multipump and mode > 0:
            command = f"{mode} {command}"
        return self.sendCommand(command)

    def restartPump(self):
        return self.sendCommand("restart ")

    def setUnits(self, units):
        units_dict = {"mL/min": "0", "mL/hr": "1", "μL/min": "2", "μL/hr": "3"}
        return self.sendCommand("set units " + units_dict[units])

    def setDiameter(self, diameter):
        return self.sendCommand("set diameter " + str(diameter))

    def setRate(self, rate):
        if isinstance(rate, list):
            command = "set rate " + ",".join(str(x) for x in rate)
        else:
            command = "set rate " + str(rate)
        return self.sendCommand(command)

    def setVolume(self, volume):
        if isinstance(volume, list):
            command = "set volume " + ",".join(str(x) for x in volume)
        else:
            command = "set volume " + str(volume)
        return self.sendCommand(command)

    def setDelay(self, delay):
        if isinstance(delay, list):
            command = "set delay " + ",".join(str(x) for x in delay)
        else:
            command = "set delay " + str(delay)
        return self.sendCommand(command)

    def setTime(self, timer):
        return self.sendCommand("set time " + str(timer))

    def getParameterLimits(self):
        return self.sendCommand("read limit parameter")

    def getParameters(self):
        return self.sendCommand("view parameter")

    def getDisplacedVolume(self):
        return self.sendCommand("dispensed volume")

    def getElapsedTime(self):
        return self.sendCommand("elapsed time")

    def getPumpStatus(self):
        return self.sendCommand("pump status")

    def setPump(self, pump):
        if self._multipump:
            self._current_pump = pump

    def addPump(self, command):
        if self._multipump:
            return f"{self._current_pump} {command}"
        return command

    # -- fake behaviour ----------------------------------------------------------
    def _answer(self, command):
        parts = command.split()
        if not parts:
            return ""
        if len(parts) > 1 and parts[0].isdigit() and self._multipump:
            parts = parts[1:]
        head = parts[0]
        args = parts[1:]
        if head == "set":
            return self._set(args)
        if head == "start":
            self._running = True
            return ""
        if head == "stop":
            self._running = False
            return ""
        if head == "pause":
            self._running = False
            return ""
        if head == "restart":
            self._running = True
            return ""
        if command == "read limit parameter":
            return "minimum 0"                 # placeholder
        if command == "view parameter":
            return self._parameters()
        if command == "dispensed volume":
            return f"{self._displaced:g}"      # placeholder
        if command == "elapsed time":
            return f"{self._elapsed:g}"        # placeholder
        if command == "pump status":
            return "running" if self._running else "stopped"
        return ""

    def _set(self, args):
        if len(args) < 2:
            return ""
        name, value = args[0], " ".join(args[1:])
        if name == "units":
            self._units = {"0": "mL/min", "1": "mL/hr", "2": "μL/min", "3": "μL/hr"}.get(value, self._units)
        elif name == "diameter":
            self._diameter = float(value)
        elif name == "rate":
            self._rate = value
        elif name == "volume":
            self._volume = value
        elif name == "delay":
            self._delay = value
        elif name == "time":
            self._time = value
        return ""

    def _parameters(self):
        """A parameter report whose lines end in the value, like the GUI expects (CHEMYX_GUI.py:237)."""
        return [
            f"units {self._units}",
            f"diameter {self._diameter:g}",
            f"rate {self._rate}",
            f"volume {self._volume}",
            f"delay {self._delay}",
            f"time {self._time}",
            f"displaced {self._displaced:g}",
            f"elapsed {self._elapsed:g}",
        ]
