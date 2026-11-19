# Facts and tags for gh.qcodespp/qcodespp

Every fact cites the pinned clone at commit `77090fc8f3ece9831887c8a07bd1249d343d18c1`.
`upstream_code` refs name `path/in/clone:LINE` or a bounded range where the statement spans adjacent lines;
`Keithley_2450.py` below is `qcodespp/instrument_drivers/tektronix/Keithley_2450.py`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

Tags: `qcodes`, `visa`, `scpi`, `source-measure-unit`, `keithley`, `2450`, `voltage-source`, `current-source`.

## Facts

| fact | source | ref |
|---|---|---|
| `Keithley_2450` is a QCoDeS `VisaInstrument` whose docstring calls it a voltage source that behaves similarly to the K2400 series driver. | upstream_code | Keithley_2450.py:5-8 |
| The constructor takes `name` and `address` and passes terminator `'\n'` to `VisaInstrument`. | upstream_code | Keithley_2450.py:10-11 |
| `rangev_source`, `rangev_sense`, `rangei_source` and `rangei_sense` are Parameters with source/sense voltage and current range queries and `{:f}` setters. | upstream_code | Keithley_2450.py:13-35 |
| `compliancev` has `get_cmd` `SOUR:CURR:VLIM:LEV?` and `set_cmd` `SOUR:CURR:VLIM:LEV {:.16f}`. | upstream_code | Keithley_2450.py:37-41 |
| `compliancei` has `get_cmd` `SOUR:VOLT:ILIM:LEV?` and `set_cmd` `SOUR:VOLT:ILIM:LEV {:.16f}`. | upstream_code | Keithley_2450.py:43-47 |
| `volt` is a Parameter with unit V whose `get_cmd` is `self._get_volt` and `set_cmd` is `self._set_volt`; its docstring says a voltage read is an error while the output is off. | upstream_code | Keithley_2450.py:49-60 |
| `curr` is a Parameter with unit A whose `get_cmd` is `self._get_current` and `set_cmd` is `self._set_current`; its docstring says a current read is an error while the output is off. | upstream_code | Keithley_2450.py:62-73 |
| `source` is a Parameter with an `Enum('VOLT', 'CURR')` validator, `get_cmd` `:SOUR:FUNC?` and `set_cmd` `self._set_mode_and_sense`. | upstream_code | Keithley_2450.py:76-80 |
| `sense` is a Parameter with `get_cmd` `:SENS:FUNC?` and `set_cmd` `:SENS:FUNC "{:s}"`. | upstream_code | Keithley_2450.py:82-86 |
| `output` is a Parameter with `get_cmd` `:OUTP:STAT?` and `set_cmd` `:OUTP:STAT {:d}`. | upstream_code | Keithley_2450.py:93-96 |
| `_get_volt` raises when `output()` is 0, returns `READ?` when `sense` starts with `"VOLT`, and otherwise returns `SOUR:VOLT?` when `source()` is `VOLT`. | upstream_code | Keithley_2450.py:125-134 |
| `_set_volt` raises when `output()` is 0 and otherwise writes `:SOUR:VOLT:LEV` with eight decimals when `source()` is `VOLT`. | upstream_code | Keithley_2450.py:136-143 |
| `_get_current` raises when `output()` is 0, returns `READ?` when `sense` starts with `"CURR`, and otherwise returns `SOUR:CURR?` when `source()` is `CURR`. | upstream_code | Keithley_2450.py:153-162 |
| `_set_current` raises when `output()` is 0 and otherwise writes `:SOUR:CURR:LEV` with sixteen decimals when `source()` is `CURR`. | upstream_code | Keithley_2450.py:164-171 |
| `_get_resistance` raises when `output()` is 0 and returns `READ?` when `sense` is CURR with source VOLT or when source is CURR with sense VOLT. | upstream_code | Keithley_2450.py:174-183 |
| `_set_mode_and_sense` sets `sense` to CURR for VOLT and to VOLT for CURR, then writes `:SOUR:FUNC`. | upstream_code | Keithley_2450.py:208-216 |
| `reset` documents a return to GPIB defaults and cancellation of pending commands, and writes `:*RST`. | upstream_code | Keithley_2450.py:218-229 |
| `_volt_parser` returns field 0, `_curr_parser` returns field 1 and `_resistance_parser` returns field 0 divided by field 1 of a comma-separated reply. | upstream_code | Keithley_2450.py:231-242 |
| The constructor adds Parameters for ranges, compliance, voltage, current, source and sense mode, four-wire sense, output, NPLC and resistance, then calls `connect_message`. | upstream_code | Keithley_2450.py:13-120 |

