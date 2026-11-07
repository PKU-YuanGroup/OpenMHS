# Facts and tags for gh.ad-sdl/pal_module

Every fact cites its source at commit `31da19a869362cbc1766ffca0508f84ccdb8405e`: `vendor_doc` (a text file of the
clone) or `upstream_code` (`path/in/clone.py:LINE`).  The driver repeats each fact; the reference file is generated
from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| PALService is the PAL3 robot service: its constructor creates the DirectFactory driver, starts routing, resolves the configuration and direct services and calls start_remote_service | upstream_code | PAL3_driver.py:512-626 |
| When no host is given, the constructor uses the PAL1 address 192.168.99.230 | upstream_code | PAL3_driver.py:514-525 |
| At import PAL3_driver imports clr and keyboard, adds a reference to System, calls os.getlogin(), appends a Windows Dropbox path to sys.path and imports CustomTracker and ContainerManager from it | upstream_code | PAL3_driver.py:1-22 |
| The upstream MADSci node constructs PALService and calls std_start('test') at startup | upstream_code | PAL_module.py:40-42 |
| std_start locks the left head, creates a new execution session, sends a status message and homes the arm | upstream_code | PAL3_driver.py:664-671 |
| set_active_modules calls std_PAL1_start only when the host is the PAL1 address and std_nmr_start only when it is the NMR address; std_PAL1_start looks up the fast wash, wash, waste, centrifuge, vortex, dilutor, gripper, syringe and dilutor tool modules by name | upstream_code | PAL3_driver.py:803-824 |
| get_current_pos calls GetArmPosition and get_xyz converts the returned EuclideanVector from metres to millimetres | upstream_code | PAL3_driver.py:903-917 |
| move_absolute creates a MoveAbsolute activity, sets DestinationX, DestinationY and DestinationZ with units.GetMilliMeter, calls session.Execute and then get_current_pos | upstream_code | PAL3_driver.py:950-963 |
| move_relative creates a MoveRelative activity, sets MovementX, MovementY and MovementZ with units.GetMilliMeter for the non-zero components only, sets ForceDirectMovement, calls session.Execute and then get_current_pos | upstream_code | PAL3_driver.py:965-978 |
| safe_home is defined twice with the same body: safe_getout, which moves relative only when safe.inside is set, then MoveToHome, then safe.inside is cleared | upstream_code | PAL3_driver.py:1012-1027 |
| set_vial resolves the address with set_pos/GetVial and allocates a vial from the current execution session | upstream_code | PAL3_driver.py:856-866 |
| move_gripper checks the target and then the source with detect_object; when the target is free and the source is found it executes the grab activity, moves above the target with gripper2object, moves the adapter to gr.width, grips and returns 0, otherwise it calls LeaveObject and returns 1 | upstream_code | PAL3_driver.py:1829-1860 |
| gripper_distance reads GenericGripperGetAdapterDistance and converts the reported metres to millimetres | upstream_code | PAL3_driver.py:1890-1895 |
| clean_wash rinses the source liner twice and the syringe at 50 percent for two cycles | upstream_code | PAL3_driver.py:1140-1143 |
| stop_remote_service calls remote_service.Disconnect when IsConnected is true and does nothing else | upstream_code | PAL3_driver.py:701-703 |
| start_remote_service resolves IRemoteService, calls Remote.Connect and then, in a finally block, direct_service.Reset, calling sys.exit(0) when Reset raises | upstream_code | PAL3_driver.py:682-699 |
| do_lock tries the left-head lock five times, calls stop_remote_service and then start_remote_service after a lock exception, and calls sys.exit(0) when every attempt failed | upstream_code | PAL3_driver.py:719-748 |
| tm_sequence checks self.pause or ctrl+q at the start of each iteration of its transfer-map loop and returns self.transfer when either is set | upstream_code | PAL3_driver.py:1096-1099 |
| centrifuge_sequence checks self.pause or ctrl+q at the start of each iteration of its while loop and returns self.transfer when either is set | upstream_code | PAL3_driver.py:1600-1603 |
| The constructor imports .NET System and Ctc.Palplus.Integration.Driver | upstream_code | PAL3_driver.py:595-611 |
| add_assembly calls sys.exit(0) when the named DLL is not found under self.dir | upstream_code | PAL3_driver.py:651-658 |
| The upstream README says the module is a work in progress and needs testing and validation on the real instrument | vendor_doc | README.md:3 |

