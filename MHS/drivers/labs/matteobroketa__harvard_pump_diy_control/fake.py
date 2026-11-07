"""Fake backend of the Harvard PHD 2000 driver: an in-memory stand-in for HarvardPHD2000Driver.

Gate G7: every public method defined here exists on
``refactored_pump_control.harvard_phd2000_driver:HarvardPHD2000Driver`` or its base
``PumpDriverBase`` in the clone (get_rate, set_rate, get_syringe_info, set_diameter, set_direction, start, stop,
query_state, get_status, run, pause, resume).  The instance attributes ``transport``, ``address`` and ``direction``
are the ones the upstream __init__ sets (harvard_phd2000_driver.py:52-61).  The values below are test data, not
device facts: every number is marked ``# placeholder``.  Nothing here talks to a device.
"""


class _FakeTransport:
    """The serial transport the upstream driver owns; the driver's teardown only disconnects it."""

    def __init__(self):
        self.connected = True

    def disconnect(self):
        self.connected = False


class _FakeState:
    """The state object the upstream query_state returns: a normalized value with is_running."""

    def __init__(self, value):
        self.value = value

    @property
    def is_running(self):
        return self.value in ("infusing", "withdrawing")


class FakeHarvardPHD2000:
    def __init__(self, **_options):
        self.transport = _FakeTransport()
        self.address = 0                        # placeholder
        self.direction = "infuse"               # placeholder
        self.state = "stopped"                  # placeholder
        self._diameter_mm = 12.0                # placeholder
        self._rates = {                         # placeholder
            "infuse": (1.0, "ul/hr"),           # placeholder
            "withdraw": (1.0, "ul/hr"),         # placeholder
        }

    @staticmethod
    def _selected(direction):
        value = getattr(direction, "value", direction)
        if str(value).strip().lower() in {"withdraw", "withdrawal", "refill", "ref", "w"}:
            return "withdraw"
        return "infuse"

    def get_rate(self, direction=None):
        return self._rates[self._selected(direction or self.direction)]

    def set_rate(self, rate, units="ul/h", direction=None):
        selected = self._selected(direction or self.direction)
        self.direction = selected
        self._rates[selected] = (float(rate), str(units))

    def get_syringe_info(self):
        return {"manufacturer": "", "model": "", "diameter_mm": self._diameter_mm}

    def set_diameter(self, diameter_mm):
        self._diameter_mm = float(diameter_mm)

    def set_direction(self, direction):
        self.direction = self._selected(direction)

    def start(self):
        self.state = "infusing" if self.direction == "infuse" else "withdrawing"

    def stop(self):
        self.state = "stopped"

    def pause(self):
        self.stop()

    def resume(self):
        self.start()

    def run(self, direction=None):
        if direction is not None:
            self.set_direction(direction)
        self.start()

    def query_state(self):
        return _FakeState(self.state)

    def get_status(self):
        return self.state
