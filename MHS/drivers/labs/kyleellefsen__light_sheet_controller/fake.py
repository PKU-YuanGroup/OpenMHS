"""Fake backend of the light sheet controller: an in-memory stand-in for LightSheetDriver.

Gate G7: every public method defined here exists on ``light_sheet_controller:LightSheetDriver``
(light_sheet_controller.py:118-281), and the attributes the driver reaches (``settings``, ``stopped``,
``sample_rate`` and ``sampsPerPeriod``) are set by the upstream ``__init__`` and ``createTask``.  The fake keeps
state in plain attributes, implements the same methods, and never talks to a DAQ, Qt or a laser.

The upstream constructor starts both analog-output tasks (light_sheet_controller.py:145-148); the deployed
hardware factory calls ``gotozero`` after construction, so this fake starts in the same stopped state.  Every
starting number below is placeholder test data, not a fact or a limit: the clone's defaults are configuration
values of its GUI (~/.lightsheet/config.p, light_sheet_controller.py:73-92), not device facts.
"""


class FakeLightSheetController:
    def __init__(self, **_options):
        self.settings = {
            "sample_rate": 5000,          # placeholder
            "mV_per_pixel": 1,            # placeholder
            "maximum_displacement": 1,    # placeholder
            "nSteps": 5,                  # placeholder
            "step_duration": 10,          # placeholder
            "flyback_duration": 20,       # placeholder
            "total_cycle_period": 0.2,    # placeholder
            "dither_amp": 1,              # placeholder
            "triangle_scan": False,       # placeholder
            "offset": 0,                  # placeholder
            "alternate_lasers": False,    # placeholder
            "blue_laser_on": False,       # placeholder
        }
        self.sample_rate = int(self.settings["sample_rate"])
        self.sampsPerPeriod = 1           # placeholder
        self.data = [0.0]                 # placeholder
        self.data2 = [0.0]                # placeholder
        self.createTask()
        self.gotozero()

    def createTask(self):
        self.stopped = False

    def calculate(self):
        period = float(self.settings["total_cycle_period"])
        samples = int(period * self.sample_rate)
        self.sampsPerPeriod = max(1, samples)

    def startstop(self):
        if self.stopped:
            self.calculate()
            self.stopped = False
        else:
            self.dither_gotozero()
            self.stopped = True

    def refresh(self):
        if not self.stopped:
            self.calculate()

    def dither_gotozero(self):
        self.data2 = [0.0]                # placeholder

    def gotozero(self):
        self.data = [0.0]                 # placeholder
        self.data2 = [0.0]                # placeholder
        self.sampsPerPeriod = 1           # placeholder
        self.stopped = True

    def gotoend(self):
        volts = (float(self.settings["maximum_displacement"])
                 * float(self.settings["mV_per_pixel"]) / 1000.0)
        self.data = [volts]               # placeholder
        self.data2 = [0.0]                # placeholder
        self.sampsPerPeriod = 1           # placeholder
        self.stopped = True

    def gotobluelaser(self):
        if self.settings["blue_laser_on"]:
            return
        self.settings["blue_laser_on"] = True

    def gotoyellowlaser(self):
        if not self.settings["blue_laser_on"]:
            return
        self.settings["blue_laser_on"] = False
