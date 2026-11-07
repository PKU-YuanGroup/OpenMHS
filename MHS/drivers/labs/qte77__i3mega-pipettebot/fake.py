"""Fake backend of the i3 Mega pipettebot driver: an in-memory G-code gantry.

Gate G7: every public method defined here exists on ``pipettebot.gantry:GcodeGantry`` (src/pipettebot/gantry.py:147-214)
with the same call shape.  The driver sends the G-code lines the upstream gantry sends (``G28 X Y``, ``G1 X... Y... Z...
F...``, ``M400``) plus the documented emergency stop ``M112``; this fake answers every line with ``ok`` exactly like
Marlin does (src/pipettebot/gantry.py:120-135) and keeps the position the way ``move_to()`` would set it.  It records
the M112 emergency stop in ``halted`` but does not model the firmware's power-cycle recovery: on the fake backend the
runtime's e-stop latch is what refuses commands, and the suite's reset must leave the fake usable.  The starting
position is test data, not a fact about any machine: every such number is marked ``# placeholder``.  Nothing here talks
to a device.
"""


class FakeGcodeGantry:
    def __init__(self, **_options):
        self._x = 0.0                 # placeholder
        self._y = 0.0                 # placeholder
        self._z = 0.0                 # placeholder
        self.halted = False
        self.closed = False
        self.lines = []

    # -- the upstream wire helpers -------------------------------------------------
    def send(self, line: str, *, max_secs: float = 30.0) -> str:
        self.lines.append(line)
        if line == "M112":
            self.halted = True
        elif line == "G28":
            self._x, self._y, self._z = 0.0, 0.0, 0.0     # placeholder
        elif line.startswith("G28"):
            axes = line.split()[1:]
            if not axes or "X" in axes:
                self._x = 0.0                             # placeholder
            if not axes or "Y" in axes:
                self._y = 0.0                             # placeholder
            if "Z" in axes:
                self._z = 0.0                             # placeholder
        elif line.startswith("G1 "):
            for token in line.split()[1:]:
                if token[0] in "XYZ" and len(token) > 1:
                    setattr(self, "_" + token[0].lower(), float(token[1:]))
        return "ok"

    def query(self, line: str, *, max_secs: float = 30.0) -> list[str]:
        self.lines.append(line)
        if line == "M114":
            # Three decimals, as in the documented M114 reply (docs/research/gantry-firmware-alternatives.md:143).
            return [f"X:{self._x:.3f} Y:{self._y:.3f} Z:{self._z:.3f} E:0.000", "ok"]
        return ["ok"]

    def flush_input(self) -> None:
        return

    # -- the named motion methods ---------------------------------------------------
    def home(self) -> str:
        return self.send("G28")

    def move_to(self, x: float, y: float, z: float, feedrate: int | None = None) -> str:
        self._x, self._y, self._z = float(x), float(y), float(z)
        f = 3000 if feedrate is None else feedrate     # placeholder: the GantryConfig example default
        return self.send(f"G1 X{self._x:.3f} Y{self._y:.3f} Z{self._z:.3f} F{f}")

    def wait_for_moves(self, *, max_secs: float = 30.0) -> str:
        return self.send("M400", max_secs=max_secs)

    def close(self) -> None:
        self.closed = True
