"""Fake backend of the Science Jubilee driver: an in-memory stand-in for science_jubilee.Machine:Machine.

Gate G7: every public method defined here exists on the upstream Machine class (src/science_jubilee/Machine.py):
``get_position``, ``move_to``, ``home_all``, ``home_x``, ``home_y``, ``home_u``, ``set_tool_offset`` and
``gcode``.  Like the upstream, ``get_position()`` returns a dict of axis name to the numeric text of
the M114 reply, ``move_to()`` formats a coordinate with two decimals before storing it, and
``set_tool_offset()`` needs a tool index.  The start positions and the home positions are test data,
not facts about a machine: each carries ``# placeholder``.  Nothing here talks to a device.
"""


class FakeMachine:
    def __init__(self, **_options):
        # placeholder: a machine at the coordinate origin, before any move
        self._position = {"X": "0.00", "Y": "0.00", "Z": "0.00", "U": "0.00"}
        self._tool_offsets = {}
        self._halted = False

    def get_position(self):
        return dict(self._position)

    def move_to(self, x=None, y=None, z=None, e=None, v=None, s=6000, param=None, wait=True):
        for axis, value in (("X", x), ("Y", y), ("Z", z), ("E", e), ("V", v)):
            if value is not None:
                self._position[axis] = f"{float(value):.2f}"
        return None

    def home_all(self):
        for axis in ("X", "Y", "Z", "U"):
            self._position[axis] = "0.00"  # placeholder: the fake reference position
        return None

    def home_x(self):
        self._position["X"] = "0.00"  # placeholder: the fake reference position
        return None

    def home_y(self):
        self._position["Y"] = "0.00"  # placeholder: the fake reference position
        return None

    def home_u(self):
        self._position["U"] = "0.00"  # placeholder: the fake reference position
        return None

    def set_tool_offset(self, tool_idx=None, x=None, y=None, z=None):
        if tool_idx is None:
            # The upstream raises MachineConfigurationError for the same input condition.
            raise ValueError("No tool index provided")
        self._tool_offsets[tool_idx] = (x, y, z)
        return None

    def gcode(self, cmd="", timeout=None, response_wait=60):
        if cmd.strip().upper().startswith("M112"):
            self._halted = True
        return "ok"  # placeholder: the fake reply, not a device reply
