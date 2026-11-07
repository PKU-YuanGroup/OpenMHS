"""Fake backend of the LeCroy driver: an in-memory stand-in for the upstream ``lecroy:lecroy`` class.

Gate G7: every public method defined here is a method of the upstream ``lecroy`` class in the clone
(lecroy.py:15-384): the trigger and horizontal setup and their getters, the channel and measurement getters, the
measurement value reader, the grid setter and the reset.  The state attributes are private instance data, so the
fake surface is the upstream method surface.

The clone has no simulator and no recorded session for this class, so this file is a recording fake: it records
each native call in ``calls`` and keeps the settings in memory.  Every number and string below is test data, not
a fact from the clone or a record of an instrument: each is marked ``# placeholder``.  Nothing here talks to a
device.
"""


class FakeLecroy:
    """A fresh in-memory oscilloscope per endpoint; every starting value is a placeholder."""

    def __init__(self, **_options):
        self.calls = []
        self._trigger = {0: "C1", 1: 0.25, 2: 0.0, 3: "Either", 4: "Auto", 5: "Edge"}  # placeholder
        self._horizontal_scale = 1e-3                                                       # placeholder
        self._analog = {                                                                    # placeholder
            1: ("CH1", 0.5, 0.0, "20MHz", "DC1M"),                                          # placeholder
            2: ("CH2", 1.0, 0.0, "Full", "DC"),                                             # placeholder
        }
        self._digital = {0: "D0", 1: "D1"}                                                  # placeholder
        self._measurements = {1: ("C1", "pkpk")}                                            # placeholder
        self._values = {"P1": 1.0, "P2": 2.0}                                               # placeholder
        self._grid = "Single"                                                               # placeholder
        self.force_count = 0                                                                # placeholder
        self.reset_count = 0                                                                # placeholder

    # -- trigger and horizontal -----------------------------------------------------------------------------------
    def trigger_setup(self, channel, trig_level, trig_horizontal, trig_slope, trig_mode):
        self.calls.append(("trigger_setup", channel, trig_level, trig_horizontal, trig_slope, trig_mode))
        self._trigger = {
            0: str(channel),
            1: float(trig_level),
            2: float(trig_horizontal),
            3: str(trig_slope),
            4: str(trig_mode),
            5: "Edge",  # placeholder
        }

    def trigger_force(self):
        self.calls.append(("trigger_force",))
        self.force_count += 1

    def get_trigger_setup(self):
        self.calls.append(("get_trigger_setup",))
        return dict(self._trigger)

    def setHorizontal_delay(self, delay=0.0):
        self.calls.append(("setHorizontal_delay", delay))
        self._trigger[2] = float(delay)

    def horizontal_scale(self, scale=1e-3):
        self.calls.append(("horizontal_scale", scale))
        self._horizontal_scale = float(scale)

    def get_horizontal_scale(self):
        self.calls.append(("get_horizontal_scale",))
        return self._horizontal_scale

    # -- channels and measurements --------------------------------------------------------------------------------
    def get_analog_channel_setup(self):
        self.calls.append(("get_analog_channel_setup",))
        return dict(self._analog)

    def get_digital_channel_setup(self):
        self.calls.append(("get_digital_channel_setup",))
        return dict(self._digital)

    def get_measurement_setup(self):
        self.calls.append(("get_measurement_setup",))
        return dict(self._measurements)

    def getValueOnChannel(self, assigned_channel, stat_type="value"):
        self.calls.append(("getValueOnChannel", assigned_channel, stat_type))
        if stat_type == "status":
            return "Okay"  # placeholder
        return float(self._values.get(assigned_channel, 0.0))  # placeholder

    # -- display and reset ----------------------------------------------------------------------------------------
    def setGrid(self, gridmode="Single"):
        self.calls.append(("setGrid", gridmode))
        self._grid = str(gridmode)

    def reset_scope(self):
        self.calls.append(("reset_scope",))
        self.reset_count += 1
        self._trigger = {0: "C1", 1: 0.25, 2: 0.0, 3: "Either", 4: "Auto", 5: "Edge"}  # placeholder
        self._horizontal_scale = 1e-3                                                       # placeholder
        self._grid = "Single"                                                               # placeholder
