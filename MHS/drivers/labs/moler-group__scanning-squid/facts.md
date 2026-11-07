OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.moler-group/scanning-squid

Every fact cites the pinned clone at commit `32a61e8f8f4f6671f04e583752e361cb00276188`. Below, `atto.py` is
`scanning-squid/instruments/atto.py`, `scanner.py` is `scanning-squid/scanner.py`, and `microscope.py` and
`susceptometer.py` are in `scanning-squid/microscope/`. The same facts are in `driver.py` (`facts = [...]`); the
reference file is generated from it.

Tags: `scanning squid`, `microscope`, `attocube`, `anc300`, `qcodes`, `cryogenic`, `positioner`.

Author: Claude (claude-opus-5-5, a model and not a human), 2026-11-05, authoring the package for the repository's
primary device in place of the blocked DeepSeek heater package (user decision of 2026-11-05: Claude authors, Claude
Sonnet reviews). Model-written; `reviewed_by` is null.

## Facts

| fact | source | ref |
|---|---|---|
| A physical scanning SQUID microscope is represented by a Microscope or a subclass such as SusceptometerMicroscope, a QCoDeS Station of instrument components. | vendor_doc | docs/pages/microscope.rst:4 |
| SusceptometerMicroscope is the Microscope subclass for a scanning SQUID susceptometer and takes the configuration file and the temperature mode. | upstream_code | susceptometer.py:51-67 |
| The Microscope constructor closes every QCoDeS instrument, loads the configuration, starts file logging and adds the Attocube controller, the Lakeshore 372 and 331, the scanner, the SQUID and the lock-ins. | upstream_code | microscope.py:78-121 |
| The Attocube component is an ANC300 built from the configuration's atto entry. | upstream_code | microscope.py:123-134 |
| Importing the microscope module writes squid_units.txt into the current directory. | upstream_code | microscope.py:62-69 |
| approach steps the z Attocube by attosteps between capacitive touchdowns until a touchdown or a safety check breaks the loop. | upstream_code | microscope.py:314-339 |
| The ANC300 axis mode parameter reads with getm n and writes with setm n; its values are gnd, inp, cap, stp, off, stp+ and stp-. | upstream_code | atto.py:71-79 |
| The axis voltage parameter is limited to the configured voltage limit of the temperature mode. | upstream_code | atto.py:81-89 |
| ask_raw clears the device, sends the command twice, raises if the second reply contains ERROR and sleeps 0.2 s. | upstream_code | atto.py:109-124 |
| stop(axis) writes 'stop n' and then sets the axis mode to gnd. | upstream_code | atto.py:143-152 |
| step(axis, steps) refuses a non-integer, sets mode stp, sends stepu or stepd with the axis and the step count, writes stepw, sleeps abs(steps)/frequency*1.25 s, sets mode gnd and records the move in its metadata. | upstream_code | atto.py:154-177 |
| step sends its stepu or stepd command with ask, not write. | upstream_code | atto.py:168-169 |
| _parse_axis accepts an axis label or controller index of the configured axes. | upstream_code | atto.py:185-209 |
| Initialising the ANC300 sets each axis frequency and voltage to the configured values, grounds each axis and prints the controller version. | upstream_code | atto.py:305-319 |
| The Scanner constructor moves the scanner to [0, 0, 0]. | upstream_code | scanner.py:51-61 |
| get_pos reads the x, y and z scanner voltages with an NI-DAQ analog-input task and clamps each to the configured voltage limits. | upstream_code | scanner.py:109-131 |
| goto writes a ramp to an analog-output task created inside the call and waits until it is done. | upstream_code | scanner.py:133-180 |
| The documentation calls the approach the most dangerous part of a measurement: a missed touchdown crashes the SQUID into the sample using the Attocubes. | vendor_doc | docs/pages/workflow.rst:34-38 |
| The example configuration maps the Attocube axes x, y and z to controller axes 1, 2 and 3. | vendor_doc | docs/examples/config_susceptometer.json:49 |

## Device choice

