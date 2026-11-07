OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.aaron-mott/keithley-2230g

Every fact cites its source at commit `4c4d9024808f33b20d9148183b006225cced7936`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The driver declares the same facts in
`driver.py`; the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The upstream README says the author used National Instruments VISA and could not test the code on the instrument. | vendor_doc | README.md:1 |
| The clone imports visa and defines the device class KEI2230G. | upstream_code | 2230G.py:10-12 |
| The constructor takes inst_address but opens self.instr_address, which it never sets. | upstream_code | 2230G.py:14-40 |
| get_info queries *IDN? and splits the reply on commas into manufacturer, model, serial and firmware. | upstream_code | 2230G.py:77-81 |
| Channel selection writes INST:NSEL with a channel number validated to range(1, 4). | upstream_code | 2230G.py:402-403 |
| The set_volt body contains VOLT command text for the selected channel. | upstream_code | 2230G.py:928 |
| The set_curr body contains CURR command text for the selected channel. | upstream_code | 2230G.py:715-731 |
| The voltage readback body contains VOLT? query text. | upstream_code | 2230G.py:960 |
| A current setpoint is queried as CURR?. | upstream_code | 2230G.py:738 |
| The selected channel output is set with CHAN:OUTP. | upstream_code | 2230G.py:657 |
| The selected channel output is queried with CHAN:OUTP?. | upstream_code | 2230G.py:665 |
| All channel outputs are set with OUTP. | upstream_code | 2230G.py:820 |
| All channel outputs are queried with OUTP?. | upstream_code | 2230G.py:828 |
| A fresh voltage measurement is requested with MEAS:VOLT? on a named channel. | upstream_code | 2230G.py:542 |
| A fresh current measurement is requested with MEAS:CURR? on a named channel. | upstream_code | 2230G.py:496 |
| get_model documents the model types 30-3, 30-6 and 60-3. | upstream_code | 2230G.py:84 |
| The model-specific branches compare the bound method self.get_model to the string '30-3', so they never run. | upstream_code | 2230G.py:568 |
| The voltage readback method calls the misspelt self.inst.quert, so that method is broken. | upstream_code | 2230G.py:960 |
| The error queue is queried with SYST:ERR?. | upstream_code | 2230G.py:1320 |
| The output protection state is cleared with OUTP:PROT:CLE. | upstream_code | 2230G.py:784 |

## Limits

The voltage and current setpoints are `Limit.operator_required`. The installed 2230G may be a 30-3, 30-6 or 60-3;
the clone's bounds differ by model and channel (2230G.py:568-652), and its `get_model` branch never runs
(2230G.py:568), so no single sourced bound applies. The operator supplies the actual unit's bounds in
`site-limits.json`; until then every setpoint write is refused with `MHS.SAFETY.LIMITS_UNSET`. The example overlay in
`site-limits.example.json` is a narrow bench envelope, not a device fact.

## Wire composition

The driver sends one channel's selection and setting as one SCPI compound line: `INST:NSEL n;:VOLT value`,
`INST:NSEL n;:CURR value` and `INST:NSEL n;:CHAN:OUTP value`. The clone writes `INST:NSEL` and the setting as separate
commands, so this exact composition is not shown in the clone and has not been tried on an instrument. The individual
command words and their argument forms are the ones in the clone. The all-channel safe-state command is `OUTP OFF`
(2230G.py:820).

## Tags

`power supply`, `keithley`, `2230g`, `scpi`, `instrument`

The leading colon after each selection resets the SCPI header to the root. Without it, `INST:NSEL 1;VOLT 2`
addresses `INST:VOLT` rather than `VOLT`. The fake now retains the SCPI header between semicolons and rejects
that malformed command, matching the [Series 2230 manual, section 4-8](https://download.tek.com/manual/2230-900-01B_April_2022_User.pdf).
String formatting defects in the Python clone (literal `.upper()` text) are not copied into the command map.

The package uses R3 for the worst credible powered-load hazard: the connected model, channel wiring, load and
operator-provided envelope have not been established. The tiny example envelope is not evidence for a lower
hardware risk class. Hardware stays unsigned and untested; the all-channel software output command is not an
independent safety-rated disconnect. Publication remains an owner decision because the source has no asserted licence.
