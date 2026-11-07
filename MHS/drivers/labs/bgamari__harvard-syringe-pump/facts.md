# Facts, limits and tags for gh.bgamari/harvard-syringe-pump

The clone is a Python 2 package for Harvard Apparatus OEM syringe pump modules. `harvardpump/pump.py` has two
classes, `Model22` and `Model44`; the GTK UI instantiates `Model44` (`harvardpump_ui:10`) on `/dev/ttyUSB0`
(`harvardpump_ui:136`), and this driver follows that class. The clone contains no README, manual, datasheet or test
suite, so every statement below cites a line of the code or the UI.

Every fact cites its source at commit `d28b04fae0695570f3e91f3d2871875f9b7a5211`: `upstream_code` is a code or
docstring line of the clone. The same facts are written into `driver.py` (`facts = [...]`); the reference file is
generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| Model 44 is the syringe pump class the GTK UI instantiates | upstream_code | harvardpump_ui:10 |
| The GTK UI opens the pump on /dev/ttyUSB0 | upstream_code | harvardpump_ui:136 |
| The serial line is 9600 baud with two stop bits | upstream_code | harvardpump/pump.py:136-137 |
| A command is written as text followed by a carriage return | upstream_code | harvardpump/pump.py:140-142 |
| A reply begins with LF, its text ends at CR, and the frame ends with a digit and one of the prompt characters | upstream_code | harvardpump/pump.py:144-165 |
| The prompts are ':' stopped, '>' running, '<' reverse, '/' paused, '*' stopped and '^' wait for a dispense trigger | upstream_code | harvardpump/pump.py:126-133 |
| The pump caches the status named by the prompt of the last reply | upstream_code | harvardpump/pump.py:160-165 |
| set_diameter sends 'DIA <value>' and its docstring names the syringe diameter in millimetres | upstream_code | harvardpump/pump.py:179-182 |
| get_diameter sends 'DIA', get_target_volume sends 'TGT' and get_volume_accum sends 'DEL' | upstream_code | harvardpump/pump.py:206-208 |
| get_flow_rate sends 'RAT' and splits the reply into a value and a unit token; the token 'ml/mn' means mL/min | upstream_code | harvardpump/pump.py:195-204 |
| set_flow_rate sends 'RAT <value> <range token>' and the range token for mL/min is 'MM' | upstream_code | harvardpump/pump.py:227-238 |
| start sends 'RUN', stop sends 'STP', clear_volume_accum sends 'CLD' and reverse sends 'DIR REV' | upstream_code | harvardpump/pump.py:216-220 |
| set_direction sends 'DIR INF' for forward and 'DIR REF' for reverse | upstream_code | harvardpump/pump.py:222-225 |
| set_target_volume sends 'TGT <value>'; clear_target sends 'TGT 0' | upstream_code | harvardpump/pump.py:219-243 |
| set_pump_mode sends 'MOD PMP', set_volume_mode sends 'MOD VOL', and get_mode sends 'MOD' and lowercases the reply | upstream_code | harvardpump/pump.py:245-256 |
| get_version sends 'VER' | upstream_code | harvardpump/pump.py:184-187 |
| _format_float rejects a value above 1e6 and truncates its formatted form to six characters; it is an encoder guard and an encoder truncation, not a range of the pump | upstream_code | harvardpump/pump.py:171-173 |
| The UI's range table gives the mL/min range the volume unit mL | upstream_code | harvardpump_ui:60-65 |
| The UI displays the Model 44 target volume in mL | upstream_code | harvardpump_ui:124 |
| The upstream setup.py describes the package as a Python interface to Harvard Apparatus OEM syringe pump modules | upstream_code | setup.py:3-5 |

## Limits

| parameter | unit | limit | source |
|---|---|---|---|
| diameter | mm | operator_required | no text states a diameter range; `_format_float` only truncates the encoded value (harvardpump/pump.py:171-173) |
| flow_rate | mL/min | operator_required | the clone sends any formatted value with one of four range tokens and states no numeric range (harvardpump/pump.py:227-238) |
| target_volume | mL | operator_required | no text states a volume range; the UI spin-button maximum is a UI default (harvardpump_ui:536-537) |
| mode | one of PMP, VOL | allowed set | `MOD PMP` and `MOD VOL` (harvardpump/pump.py:245-251) |
| set_direction direction input | one of INF, REF | allowed set | `DIR INF` and `DIR REF` (harvardpump/pump.py:222-225) |

The three numeric limits are `Limit.operator_required` because the clone states no range for them. The GTK spin
buttons cap the UI at 100 for the diameter, 9999 for the flow rate and 100 for the volume
(`harvardpump_ui:38-44`, `536-537`), but a spin-button default is not a device bound and is not copied into a
Limit. `_format_float` raises only when a value is above 1e6 and then truncates the six-decimal text to six
characters (harvardpump/pump.py:171-173); that is an encoder behavior, not the range of the syringe or the pump.
Without an operator overlay every write of diameter, flow rate or target volume is refused
`MHS.SAFETY.LIMITS_UNSET`; `site-limits.example.json` shows an example overlay, not a statement about any syringe.

The driver covers one of the four flow-rate ranges: mL/min (`RAT <value> MM`). The other ranges (uL/min, uL/hr and
mL/hr, `harvardpump/pump.py:229-233`) are not exposed, because the read has to know the unit of the value. The
accumulated volume is therefore reported in mL, the unit the UI's range table gives the mL/min range
(`harvardpump_ui:60-65`).

## Safety

* The e-stop and the safe-state action send `STP`, the native stop (`harvardpump/pump.py:216-218`). The state after
  STP is the prompt ':' (stopped, `harvardpump/pump.py:126-133`); no new motion starts until a RUN.
* The clone text names no independent hardware emergency stop, interlock, door or watchdog, so
  `estop_physical_ref` is not set and the safe-state action `x-cap.bgamari.stop_pump.v1` is the R2 stop path
  required by SAFE-045. The e-stop and the safe-state action both send STP.
* A pump that dispenses liquid is at least R2 (`MHS/spec/04-safety.md`), so the driver is R2 even though the card's
  `risk_floor` is R0.
* Hardware was never attached, the hardware backend was never opened, and this is a model-authored, unreviewed
  package (`driver.lock.json` `reviewed_by` is null).

## Tags

syringe pump, pump, serial, infuse, withdraw, harvard apparatus
