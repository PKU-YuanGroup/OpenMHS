# Facts and limits for gh.quantumllama/python-lab-drivers

The package serves the function generator of the clone (a Siglent SDG 2042X).  The clone is two PyVISA debug
scripts, not a library; it has no simulator and no recorded session.  Every sourced Fact and Limit cites a file of
the clone at commit `3fee8226c25d749e86f9108c0c9df2051a4aceb8`; the three operator_required limits have no source by
design.  The sourced facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The clone is a function-generator debug script tested on a Siglent SDG 2042X | upstream_code | func_gen_test.py:3 |
| The script opens the first VISA resource and queries *IDN? to confirm the instrument | upstream_code | func_gen_test.py:14-19 |
| The script writes C2:OUTP OFF, then C2:BaSic_WaVe WVTP,SQUARE,FRQ,100,AMP,2.5,OFST,1.25,DUTY,50, then C2:OUTP ON,LOAD,HZ,PLRT,NOR | upstream_code | func_gen_test.py:22-25 |

Limits:

| parameter | command | limit | source and ref |
|---|---|---|---|
| output | C2:OUTP | ON or OFF | upstream_code, func_gen_test.py:22-25 |
| waveform | C2:BaSic_WaVe WVTP | operator_required: only the programming guide (a PDF) lists the types | no source; the reason is in driver.py |
| frequency (Hz) | C2:BaSic_WaVe FRQ | operator_required: the guide states the unit and refers the range to the data sheet, which is not in the clone | no source; the reason is in driver.py |
| amplitude (Vpp) | C2:BaSic_WaVe AMP | operator_required: the guide states the unit and refers the range to the data sheet, which is not in the clone | no source; the reason is in driver.py |
| offset (V) | C2:BaSic_WaVe OFST | operator_required: the guide states the unit and refers the range to the data sheet, which is not in the clone | no source; the reason is in driver.py |
| duty_cycle (%) | C2:BaSic_WaVe DUTY | operator_required: only the programming guide (a PDF) states the range | no source; the reason is in driver.py |

Safety: the e-stop writes `C2:OUTP OFF`, disabling the one physical output this driver controls.  The device has no
independent hardware e-stop in the clone and none is needed at R1.  The safe state is the output disabled.

Vendor documentation that is not a citation: the clone's `SDG_Wavegen_Programming_Guide.pdf` (physical pages)
documents the output command and its reply `C1:OUTP ON,LOAD,HZ,PLRT,NOR` (page 19), the basic-wave parameters with
the waveform types SINE, SQUARE, RAMP, PULSE, NOISE, ARB, DC and PRBS and a duty cycle of 0 to 100 percent that
depends on the frequency and is settable only for SQUARE or PULSE (page 20), and the identification command (in the
command table of page 14).  The gate cannot read a PDF and a model review accepts no PDF citation, so none of this is
a Fact or a Limit: a human who reads those pages may restore them as cited bounds when signing `reviewed_by`.

NOT COVERED: the oscilloscope script (`oscope_test.py`), whose whole interface in the clone is `*IDN?` plus
`MENU ON`/`MENU OFF`; it is not a second device of this package.

Tags: signal generator, function generator, waveform generator, awg, siglent, sdg2042x, scpi
