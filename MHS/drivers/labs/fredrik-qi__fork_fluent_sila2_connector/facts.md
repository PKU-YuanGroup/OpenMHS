# Facts and tags for gh.fredrik-qi/fork_fluent_sila2_connector

Every fact cites its source at commit `4a2f857c619c5bcead352b52622a72cc2d356ffe`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Fluent is a SiLA2 client wrapper: it builds a SilaClient unless one is passed, and refuses a server without the SilaFluentController feature | upstream_code | Python/src/tecan/__Fluent.py:20-34 |
| start_fluent() with no credentials calls StartFluentOrAttach; simulation_mode calls StartFluentInSimulationMode; a username and password call StartFluentAndLogin | upstream_code | Python/src/tecan/__Fluent.py:262-287 |
| prepare_method() calls PrepareMethod and run_method() calls RunMethod on the SilaFluentController | upstream_code | Python/src/tecan/__Fluent.py:184-201 |
| pause_run(), resume_run() and stop_method() call PauseRun, ResumeRun and StopMethod on the SilaFluentController | upstream_code | Python/src/tecan/__Fluent.py:203-215 |
| The stop_method docstring says it stops a method run and recommends finish_execution() for a soft stop | upstream_code | Python/src/tecan/__Fluent.py:212-215 |
| StopMethod is an unobservable command without parameters, described as 'Stops the method' | upstream_code | Server/SilaFluentServer/SilaFluentController.sila.xml:500-505 |
| The server's StopMethod handler calls the implementation's StopMethod and returns an empty response; it has no try/catch | upstream_code | Server/SilaFluentServer/SilaFluentController/Provider.cs:677-681 |
| The C# StopMethod calls AssertRuntime() and then _runtime.StopMethod() | upstream_code | Server/SilaFluentController/SilaFluentController.cs:179-183 |
| AssertRuntime throws InvalidOperationException while no runtime exists ('This may be because FluentControl has not been started') | upstream_code | Server/SilaFluentController/SilaFluentController.cs:294-300 |
| CreateRuntimeAndRegisterEvents takes the runtime from the FluentControl process and registers the ChannelOpens, ModeChanged, ProgressChanged and Error handlers | upstream_code | Server/SilaFluentController/SilaFluentController.cs:311-318 |
| The connector's State starts as FluentControlState.Unknown and its Progress as -1 | upstream_code | Server/SilaFluentController/SilaFluentController.cs:30-31 |
| Runtime_ModeChanged sets State by casting the runtime's StateMachineStates value to FluentControlState | upstream_code | Server/SilaFluentController/SilaFluentController.cs:377-384 |
| The status provider's GetState returns the implementation's State property | upstream_code | Server/SilaFluentServer/SilaFluentStatusProvider/Provider.cs:74-77 |
| The status provider declares State (FluentControlState), Progress (Integer) and LastError (String) as observable properties | upstream_code | Server/SilaFluentServer/SilaFluentStatusProvider.sila.xml:6-31 |
| FluentControlState is a String constrained to a set of named states, among them EditMode, RunModeRunning, RunModePaused, RunModeStopOnError, RunModeRunFinished and Unknown | upstream_code | Server/SilaFluentServer/SilaFluentStatusProvider.sila.xml:33-70 |
| FluentControlState documents EditMode as 'Application is in edit mode' | upstream_code | Server/Contracts/FluentControlState.cs:41-46 |
| FluentControlState documents RunModeRunFinished as 'Run mode is active; Run is finished or aborted' | upstream_code | Server/Contracts/FluentControlState.cs:103-107 |
| Aspirate and Dispense take an integer volume, a labware name, a liquid-class name and an integer well offset | upstream_code | Server/Contracts/ISilaFluentController.cs:120-139 |
| The Aspirate command class takes only a volume, a labware, a liquid class and a well offset | upstream_code | Server/SilaFluentController/Aspirate.cs:12-18 |
| Aspirate's generated script writes the same volume into each of its eight Volumes entries | upstream_code | Server/SilaFluentController/Aspirate.cs:33-58 |
| Aspirate's generated script fixes SelectedWellsString '8 * A1' and selected tip indexes 0 to 7, and inserts the WellOffset | upstream_code | Server/SilaFluentController/Aspirate.cs:70-100 |
| Aspirate's generated script names the device alias Instrument=1/Device=LIHA:1 and the fixed device ID USB:TECAN,MYRIUS,1310005667/LIHA:1 | upstream_code | Server/SilaFluentController/Aspirate.cs:111-116 |
| The Dispense command class takes only a volume, a labware, a liquid class and a well offset | upstream_code | Server/SilaFluentController/Dispense.cs:13-19 |
| Dispense's generated script writes the same volume into each of its eight Volumes entries | upstream_code | Server/SilaFluentController/Dispense.cs:33-58 |
| Dispense's generated script fixes SelectedWellsString 'A1 - H1' and selected tip indexes 0 to 7, and inserts the WellOffset | upstream_code | Server/SilaFluentController/Dispense.cs:70-100 |
| Dispense's generated script names the device alias Instrument=1/Device=LIHA:1 and the fixed device ID USB:TECAN,MYRIUS,1310005667/LIHA:1 | upstream_code | Server/SilaFluentController/Dispense.cs:111-116 |
| DropTips' generated script names the device alias Instrument=1/Device=LIHA:1 and the fixed device ID USB:TECAN,MYRIUS,1310005667/LIHA:1 | upstream_code | Server/SilaFluentController/DropTips.cs:66-71 |
| PrepareMethod runs 'cmd.exe /c rd' against the Journaling/000 and Journaling/ToDelete directories before _runtime.PrepareMethod | upstream_code | Server/SilaFluentController/SilaFluentController.cs:153-159 |
| get_all_runnable_methods returns GetAllRunnableMethods().ReturnValue; its docstring says it can only show methods that are visible in touchtools | upstream_code | Python/src/tecan/__Fluent.py:250-255 |
| get_variable_names only works if a method is prepared but not yet running | upstream_code | Python/src/tecan/__Fluent.py:233-239 |
| set_variable_value sends the variable name and the string form of the value to SetVariableValue | upstream_code | Python/src/tecan/__Fluent.py:222-231 |
| TriggerCommand executes a command only when the current execution channel exists and IsAlive; otherwise it throws NoExecutionChannelException | upstream_code | Server/SilaFluentController/SilaFluentController.cs:341-358 |
| StartFluentOrAttach waits on _waitForRuntimeIsReady.Wait() with no timeout when FluentControl was not already running | upstream_code | Server/SilaFluentController/SilaFluentController.cs:260-274 |
| PrepareMethodRun waits on _waitForEditMode.Wait() with no timeout unless the runtime reports EditMode, then calls _runtime.PrepareMethod('Method to prepare') | upstream_code | Server/SilaFluentController/SilaFluentController.cs:368-376 |
| set_location, transfer_labware and transfer_labware_back_to_base call the same-named SilaFluentController commands | upstream_code | Python/src/tecan/__Fluent.py:74-112 |
| drop_tips calls DropTips on the SilaFluentController | upstream_code | Python/src/tecan/__Fluent.py:176-181 |
| The SiLA SimulationController reports SimulationMode false and its StartSimulationMode throws | upstream_code | Server/SilaFluentServer/SimulationController/SimulationController.cs:14-23 |
| The README says to install the server with the Windows installer in the Binaries folder and then start SilaFluentServer.exe | vendor_doc | README.md:54-57 |
| LICENSE is the BSD 3-Clause License, copyright 2019 Tecan Trading AG | vendor_doc | LICENSE:1-3 |
| Python/pyproject.toml lists the classifier 'License :: OSI Approved :: MIT License' | upstream_code | Python/pyproject.toml:18 |

