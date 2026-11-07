# Facts and tags for gh.silab-bonn/basil

Every fact cites its source at commit `0630d8fd717fed83cb036b0c1b6015bdd7b25547`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page. This package
drives one device class of the repository, `basil.HL.iseg_hv:IsegHV`; the other hardware layers of the clone
(oscilloscopes, sequencer, register layers) are not covered.

| fact | source | ref |
|---|---|---|
| The class is an RS-232 interface for ISEG high-voltage power supplies of the SHQ and NQH series | upstream_code | basil/HL/iseg_hv.py:17 |
| The CMDS table gives every command as one letter plus the channel and, for a setting, '=<value>' | upstream_code | basil/HL/iseg_hv.py:23-46 |
| A query echoes the command first and the answer follows on the next read; a different echo raises | upstream_code | basil/HL/iseg_hv.py:444-451 |
| The device reports '????' (syntax error), '?WCN' (wrong channel) and '?TOT' (timeout); the reader raises RuntimeError on them | upstream_code | basil/HL/iseg_hv.py:57-61 |
| get_voltage and get_current return the actual output voltage in V and current in A of the channel | upstream_code | basil/HL/iseg_hv.py:118-138 |
| get_source_voltage returns the target voltage in V and set_voltage sends the absolute value | upstream_code | basil/HL/iseg_hv.py:166-178 |
| set_voltage refuses a magnitude above the hardware voltage limit, which is a percentage of V_MAX | upstream_code | basil/HL/iseg_hv.py:140-143 |
| The module identifier is 'UNIT_NUMBER;SOFTWARE_REL;V_MAX;I_MAX' and V_MAX is its third field | upstream_code | basil/HL/iseg_hv.py:253-262 |
| V_MAX is returned by the module identifier, not held as a constant of the clone | upstream_code | basil/HL/iseg_hv.py:486-487 |
| The ramp speed is 1 up to and including 255 V/s | upstream_code | basil/HL/iseg_hv.py:267 |
| The answer delay is 1 up to and including 255 ms | upstream_code | basil/HL/iseg_hv.py:284 |
| get_autostart is True when the device answers '008' and set_autostart sends 8 for True and 0 for False | upstream_code | basil/HL/iseg_hv.py:298-313 |
| The channel must satisfy 1 <= channel <= n_channel, and n_channel comes from the init configuration | upstream_code | basil/HL/iseg_hv.py:248-251 |
| off() sets the output voltage to 0 V | upstream_code | basil/HL/iseg_hv.py:459-460 |

Limits (both `upstream_code`):

| parameter | command | limit | ref |
|---|---|---|---|
| ramp_speed (V/s) | V<channel>=<value> | 1 to 255 | basil/HL/iseg_hv.py:277 (`if not 1 <= rs <= 255`) |
| answer_delay (ms) | W=<value> | 1 to 255 | basil/HL/iseg_hv.py:294 (`if not 1 <= bt <= 255`) |

`voltage_target` (the target voltage) and `channel` are `Limit.operator_required`: the module's `V_MAX` and its
channel count are returned by the device or set in its init configuration, and the clone states no value for
either. The operator supplies both in `site-limits.json`; `site-limits.example.json` is a filled example.

Safety: the e-stop calls the upstream `off()`, which sets the target voltage to 0 V. The HV output of the module
is switched at the front panel or by the polarity/`autostart` configuration the driver does not touch, so the
e-stop lowers the demand and does not claim to open a physical switch. This is R3 (a high-voltage supply, MHS/spec/04-safety.md; a model review raised it from the card's R1), with the
safe-state action `x-cap.silab-bonn.output_off.v1` as its independent stop; there is no hardware e-stop reference
in the clone and none is claimed. A deployment on a real detector should treat the
front-panel HV-ON switch and the interlock as the authoritative stop.

Tags: high voltage, power supply, iseg, rs-232, hv
