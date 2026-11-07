"""Fake backend of the CHX syringe-pump controller: an in-memory stand-in for the upstream ``pump`` class.

The upstream class ``pump`` (``pump_controler.py:10``) owns a pyserial link in ``self.ser`` and implements the
protocol as methods: ``get_direction``, ``set_rate``, ``set_diameter``, ``set_volume``, ``get_volume``,
``get_dispense``, ``reset_dispense``, ``get_rate``, ``run`` and ``stop``.  This fake implements the methods this
driver uses with the same names and signatures, so G7 can compare them with the clone's AST (the clone is Python
2, so G7 cannot parse it; see ``RESULT.json``).  It answers with the reply layouts the clone's own slices expect:
the direction at ``reply[4:7]``, the volume at ``reply[4:-3]`` and ``reply[-3:-1]``, the two dispense fields at
``reply[5:10]`` and ``reply[11:16]``, and the rate unit at ``reply[-3:-1]``.

All numbers and replies below are canned test data, not facts about an instrument, and are marked ``# placeholder``.
The fake is not a recording of a hardware run.
"""


class FakePump:
    """A stateful stand-in for one addressed pump of the upstream controller."""

    def __init__(self, **_options):
        self._address = str(_options.get("address", "00"))   # placeholder: the panel's example address
        self._direction = "INF"                             # placeholder: start direction
        self._rate_umin = 0.0                               # placeholder: start flow rate
        self._volume_ul = 0.0                               # placeholder: start dispense volume
        self._dispensed_inf = 0.0                           # placeholder: start INF dispensed volume
        self._dispensed_wdr = 0.0                           # placeholder: start WDR dispensed volume
        self._running = False                               # placeholder: start run state

    # -- the upstream method surface -----------------------------------------------------------------------------
    def get_direction(self, pump=0):
        return "+" if self._direction == "INF" else "-"

    def set_rate(self, flowrate, unit="UM*", pump=0):
        if unit not in ("UM*", "UM"):
            raise ValueError(f"the fake models the UM* unit, not {unit!r}")
        value = float(flowrate)
        self._direction = "WDR" if value < 0 else "INF"
        self._rate_umin = abs(value)

    def set_volume(self, vol, unit="UL", pump=0):
        self._volume_ul = float(vol)

    def get_volume(self, pump=0):
        return self._volume_ul, "UL"

    def get_dispense(self, direction="INF", pump=0):
        if direction == "INF":
            return self._dispensed_inf, "UL"
        if direction == "WDR":
            return self._dispensed_wdr, "UL"
        raise ValueError(f"unknown dispense direction {direction!r}")

    def reset_dispense(self, direction="INF", pump=0):
        if direction == "INF":
            self._dispensed_inf = 0.0
        elif direction == "WDR":
            self._dispensed_wdr = 0.0
        else:
            raise ValueError(f"unknown dispense direction {direction!r}")

    def get_rate(self, pump=0):
        sign = "+" if self._direction == "INF" else "-"
        return f"{sign}{self._rate_umin:.1f}  ul/min"

    def run(self, pump=None):
        self._running = True
        # The pump dispenses the volume it was set to; this makes the action's effect observable.
        if self._volume_ul > 0.0:
            if self._direction == "INF":
                self._dispensed_inf = self._volume_ul
            else:
                self._dispensed_wdr = self._volume_ul

    def stop(self, pump=None):
        self._running = False