## Scope and deviation from the card

The card is the whole qcodespp driver pack and names four entry classes. This package serves one concrete
implementation of it, the Keithley 2450 source measure unit. The card's `QcodesDriver` helper cannot express the
class: every Parameter of `Keithley_2450` is built with `add_parameter` (Keithley_2450.py:13-120), while G7's QCoDeS
profile proves only an explicit `self.<name> = Parameter(...)` constructor and refuses `add_parameter`
(`MHS/sdk/docs/qcodes-driver.md`). The actual runtime is a QCoDeS object with ordinary measurement/setter methods and
literal SCPI commands, so this package uses a direct `Driver` with `native.py` as the hardware factory and a
source-shaped fake. This is the `DEVIATION FROM THE CARD` recorded in `RESULT.json`.

Served, each from a source-visible method or Parameter of the selected class:

| field | access | unit | source |
|---|---|---|---|
| `voltage` | read | V | `_get_volt` then `_volt_parser` for a multi-field `READ?` reply, `float` for a single setpoint (Keithley_2450.py:125-134, 231-233) |
| `current` | read | A | `_get_current` then `_curr_parser` for a multi-field `READ?` reply, `float` for a single setpoint (Keithley_2450.py:153-162, 235-237) |
| `resistance` | read | Ohm | `_get_resistance` then `_resistance_parser` (Keithley_2450.py:174-183, 239-242) |
| `output` | read, write | (boolean) | `:OUTP:STAT?` and `:OUTP:STAT {:d}` (Keithley_2450.py:93-96) |
| `source` | read, write | (string) | `:SOUR:FUNC?` and `_set_mode_and_sense` (Keithley_2450.py:76-80, 208-216) |
| `compliancev` | read, write | V | `SOUR:CURR:VLIM:LEV?` and `SOUR:CURR:VLIM:LEV {:.16f}` (Keithley_2450.py:37-41) |
| `compliancei` | read, write | A | `SOUR:VOLT:ILIM:LEV?` and `SOUR:VOLT:ILIM:LEV {:.16f}` (Keithley_2450.py:43-47) |
| `voltage` | write | V | requires output on; selects source VOLT with `_set_mode_and_sense` then `_set_volt` with `:SOUR:VOLT:LEV` (Keithley_2450.py:136-143, 208-216) |
| `current` | write | A | requires output on; selects source CURR with `_set_mode_and_sense` then `_set_current` with `:SOUR:CURR:LEV` (Keithley_2450.py:164-171, 208-216) |

The upstream `volt` and `curr` Parameters declare `get_parser=float`, which parses the whole `READ?` reply; the class's
own `_volt_parser`, `_curr_parser` and `_resistance_parser` split the comma-separated reply (Keithley_2450.py:231-242).
This adapter calls those upstream parsers after the measurement methods, so a `READ?` reply carrying several fields is
handled as the upstream parsers intend. A single-value setpoint reply is parsed as a float, as the upstream `volt` and
`curr` Parameters do with `get_parser=float` (Keithley_2450.py:49-73). The upstream `_get_volt`, `_get_current` and
`_get_resistance` raise while the output is off (Keithley_2450.py:125-183); the adapter checks `:OUTP:STAT?` first and
returns `None` for the measurement instead of raising, so the resource remains readable while the source is disabled.
The source's `output` Parameter has no validator, so the adapter writes the same `0` or `1` the Parameter's
`:OUTP:STAT {:d}` setter writes and reads the state through `:OUTP:STAT?`. The `voltage` and `current` writes require
the output on and select the matching source function through `_set_mode_and_sense` when needed; a write while the
output is off is refused before any mode change with `MHS.DEVICE.PRECONDITION_UNMET`.

NOT COVERED, with the source reason:

- `rangev_source`, `rangev_sense`, `rangei_source`, `rangei_sense`, `nplcv`, `nplci` and `fourwiresense`: ordinary
  range/integration settings (Keithley_2450.py:13-35, 88-91, 98-108) that the card does not require for the primary
  source/measure control; they are not served.
- `reset`/`:*RST`: not exposed. A `:*RST` changes the instrument's state (Keithley_2450.py:218-229), so it is not a
  communication-only reset and is not used as a recovery hook.