The repository is the control software of one instrument, a scanning SQUID microscope (README.md:3;
docs/pages/microscope.rst:4); the earlier package served the BlueFors warm-up heater supply, a peripheral that only
`fridge.py` uses. The native is the class the documentation's examples construct, `SusceptometerMicroscope`, under the
module name the documentation uses with the repository's `scanning-squid` directory on the path
(docs/pages/workflow.rst:15); the routing override `MHS/registry/overrides/p3-reauthor-routing.json` makes it the
card's entry (it replaces the `untriaged` recon route). G7 resolves it at the pin; the earlier
`scanning_squid.instruments.heater:EL320P` named a module the clone does not have (G7.NATIVE_NOT_FOUND).

## Scope

| capability | upstream | note |
|---|---|---|
| `scanner_position` (state read) | `scanner.get_pos()` | x, y, z DAQ voltages, clamped by the upstream to the configured limits |
| `attocube_modes` (state read) | `atto.parameters["mode_ax<n>"].get()` | `getm n`; refused (BUSY) while a step is in progress |
| `x-cap.moler-group.atto_step.v1` (R2) | `atto.step(axis, steps)` | then the mode read back; `steps` is the count requested, not the steps made (below) |
| `x-cap.moler-group.atto_ground.v1` (safe state, R2) | `atto.stop(axis)` for z, x, y, then every mode read back | gnd on every axis or a failure |
| e-stop | as the ground action | |

Not covered: the piezo scanner's motion (`goto`, `retract`, scan lines: an analog-output task created and awaited
inside the call, scanner.py:159-168, which nothing outside can stop), capacitive touchdowns, approach, surfaces, scans
(long loops that end on KeyboardInterrupt and write data files), the lock-ins, the Lakeshore controllers, the DAQ
acquisitions, the SQUID record, the heater and the fridge warm-up.

## Limits

`steps` carries `Limit.operator_required`: no source bounds a step count, and how far a model may step each axis, and
in which direction z approaches the sample, depend on the mounting and the sample. `site-limits.example.json` allows
-20 to 20 requested steps per command on an example bench. A step lasts abs(steps)/frequency*1.25 s (atto.py:172) at
the configured frequency; the operator chooses the limit so a step ends within the caller's deadline.

The limit bounds the count requested, not the steps made. `step` sends its `stepu`/`stepd` command with `ask`
(atto.py:168-169), and the class's `ask_raw`, which QCoDeS's `ask` calls, writes every command twice and checks the
second reply for ERROR (atto.py:109-124, 140-141). The source does not show what the ANC300 does with the second copy:
it may make the steps again (up to about twice the count, and the wait of atto.py:172 covers one count only, so the
`gnd` of atto.py:173 may cut the second run short), restart the count, or answer ERROR, after which `step` raises with
the first copy under way. The operator measures the steps one command makes on the bench before setting the limit.
The fake writes the command twice and counts the requested steps once, a placeholder.

## Safety and stop

R2: a wrong Attocube step can crash the SQUID into the sample (docs/pages/workflow.rst:34-38, 54). The e-stop and the
safe-state action call `atto.stop(axis)` for z, x and y (every axis is tried even if one raises) and read every mode
back; they succeed only when all three read `gnd`. A grounded axis gets no drive voltage, so it cannot step. The
piezo scanner keeps its voltage: it is not stopped, because its ramps cannot be. The upstream holds no lock on the
ANC300's VISA session: an e-stop that lands while `step` exchanges its first commands may interleave with them (the
read-back then fails and the runtime keeps the latch and retries), and `step` itself, waking after the e-stop, sets the
axis to `gnd` again and records the full requested move in its metadata (atto.py:173-176). A step checks for
cancellation under the lock the stop takes before it starts; a stop that runs while a step is in flight reports itself
unconfirmed, because the upstream step may set its axis to `stp` and send `stepu`/`stepd` after it (atto.py:167-169),
and the runtime keeps the latch and re-runs the stop, which confirms once the step has returned (package cases check
both). If `atto.step` raises (for example on an ERROR reply to the second copy of the step command), the action stops
and grounds that axis with `atto.stop`, reads its mode back and reports `MHS.OUTCOME.UNKNOWN`, because the axis may
have stepped (a package case checks it). Opening the hardware backend moves the scanner to [0, 0, 0] V
(scanner.py:61) and re-initialises the ANC300 (native.py).
