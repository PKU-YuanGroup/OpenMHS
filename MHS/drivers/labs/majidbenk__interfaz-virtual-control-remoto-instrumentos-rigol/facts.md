# Facts and tags for gh.majidbenk/interfaz-virtual-control-remoto-instrumentos-rigol

The package drives the RIGOL DP832A DC power supply of the upstream Tkinter application.  The upstream
``FuenteContinua`` class is GUI-bound, so the driver uses the card's ScpiDriver shape: the command map below is the
same SCPI text the class builds, while the runtime opens the transport.  No upstream code is imported by the fake
or by the hardware view of the bridge.

Every fact cites its source at commit `770ab3a1f81699873a7aeb86df0b1ab4a5061f5f` from the clone root as it is.
The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not
from this page.

| fact | source | ref |
|---|---|---|
| The README states the project controls RIGOL instruments (an oscilloscope and a DC power supply) over PYVISA | vendor_doc | README.txt:2-3 |
| The README maps the DS1000 oscilloscope to `interfaz_osciloscopio_v4.py` and the DP800 DC supply to `intefaz_FuenteContinua_v2.py` | vendor_doc | README.txt:10-11 |
| `FuenteContinua` is a Tk window: its `__init__` creates a `Toplevel` | upstream_code | intefaz_FuenteContinua_v2.py:31-35 |
| `Connection` opens the selected VISA resource with pyvisa and queries `*IDN?` | upstream_code | intefaz_FuenteContinua_v2.py:68-74 |
| The supply window names the instrument RIGOL DP832A | upstream_code | intefaz_FuenteContinua_v2.py:36 |
| A channel is selected with `:INST:NSEL` and its voltage and current set points are written with `:VOLT` and `:CURR` | upstream_code | intefaz_FuenteContinua_v2.py:435-440 |
| The voltage and current protections are written with `:VOLT:PROT` and `:CURR:PROT` on the selected channel | upstream_code | intefaz_FuenteContinua_v2.py:443-448 |
| A channel output is enabled or disabled with `:OUTP CHn,ON` or `:OUTP CHn,OFF` | upstream_code | intefaz_FuenteContinua_v2.py:411-413 |
| The measured voltage, current and power are read with `:MEAS:VOLT?`, `:MEAS:CURR?` and `:MEAS:POWE?` on a named channel | upstream_code | intefaz_FuenteContinua_v2.py:452-458 |
| The channel labels state 30 V and 3 A for channels 1 and 2 and 5 V and 3 A for channel 3 | upstream_code | intefaz_FuenteContinua_v2.py:234-240 |
| The protection dialog states maximum protection values CH1 33V-3.3A, CH2 33V-3.3A and CH3 5.5V-3.3A | upstream_code | intefaz_FuenteContinua_v2.py:216 |
| The protection entry defaults are 33 V and 3.3 A, and channel 3 starts at 5.5 V | upstream_code | intefaz_FuenteContinua_v2.py:335-359 |
| The transistor sweep writes 0 V and 0.4 A and then disables both channels | upstream_code | intefaz_FuenteContinua_v2.py:153-203 |

Limits, all from the clone's own text:

| limit | bound | source | ref |
|---|---|---|---|
| `voltage_1` | 0 to 30 V | upstream_code | intefaz_FuenteContinua_v2.py:234 |
| `voltage_2` | 0 to 30 V | upstream_code | intefaz_FuenteContinua_v2.py:237 |
| `voltage_3` | 0 to 5 V | upstream_code | intefaz_FuenteContinua_v2.py:240 |
| `current_1`, `current_2`, `current_3` | 0 to 3 A | upstream_code | intefaz_FuenteContinua_v2.py:234-240 |
| `ovp_1`, `ovp_2` | 0 to 33 V | upstream_code | intefaz_FuenteContinua_v2.py:216 |
| `ovp_3` | 0 to 5.5 V | upstream_code | intefaz_FuenteContinua_v2.py:216 |
| `ocp_1`, `ocp_2`, `ocp_3` | 0 to 3.3 A | upstream_code | intefaz_FuenteContinua_v2.py:216 |

The minimum 0 of each rule is the floor of a magnitude; the upstream setters write the 0 values and the gate does
not require a separate citation for a zero bound.  The upper bounds are the output labels (30 V / 3 A for CH1 and
CH2, 5 V / 3 A for CH3) and the protection dialog (33 V / 3.3 A for CH1 and CH2, 5.5 V / 3.3 A for CH3).

The bridge sends the channel selection and the set point on one line with the SCPI separator
(`:INST:NSEL 1;:VOLT 5`), because a single ScpiDriver write entry has one template; the two individual commands,
their spelling and their order are the upstream ones at lines 435-436.  The safe-state action sends the three OFF
commands on one line for the same reason.  Gate G7 splits the line at `;` and finds both command mnemonics in the
clone.

Safety: the outputs are the hazard this driver controls.  The e-stop writes `:OUTP CH1,OFF`, `:OUTP CH2,OFF` and
`:OUTP CH3,OFF`, and the `x-cap.majidbenk.output_off.v1` action with `safe_state=True` sends the same three OFF
commands.  The upstream text names no independent hardware emergency-stop input, so this package does not claim
one.  The driver is R1; the loader refuses the hardware backend of an unreviewed model-written package only at R2
and R3, so a human review is required before hardware use.

The DS1000 oscilloscope in the same repository is not covered by this package: the card has one driver package and
this package binds the supply (the entry symbol `intefaz_FuenteContinua_v2:FuenteContinua`).  The oscilloscope's
waveform array is not represented by a catalogue class used here.

Tags: power-supply, dc-source, rigol, dp832a, scpi, visa
