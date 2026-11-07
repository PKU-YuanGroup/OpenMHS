"""Fake backend of the ZEN microscope driver: an in-memory stand-in for the ZEN blue connector.

Gate G7: every public method defined here exists on
``microscope_automation.connectors.connect_zen_blue:ConnectMicroscope``.  The signatures follow the upstream
methods (``snap_image(experiment=None)``, ``live_mode_start(experiment=None)``,
``live_mode_stop(experiment=None)``, ``get_stage_pos()``, ``get_objective_name()``, ``get_objective_position()``
and ``get_microscope_name()``) so the fake answers the same calls the real connector answers.  The values never
move by themselves, so reading the state twice gives the same state.  Nothing here talks to a device.

The start values below are test data only (# placeholder); they are not facts about any unit and they are not
copied into a Fact or a Limit.
"""


class FakeConnectMicroscope:
    """A ZEN blue connector that keeps its state in memory."""

    def __init__(self, **_options):
        self._x = 60000.0        # placeholder (test data, not a device fact)
        self._y = 40000.0        # placeholder (test data, not a device fact)
        self._objective_name = "Dummy Objective"   # placeholder
        self._objective_position = 0               # placeholder
        self._live = False
        self._experiment = None
        self._image = None

    def get_stage_pos(self):
        return self._x, self._y

    def get_objective_name(self):
        return self._objective_name

    def get_objective_position(self):
        return self._objective_position

    def get_microscope_name(self):
        return "ZEN blue simulation"   # placeholder

    def snap_image(self, experiment=None):
        self._experiment = experiment
        self._image = {"experiment": experiment}   # placeholder: a stand-in for the ZEN image object
        return None

    def live_mode_start(self, experiment=None):
        self._experiment = experiment
        self._live = True
        return {"experiment": experiment}          # placeholder: a stand-in for the live ZenImage

    def live_mode_stop(self, experiment=None):
        self._experiment = experiment
        self._live = False
        return None
