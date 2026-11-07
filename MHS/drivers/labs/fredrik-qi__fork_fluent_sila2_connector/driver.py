"""OpenMHS driver for gh.fredrik-qi/fork_fluent_sila2_connector: the Tecan Fluent liquid handler.

The pinned clone is a SiLA2 connector for Tecan FluentControl.  Its Python class
``tecan.__Fluent:Fluent`` (Python/src/tecan/__Fluent.py) is a client for the C# ``SilaFluentController`` feature and
the ``SilaFluentStatusProvider`` properties.  This package is a direct Driver over that class: every method below
forwards to a method of ``Fluent`` and every read forwards to one of its properties or getters.

Covered interface:

* reads: the FluentControl state, progress, last error, the runnable methods and the prepared method's variable names;
* actions: start/attach FluentControl, prepare a method, run the prepared method, pause/resume/stop a run, the
  connector's aspirate and dispense parameters, drop tips, set a labware location, transfer labware and set a method
  variable;
* the native stop is ``Fluent.stop_method()`` (``SilaFluentController.StopMethod``), confirmed by the connector's
  ``State``: the e-stop and the safe-state action ``x-cap.fredrik-qi.stop_method.v1`` each send it and then read
  ``State`` until it is ``RunModeRunFinished`` (documented as "Run is finished or aborted") or ``EditMode``, for at
  most ``STOP_CONFIRM_S``; any other state, or a failing call, is ``MHS.SAFETY.SAFE_STATE_UNREACHED`` and the latch
  stays.  There is no @reset: a reset only releases the latch and the next ordinary prepare/run command is the new
  start.

Deliberate limits of this package:

* The C# ``Aspirate`` fixes the well selection to ``8 * A1`` and ``Dispense`` fixes it to ``A1 - H1``; the connector's
  public parameters are a labware name and an integer well offset, not a well.  The standard
  ``cap.fluid.aspirate.v1`` / ``cap.fluid.dispense.v1`` classes require a ``source`` / ``target`` well and forbid the
  liquid-class parameter, so binding them would silently ignore a requested well.  The extension actions carry the
  connector's exact parameters instead.  The generated Aspirate, Dispense and DropTips scripts also name one fixed
  instrument ID (``USB:TECAN,MYRIUS,1310005667/LIHA:1``); what FluentControl does with it on another instrument is
  not in the clone.
* The clone states neither a volume unit nor a numeric range for any of the connector's integer parameters.  Every
  numeric action input is therefore ``Limit.operator_required``: it is refused ``MHS.SAFETY.LIMITS_UNSET`` until the
  operator's site-limits.json supplies the bound (site-limits.example.json is an example, not a device statement).
* The clone's stop surface is ``StopMethod`` (plus the soft ``FinishExecution`` and ``CloseMethod``); it documents no
  independent hardware e-stop and no proof that ``StopMethod`` retracts tips, clears a worktable or aborts an
  in-flight pipetting step.  ``State`` is the connector's cache of FluentControl mode-change events, not a fresh query
  of the instrument.  FluentControl and the robot remain powered.  The hardware path (native.py) has never been run.
  This package is model-authored and unreviewed, so the loader refuses its hardware backend at R2 until a human sets
  ``reviewed_by`` in driver.lock.json.
"""

import time

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read

#: States that confirm the stop (Server/Contracts/FluentControlState.cs:41-46 and 103-107); every other state is not.
STOPPED_STATES = ("RunModeRunFinished", "EditMode")
#: How long one stop call waits for a confirming State (seconds); the e-stop and the safe-state action each wait.
STOP_CONFIRM_S = 0.4
STOP_POLL_S = 0.05


def _volume_limit(operation: str) -> Limit:
    return Limit.operator_required(
        f"the clone declares the {operation} volume as an integer with no unit and no range; the site supplies "
        "the accepted range for its own liquid classes")


def _offset_limit(operation: str) -> Limit:
    return Limit.operator_required(
        f"the clone declares the {operation} well offset as an integer with no range; the site supplies the accepted "
        "range for its own labware")


