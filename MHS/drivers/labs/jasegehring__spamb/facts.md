# Facts and tags for gh.jasegehring/spamb

Every fact cites its source at commit `06a404c1879d0d1f926ba59470f81f9b7e7987cb`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| SPAMB drives a syringe pump, a 10-position selector valve and two solenoid valves over serial | vendor_doc | README.md:3-5 |
| PumpController selects MockPump when mock=True and the Chemyx adapter otherwise | upstream_code | fluidics-control/hardware/pump.py:815-819 |
| set_diameter takes the syringe inner diameter in mm | upstream_code | fluidics-control/hardware/pump.py:298-299 |
| set_rate takes the flow rate in mL/min | upstream_code | fluidics-control/hardware/pump.py:314-315 |
| set_volume takes the target volume in mL and sends a negative volume for withdraw | upstream_code | fluidics-control/hardware/pump.py:331-341 |
| The pump direction is 'infuse' or 'withdraw' | upstream_code | fluidics-control/hardware/pump.py:358-364 |
| get_status reports is_running, rate, target_volume, dispensed_volume, volume_remaining, diameter and direction | upstream_code | fluidics-control/hardware/pump.py:666-676 |
| stop() sends the pump stop command for the configured pump number and clears the running state | upstream_code | fluidics-control/hardware/pump.py:449-457 |
| A command is sent as the command text plus a carriage return | upstream_code | fluidics-control/hardware/chemyx_official/connect.py:124-125 |
| A response is complete at the '>' prompt | upstream_code | fluidics-control/hardware/chemyx_official/connect.py:211-213 |
| In multipump mode a 'set' command is prefixed with the pump number | upstream_code | fluidics-control/hardware/chemyx_official/connect.py:117-118 |
| The pump must be in Multi-Step Mode to accept computer commands | upstream_code | fluidics-control/hardware/pump.py:248-258 |
| The 60 mL BD plastic syringe of the example configuration has a 26.59 mm inner diameter | vendor_doc | fluidics-control/README.md:130 |
| The example configuration declares a 50000 uL syringe capacity and a 45000 uL warning threshold | vendor_doc | fluidics-control/README.md:131-132 |
| The README gives a configured flow rate range of 1 to 50000 uL/min and tells the operator to confirm the real limits for the pump and syringe | vendor_doc | fluidics-control/README.md:322-323 |
| The pump-hardware notes use a 10 mL syringe with diameter 14.5 mm, rate 1.0 mL/min and volume 5.0 mL in an example | vendor_doc | docs/pump-hardware.md:41-43 |

## Limits

Flow rate, target volume and syringe diameter are `Limit.operator_required`. The clone gives example syringe sizes
and a configured example flow-rate range, then tells the operator to confirm the real limits for the pump and
syringe (`fluidics-control/README.md:322-323`); it states no device bound. `site-limits.example.json` shows the
overlay the site supplies, and until it does every write is refused `MHS.SAFETY.LIMITS_UNSET`.

The direction allowed set is `infuse`/`withdraw`, the words the upstream validation accepts
(`fluidics-control/hardware/pump.py:358-364`).

## Scope and safety

This Driver serves the pump only: the card also lists the selector valve (`hardware.valve:ValveController`) and the
solenoid pair (`hardware.solenoids:SolenoidController`), two further devices with their own framed binary serial
protocols. One Driver class cannot serve three devices with three different native classes, so the package
covers the pump and records the valve and solenoids as not covered in RESULT.json.

The pump is R2 because it dispenses liquid. The native `PumpController.stop()` is the `@estop` method and the
safe-state action `x-cap.jasegehring.stop_pump.v1` (SAFE-045). No line of the clone documents an independent
hardware emergency stop, so `estop_physical_ref` is not set.

Tags: spamb, fluidics, syringe pump, chemyx, fusion 4000-x, serial
