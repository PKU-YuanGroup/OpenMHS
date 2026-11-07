"""Fake Vortran Stradus laser of the copylot driver: a recording stand-in at the level of the upstream object.

The driver calls the upstream object (``VortranLaser``); this class offers the same members the driver touches and
keeps their state, so a write has an observable effect on the resource state (``laser_power = 3`` changes
``laser_power``) and the emission aliases switch the emission flag.  Every member of this class exists on
``copylot.hardware.lasers.vortran.vortran:VortranLaser``, which gate G7 reads from the clone's AST.

Every number and every string here is test data, marked ``# placeholder``: none of them is a fact of the laser and
none of them is cited anywhere.  Nothing here opens a port or talks to an instrument.
"""


def _on(value) -> bool:
    """The upstream setter receives 1/0 for a flag; accept its own truth forms."""
    return str(value).strip() in ("1", "ON", "TRUE", "True")


class FakeVortranLaser:
    def __init__(self, **_options):
        self._emission = "0"                    # placeholder
        self._power = 1.0                       # placeholder
        self._max_power = 10.0                  # placeholder
        self._emission_delay = "1"              # placeholder
        self._pulse_mode = "0"                  # placeholder
        self._fault_code = 0                    # placeholder
        self._fault_description = "NO FAULT"    # placeholder

    # -- the flags of the upstream properties --------------------------------------------------------------
    @property
    def toggle_emission(self):
        return self._emission

    @toggle_emission.setter
    def toggle_emission(self, value):
        self._emission = "1" if _on(value) else "0"

    @property
    def emission_delay(self):
        return self._emission_delay

    @emission_delay.setter
    def emission_delay(self, value):
        self._emission_delay = "1" if _on(value) else "0"

    @property
    def pulse_mode(self):
        return self._pulse_mode

    @pulse_mode.setter
    def pulse_mode(self, value):
        self._pulse_mode = "1" if _on(value) else "0"

    # -- the power of the upstream properties --------------------------------------------------------------
    @property
    def laser_power(self):
        return self._power

    @laser_power.setter
    def laser_power(self, value):
        # The upstream setter clamps the value to the maximum power of the head (vortran.py:373-377).
        self._power = min(float(value), self._max_power)

    @property
    def maximum_power(self):
        return self._max_power

    # -- status and the emission aliases -------------------------------------------------------------------
    @property
    def status(self):
        return (self._fault_code, self._fault_description)

    def turn_on(self):
        self.toggle_emission = 1
        return self._emission

    def turn_off(self):
        self.toggle_emission = 0
        return self._emission
