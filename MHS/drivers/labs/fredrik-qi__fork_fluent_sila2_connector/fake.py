"""Fake backend of the Tecan Fluent driver: an in-memory stand-in for tecan.__Fluent:Fluent.

Gate G7: every public name defined here exists on the upstream class ``Fluent``
(Python/src/tecan/__Fluent.py): start_fluent, prepare_method, run_method, pause_run, resume_run, stop_method,
aspirate, dispense, drop_tips, set_location, transfer_labware, transfer_labware_back_to_base, set_variable_value,
get_variable_value, get_variable_names and get_all_runnable_methods, plus the read-only properties state, progress
and lastError.  The methods are synchronous and return None, like the upstream wrapper.

The starting values and every canned reply are test data, not device facts; each numeric or state literal carries a
``# placeholder`` comment, except where a comment cites the clone.  The fake starts as if a start command had created
the connector's runtime, with a prepared method and a live execution channel, so that the gate can exercise every
action on a fresh endpoint; the real connector requires the operator to start FluentControl, prepare a method and
run a method that opens an execution channel first.

What the fake takes from the clone: StopMethod and the other runtime commands fail while no runtime exists
(AssertRuntime, SilaFluentController.cs:294-300), and a start prepares 'Method to prepare' (SilaFluentController.cs:374).
Its stop ends in RunModeRunFinished, the state the clone documents as "Run is finished or aborted"
(FluentControlState.cs:103-107), and ends the execution channel; the clone does not show StopMethod doing either.
Three test switches, passed as backend options, model what the default leaves out:

* ``attached=False``: no start command has run on this server process, so State reads Unknown (the C# initial
  value, SilaFluentController.cs:30) and every runtime command, StopMethod included, fails as AssertRuntime does;
* ``stop_ignored=True``: StopMethod answers but the run keeps running (State stays as it was);
* ``channel_checked=True``: the API-channel commands (aspirate, dispense, drop_tips, set_location, transfer_labware,
  transfer_labware_back_to_base) fail without a live execution channel, as TriggerCommand does
  (SilaFluentController.cs:341-358).  It is off by default because the conformance run's recovery probe (aspirate
  after an e-stop and a reset) would otherwise fail; the fake's stop ends the channel because a stopped run is not
  expected to keep it alive, which the clone does not state.

Nothing here talks to a device, models motion, or proves that the real StopMethod retracts tips, clears a worktable,
is idempotent or changes State the way this fake does.
"""


class _ExecutionError(RuntimeError):
    """What the fake raises where the connector answers a command with an execution error."""


class FakeFluent:
    def __init__(self, *, attached=True, stop_ignored=False, channel_checked=False, **_options):
        self.attached = bool(attached)              # test switch, see the module docstring
        self.stop_ignored = bool(stop_ignored)      # test switch
        self.channel_checked = bool(channel_checked)  # test switch
        self._state = "EditMode" if self.attached else "Unknown"  # placeholder; Unknown is the C# initial value
        self._progress = -1                      # placeholder
        self._last_error = ""                    # placeholder
        self._runnable = ["DemoMethod"]          # placeholder
        self._variables = {"DemoVariable": "0"}  # placeholder
        self._prepared = "DemoMethod"            # placeholder
        self._channel_alive = True               # placeholder
        self._labware = {}

    # The upstream wrapper exposes these as read-only properties.
    @property
    def state(self):
        return self._state

    @property
    def progress(self):
        return self._progress

    @property
    def lastError(self):
        return self._last_error

    def _require_runtime(self):
        if not self.attached:
            raise _ExecutionError("No runtime available. This may be because FluentControl has not been started.")

    def _require_channel(self):
        self._require_runtime()
        if self.channel_checked and not self._channel_alive:
            raise _ExecutionError("There is no execution channel available")

    # -- method lifecycle ---------------------------------------------------------------------------------------
    def start_fluent(self, username=None, password=None, simulation_mode=False):
        if username is None:
            if password is not None:
                raise AttributeError("username missing")
        elif password is None:
            raise AttributeError("password missing")
        self.attached = True
        self._prepared = "Method to prepare"     # the method name the connector prepares after a start
        self._state = "EditMode"                 # placeholder

    def prepare_method(self, to_prepare):
        self._require_runtime()
        self._prepared = str(to_prepare)
        self._state = "EditMode"                 # placeholder
        self._variables.setdefault(str(to_prepare), "0")  # placeholder

    def run_method(self):
        self._require_runtime()
        self._channel_alive = True               # placeholder: the run opens an execution channel
        self._state = "RunModeRunning"           # placeholder

    def pause_run(self):
        self._require_runtime()
        self._state = "RunModePaused"            # placeholder

    def resume_run(self):
        self._require_runtime()
        self._state = "RunModeRunning"           # placeholder

    def stop_method(self):
        self._require_runtime()
        if self.stop_ignored:
            return
        self._channel_alive = False
        self._state = "RunModeRunFinished"       # "Run is finished or aborted" (FluentControlState.cs:103-107)

    # -- pipetting ---------------------------------------------------------------------------------------------
    def aspirate(self, volume, labware, liquid_class, well_offset=0):
        self._require_channel()
        self._labware[str(labware)] = {"liquid_class": str(liquid_class), "well_offset": int(well_offset)}
        self._progress = 100                     # placeholder
        self._state = "RunModeRunning"           # placeholder

    def dispense(self, volume, labware, liquid_class, well_offset=0):
        self._require_channel()
        self._labware[str(labware)] = {"liquid_class": str(liquid_class), "well_offset": int(well_offset)}
        self._progress = 100                     # placeholder
        self._state = "RunModeRunning"           # placeholder

    def drop_tips(self, labware):
        self._require_channel()
        self._labware[str(labware)] = {"tips_dropped": True}
        self._state = "RunModeRunning"           # placeholder

    # -- labware and variables ---------------------------------------------------------------------------------
    def set_location(self, labware, rotation, target_location, target_site):
        self._require_channel()
        self._labware[str(labware)] = {"rotation": int(rotation), "target_location": str(target_location),
                                       "target_site": int(target_site)}
        self._state = "EditMode"                 # placeholder

    def transfer_labware(self, labware_to_location, target_location, target_position=0,
                         only_use_selected_site=True):
        self._require_channel()
        self._labware[str(labware_to_location)] = {"target_location": str(target_location),
                                                   "target_position": int(target_position),
                                                   "only_use_selected_site": bool(only_use_selected_site)}
        self._state = "RunModeRunning"           # placeholder

    def transfer_labware_back_to_base(self, labware_name):
        self._require_channel()
        self._labware[str(labware_name)] = {"base": True}
        self._state = "RunModeRunning"           # placeholder

    def set_variable_value(self, variable_name, value):
        self._require_runtime()
        self._variables[str(variable_name)] = str(value)

    def get_variable_value(self, variable_name):
        self._require_runtime()
        return self._variables.get(str(variable_name), "")  # placeholder for an unknown name

    def get_variable_names(self):
        self._require_runtime()
        return list(self._variables)

    def get_all_runnable_methods(self):
        self._require_runtime()
        return list(self._runnable)
