# Facts and tags for gh.azdagkas/kinesis-piezo

Every fact cites its source at commit `ecfe0586cef37d83e287a1fee3496a3eb67f4acd`: `vendor_doc` (a text file of the
clone) or `upstream_code` (a path of the clone and a line). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository contains code for the control of the Thorlabs TPZ001 piezo driver and TSG001 strain gauge reader with the Kinesis API | vendor_doc | README.md:4-5 |
| The module imports pythonnet's clr and the Thorlabs Kinesis .NET assemblies | upstream_code | piezo.py:5-18 |
| The README lists pythonnet as a requirement | vendor_doc | README.md:23-25 |
| The Kinesis DLLs the module references must be placed in libs/kinesis | vendor_doc | libs/kinesis/info.txt:1-13 |
| PiezoController takes the controller serial number and an optional strain gauge reader serial number | upstream_code | piezo.py:178-182 |
| initialize creates a StrainReader from the reader serial number when one is configured | upstream_code | piezo.py:224-225 |
| initialize sets the output voltage range maximum to 75 and both the voltage and percentage jog step sizes to 1 before loading the settings into the device | upstream_code | piezo.py:218-222 |
| connect_enable connects the device, waits for the settings, starts 250 ms polling, sleeps 500 ms and enables the device | upstream_code | piezo.py:55-94 |
| get_units returns '%' in closed loop and 'V' in open loop | upstream_code | piezo.py:227-232 |
| get_value returns the percentage travel in closed loop and the output voltage in open loop | upstream_code | piezo.py:234-239 |
| set_value writes the percentage travel in closed loop and the output voltage in open loop | upstream_code | piezo.py:241-245 |
| moveup and movedown call Jog(1) and Jog(2) | upstream_code | piezo.py:247-251 |
| move_to_home writes 0 percentage travel in closed loop and 0 output voltage in open loop | upstream_code | piezo.py:253-257 |
| is_closed_loop returns the device status flag IsClosedLoop | upstream_code | piezo.py:260-261 |
| set_closed_loop selects the software voltage source and position control mode 2 | upstream_code | piezo.py:263-277 |
| set_open_loop selects the software voltage source and position control mode 1 | upstream_code | piezo.py:279-293 |
| calibrate_pos drives 10 and 70 percent of travel, reads the strain gauge position at each point, and fits percentage = a*position + b | upstream_code | piezo.py:295-325 |
| move_to_pos converts a reader position to percentage travel with the calibration slope and offset | upstream_code | piezo.py:327-329 |
| move_pos_up moves 1 reader unit up while the reading is below 19 and move_pos_down moves 1 unit down while it is above 1 | upstream_code | piezo.py:331-337 |
| move_pos_to_home calls move_to_pos(0) | upstream_code | piezo.py:339-340 |
| The reader position is the strain gauge status reading converted from a .NET Decimal to double | upstream_code | piezo.py:134-136 |
| set_zero calls SetZero and is_zeroing returns the status flag IsZeroing | upstream_code | piezo.py:138-142 |
| The reader get_units maps display mode 1 to micrometre, 2 to volt, 3 to newton and anything else to an error string | upstream_code | piezo.py:144-153 |

## Limits

The clone names the upstream's own configuration choices, not a safe operating range of an installed stage: it sets
the output voltage range maximum to 75 (piezo.py:219) and both jog step sizes to 1 (piezo.py:220-221). Those are
settings the upstream applies, not a travel or voltage envelope of the device. The clone also uses 19 and 1 reader
units as guards in two convenience steps (piezo.py:332,336), which are not a travel range either.

Every numeric input is therefore `Limit.operator_required`:

| input | limit |
|---|---|
| `value` write | operator-required: the site supplies the permitted percentage travel or output voltage of the installed stage in the mode in use |
| `x-cap.azdagkas.kinesis_piezo.move_to_position.v1` `position` | operator-required: the site supplies the permitted reader position range in the reader display unit |

Until an operator overlay fills them, the runtime refuses every such call with `MHS.SAFETY.LIMITS_UNSET`.
`site-limits.example.json` supplies example numbers for the gate and for an operator to copy; those numbers are
placeholders, not a statement about any stage.

## Units

The controller value is percentage travel in closed loop and output voltage in open loop; `units` reads '%' or 'V'
from the upstream get_units (piezo.py:227-232). The value field therefore has no single UCUM unit; it is declared
with the dimensionless code `1` and the description points at `units`, which reports the physical unit of the value
in the mode in use. The strain gauge reading is exposed in the reader's own display unit,
which `reader_units` reports: micrometre, volt, newton, or the upstream error string (piezo.py:144-153). Because the
unit of the reading depends on that display mode, both `reader_reading` and the calibrated position input use the
dimensionless unit `1`; the description points at `reader_units`.

## Safety

The e-stop and the `safe_state=True` action `x-cap.azdagkas.kinesis_piezo.move_to_home.v1` both call the native
`move_to_home()`, which writes 0 percentage travel in closed loop or 0 output voltage in open loop
(piezo.py:253-257). The declared safe state is "piezo travel driven to zero (percentage travel 0 or output voltage
0 V)". No line of the clone documents an independent, safety-rated hardware e-stop, so this package sets no
`estop_physical_ref` and claims no hardware protection beyond the software stop. The clone declares no high-energy,
heating, laser or high-force hazard; the device is a small-travel piezo motion axis, and the driver is declared at
R1, the card's floor.

The package is model-authored and unreviewed and was checked on the fake backend only. The hardware factory
(`native.py`) was never imported or run, and no hardware test was performed.

Tags: thorlabs, piezo, stage, motion, kinesis, strain-gauge
