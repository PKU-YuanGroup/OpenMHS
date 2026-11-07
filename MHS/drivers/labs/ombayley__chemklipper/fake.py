"""Fake backend of the ChemKlipper gantry: an in-memory stand-in for chem_klipper.devices.gantry:Gantry.

Gate G7: every public method and property here exists on ``chem_klipper.devices.gantry:Gantry`` (including the
methods it inherits from ``chem_klipper.devices.moonraker_device:MoonrakerDevice``).  Like the upstream class, each
device method is a coroutine function, ``is_connected`` is a property, and positions are returned as the upstream
dictionaries keyed ``X``, ``Y``, ``Z`` and ``E``.  The numeric starting values, the printer state string and the
canned replies below are test data only: each is marked ``# placeholder`` and none is a fact or a limit of any
machine.  Nothing here talks to a device or imports the upstream package.
"""


class FakeGantry:
    def __init__(self, **_options):
        self._connected = True                                      # placeholder
        self._status = "Ready"                                      # placeholder
        self._motors_enabled = True                                 # placeholder
        self._position = {"X": 0.0, "Y": 0.0, "Z": 0.0, "E": 0.0}   # placeholder
        self._target = {"X": 0.0, "Y": 0.0, "Z": 0.0, "E": 0.0}     # placeholder

    @property
    def is_connected(self):
        return self._connected

    async def connect(self):
        self._connected = True

    async def disconnect(self):
        self._connected = False

    async def send_command(self, command):
        if command == "M18":
            self._motors_enabled = False
        elif command == "M17":
            self._motors_enabled = True
        return "ok"

    async def send_query(self, query):
        if query == "gcode_move":
            return {"status": {"gcode_move": {"position": [self._target["X"], self._target["Y"],
                                                           self._target["Z"], self._target["E"]],
                                              "axis_map": {"X": 0, "Y": 1, "Z": 2, "E": 3}}}}
        if query == "motion_report":
            return {"status": {"motion_report": {"live_position": [self._position["X"], self._position["Y"],
                                                                   self._position["Z"], self._position["E"]]}}}
        return {"status": {}}

    async def get_status(self):
        return self._status

    async def wait_until_queue_empty(self):
        return None

    async def get_target_position(self):
        return dict(self._target)

    async def get_current_position(self):
        return dict(self._position)

    async def wait_for_move(self, timeout=180.0, tol=0.001):  # placeholder defaults
        return None

    async def home(self, debug=False):
        if debug:
            self._position = {"X": 0.0, "Y": 0.0, "Z": 0.0, "E": 0.0}   # placeholder
            self._target = dict(self._position)
            return
        self._position = {"X": 0.0, "Y": 0.0, "Z": 0.0, "E": 0.0}       # placeholder
        self._target = dict(self._position)

    async def move(self, x=None, y=None, z=None, speed=20.0, power=1.0, timeout=180.0):  # placeholder defaults
        for axis, value in (("X", x), ("Y", y), ("Z", z)):
            if value is not None:
                self._target[axis] = float(value)
                self._position[axis] = float(value)

    async def enable_motors(self):
        self._motors_enabled = True

    async def disable_motors(self):
        self._motors_enabled = False
