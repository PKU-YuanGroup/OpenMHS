# Facts and tags for gh.festo-se/festo-dev-fluid-control

Every fact cites its source at commit `2da14c5d6b202d3aca1ca1ca6e173f68eaf266c3`: `vendor_doc`
(a text file of the clone) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written
into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this
page.

| fact | source | ref |
|---|---|---|
| A pressure-over-liquid instrument pressurises a liquid reservoir with the PGVA and opens a solenoid valve via the VAEM for a calibrated duration; the calibration maps target volume (uL) to valve opening time (ms) | vendor_doc | docs/index.md:9 |
| The Dispenser class is the fixed-volume, non-aspirating entry point; the Pipettor class extends it with aspirate, mix and tip-handling operations | vendor_doc | docs/index.md:25 |
| Dispense takes a mapping of channel IDs to {volume in uL, liquid_class} commands and applies the pressure-over-liquid process to each selected valve channel | upstream_code | src/fluid_control/capabilities.py:45-71 |
| Aspirate takes the same channel-command mapping as dispense and runs the aspirate calibration process | upstream_code | src/fluid_control/capabilities.py:77-94 |
| Mix repeats an aspirate and a dispense on the channel for the requested number of cycles | upstream_code | src/fluid_control/capabilities.py:100-121 |
| A transfer aspirates a volume and then dispenses it; both operations take the same channel-command mapping but use their own calibrated pressure | vendor_doc | docs/examples/pipettor.md:49-52 |
| The calibration parameter parameters.pressure is the PGVA output pressure in mbar for one liquid class and process | vendor_doc | docs/configuration/index.md:258 |
| The active valve channel IDs come from active_valve_terminals and the channel count from fluid-channel-count in the component configuration | upstream_code | src/fluid_control/device_config.py:76-78 |
| The liquid classes are the keys of the live calibration mapping | upstream_code | src/fluid_control/device_config.py:105-107 |
| The session returns the active channel IDs, the liquid-class names and the combined fluid-control, pressure and valve status | upstream_code | src/fluid_control/cli/session.py:409-438 |
| set_pressure takes a target pressure in mbar, sends it to the pressure controller and blocks until the reading stabilises | upstream_code | src/fluid_control/cli/session.py:239-248 |
| An output pressure of 0 mbar is the neutral value the manual valve command uses by default | upstream_code | src/fluid_control/cli/session.py:145-146 |
| The component context-manager exit sets the pressure to 0, deselects every valve and clears the fluid-control status | upstream_code | src/fluid_control/fluid_control.py:774-780 |
| _wait_output_pressure issues set_output_pressure and then polls get_output_pressure until the reading is within 1 mbar of the target | upstream_code | src/fluid_control/fluid_control.py:650-665 |
| The pressure-readiness and valve-readiness polling loops are bounded by a 30 second timeout | upstream_code | src/fluid_control/fluid_control.py:31-34 |
| The engine rejects a negative volume, a channel that is not in the active channel configuration and a non-positive valve opening time | upstream_code | src/fluid_control/fluid_control.py:718-738 |
| The fluid-control status codes are 0 clear, 1 error and 2 busy | upstream_code | src/fluid_control/fluid_control.py:783-793 |
| The upstream pressure validator is a no-op TODO, so the library itself does not enforce a pressure range | upstream_code | src/fluid_control/fluid_control.py:740-742 |

## Limits

All numeric limits are `Limit.operator_required`: the clone documents the units and the calibration
model but not the safe envelope of a configured instrument.

- `pressure` (PGVA output pressure, mbar): no text file states the range, and the upstream
  `_validate_pressure` is a no-op TODO (`src/fluid_control/fluid_control.py:740-742`). The site
  supplies the range.
- The aspirate, dispense and mix `channel` inputs: the active valve terminals come from the
  instrument configuration (`src/fluid_control/device_config.py:76-78`), not from a fixed range.
  The site supplies the channel set of its VAEM.
- The `volume` inputs (uL): the calibration maps a volume to a valve opening time, but no text file
  states a volume range for the tips and the reservoir. The site supplies the volume envelope.
- The `cycles` input of mix: no text file states a cycle bound. The site supplies it.
- `site-limits.example.json` is an example operator overlay only; it is not a statement about any
  instrument.

## Safety

- The instrument moves liquid under pressure, so the driver declares R2 (the card's floor is R2).
- The e-stop is the upstream `set_pressure(0)`: 0 mbar is the documented neutral value
  (`src/fluid_control/cli/session.py:145-146`). The safe-state action
  `x-cap.festo-se.deactivate.v1` also calls the component context-manager exit, which sets the
  pressure to 0, deselects every valve and clears the status
  (`src/fluid_control/fluid_control.py:774-780`).
- The clone documents no independent, safety-rated hardware e-stop, so `estop_physical_ref` is
  absent and this package does not claim one.
- `set_pressure` issues the pressure command before polling, but it can wait up to the upstream
  30 second timeout (`src/fluid_control/fluid_control.py:31-34`, `:650-665`) if the reading never
  reaches the target. The e-stop path was never run on hardware.
- The upstream aspirate, dispense and mix calls are synchronous and share the same PGVA and VAEM
  controllers (`src/fluid_control/fluid_control.py:406-471`). The clone exposes no cancellation
  hook, so a running operation is not preempted by the e-stop, and the e-stop pressure command can
  contend with the running operation's controller call. The safe-state action still releases the
  pressure and deselects the valves.
- This package is model-authored and unreviewed. The loader refuses its R2 hardware backend until
  a human sets `reviewed_by`; the gate and the tests here exercise the fake backend only.

Tags: festo, pressure-over-liquid, dispenser, pipettor, liquid-handling
