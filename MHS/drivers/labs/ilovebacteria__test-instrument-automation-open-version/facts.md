# Facts and tags for gh.ilovebacteria/test-instrument-automation-open-version

This package binds one device of the repository's four-device PyMeasure pack: the GW Instek AFG-2225 function
generator (entry symbol `devices.afg2225:AFG2225`).  The HP 3458A multimeter, HP 53131A counter and HP E4419B power
meter are not covered.  Every fact cites the pinned clone at commit
`59499fa8b568d977aa5e2d5f1144725ee7f3cb0f`.

| fact | source | ref |
|---|---|---|
| AFG2225 is a two-channel function generator whose channel attributes ch1 and ch2 are AFG2225Channel creators | upstream_code | src/test_engine/devices/afg2225.py:90-97 |
| The channel shape control writes SOURce{ch}:FUNCtion using the SHAPES map: sine, square, ramp, pulse, noise and user | upstream_code | src/test_engine/devices/afg2225.py:18-30 |
| The channel frequency control is in Hz and its strict_range accepts 1e-6 to 25e6 | upstream_code | src/test_engine/devices/afg2225.py:32-37 |
| The channel amplitude control is peak-to-peak volts and its strict_range accepts 0.001 to 10.0 | upstream_code | src/test_engine/devices/afg2225.py:39-44 |
| The channel DC offset control is in volts and the clone states no offset range | upstream_code | src/test_engine/devices/afg2225.py:46-49 |
| The channel phase control is in degrees and its strict_range accepts -360 to 360 | upstream_code | src/test_engine/devices/afg2225.py:51-56 |
| The channel output_enabled control reads OUTPut{ch}? and writes OUTPut{ch} ON or OFF | upstream_code | src/test_engine/devices/afg2225.py:58-65 |
| The LOADS map defines the load keys 50ohm and highZ | upstream_code | src/test_engine/devices/afg2225.py:22 |
| The channel load control reads OUTPut{ch}:LOAD? and writes OUTPut{ch}:LOAD | upstream_code | src/test_engine/devices/afg2225.py:67-73 |
| The channel duty-cycle control is percent and its strict_range accepts 1.0 to 99.0 | upstream_code | src/test_engine/devices/afg2225.py:75-80 |
| The channel ramp-symmetry control is percent and its strict_range accepts 0 to 100 | upstream_code | src/test_engine/devices/afg2225.py:82-87 |
| sync_phase writes SOURce1:PHASe:SYNChronize | upstream_code | src/test_engine/devices/afg2225.py:156-162 |
| The error measurement reads SYSTem:ERRor? | upstream_code | src/test_engine/devices/afg2225.py:172-175 |
| The upstream write method sleeps 0.5 s before every command | upstream_code | src/test_engine/devices/afg2225.py:126-128 |
| setup() resets the instrument, sleeps 2 s, clears it and enables the OPC and status-byte summary; reset() writes *RST | upstream_code | src/test_engine/devices/afg2225.py:113-124 |

The same facts are in `driver.py` (`facts = [...]`); `reference.json` and `REFERENCE.md` are generated from the
driver, not from this page.

## Limits

| field | limit | source | ref |
|---|---|---|---|
| ch1_freq, ch2_freq | 1e-6 to 25e6 Hz | upstream_code | src/test_engine/devices/afg2225.py:36 |
| ch1_vpp, ch2_vpp | 0.001 to 10.0 V peak-to-peak | upstream_code | src/test_engine/devices/afg2225.py:43 |
| ch1_phase, ch2_phase | -360 to 360 deg | upstream_code | src/test_engine/devices/afg2225.py:55 |
| ch1_duty, ch2_duty | 1.0 to 99.0 percent | upstream_code | src/test_engine/devices/afg2225.py:79 |
| ch1_sym, ch2_sym | 0 to 100 percent | upstream_code | src/test_engine/devices/afg2225.py:86 |
| ch1_shape, ch2_shape | allowed set sine, square, ramp, pulse, noise, user | upstream_code | src/test_engine/devices/afg2225.py:18-21 |
| ch1_load, ch2_load | allowed set 50ohm, highZ | upstream_code | src/test_engine/devices/afg2225.py:22 |

The DC offset of either channel is written through the extension action
`x-cap.ilovebacteria.set_offset.v1` (`channel` 1 or 2 plus `offset_v`).  Its `offset_v` bound is
`Limit.operator_required`: the upstream offset control names only its unit and validates no range
(src/test_engine/devices/afg2225.py:46-49), so every offset write is refused `MHS.SAFETY.LIMITS_UNSET` until an
operator overlay supplies the envelope.  `site-limits.example.json` is an example overlay only; its -5 V to 5 V range is operator data, not a
device fact.  The offset action is split out of `cap.device.configure.v1` so that the configure tool stays within
the 2 KB MCP tool limit; the remaining channel controls are ordinary writable state.

## Safety

The safe state is both channel outputs read back as off. `@estop` (`stop_outputs`) attempts both
`output_enabled = False` writes even if one fails, then requires both controls to read back as `False`
(afg2225.py:58-65). An ignored write, missing confirmation or exception fails the stop. The upstream class has
no separate stop method. The clone
states no independent hardware emergency stop, and this R1 package does not claim `estop_physical_ref`; SAFE-045's
independent-stop requirement applies at R2 and above.

No `@reset` is declared: the upstream `reset()` writes `*RST` to the instrument (afg2225.py:122-124), which changes
the device rather than only re-establishing communication.  Enabling either output is an ordinary writable state,
not a reset step; the runtime refuses it while the e-stop latch is engaged, and a reset hook never turns an output
on.

The package chooses a 5000 ms e-stop budget; this is a software policy, not a device latency guarantee.
The upstream write method sleeps 0.5 s per command (afg2225.py:126-128), so two OFF writes alone take at least
1 s before I/O time; the two readbacks add query time. A slow or failed link can still exceed the budget and
must leave the e-stop failed and latched. The fake does not model this pacing or concurrent VISA traffic.

## Scope and fake

Covered: both channels' waveform, frequency, amplitude, offset, phase, output enable, load, duty cycle and ramp
symmetry; the error queue; the native phase synchronization.  Not covered: the upstream `setup()`, `reset()`,
`remote_mode()`, `local_mode()` and `wait_for_opc()` helpers, and the HP 3458A, HP 53131A and HP E4419B device
classes of the same repository.

The fake backend is an in-memory stand-in for the upstream PyMeasure object, not a recording and not the upstream
`pyvisa_sim.yaml` simulator.  It defines only members the pinned `AFG2225` class has (`ch1`, `ch2`, `sync_phase`,
`error`) and the channel controls that class's `AFG2225Channel` exposes.  Every starting value and canned reply in
`fake.py` is marked `# placeholder`; none is a Fact or a Limit.  No hardware was attached and the hardware backend was
never imported or run.

The synchronization fake models command completion only. The clone sends `SOURce1:PHASe:SYNChronize`
(afg2225.py:156-162) but does not specify the configured phase-register readbacks after it, so the tests no
longer assert that both phase registers become zero. Neither the fake nor this model review establishes
physical phase alignment. The repository has no top-level licence declaration; publication still requires
the owner's licence decision, as the card states.

Tags: signal-generator, waveform, function-generator, scpi, pymeasure
