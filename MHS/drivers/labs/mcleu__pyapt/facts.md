# Facts and tags for gh.mcleu/pyapt

Every fact cites its source at commit `2d5c4c64350d70daa60c0bd49c9afd03f85bc412`: `vendor_doc` (README text) or
`upstream_code` (a file and line of the clone). The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| PyAPT controls Thorlabs APT hardware from Python through APT.dll and APT.lib | vendor_doc | README.md:5 |
| The README tells the user to obtain the x86 or x64 APT.dll and APT.lib and to install the Thorlabs APT software | vendor_doc | README.md:10-12 |
| The README lists Thorlabs APT controllers including the BSC001, TDC001, LTSXXX and BBD10X | vendor_doc | README.md:29-46 |
| The module imports ctypes.windll and uses Python 2 print statements, so it is Windows-only and does not parse as Python 3 | upstream_code | PyAPT/PyAPT.py:18-21 |
| The constructor loads APT.dll into self.aptdll, calls EnableEventDlg(True) and APTInit, and keeps the serial number as a c_long | upstream_code | PyAPT/PyAPT.py:44-57 |
| initializeHardwareDevice calls InitHWDevice(serial) and sets Connected only when it returns zero | upstream_code | PyAPT/PyAPT.py:89-103 |
| getPos calls MOT_GetPosition and refuses to read when the object is not Connected | upstream_code | PyAPT/PyAPT.py:183-194 |
| mRel calls MOT_MoveRelativeEx with the wait flag True, and mAbs calls MOT_MoveAbsoluteEx with the wait flag True | upstream_code | PyAPT/PyAPT.py:196-221 |
| go_home calls MOT_MoveHome with the serial number; the upstream call passes no other argument | upstream_code | PyAPT/PyAPT.py:289-298 |
| getVelocityParameters reads MOT_GetVelParams and setVelocityParameters writes MOT_SetVelParams | upstream_code | PyAPT/PyAPT.py:139-159 |
| getVelocityParameterLimits reads the controller's maximum acceleration and maximum velocity at run time through MOT_GetVelParamLimits | upstream_code | PyAPT/PyAPT.py:167-172 |
| getStageAxisInformation returns the minimum position, maximum position, unit code and pitch from MOT_GetStageAxisInfo | upstream_code | PyAPT/PyAPT.py:114-121 |
| The stage unit code is 1 for millimetres and 2 for degrees | upstream_code | APTDLLPack/APTDLLClient/APTAPI.h:82-84 |
| APT.dll declares MOT_StopProfiled(long lSerialNum) | upstream_code | APTDLLPack/APTDLLClient/APTAPI.h:148 |
| The vendor APT client calls MOT_StopProfiled from its StopProfiled button handler | upstream_code | APTDLLPack/APTDLLClient/APTDLLClientDlg.cpp:593-599 |
| MOT_MoveHome, MOT_MoveRelativeEx and MOT_MoveAbsoluteEx take the serial number and a wait flag | upstream_code | APTDLLPack/APTDLLClient/APTAPI.h:144-146 |
| cleanUpAPT calls APTCleanUp and sets Connected to False | upstream_code | PyAPT/PyAPT.py:309-316 |

## Limits

The driver is generic over the Thorlabs APT controllers and stages the README lists, and the controller reports the
stage unit at run time (1 for mm, 2 for degrees; APTDLLPack/APTDLLClient/APTAPI.h:82-84). The clone reads the travel
range with `getStageAxisInformation` (PyAPT/PyAPT.py:114-121) and the velocity and acceleration limits with
`getVelocityParameterLimits` (PyAPT/PyAPT.py:167-172); it states no fixed number for either. The absolute position,
maximum velocity, acceleration and relative distance are therefore `Limit.operator_required`: every call that sets one
is refused `MHS.SAFETY.LIMITS_UNSET` until the site supplies the bound of the installed stage.
`site-limits.example.json` is an example overlay, not a statement about any stage. The integer stage-unit code and the
limit-switch modes are read-only state, so they need no numeric write limit.

## Safety

The e-stop calls APT.dll `MOT_StopProfiled` through the upstream object's `aptdll` handle
(APTDLLPack/APTDLLClient/APTAPI.h:148) and then reads the position; the safe-state action
`x-cap.mcleu.stop.v1` sends the same native stop. No line of the clone documents an independent hardware e-stop, so
`estop_physical_ref` is not set. The hardware limit switches are reported as state, not claimed as an independent stop.

## Fake backend

The fake is an in-memory stand-in, not a recording: it does not model the APT USB/DLL protocol, motion kinematics, the
controller's own travel-range check, the configured homing profile or the status bits beyond the values the driver
reads. All starting values are test data and are marked `# placeholder` in `fake.py`. The package is model-authored
and unreviewed; it is checked on the fake backend only and no hardware was attached or run.

Tags: thorlabs, apt, motion, stage, ctypes, windows