class Fluent(Driver):
    device_id = "tecan-fluent"
    device_kind = "lab.liquid_handler"
    mode = "hardware"
    risk = "R2"
    native = "tecan.__Fluent:Fluent"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeFluent"}
    vendor = "Tecan"
    model = "FluentControl via SilaFluentController"
    display_name = "Tecan Fluent liquid handler"
    tags = ["liquid-handler", "pipetting", "fluentcontrol", "sila2", "labware"]
    facts = [
        Fact("Fluent is a SiLA2 client wrapper: it builds a SilaClient unless one is passed, and refuses a server "
             "without the SilaFluentController feature", source="upstream_code", ref="Python/src/tecan/__Fluent.py:20-34"),
        Fact("start_fluent() with no credentials calls StartFluentOrAttach; simulation_mode calls "
             "StartFluentInSimulationMode; a username and password call StartFluentAndLogin",
             source="upstream_code", ref="Python/src/tecan/__Fluent.py:262-287"),
        Fact("prepare_method() calls PrepareMethod and run_method() calls RunMethod on the SilaFluentController",
             source="upstream_code", ref="Python/src/tecan/__Fluent.py:184-201"),
        Fact("pause_run(), resume_run() and stop_method() call PauseRun, ResumeRun and StopMethod on the "
             "SilaFluentController", source="upstream_code", ref="Python/src/tecan/__Fluent.py:203-215"),
        Fact("The stop_method docstring says it stops a method run and recommends finish_execution() for a soft stop",
             source="upstream_code", ref="Python/src/tecan/__Fluent.py:212-215"),
        Fact("StopMethod is an unobservable command without parameters, described as 'Stops the method'",
             source="upstream_code", ref="Server/SilaFluentServer/SilaFluentController.sila.xml:500-505"),
        Fact("The server's StopMethod handler calls the implementation's StopMethod and returns an empty response; "
             "it has no try/catch", source="upstream_code",
             ref="Server/SilaFluentServer/SilaFluentController/Provider.cs:677-681"),
        Fact("The C# StopMethod calls AssertRuntime() and then _runtime.StopMethod()", source="upstream_code",
             ref="Server/SilaFluentController/SilaFluentController.cs:179-183"),
        Fact("AssertRuntime throws InvalidOperationException while no runtime exists ('This may be because "
             "FluentControl has not been started')", source="upstream_code",
             ref="Server/SilaFluentController/SilaFluentController.cs:294-300"),
        Fact("CreateRuntimeAndRegisterEvents takes the runtime from the FluentControl process and registers the "
             "ChannelOpens, ModeChanged, ProgressChanged and Error handlers", source="upstream_code",
             ref="Server/SilaFluentController/SilaFluentController.cs:311-318"),
        Fact("The connector's State starts as FluentControlState.Unknown and its Progress as -1",
             source="upstream_code", ref="Server/SilaFluentController/SilaFluentController.cs:30-31"),
        Fact("Runtime_ModeChanged sets State by casting the runtime's StateMachineStates value to FluentControlState",
             source="upstream_code", ref="Server/SilaFluentController/SilaFluentController.cs:377-384"),
        Fact("The status provider's GetState returns the implementation's State property", source="upstream_code",
             ref="Server/SilaFluentServer/SilaFluentStatusProvider/Provider.cs:74-77"),
        Fact("The status provider declares State (FluentControlState), Progress (Integer) and LastError (String) as "
             "observable properties", source="upstream_code",
             ref="Server/SilaFluentServer/SilaFluentStatusProvider.sila.xml:6-31"),
        Fact("FluentControlState is a String constrained to a set of named states, among them EditMode, "
             "RunModeRunning, RunModePaused, RunModeStopOnError, RunModeRunFinished and Unknown",
             source="upstream_code", ref="Server/SilaFluentServer/SilaFluentStatusProvider.sila.xml:33-70"),
        Fact("FluentControlState documents EditMode as 'Application is in edit mode'", source="upstream_code",
             ref="Server/Contracts/FluentControlState.cs:41-46"),
        Fact("FluentControlState documents RunModeRunFinished as 'Run mode is active; Run is finished or aborted'",
             source="upstream_code", ref="Server/Contracts/FluentControlState.cs:103-107"),
        Fact("Aspirate and Dispense take an integer volume, a labware name, a liquid-class name and an integer well "
             "offset", source="upstream_code", ref="Server/Contracts/ISilaFluentController.cs:120-139"),
        Fact("The Aspirate command class takes only a volume, a labware, a liquid class and a well offset",
             source="upstream_code", ref="Server/SilaFluentController/Aspirate.cs:12-18"),
        Fact("Aspirate's generated script writes the same volume into each of its eight Volumes entries",
             source="upstream_code", ref="Server/SilaFluentController/Aspirate.cs:33-58"),
        Fact("Aspirate's generated script fixes SelectedWellsString '8 * A1' and selected tip indexes 0 to 7, and "
             "inserts the WellOffset", source="upstream_code", ref="Server/SilaFluentController/Aspirate.cs:70-100"),
        Fact("Aspirate's generated script names the device alias Instrument=1/Device=LIHA:1 and the fixed device ID "
             "USB:TECAN,MYRIUS,1310005667/LIHA:1", source="upstream_code",
             ref="Server/SilaFluentController/Aspirate.cs:111-116"),
        Fact("The Dispense command class takes only a volume, a labware, a liquid class and a well offset",
             source="upstream_code", ref="Server/SilaFluentController/Dispense.cs:13-19"),
        Fact("Dispense's generated script writes the same volume into each of its eight Volumes entries",
             source="upstream_code", ref="Server/SilaFluentController/Dispense.cs:33-58"),
        Fact("Dispense's generated script fixes SelectedWellsString 'A1 - H1' and selected tip indexes 0 to 7, and "
             "inserts the WellOffset", source="upstream_code", ref="Server/SilaFluentController/Dispense.cs:70-100"),
        Fact("Dispense's generated script names the device alias Instrument=1/Device=LIHA:1 and the fixed device ID "
             "USB:TECAN,MYRIUS,1310005667/LIHA:1", source="upstream_code",
             ref="Server/SilaFluentController/Dispense.cs:111-116"),
        Fact("DropTips' generated script names the device alias Instrument=1/Device=LIHA:1 and the fixed device ID "
             "USB:TECAN,MYRIUS,1310005667/LIHA:1", source="upstream_code",
             ref="Server/SilaFluentController/DropTips.cs:66-71"),
        Fact("PrepareMethod runs 'cmd.exe /c rd' against the Journaling/000 and Journaling/ToDelete directories "
             "before _runtime.PrepareMethod", source="upstream_code",
             ref="Server/SilaFluentController/SilaFluentController.cs:153-159"),
        Fact("get_all_runnable_methods returns GetAllRunnableMethods().ReturnValue; its docstring says it can only "
             "show methods that are visible in touchtools", source="upstream_code",
             ref="Python/src/tecan/__Fluent.py:250-255"),
        Fact("get_variable_names only works if a method is prepared but not yet running", source="upstream_code",
             ref="Python/src/tecan/__Fluent.py:233-239"),
        Fact("set_variable_value sends the variable name and the string form of the value to SetVariableValue",
             source="upstream_code", ref="Python/src/tecan/__Fluent.py:222-231"),
        Fact("TriggerCommand executes a command only when the current execution channel exists and IsAlive; "
             "otherwise it throws NoExecutionChannelException", source="upstream_code",
             ref="Server/SilaFluentController/SilaFluentController.cs:341-358"),
        Fact("StartFluentOrAttach waits on _waitForRuntimeIsReady.Wait() with no timeout when FluentControl was not "
             "already running", source="upstream_code",
             ref="Server/SilaFluentController/SilaFluentController.cs:260-274"),
        Fact("PrepareMethodRun waits on _waitForEditMode.Wait() with no timeout unless the runtime reports EditMode, "
             "then calls _runtime.PrepareMethod('Method to prepare')", source="upstream_code",
             ref="Server/SilaFluentController/SilaFluentController.cs:368-376"),
        Fact("set_location, transfer_labware and transfer_labware_back_to_base call the same-named "
             "SilaFluentController commands", source="upstream_code", ref="Python/src/tecan/__Fluent.py:74-112"),
        Fact("drop_tips calls DropTips on the SilaFluentController", source="upstream_code",
             ref="Python/src/tecan/__Fluent.py:176-181"),
        Fact("The SiLA SimulationController reports SimulationMode false and its StartSimulationMode throws",
             source="upstream_code", ref="Server/SilaFluentServer/SimulationController/SimulationController.cs:14-23"),
        Fact("The README says to install the server with the Windows installer in the Binaries folder and then "
             "start SilaFluentServer.exe", source="vendor_doc", ref="README.md:54-57"),
        Fact("LICENSE is the BSD 3-Clause License, copyright 2019 Tecan Trading AG", source="vendor_doc",
             ref="LICENSE:1-3"),
        Fact("Python/pyproject.toml lists the classifier 'License :: OSI Approved :: MIT License'",
             source="upstream_code", ref="Python/pyproject.toml:18"),
    ]
    safe_state = ("After StopMethod returned, the connector's State reads RunModeRunFinished (documented as finished "
                  "or aborted) or EditMode within 0.4 s, else SAFE_STATE_UNREACHED with the latch held; State caches "
                  "FluentControl mode-change events (not a fresh query), StopMethod's effect on an API command in "
                  "flight is not in the clone, and FluentControl and the instrument stay powered with tips, liquid "
                  "and labware where the stop left them.")

    # -- reads -------------------------------------------------------------------------------------------------
    @read("state", type="string", description="FluentControl state (SilaFluentStatusProvider.State)")
    def state(self):
        return str(self.native.state)

    @read("progress", type="integer", description="Last progress update (SilaFluentStatusProvider.Progress)")
    def progress(self):
        return int(self.native.progress)

    @read("last_error", type="string", description="Last error message (SilaFluentStatusProvider.LastError)")
    def last_error(self):
        return str(self.native.lastError or "")

    @read("runnable_methods", type="array", items="string",
          description="Methods that FluentControl reports as runnable and visible in touchtools")
    def runnable_methods(self):
        return [str(item) for item in (self.native.get_all_runnable_methods() or [])]

    @read("variable_names", type="array", items="string",
          description="Variables of the prepared method (only available while a method is prepared and not running)")
    def variable_names(self):
        return [str(item) for item in (self.native.get_variable_names() or [])]

    # -- method lifecycle actions ------------------------------------------------------------------------------
    @action(name="x-cap.fredrik-qi.start_fluent.v1",
            description="Start FluentControl or attach to a running instance without credentials; the connector "
                        "may wait without a timeout and then prepares the method 'Method to prepare'",
            output={"state": Field("string", description="FluentControl state after the command")})
    def start_fluent(self):
        self.native.start_fluent()
        return {"state": str(self.native.state)}

    @action(name="x-cap.fredrik-qi.prepare_method.v1",
            description="Prepare a FluentControl method; the connector deletes the Journaling/000 and "
                        "Journaling/ToDelete directories before preparing",
            input={"method": Field("string", description="Name of the FluentControl method to prepare")},
            output={"state": Field("string", description="FluentControl state after the command"),
                    "method": Field("string", description="Method name reported back from the command")})
    def prepare_method(self, method):
        self.native.prepare_method(to_prepare=method)
        return {"state": str(self.native.state), "method": method}

    @action(name="x-cap.fredrik-qi.run_method.v1",
            description="Run the currently prepared FluentControl method",
            output={"state": Field("string", description="FluentControl state after the command")})
    def run_method(self):
        self.native.run_method()
        return {"state": str(self.native.state)}

    @action(name="x-cap.fredrik-qi.pause_run.v1",
            description="Pause the current FluentControl method; this is not the safe-state stop",
            output={"state": Field("string", description="FluentControl state after the command")})
    def pause_run(self):
        self.native.pause_run()
        return {"state": str(self.native.state)}

    @action(name="x-cap.fredrik-qi.resume_run.v1",
            description="Resume a method paused by pause_run",
            output={"state": Field("string", description="FluentControl state after the command")})
    def resume_run(self):
        self.native.resume_run()
        return {"state": str(self.native.state)}

    @action(name="x-cap.fredrik-qi.stop_method.v1", safe_state=True,
            description="Stop the running method (SilaFluentController.StopMethod) and confirm that State reads "
                        "RunModeRunFinished or EditMode; it takes no input",
            output={"state": Field("string", description="FluentControl state that confirmed the stop")})
    def stop_method(self):
        return {"state": self._stop_confirmed()}

    # -- pipetting actions -------------------------------------------------------------------------------------
    @action(name="x-cap.fredrik-qi.aspirate.v1",
            description="Aspirate with the connector's fixed 8-tip A1 selection; it requires a live execution "
                        "channel and passes the volume, labware, liquid class and well offset through unchanged",
            input={
                "volume": Field("integer", description="Aspirate volume passed to SilaFluentController.Aspirate; "
                                                       "the clone states no unit",
                                limit=_volume_limit("aspirate")),
                "labware": Field("string", description="Source labware name passed to SilaFluentController.Aspirate"),
                "liquid_class": Field("string",
                                      description="Liquid-class name passed to SilaFluentController.Aspirate"),
                "well_offset": Field("integer", unit="1",
                                     description="Well offset passed to SilaFluentController.Aspirate",
                                     limit=_offset_limit("aspirate")),
            },
            output={
                "state": Field("string", description="FluentControl state after the command"),
                "volume": Field("integer", description="Volume reported back from the command; the connector "
                                                       "reports no measured aspirated volume"),
                "labware": Field("string", description="Labware name reported back from the command"),
                "liquid_class": Field("string", description="Liquid-class name reported back from the command"),
                "well_offset": Field("integer", description="Well offset reported back from the command"),
            })
    def aspirate(self, volume, labware, liquid_class, well_offset):
        self.native.aspirate(volume=volume, labware=labware, liquid_class=liquid_class, well_offset=well_offset)
        return {"state": str(self.native.state), "volume": volume, "labware": labware,
                "liquid_class": liquid_class, "well_offset": well_offset}

    @action(name="x-cap.fredrik-qi.dispense.v1",
            description="Dispense with the connector's fixed A1-H1 8-tip selection; it requires a live execution "
                        "channel and passes the volume, labware, liquid class and well offset through unchanged",
            input={
                "volume": Field("integer", description="Dispense volume passed to SilaFluentController.Dispense; "
                                                       "the clone states no unit",
                                limit=_volume_limit("dispense")),
                "labware": Field("string", description="Target labware name passed to SilaFluentController.Dispense"),
                "liquid_class": Field("string",
                                      description="Liquid-class name passed to SilaFluentController.Dispense"),
                "well_offset": Field("integer", unit="1",
                                     description="Well offset passed to SilaFluentController.Dispense",
                                     limit=_offset_limit("dispense")),
            },
            output={
                "state": Field("string", description="FluentControl state after the command"),
                "volume": Field("integer", description="Volume reported back from the command; the connector "
                                                       "reports no measured dispensed volume"),
                "labware": Field("string", description="Labware name reported back from the command"),
                "liquid_class": Field("string", description="Liquid-class name reported back from the command"),
                "well_offset": Field("integer", description="Well offset reported back from the command"),
            })
    def dispense(self, volume, labware, liquid_class, well_offset):
        self.native.dispense(volume=volume, labware=labware, liquid_class=liquid_class, well_offset=well_offset)
        return {"state": str(self.native.state), "volume": volume, "labware": labware,
                "liquid_class": liquid_class, "well_offset": well_offset}

    @action(name="x-cap.fredrik-qi.drop_tips.v1",
            description="Drop the mounted disposable tips into the named labware",
            input={"labware": Field("string", description="Labware name passed to SilaFluentController.DropTips")},
            output={"state": Field("string", description="FluentControl state after the command"),
                    "labware": Field("string", description="Labware name reported back from the command")})
    def drop_tips(self, labware):
        self.native.drop_tips(labware=labware)
        return {"state": str(self.native.state), "labware": labware}

    # -- labware and variable actions --------------------------------------------------------------------------
    @action(name="x-cap.fredrik-qi.set_location.v1",
            description="Set the location of a labware on the worktable",
            input={
                "labware": Field("string", description="Labware name passed to SilaFluentController.SetLocation"),
                "rotation": Field("integer", description="Rotation passed to SilaFluentController.SetLocation",
                                  limit=Limit.operator_required(
                                      "the clone declares the labware rotation as an integer with no allowed values; "
                                      "the site supplies the rotations its labware permits")),
                "target_location": Field("string",
                                         description="Target location group passed to "
                                                     "SilaFluentController.SetLocation"),
                "target_site": Field("integer", unit="1",
                                     description="Target site passed to SilaFluentController.SetLocation",
                                     limit=Limit.operator_required(
                                         "the clone declares the target site as an integer with no range; the site "
                                         "supplies the site indexes of its worktable")),
            },
            output={"state": Field("string", description="FluentControl state after the command"),
                    "labware": Field("string", description="Labware name reported back from the command"),
                    "rotation": Field("integer", description="Rotation reported back from the command"),
                    "target_location": Field("string", description="Target location reported back from the command"),
                    "target_site": Field("integer", description="Target site reported back from the command")})
    def set_location(self, labware, rotation, target_location, target_site):
        self.native.set_location(labware=labware, rotation=rotation, target_location=target_location,
                                 target_site=target_site)
        return {"state": str(self.native.state), "labware": labware, "rotation": rotation,
                "target_location": target_location, "target_site": target_site}

    @action(name="x-cap.fredrik-qi.transfer_labware.v1",
            description="Transfer labware on the worktable with the RGA",
            input={
                "labware_to_location": Field("string",
                                             description="Labware name passed to "
                                                         "SilaFluentController.TransferLabware"),
                "target_location": Field("string",
                                         description="Target location group passed to "
                                                     "SilaFluentController.TransferLabware"),
                "target_position": Field("integer", unit="1",
                                         description="Target position passed to SilaFluentController.TransferLabware",
                                         limit=Limit.operator_required(
                                             "the clone declares the target position as an integer with no range; the "
                                             "site supplies the positions of its worktable")),
                "only_use_selected_site": Field("boolean",
                                                description="Only-use-selected-site flag passed to "
                                                            "SilaFluentController.TransferLabware"),
            },
            output={"state": Field("string", description="FluentControl state after the command"),
                    "labware_to_location": Field("string", description="Labware name reported back from the "
                                                                      "command"),
                    "target_location": Field("string", description="Target location reported back from the command"),
                    "target_position": Field("integer", description="Target position reported back from the "
                                                                   "command"),
                    "only_use_selected_site": Field("boolean", description="Only-use-selected-site flag reported "
                                                                          "back from the command")})
    def transfer_labware(self, labware_to_location, target_location, target_position, only_use_selected_site):
        self.native.transfer_labware(labware_to_location=labware_to_location, target_location=target_location,
                                     target_position=target_position,
                                     only_use_selected_site=only_use_selected_site)
        return {"state": str(self.native.state), "labware_to_location": labware_to_location,
                "target_location": target_location, "target_position": target_position,
                "only_use_selected_site": only_use_selected_site}

    @action(name="x-cap.fredrik-qi.transfer_labware_back_to_base.v1",
            description="Transfer labware back to the spot where it was added to the worktable",
            input={"labware_name": Field("string",
                                         description="Labware name passed to "
                                                     "SilaFluentController.TransferLabwareBackToBase")},
            output={"state": Field("string", description="FluentControl state after the command"),
                    "labware_name": Field("string", description="Labware name reported back from the command")})
    def transfer_labware_back_to_base(self, labware_name):
        self.native.transfer_labware_back_to_base(labware_name=labware_name)
        return {"state": str(self.native.state), "labware_name": labware_name}

    @action(name="x-cap.fredrik-qi.set_variable_value.v1",
            description="Set a variable of the prepared method and read it back",
            input={
                "variable_name": Field("string", description="Variable name passed to "
                                                             "SilaFluentController.SetVariableValue"),
                "value": Field("string", description="String value passed to SilaFluentController.SetVariableValue"),
            },
            output={"value": Field("string", description="Value read back from the prepared method")})
    def set_variable_value(self, variable_name, value):
        self.native.set_variable_value(variable_name=variable_name, value=value)
        return {"value": str(self.native.get_variable_value(variable_name))}

    # -- safety ------------------------------------------------------------------------------------------------
    @estop(native="stop_method")
    def stop(self):
        """The native stop: SilaFluentController.StopMethod through Fluent.stop_method(), confirmed by State."""
        self._stop_confirmed()

    def _stop_confirmed(self):
        """Send StopMethod, then read State until it confirms the stop; any other outcome is not a safe state.

        A failing StopMethod (no runtime yet, a server error) propagates.  The confirmation reads the connector's
        cached State (the last FluentControl mode change), so a mode change the connector has not received yet is
        not seen.  Every call sends StopMethod again: a repeated stop is kept rather than a lost one.
        """
        self.native.stop_method()
        deadline = time.monotonic() + STOP_CONFIRM_S
        while True:
            state = str(self.native.state)
            if state in STOPPED_STATES:
                return state
            if time.monotonic() >= deadline:
                raise DriverFailed("MHS.SAFETY.SAFE_STATE_UNREACHED",
                                   f"StopMethod returned but State reads {state!r}, not RunModeRunFinished or "
                                   "EditMode")
            time.sleep(STOP_POLL_S)