## Limits

The clone states no travel envelope for the PAL3 rail or the tool axes.  Every absolute position component
(`position.x`, `position.y`, `position.z`) and every relative displacement (`dx`, `dy`, `dz`) is therefore
`Limit.operator_required`: every move is refused `MHS.SAFETY.LIMITS_UNSET` until the operator supplies the workspace in
`site-limits.json`.  `site-limits.example.json` is example data only, not a statement about any installed rail.

## Safety

The upstream class has no motion-stop, abort, halt, cancel or emergency-stop method: a search of PAL3_driver.py at the
pin for those words finds only `stop_remote_service` and log strings.  `stop_remote_service` (PAL3_driver.py:701-703)
only disconnects the remote service; what a disconnect does to an activity that `session.Execute` is running is decided
by the Ctc.Palplus .NET library, which is not in the clone.  `pause` is read only at the start of loop iterations
(PAL3_driver.py:1098, 1542, 1602, 1667) and interrupts no running call.  The clone documents no independent hardware
e-stop, so `estop_physical_ref` is not set.

The e-stop therefore calls the disconnect as a best-effort step and then reports `MHS.SAFETY.SAFE_STATE_UNREACHED`
with the latch held; the SDK's background retry calls it again about once a second until an operator reset (a probe
on the fake counted four calls, the first included, in the first three seconds).  `x-cap.ad-sdl.disconnect.v1` is an ordinary action, not a safe
state.  `start_remote_service` is the declared re-enable: the upstream lock-retry path calls it after a disconnect
(PAL3_driver.py:719-748), and it runs `direct_service.Reset` (and `sys.exit(0)` when that Reset raises), whose effect
on the instrument is not in the clone; the reset itself only releases the latch.  The package stays blocked
(`NO_HARDWARE_FREE_PATH`): the user's decision of 2026-11-04 keeps an actuator without a source-backed stop blocked.

The hardware backend needs Windows, .NET, the Ctc.Palplus assemblies, the PalPlusDriver DLLs under the upstream
constructor's Windows path and the CustomTracker and ContainerManager modules from a Dropbox path outside the clone
(PAL3_driver.py:19-22); it was never run.  Opening it runs `std_start`, which homes the arm without a command
(PAL3_driver.py:664-671).  The upstream README says the module is work in progress that needs testing and validation
on the real instrument (README.md:3).

## Model review (claude-opus-5-5, a model and not a human, 2026-11-05)

- The author bound `stop_remote_service` as the `@estop` and, through `x-cap.ad-sdl.disconnect.v1`, as a
  `safe_state=True` action, so the SDK reported every e-stop completed and the safe state achieved for a teardown.
  The e-stop now raises `SAFE_STATE_UNREACHED` after the disconnect, the disconnect is an ordinary action, and the
  e-stop case expects the unreached outcome with the latch held.
- Facts corrected: the README claim is on line 3, not 2; "executes it synchronously" (a claim about the .NET
  library) was removed from the two move facts; the safe_home fact now cites both definitions (1012-1027); the
  lock-retry fact now cites the whole of `do_lock` (719-748) and states its `sys.exit(0)`; the start_remote_service
  fact states its `sys.exit(0)`; the pause facts no longer claim what the .NET library does; the universal
  "no stop method" fact cited to three lines became the search note above.  Facts added: the default PAL1 host, the
  import-time dependencies outside the clone and `set_active_modules`.
- `native.py` said the .NET imports run at module import; they run in the constructor, and the module import itself
  needs the Dropbox script modules.

Tags: `pal3`, `robot-arm`, `gantry`, `gripper`, `vial-transfer`, `windows`, `dotnet`
