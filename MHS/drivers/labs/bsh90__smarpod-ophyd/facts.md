# Facts and tags for gh.bsh90/smarpod-ophyd

Every fact cites the clone at commit `a3d50e67618b9a15527d54339a333f199f58681d`. `upstream_code` is code of the
clone; `vendor_doc` is text under the clone root. The driver's `facts` list is authoritative; this page repeats it
with the notes a reviewer needs.

| fact | source | ref |
|---|---|---|
| `SmarSignalRO` derives from ophyd `Signal`, creates a `SmarPod` and opens the controller in its constructor | upstream_code | `src/OphydSmarPod.py:10-20` |
| `SmarSignalRO.get` reads the current pose with `smarpod.GetPose` and returns `pose_to_double_list(pose)` | upstream_code | `src/OphydSmarPod.py:25-27` |
| `pose_to_double_list` returns `positionX, positionY, positionZ, rotationX, rotationY, rotationZ` in that order | upstream_code | `src/SmarPodMain.py:45-53` |
| `SmarSignal.set` verifies reachability, calls `smarpod.Move(handle, pose, 0, True)` and then requires the move status to be stopped | upstream_code | `src/OphydSmarPod.py:68-79` |
| `SmarSignal.get_status` reports stopped when `smarpod.GetMoveStatus` equals `MoveStatus.STOPPED` | upstream_code | `src/OphydSmarPod.py:81-88` |
| `SmarSignal.check_pose` asks `smarpod.IsPoseReachable`; `verify_reachable_position` raises when it is not reachable | upstream_code | `src/OphydSmarPod.py:96-104` |
| `SmarSignalDifferentAxis.set` constructs a new `SmarSignalRO` without an `optional_handle`, reads its pose, replaces component `i` and sets the pose through a new `SmarSignal` on that handle | upstream_code | `src/OphydSmarPod.py:107-114` |
| `SmarSignalRO.trigger` reads `GetMoveStatus` once, before its loop, then sleeps 10 s per iteration while that single reading is not `STOPPED`; the loop never reads the status again | upstream_code | `src/OphydSmarPod.py:55-62` |
| `SmarPod.set_speed_and_frequency_and_pivot_point_and_coordinate_system` sets speed, maximum frequency, `RELATIVE` pivot mode with pivot `[10e-3, 0, 0]` and a coordinate system | upstream_code | `src/SmarPodMain.py:55-68` |
| The `SmarPod` class attributes are model `10052` and locator `usb:sn:MCS2-00006657` | upstream_code | `src/SmarPodMain.py:8-9` |
| `SmarPod.set_up` opens the controller with its model and locator, calibrates, searches reference marks when the controller is not referenced, enables the sensor, then calls `smarpod.Stop` and raises when the move status is not `STOPPED` | upstream_code | `src/SmarPodMain.py:70-124` |
| The except clause of `set_up` catches `smarpod.Error` and `Exception`, logs and prints a message built from `err.func` and `err.code`, and does not re-raise | upstream_code | `src/SmarPodMain.py:126-133` |
| The stop path is `smarpod.Stop(handle)` followed by a fresh `GetMoveStatus` check for `MoveStatus.STOPPED` | upstream_code | `src/SmarPodMain.py:109-121` |
| `SmarPod.moving` checks every pose with `IsPoseReachable` and `move_sequence` sends each pose with `smarpod.Move` | upstream_code | `src/SmarPodMain.py:142-161` |
| The README describes connecting to a SmarPod through the Ophyd interface or directly to its API and states no pose unit, travel range or workspace bound | vendor_doc | `README.md:1-13` |

## Units, bounds and the stop

- The clone states no engineering unit for any pose component. Gate G8 requires a unit on every numeric input of a
  hardware driver, so the pose fields carry the UCUM code `1` as a placeholder; every description says that it is not
  a dimensionless claim (the values are the vendor API's own position and rotation units), and one operator envelope
  bounds all six components. No conversion is performed.
- The clone states no workspace or travel range. The controller checks a pose with `smarpod.IsPoseReachable`
  (`src/OphydSmarPod.py:96-104`); that is a run-time check, not a static bound. Both the `pose` write and the pose
  input of the extension action are therefore `Limit.operator_required`; without a site envelope they refuse with
  `MHS.SAFETY.LIMITS_UNSET`.
- The stop is the vendor `smarpod.Stop(handle)` at `src/SmarPodMain.py:109`, confirmed with a fresh
  `GetMoveStatus` check at `src/SmarPodMain.py:110-121`. It is a software stop of commanded motion, not a physical
  emergency stop; the clone contains no text about a hardware e-stop.
- Automatic calibration and reference-mark search are not performed by the production adapter. They move the
  platform without an MHS command (`src/SmarPodMain.py:87-95`) and would bypass the operator envelope; the adapter
  refuses to start on an unreferenced controller instead.

Tags (short lowercase keywords): `ophyd`, `smaract`, `hexapod`, `motion`, `pose`, `six-axis`.
