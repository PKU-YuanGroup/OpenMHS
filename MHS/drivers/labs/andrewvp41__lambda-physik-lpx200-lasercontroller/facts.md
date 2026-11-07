# Facts and tags for gh.andrewvp41/lambda-physik-lpx200-lasercontroller

Every fact cites its source at commit `abd240f534a93923342ae6bef374e9d9885b8776`: `vendor_doc` (a text file of the
clone, here README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are in `driver.py`
(`facts = [...]`); the reference files are generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The project is remote control software for controlling, monitoring and data collection on the LPX200 laser, mimicking the Lambda Physik handheld keypad | vendor_doc | README.md:1-2 |
| The program opens the pyvisa resource ASRL4::INSTR and sets CR as both the write and the read termination, so the link is a line-oriented ASCII serial port | upstream_code | LPX200.py:266-270 |
| commRes sends every command with laser_instr.query and answers 'Not a valid Command' when the query raises | upstream_code | LPX200.py:251-256 |
| The status line queries MODE?, REPRATE?, HV?, EGY?, PRESSURE? and Menu?, and prints the values in Hz, kV, mJ and mbar; the third field of the Menu? reply is the gas mixture | upstream_code | LPX200.py:61 |
| The running modes are HV, EGY PGR and EGY NGR | upstream_code | LPX200.py:86 |
| The gas lines are BUFFER, HALOGEN, INERT and RARE | upstream_code | LPX200.py:87 |
| The RUN STOP key reads OPMODE? and writes OPMODE=OFF when it is ON, otherwise OPMODE=ON | upstream_code | LPX200.py:108-111 |
| The TRIG INT/EXT key reads TRIGGER? and writes TRIGGER=EXT when it is INT, otherwise TRIGGER=INT | upstream_code | LPX200.py:113-118 |
| The MODE key sends MODE= followed by one of the running mode names | upstream_code | LPX200.py:120-122 |
| The REP RATE key sends the REPRATE= prefix and the COUNTS SEL key sends the COUNTS= prefix | upstream_code | LPX200.py:124-130 |
| The HV key builds HV= as the prefix of the value typed on the keypad | upstream_code | LPX200.py:140-142 |
| The EGY key builds EGY= as the prefix of the value typed on the keypad | upstream_code | LPX200.py:156-158 |
| The gas routines build OPMODE=NEW FILL, OPMODE=FLUSH <line> LINE, OPMODE=PURGE <line> LINE, OPMODE=PURGE RESERVOIR and OPMODE=ENERGY CAL | upstream_code | LPX200.py:132-170 |
| The REPRATE value is specified in Hz, the HV value is the charging voltage, and the EGY value is the beam output energy specified in mJ | vendor_doc | README.md:69-73 |
| The RUN STOP key starts and stops laser operation; when the laser is running, pressing it immediately stops laser emission | vendor_doc | README.md:58-59 |
| The gas actions are required for maintenance and should only be carried out by correspondingly authorized and trained personnel | vendor_doc | README.md:90 |
| LaserData.py queries opmode?, trigger?, reprate?, hv?, egy?, pressure?, mode? and menu?, and splits the menu reply into gas menu number, wavelength and gas mixture | upstream_code | LaserData.py:19-25 |

Limits:

| parameter | command | limit | source and ref |
|---|---|---|---|
| repetition_rate (Hz) | REPRATE= | operator_required: no text states the range | no source states a bound; the site supplies it |
| high_voltage (kV) | HV= | operator_required: no text states the range | no source states a bound; the site supplies it |
| energy (mJ) | EGY= | operator_required: no text states the range | no source states a bound; the site supplies it |
| mode | MODE= | one of HV, EGY PGR, EGY NGR | upstream_code, LPX200.py:86 |
| trigger_mode | TRIGGER= | one of INT, EXT | upstream_code, LPX200.py:113-118 |

The clone names the units of the three numeric settings (README.md:69-73 and the status line LPX200.py:61) but no
range for any of them, and no manual or datasheet is in the clone. `Limit.operator_required` therefore refuses every
REPRATE=, HV= and EGY= write with `MHS.SAFETY.LIMITS_UNSET` until the operator supplies the rated range of the
installed unit in `site-limits.json`. `site-limits.example.json` is an example overlay with arbitrary example numbers,
not a statement about a device.

Safety: the `@estop` and the `x-cap.andrewvp41.emission_off.v1` safe-state action send `OPMODE=OFF`, the RUN STOP
stop command (LPX200.py:108-111, README.md:58-59). The clone has no separate emergency-stop input, so the package
declares the safe-state action instead of an `estop_physical_ref`, and it is R3 because it sets the charging high
voltage (MHS-004 lists high voltage as R3).

Not covered by this package: the gas maintenance routines (OPMODE=NEW FILL, FLUSH LINE, PURGE LINE, PURGE
RESERVOIR, ENERGY CAL), MENU RESET, the pulse counters and the function keys; the clone builds their commands but
the package does not expose them.

Tags: laser, lpx200, lambda-physik, pyvisa, serial, emission control, high voltage
