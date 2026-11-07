# Facts and tags for gh.imswitch2/imswitch2

Every fact cites its source at commit `86763f7ba89fb15efbf3229ea5df1c9e1395fc7d`: `vendor_doc` (documentation text
of the clone) or `upstream_code` (code or a comment of the clone). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| StandaRotatorManager drives a Standa-branded motor controller, for example 8SMC5 for a motorized rotation mount | upstream_code | imswitch/imcontrol/model/managers/rotators/StandaRotatorManager.py:5-8 |
| The manager reads motorListIndex, ximcLibLocation, stepsPerTurn and microstepsPerStep from the rotator setup and constructs a StandaMotor with them | upstream_code | imswitch/imcontrol/model/managers/rotators/StandaRotatorManager.py:15-20 |
| The manager's get_pos stores the value the motor reports in _position | upstream_code | imswitch/imcontrol/model/managers/rotators/StandaRotatorManager.py:29-30 |
| The position property returns the manager's _position field | upstream_code | imswitch/imcontrol/model/managers/rotators/RotatorManager.py:27-30 |
| The manager's move_abs passes its argument to the motor's moveabs and refreshes the position | upstream_code | imswitch/imcontrol/model/managers/rotators/StandaRotatorManager.py:36-38 |
| The manager's move_rel passes its argument to the motor's moverel and refreshes the position | upstream_code | imswitch/imcontrol/model/managers/rotators/StandaRotatorManager.py:32-34 |
| The manager's set_zero_pos calls the motor's set_zero_pos and refreshes the position | upstream_code | imswitch/imcontrol/model/managers/rotators/StandaRotatorManager.py:40-42 |
| The manager's stop_cont_rot calls the motor's stop_cont_rot | upstream_code | imswitch/imcontrol/model/managers/rotators/StandaRotatorManager.py:50-51 |
| StandaMotor.stop_cont_rot sends command_sstp | upstream_code | imswitch/imcontrol/model/interfaces/standamotor.py:170-171 |
| The widget documents the absolute position and the relative step of the rotation mount in degrees | upstream_code | imswitch/imcontrol/view/widgets/RotatorWidget.py:80-91 |
| The widget displays the rotation position in deg | upstream_code | imswitch/imcontrol/view/widgets/RotatorWidget.py:104-105 |
| StandaMotor.dist_translate converts an angle in degrees to steps and microsteps, and dist_translate_inv converts a reported step position back to degrees | upstream_code | imswitch/imcontrol/model/interfaces/standamotor.py:129-143 |
| The documentation defines stepsPerTurn as the full motor steps per 360 degrees and microstepsPerStep as the microstep subdivision | vendor_doc | docs/devices/rotators.rst:77-82 |
| The manager's close calls the motor's close | upstream_code | imswitch/imcontrol/model/managers/rotators/StandaRotatorManager.py:68-69 |

Limits: the joint position is `Limit.operator_required`. No text file of the clone states the travel range of a
rotation mount: `dist_translate` maps any angle in degrees to steps and microsteps
(imswitch/imcontrol/model/interfaces/standamotor.py:129-140), and `stepsPerTurn` is only the resolution of one turn
(docs/devices/rotators.rst:77-82). The operator supplies the axis envelope; `site-limits.example.json` shows the
overlay with an example range and is not a statement about any unit.

Safety: the e-stop and the `cap.motion.stop.v1` action both call the native `stop_cont_rot`, which sends
`command_sstp` (StandaRotatorManager.py:50-51, standamotor.py:170-171). No line of the clone documents an
independent hardware e-stop, so `estop_physical_ref` is not set. The package is R1, so SAFE-045 does not require a
safe-state action; the native stop is still the declared safe state.

Not covered by this package: the continuous rotation (`start_cont_rot`), the relative move (`move_rel`), the speed
write (`set_rot_speed`, mrpm), the software zero (`set_zero_pos`), the sync-in settings (`set_sync_in_set`) and
`get_info`; only the position read, the absolute move, the stop and the e-stop are exposed.

Other entry symbols of the card are not part of this package: `NidaqManager` (NI-DAQ tasks and scan output),
`RecordingManager` (detector recording), `Cobolt06` and `Cobolt06DPL` (Cobolt laser serial interfaces); the card
lists them for the same application, but this package implements one device class.

Tags: rotation mount, standa, 8smc5, libximc, motion, imswitch2