Limits: every numeric action input (aspirate/dispense volume and well offset, set_location rotation and target site,
transfer_labware target position) is `Limit.operator_required`. The clone declares each one as a bare integer with no
unit, no allowed set and no range; `site-limits.example.json` supplies example-only bounds for the gate, not a statement
about any worktable. The generated Aspirate and Dispense scripts write the one volume into all eight `Volumes` entries
next to eight selected tip indexes (0 to 7), so a site should read the volume as per tip, not per call, until the
instrument shows otherwise.

Safety: the e-stop and the safe-state action `x-cap.fredrik-qi.stop_method.v1` both call the native
`Fluent.stop_method()` (SilaFluentController.StopMethod, Python/src/tecan/__Fluent.py:212-215 and
Server/SilaFluentController/SilaFluentController.cs:179-183) and then read the connector's `State` until it is
`RunModeRunFinished` (documented as "Run is finished or aborted", Server/Contracts/FluentControlState.cs:103-107) or
`EditMode`, for at most 0.4 s each; any other state, or a failing call, gives `MHS.SAFETY.SAFE_STATE_UNREACHED` with the
latch held, and the runtime retries the stop in the background. What this confirmation does not prove:

- `State` is the connector's cache of FluentControl's mode-change events (SilaFluentController.cs:377-384), set by an
  integer cast from the runtime's `StateMachineStates`, which is not in the clone; a mode change the connector has not
  received yet is not seen.
