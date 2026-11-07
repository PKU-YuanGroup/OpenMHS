# Facts and tags for gh.knerlab/sim_control_software

This package implements one device of the knerlab structured-illumination/adaptive-optics microscope application: the
motorized polarizer class `A8MRU` (`motorized_pol_v2.py:23`). Every fact cites the clone at commit
`4abc7e9ddafa89bc0ab0fc8f6e25321fe676d95c`; the same facts are written into `driver.py` (`facts = [...]`), and
`reference.json` is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository's motorized polarizer class is A8MRU in motorized_pol_v2.py, and the module loads USMCDLL.dll through ctypes | upstream_code | motorized_pol_v2.py:20-23 |
| The module appends an external MicroSMC directory to sys.path and imports the USMC parameter structures from pol_rotator_p35.Mot_pol_params | upstream_code | motorized_pol_v2.py:14-16 |
| The A8MRU constructor calls USMC_Init and writes the mode, parameters and start parameters it built | upstream_code | motorized_pol_v2.py:25-32 |
| The initial mode sets ResetD=1 (power off and make a whole step) and disables both trailer limit switches (Tr1En and Tr2En are 0) | upstream_code | motorized_pol_v2.py:139-150 |
| degperstep is 0.075 degrees per microstep | upstream_code | motorized_pol_v2.py:33 |
| getCurPos converts the controller's CurPos to degrees as CurPos * (360. / 4800.) | upstream_code | motorized_pol_v2.py:101-105 |
| MoveAbs divides the target position in degrees by degperstep and calls USMC_Start | upstream_code | motorized_pol_v2.py:64-69 |
| MoveAbsWait polls getCurPos until the angle is within 2 degrees and has no timeout | upstream_code | motorized_pol_v2.py:71-79 |
| MoveRel reads the state, adds the jog divided by degperstep, and calls USMC_Start | upstream_code | motorized_pol_v2.py:81-85 |
| Stop calls USMC_Stop | upstream_code | motorized_pol_v2.py:133-135 |
| The vendor header documents USMC_State.CurPos as the current position in microsteps | upstream_code | USMCDLL.h:106-108 |
| The vendor header documents USMC_Stop as stopping the device | upstream_code | USMCDLL.h:216-219 |
| The vendor header documents USMC_Start as taking a destination position, a speed and the start parameters | upstream_code | USMCDLL.h:208-214 |
| The microscope application enables the motor with MotorOn after constructing A8MRU | upstream_code | microscope_p35.py:67-68 |

## Units and ranges

* The position read is in degrees (`motorized_pol_v2.py:101-105`); the native `MoveAbs` also takes degrees
  (`motorized_pol_v2.py:64-69`). The catalogue input `joint_positions` is in rad and is converted once at the driver
  boundary.
* The controller's position unit is 0.075 degrees per microstep (`motorized_pol_v2.py:33`, `motorized_pol_v2.py:104`);
  the vendor header calls the raw field `CurPos` in microsteps (`USMCDLL.h:108`).
* No text of the clone states a travel range or a safety envelope for the polarizer. `MoveAbs` accepts any angle, and
  the initial mode disables both trailer limit switches (`motorized_pol_v2.py:148-149`). The joint input is therefore
  `Limit.operator_required`: without an operator overlay every move is refused `MHS.SAFETY.LIMITS_UNSET`.
  `site-limits.example.json` supplies an example envelope of one turn in either direction; it is an example, not a
  statement about a unit.
* The clone states no speed range. The class has `setSpeed`, but it returns a DLL status code and has no read-back
  (`motorized_pol_v2.py:42-52`); this package does not expose a speed write and uses the class default.

## Safety

The e-stop and the `cap.motion.stop.v1` action both call the native stop `Stop`, which sends `USMC_Stop`
(`motorized_pol_v2.py:133-135`, `USMCDLL.h:216-219`). No text of the clone documents an independent hardware e-stop;
the package is R1, so SAFE-045 does not apply and `estop_physical_ref` is not set. `safe_state` is "rotation stopped by
the controller (A8MRU.Stop sends USMC_Stop)".

The class does not interpret the DLL return codes; neither does this driver. A DLL call that raises is not swallowed:
it becomes a failed receipt, or an unknown outcome after a move was commanded.

## The fake

The card's mock strategy prefers a transcript. The upstream repository has no simulator or mock for A8MRU and no
recorded session, so this package uses `fake.py`: an in-memory `FakeA8MRU` with only the members the driver uses, all
of which exist on the upstream class. It keeps the angle in degrees and records the calls it received. It has no
motion over time, no speed, no limit switches and no controller errors, and the starting position is placeholder test
data, not a fact.

## The other entry symbols of the card

The card lists three entry symbols for the application. This package implements the first confirmed device class,
`motorized_pol_v2:A8MRU`, as the playbook asks for one device class per repository. The others are not part of this
package:

* `pyAndor_P35_a:ccd` (`pyAndor_P35_a.py:14`) is the Andor camera wrapper. It loads `atmcd64d.dll` from an absolute
  Windows path (`pyAndor_P35_a.py:10`), and its essential output is the image array; the camera's scalar settings and
  temperature reads are not covered here. This package does not claim them.
* `Lib64.asdk37:DM` (`Lib64/asdk37.py:95`) is the SWIG proxy of the Alpao deformable mirror; it needs the compiled
  `_asdk37` extension, which is not in the clone (`Lib64/asdk37.py:14-17`). Its essential output is a mirror pattern;
  this package does not claim it.

## Deviations from the card

The card's `decision` is `family-config` with `helper: SerialDriver`. The upstream A8MRU opens no serial port and emits
no text command: it loads `USMCDLL.dll` with ctypes and calls `USMC_Init`, `USMC_Start` and `USMC_Stop`
(`motorized_pol_v2.py:20`, `motorized_pol_v2.py:68`, `motorized_pol_v2.py:134`). A SerialDriver command table cannot
express that binary interface, so this is a direct `Driver` with a `native.py` factory. This is the "DEVIATION FROM THE
CARD" recorded in `RESULT.json`.

## Deployment notes

The upstream repository is a script bundle with no install metadata. The hardware factory imports
`motorized_pol_v2.A8MRU`, which additionally requires the external `pol_rotator_p35` package (`Mot_pol_params`,
`motorized_pol_v2.py:16`) and `USMCDLL.dll` on the Windows DLL search path (`motorized_pol_v2.py:20`). The clone root
must be importable and, on Windows, be the working directory or on PATH so the DLL is found. None of that was
executed; the acceptance gate runs the fake backend.

Tags: motorized polarizer, rotation stage, usmc, structured illumination, motion
