# Facts and tags for gh.t-wagner/pymeasure

Every fact cites its source at commit `d9c552f3a3fabd51c9fb4b76cd1e095f738e96bf`: `upstream_code` is a code,
docstring or comment line of the clone. The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| Keithley2000Multimeter is a PyVisaInstrument opened at a VISA address | upstream_code | instruments/keithley2000_multimeter.py:639-642 |
| The multimeter creates three channels in this order: voltage_dc, current_dc and resistance | upstream_code | instruments/keithley2000_multimeter.py:651-659 |
| The voltage channel selects the VOLT:DC sense function | upstream_code | instruments/keithley2000_multimeter.py:225-226 |
| The current channel selects the CURR:DC sense function | upstream_code | instruments/keithley2000_multimeter.py:254-255 |
| The resistance channel selects the RES sense function | upstream_code | instruments/keithley2000_multimeter.py:283-284 |
| A channel query writes TRIG:SIGN and reads the measurement with FETCH? | upstream_code | instruments/keithley2000_multimeter.py:84-88 |
| A channel query returns a list and appends the first FETCH? value for each sample | upstream_code | instruments/keithley2000_multimeter.py:82-90 |
| identification queries *IDN? | upstream_code | instruments/keithley2000_multimeter.py:677-679 |
| reset writes *RST and *CLS and then loads the defaults | upstream_code | instruments/keithley2000_multimeter.py:667-671 |
| A channel range property reads the range with a RANG? query of its sense function | upstream_code | instruments/keithley2000_multimeter.py:229-232 |
| The voltage range setter accepts 0 V to 1010 V | upstream_code | instruments/keithley2000_multimeter.py:236-245 |
| The current range setter accepts 0 A to 3.1 A | upstream_code | instruments/keithley2000_multimeter.py:265-274 |
| The resistance range setter accepts 0 Ohm to 120e6 Ohm | upstream_code | instruments/keithley2000_multimeter.py:294-303 |

## Limits

The package declares three sourced limits, all from the upstream setters:

| field | limit | ref |
|---|---|---|
| `voltage_range` write | 0 to 1010 V | instruments/keithley2000_multimeter.py:236-245 |
| `cap.measure.voltage.v1` input `range_v` | 0 to 1010 V | instruments/keithley2000_multimeter.py:236-245 |
| `cap.measure.current.v1` input `range_a` | 0 to 3.1 A | instruments/keithley2000_multimeter.py:265-274 |
| `cap.measure.voltage.v1` input `channel` | one of `voltage_dc` | instruments/keithley2000_multimeter.py:653 |
| `cap.measure.current.v1` input `channel` | one of `current_dc` | instruments/keithley2000_multimeter.py:656 |
| `cap.measure.resistance.v1` input `channel` | one of `resistance` | instruments/keithley2000_multimeter.py:659 |

No bound is `operator_required`, so there is no `site-limits.example.json` to narrow. The runtime enforces
these bounds before any native call; the driver never clamps a range, and its channel selector check is a
precondition, not a second bound.

## Scope and safety

The package reads the identity and the three channels the upstream class creates (`voltage_dc`, `current_dc`
and `resistance`), and serves the catalogue read classes `cap.measure.voltage.v1`,
`cap.measure.current.v1` and `cap.measure.resistance.v1` as one measurement action each. It binds one
`@write`, `voltage_range` (the voltage channel's `SENS:VOLT:DC:RANG` setting, read back through the
upstream range property), and the optional measurement range of the voltage and current actions, all
bounded by the upstream range setters (`instruments/keithley2000_multimeter.py:236-245` and
`265-274`), plus the operator-only `reset()`. The upstream trigger, buffer, display, format and `defaults()`
write paths are not bound. The clone defines only `VOLT:DC` and a two-wire `RES` function, so the action
inputs `dc=false` and `four_wire=true` are refused rather than mapped to an invented command. The
`voltage_range` write makes the configure binding's class floor govern, so the package declares R1: it has an
`@estop` that runs the upstream `reset()` (*RST and *CLS) and the safe state sentence "multimeter reset to
its defaults (*RST, *CLS)". No hardware e-stop is claimed. `fixtures/conformance.json` supplies the measurement inputs with the channel names the clone
creates, so the conformance suite does not send the catalogue's generic `ch1` example.

The `@reset` method runs the upstream `reset()` (*RST and *CLS) only after an operator accepts a reset of a
latched e-stop; the agent's own reset is refused by the runtime, so the fake's reset path is not reached by an
agent.

The clone has no simulator, mock or recorded session for this class, and the card's `mock_strategy` prefers a
transcript. The package fake is an in-memory stand-in with fixed placeholder values marked `# placeholder` in
`fake.py`; those values are test data, not facts, limits or a recording. The fake answers the upstream
`channels()` accessor and the channel `query()` shape; `channels()` comes from the pymeasure container
(`case.py:447-453`), which the gate's AST cannot follow through the external `PyVisaInstrument` base, so G7 may
report it as a `MAYBE_ABSENT` warning.

The hardware path was never run: `native.py` opens the upstream class through its VISA address, the gate never
imports it, and no hardware was attached. The package is model-authored and unreviewed; no human review or
hardware test is claimed.

Tags: keithley, 2000, dmm, multimeter, voltage, current, resistance, measurement
