# Facts and tags for gh.croningp/pycont

Every fact cites its source at commit `3f6dacb2a6ee82ce1806f6e471013a9ab809c0e6`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| pycont is a Python library to control Tricontinent C3000 pumps | vendor_doc | README.md:3 |
| Volumes in the pycont API are always in mL | vendor_doc | README.md:142 |
| The syringe volume, the operating speed and the microstep mode are per-pump configuration fields | vendor_doc | README.md:60-64 |
| C3000Controller stores the configured syringe volume in mL and derives steps_per_ml from the microstep count | upstream_code | pycont/controller.py:385-386 |
| The valve positions are input 'I', output 'O', bypass 'B' and extra 'E'; a 6-way valve adds positions '1' to '6' | upstream_code | pycont/controller.py:49-58 |
| Microstep mode 0 uses 3000 steps and microstep mode 2 uses 24000 steps | upstream_code | pycont/controller.py:65-68 |
| The maximum top velocity is 6000 steps/s in microstep mode 0 and 48000 steps/s in microstep mode 2 | upstream_code | pycont/controller.py:70-73 |
| The top velocity is expressed in steps per second | upstream_code | pycont/controller.py:673 |
| The serial I/O defaults to 9600 baud and a 1 s timeout | upstream_code | pycont/controller.py:75-78 |
| A C3000 instruction packet starts with '/' and ends with a carriage return | upstream_code | pycont/dtprotocol.py:12-13 |
| terminate() sends the command that terminates the current action | upstream_code | pycont/controller.py:1239-1243 |

The Fact for the microstep step counts cites lines 65-68 (the step-count constants and their mode comments);
`driver.py` cites the same range. No number from `fake.py` is used here: the fake's start volume, step resolution and
recording values are marked `# placeholder` test data.

Limits:

- The valve position is closed to the named positions `I`, `O`, `B`, `E` and the 6-way positions `1` to `6`, all
  written in `pycont/controller.py:49-58`.
- The pump action's `flow_rate` (uL/s) is `Limit.operator_required`: the reachable rate depends on the configured
  syringe volume and microstep mode, from which the clone derives `steps_per_ml`
  (`pycont/controller.py:385-386`, `pycont/controller.py:70-73`). The site supplies the range.
- The pump action's `volume` (uL) is `Limit.operator_required`: the syringe volume is per-pump configuration
  (`pycont/controller.py:363-388`, README.md:60-64). The site supplies the range.
- The site overlay in `site-limits.example.json` fills both bounds; it is an example, not a statement about any
  installed pump.

Safety: there is no line of the clone that documents an independent hardware e-stop, so `estop_physical_ref` is not
set. The native `terminate()` command is the `@estop` and, through the `x-cap.croningp.terminate.v1` action, the
safe-state action (SAFE-045 for this R2 hardware driver). `terminate()` stops the current action; it is not a
safety-rated stop. The hardware path (`native.py`, the serial connection and the real protocol pacing) was never run.

Tags: syringe-pump, tricontinent, c3000, fluid, serial