- the QCoDeS validators and value wrappers: the served fields are direct methods and commands, not Parameter `.get()`
  and `.set()` calls, so a deployment must check the installed QCoDeS version's command handling in a supervised run.

## Safety

The Keithley 2450 is a source measure unit: with the output on it drives voltage and current into an external
circuit. A wrong level or compliance can be high-energy and damage the load, so the driver is conservatively R3, above the card's R1
floor; no source-backed voltage ceiling excludes hazardous sourcing. The clone does not state a voltage, current or compliance bound (Keithley_2450.py:13-120, 136-171), so every
numeric write carries `Limit.operator_required` and stays refused with `MHS.SAFETY.LIMITS_UNSET` until the operator's
`site-limits.json` supplies a range; `site-limits.example.json` is an example overlay, not a device bound. The package
is blocked: lack of a source-backed voltage bound cannot justify an R2 ceiling.

The software safe-state action is the input-free action `x-cap.qcodespp.output_off.v1`: it writes `:OUTP:STAT 0` (the
output Parameter's own setter command, Keithley_2450.py:93-96) and confirms `:OUTP:STAT?` reports the output off. The
`@estop` method writes the same command. The source keeps its configured level, but the output is disabled, and the
e-stop latch refuses later writes. This is a software command to the instrument, not a hardware e-stop; no source in
the clone states that a physical relay or interlock is opened, so `estop_physical_ref` is not claimed. An e-stop
calls the `@estop` method and then the safe-state action, so the output-off command is sent twice; the command is
idempotent.

## Fake fidelity

`fake.py` is a source-shaped stand-in: it implements `_get_volt`, `_set_volt`, `_get_current`, `_set_current`,
`_get_resistance`, `_set_mode_and_sense`, `_volt_parser`, `_curr_parser`, `_resistance_parser` and the inherited
VISA `write`, `ask` and `close` that the driver uses. It sends and understands the same command strings, and it
reproduces the output-on and source/sense preconditions of the upstream methods. Initial values are placeholders
marked `# placeholder`, not facts: source current, sense voltage, output on, 1.0 V, 1 mA, 10 V voltage compliance and
0.1 A current compliance. It does not model instrument timing, auto-range, the SCPI error queue, range/compliance
rounding, the output relay, or the QCoDeS validators; a first supervised hardware run must exercise the source modes,
both compliances and the output-off readback.

## Hardware backend

`native.py` imports `qcodespp.instrument_drivers.tektronix.Keithley_2450:Keithley_2450` only when an operator loads
the hardware backend with an explicit VISA resource address. The constructor opens the session, adds every Parameter
and calls `connect_message()` (Keithley_2450.py:10-120) but does not turn the output on. `teardown` calls the QCoDeS
`close()`. Nothing was run: the package has never opened a VISA session.

## Package notes

The package is model-authored (`driver.lock.json` `authored_by` kind `model`) and unreviewed (`reviewed_by` null). It
has run on the fake backend only; its evidence is `contract_checked`, never an MHS-Device level. The hardware backend
of a model-written R3 package is refused by the loader until a human signs `reviewed_by`.

## Blocking model-review findings

The added regression cases intentionally fail pending a source-backed repair; the stock gate assertion remains
unchanged. With no site overlay, `configure({output: true})` energizes stored levels and `configure({source: VOLT})`
selects the stored voltage while the output is on. Neither input carries a numeric envelope, so the numeric
`operator_required` limits do not cover these paths. Level setters also switch modes before setting the new level.
The output Parameter (Keithley_2450.py:93-96), mode setter (:208-216), and output-on-only level setters (:136-171)
require an explicit bounded enable/re-enable design. Reset currently only clears the latch; no re-enable action
is declared. A software output-off readback is not an independent physical stop or a voltage-discharge measurement.

The fake invents a five-field READ? reply. The served class never configures that format; `_get_resistance`
(:174-183) reads the currently selected sensing function, and the upstream ratio parser (:239-242) requires a
voltage/current pair. The adapter instead labels any scalar reply as Ohm. A scalar sensing sample must not be
reported as resistance, and no live reply format was verified.

Other card entries are excluded: Lakeshore Model_340 is a temperature controller with heater/setpoint control;
MercuryiPS_120 controls a magnet power supply and includes a source safety TODO (:42-68); AttocubeAMC100 opens
a vendor device and controls motion (AMC100.py:250-299). None of those paths was imported, run or validated.
