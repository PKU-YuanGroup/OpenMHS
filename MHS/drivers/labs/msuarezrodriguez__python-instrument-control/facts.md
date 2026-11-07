# Facts and tags for gh.msuarezrodriguez/python-instrument-control

Every fact cites the pinned clone at commit `e56156e1ba6a2e5469094291fef91945ca9ee069`. The same facts are written
into `driver.py` (`facts = [...]`); the generated reference is made from the driver, not from this page.

Tags: `qcodes`, `visa`, `gpib`, `temperature-controller`, `cryostat`, `heater`, `lakeshore`.

## Facts

| fact | source | ref |
|---|---|---|
| LakeShore336 is a minimal QCoDeS driver for the Lake Shore Model 336 temperature controller. | upstream_code | instruments/lakeshore_336.py:10-12 |
| The class reads inputs A-D, gets and sets loops 1-4, gets and sets heater ranges on outputs 1-2, configures OUTMODE and RAMP, and offers manual heater output MOUT. | upstream_code | instruments/lakeshore_336.py:14-20 |
| The class does not send *RST on init, to preserve sensor curves and setup; it sends only *CLS. | upstream_code | instruments/lakeshore_336.py:22-26 |
| The constructor passes name and address to VisaInstrument and writes *CLS. | upstream_code | instruments/lakeshore_336.py:95-110 |
| The valid sensor channels are A, B, C and D. | upstream_code | instruments/lakeshore_336.py:30 |
| Heater ranges off, low, medium and high map to codes 0, 1, 2 and 3, and max is an alias for high. | upstream_code | instruments/lakeshore_336.py:32-40 |
| Output modes off, closed loop, zone, open loop, monitor and warmup map to codes 0 to 5. | upstream_code | instruments/lakeshore_336.py:45-60 |
| The control input code maps none to 0 and A to D to 1 to 4. | upstream_code | instruments/lakeshore_336.py:70-79 |
| get_temperature sends KRDG? <channel> and returns a float in Kelvin. | upstream_code | instruments/lakeshore_336.py:150-170 |
| get_sensor_units sends SRDG? <channel> and returns the raw float sensor reading. | upstream_code | instruments/lakeshore_336.py:172-192 |
| get_setpoint and set_setpoint use SETP? and SETP with the loop index, in the preferred units of the control input, which the docstrings call usually Kelvin. | upstream_code | instruments/lakeshore_336.py:197-217 |
| get_ramp and set_ramp use RAMP? and RAMP with the rate and state. | upstream_code | instruments/lakeshore_336.py:219-248 |
| get_heater_range and set_heater_range use RANGE? and RANGE with the output index and range code; set_heater_range accepts the text names off, low, medium and high. | upstream_code | instruments/lakeshore_336.py:253-299 |
| set_manual_output sends MOUT <output>,<percent> and documents 0 to 100 percent of full scale. | upstream_code | instruments/lakeshore_336.py:301-316 |
| get_output_mode parses OUTMODE? into mode code and text, input code and text, and a power-up flag. | upstream_code | instruments/lakeshore_336.py:321-353 |
| set_output_mode sends OUTMODE <output>,<mode>,<input>,<powerup> and documents the accepted mode and input names. | upstream_code | instruments/lakeshore_336.py:355-401 |
| main.py configures output 1 in closed loop with sensor A, heater range high, and a 1 K/min ramp disabled. | upstream_code | main.py:189-202 |
| main.py closes the LakeShore instrument. | upstream_code | main.py:407 |
| The README lists the Keithley 2634B source-measure unit and the LakeShore 336 temperature controller as the supported instruments. | vendor_doc | README.md:7-10 |

## Scope

The card lists two entry classes, the LakeShore 336 temperature controller and the Keithley 2634B source-measure unit.
One driver package serves one native class, which gate G7 proves; this package integrates the first entry, the
temperature controller. The Keithley SMU needs its own card and package.