- StopMethod needs a runtime that a start command created on this server process (AssertRuntime,
  SilaFluentController.cs:294-300): before `start_fluent`, every e-stop is SAFE_STATE_UNREACHED, also while a method
  started from FluentControl itself is running.
- The clone documents no independent hardware e-stop, no retraction of tips, no cancellation of an in-flight pipetting
  or gripper command by StopMethod, no client deadline on the SiLA call, and no idempotence (the runtime sends
  StopMethod at least twice per e-stop: the native stop and the safe-state action). FluentControl and the instrument
  stay powered.
- The API commands (aspirate, dispense, drop_tips, set_location, transfer_labware, transfer_labware_back_to_base) run
  only through a live execution channel that a running method opens (TriggerCommand, SilaFluentController.cs:341-358,
  335-339); the clone does not say whether a stopped run's channel stays alive, so expect them to fail after a stop
  until a new run opens one. The fake models that only with its `channel_checked` switch, because the conformance
  run's recovery probe (aspirate after an e-stop and a reset) needs the default fake to keep serving.

Model review notes (claude-opus-5-5, a model and not a human, 2026-11-05):

- The generated Aspirate, Dispense and DropTips scripts name one fixed instrument ID,
  `USB:TECAN,MYRIUS,1310005667/LIHA:1` (Aspirate.cs:111-116, Dispense.cs:111-116, DropTips.cs:66-71); what
  FluentControl does with it on any other instrument is not in the clone.
- `run_method` runs whatever method is prepared and `set_variable_value` sets any variable of it: the envelope bounds
  only this package's own numeric inputs, not what a FluentControl method does.
- `prepare_method` deletes FluentControl's Journaling/000 and Journaling/ToDelete directories before it prepares
  (SilaFluentController.cs:153-159).
- Licence: LICENSE is BSD 3-Clause (LICENSE:1-3) while Python/pyproject.toml:18 lists the MIT classifier; the card
  says BSD-3-Clause. The server is distributed as a prebuilt Windows installer (Binaries/, README.md:54-57).
- The wrapper passes multi-parameter commands as one tuple (for example Python/src/tecan/__Fluent.py:156-158) against
  the pinned `sila2==0.1.0`; whether that client accepts the form is not shown in the clone.

The hardware path was never run, and this R2 package is model-authored and unreviewed.

Tags: liquid-handler, pipetting, fluentcontrol, sila2, labware
