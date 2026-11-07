OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.aaron-mott/keithley-2200

Every fact cites its source at commit `348fb5df70d92bd96593452e188c90f0ae3d71c4`: `vendor_doc` for the two
README lines and `upstream_code` for the clone's one class. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The upstream KEI2220S class defines a misspelled __innit__ routine containing the VISA resource open | upstream_code | 2220 Programmable DC Power Supplies.py:11-39 |
| The README says the program uses National Instruments VISA to communicate with the Keithley Series 2200 Programmable DC Power Supplies | vendor_doc | README.md:1 |
| The README says the author could not test the code on the instrument | vendor_doc | README.md:2 |
| The __innit__ parameter is inst_address, but open_resource is called with self.instr_address, which the routine never sets | upstream_code | 2220 Programmable DC Power Supplies.py:13-39 |
| get_info queries *IDN? and splits the reply into manufacturer, model, serial number and firmware version | upstream_code | 2220 Programmable DC Power Supplies.py:120-128 |
| A new current measurement is initiated with MEAS:CURR? and a new voltage measurement with MEAS:VOLT? | upstream_code | 2220 Programmable DC Power Supplies.py:135-149 |
| FETCh:POW? returns the last measured output power without initiating a measurement; the instrument recomputes power about every 100 ms | upstream_code | 2220 Programmable DC Power Supplies.py:109-118 |
| set_curr writes CURR and accepts a per-model maximum of 1.2, 1.5, 2.5, 3 or 5 A | upstream_code | 2220 Programmable DC Power Supplies.py:245-257 |
| set_volt writes VOLT and its code accepts only 0 through 30 V | upstream_code | 2220 Programmable DC Power Supplies.py:695-699 |
| set_ovp writes VOLT:PROT and its code accepts only 0 through 30 V | upstream_code | 2220 Programmable DC Power Supplies.py:721-725 |
| set_output_state contains OUTP writes and get_output_state queries OUTP?; its ON/OFF string branch appends literal .upper() text | upstream_code | 2220 Programmable DC Power Supplies.py:614-633 |
| set_ovp_state contains VOLT:PROT:STAT writes and queries; its ON/OFF string branch appends literal .upper() text | upstream_code | 2220 Programmable DC Power Supplies.py:731-750 |

## Limits

All three numeric writes are `Limit.operator_required`. The clone's `set_volt` and `set_ovp` code checks say
0 through 30 V (lines 695-699 and 721-725), but the same class lists 2200-60-2 and 2200-72-1 models in
`set_curr` (lines 245-257) and never states their voltage range; `set_curr` itself lists a different maximum for
each model string. A bound copied from one model's code check would therefore be wrong for another installed
unit, so the operator supplies the envelope in `site-limits.json`. `site-limits.example.json` is an example
overlay for a 30 V / 5 A member of the series (0-30 V, 0-5 A, 0-30 V OVP); its numbers are example-only and are
not device facts.

| parameter | command | limit | ref |
|---|---|---|---|
| voltage (V) | VOLT | operator-required | 2220 Programmable DC Power Supplies.py:695-699 (the code's model-incomplete 0-30 V check) |
| current (A) | CURR | operator-required | 2220 Programmable DC Power Supplies.py:245-257 (per-model maxima) |
| overvoltage_protection (V) | VOLT:PROT | operator-required | 2220 Programmable DC Power Supplies.py:721-725 (the code's model-incomplete 0-30 V check) |
| output | OUTP | not numeric: ON/OFF | 2220 Programmable DC Power Supplies.py:614-626 |
| overvoltage_protection_enabled | VOLT:PROT:STAT | not numeric: ON/OFF | 2220 Programmable DC Power Supplies.py:740-743 |

## Safety

The e-stop and the no-input safe-state action both write `OUTP OFF`. The clone documents ON/OFF and numeric
output states (lines 623-626), but its string formatting incorrectly emits literal `.upper()` text; this command
map sends the intended SCPI argument directly. The voltage and current set points are not changed. The clone documents no separate
hardware emergency-stop input, so `estop_physical_ref` is not set; the `x-cap.aaron-mott.output_off.v1`
safe-state action is the independent stop path, and it reaches the device through the same SCPI transport as
every other command. It is not a safety-rated channel: the physical supply's own protection and any bench
disconnect remain authoritative.

Risk is R3: the series can source a hazardous voltage and high energy, and no text of the clone states the
limits of the connected unit. The package is model-authored and unreviewed (`reviewed_by` is null), so no
hardware backend was run and none is claimed.

## Tags

keithley, 2200, power supply, dc power supply, scpi, visa

The fake models an instantaneous resistive load and does not model the instrument's approximately 100 ms
power-update cadence or cached measurement age. Measurements are placeholders, not a captured instrument session.
No transport/identity validation or hardware behavior is claimed. Publication remains an owner decision because
this source has no asserted licence.