`QcodesDriver` was not usable for this class even though the card names it: its `parameter_bindings` must name QCoDeS
`Parameter` objects with an explicit `get()`/`set()`, and these upstream classes have plain methods that assemble text
commands from parts. The package is therefore a direct `Driver` over the upstream object with `native.py`, as
driver-authoring.md "Choosing the shape" prescribes.

The served reads use output 1, control loop 1 and input A, the configuration `main.py` applies. The e-stop and the
safe-state action turn both heater outputs off because the class documents outputs 1-2.

## Limits

`setpoint` and `ramp_rate` are `Limit.operator_required`: no text file of the clone states the accepted temperature or
ramp-rate range of the controller. The clone only says "typically 0.1-100 K/min" in a comment and points to a manual
that is not present (`instruments/lakeshore_336.py:243`), so that comment is not used as a device bound. The site
supplies both ranges; until then every write of either field is refused `MHS.SAFETY.LIMITS_UNSET`.

The heater-range, output-mode and control-input names are the closed sets the upstream maps (`off`/`low`/`medium`/
`high`, the six modes, and `none`/`A`-`D`). The manual output is bounded by the 0-100 percent the upstream docstring
states for the controller (`instruments/lakeshore_336.py:310`).

`site-limits.example.json` is an operator example, not a device fact. Its setpoint range follows the 10-300 K sweep
examples of `main.py:101-118` and its ramp range the 1-5 K/min examples of `main.py:103,119,202`; a deployed site must
replace them with the range its own cryostat, sensor and heater permit.

## Safety

The device is a heater controller: heating a cryostat is R2. No line of the clone documents a physical emergency stop
or its wiring, so `estop_physical_ref` is not set. The `@estop` and the safe-state action
`x-cap.msuarezrodriguez.heaters_off.v1` send `RANGE n,0` and `OUTMODE n,0,0,0` for outputs 1 and 2. The safe-state
action then reads the ranges and modes back and fails `MHS.SAFETY.SAFE_STATE_UNREACHED` unless all four read `off`
(model review, 2026-11-05: it first returned any read-back as a completed safe state). The e-stop does not wait for
that readback. The class addresses heater outputs 1 and 2 only; any other output of the controller is not commanded.
The e-stop and safe-state writes share the VISA session with any call in flight.

The setpoint is served in kelvin, but `SETP` and `SETP?` use the preferred unit of the control input, which the
upstream docstrings call "usually Kelvin" (`instruments/lakeshore_336.py:201, 215`). The package is correct only while
that unit is kelvin; a site whose control input reports Celsius or sensor units must not use the setpoint write.

The stop does not cool the cryostat, recall a setpoint already stored in the controller, cancel a ramp stored in the
controller, or restore a previous configuration. It disables both heater outputs and both control loops, so no new
heater power is regulated, but the sample can keep changing temperature from thermal inertia. A model-authored
hardware package at R2 never runs its hardware backend until a human sets `reviewed_by`.

## Fake fidelity

`fake.py` is a source-shaped in-memory model, not a recording. It keeps the upstream text/code maps and parser result
types, but it does not exercise the QCoDeS VISA session, its timeouts, the constructor's `*CLS` write or a device-side
rejection of a command. It stores any accepted value; the server enforces the driver limits before the fake sees a
call. `set_manual_output` has no query in the upstream class, so the fake stores the level without a readback. The
identity string, temperatures, raw sensor values and initial settings are placeholders, not facts about a Lake Shore
336 or a cryostat.

## Hardware backend

`native.py` imports the upstream class only when an operator loads the hardware backend, with the VISA resource
address as an explicit option. The upstream constructor opens the VISA session and writes `*CLS`; it deliberately
does not send `*RST` (`instruments/lakeshore_336.py:22-26, 95-110`). A failure there raises before the driver serves
anything. QCoDeS keeps a registry of instrument names, so `name` must be unique in the process. Nothing was run: the
package has never opened a VISA session, and the fake backend is the only one checked.
