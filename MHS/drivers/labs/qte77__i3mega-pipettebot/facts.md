# Facts and tags for gh.qte77/i3mega-pipettebot

Every fact cites its source at commit `99dc2e0a8c15067f3d994e6484507fa2be2301d7`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| home() sends G28, move_to() sends G1 X... Y... Z... F... with three decimals, and wait_for_moves() sends M400 | upstream_code | src/pipettebot/gantry.py:194-211 |
| send() writes the command with a trailing newline and waits for a reply line equal to 'ok' or starting with 'ok ' | upstream_code | src/pipettebot/gantry.py:120-134 |
| send() and query() default max_secs to 30.0 | upstream_code | src/pipettebot/gantry.py:160-172 |
| send_and_wait_for_ok raises TimeoutError when no ok arrives before max_secs | upstream_code | src/pipettebot/gantry.py:135 |
| GantryConfig defaults the feedrate to 3000 mm/min | upstream_code | src/pipettebot/gantry.py:144 |
| M114 reports the current XYZE position as Marlin sees it | vendor_doc | docs/marlin-commands.md:49 |
| The documented M114 reply is X:0.000 Y:0.000 Z:0.000 E:0.000 followed by ok | vendor_doc | docs/research/gantry-firmware-alternatives.md:143 |
| M112 is the emergency stop: Marlin halts and refuses commands until power-cycle | vendor_doc | docs/marlin-commands.md:58 |
| G28 homes all axes (X, then Y, then Z) | vendor_doc | docs/marlin-commands.md:75 |
| After head removal G28 succeeds for X and Y but can hang or crash on Z; the clone says to use G28 X Y until a Z-endstop strategy exists | vendor_doc | docs/marlin-commands.md:107 |
| G28 X Y is the XY homing command of the safe_home path | upstream_code | src/pipettebot/devices.py:314 |
| Soft limits are not enforced in software and any hardcoded coordinate is untrusted | vendor_doc | docs/hardware.md:206-207 |
| The print head, hotend, fan, sensor PCB and heater wiring have been physically removed from the carriage | vendor_doc | docs/hardware.md:188-190 |
| The i3 Mega is no longer a 3D printer; it is a 3-axis motion platform | vendor_doc | docs/hardware.md:191-192 |
| The dPette is a separate USB device whose 6-byte serial protocol is delegated to the external dpette-usb-driver package | vendor_doc | docs/hardware.md:21-25 |
| PipetteBot.aspirate_at moves, waits for the moves (M400), then calls the pipette's aspirate | upstream_code | src/pipettebot/bot.py:38-42 |
| The gantry serial link is 250000 8N1 on stock Anycubic firmware | vendor_doc | docs/hardware.md:36 |

Limits: x, y and z are `Limit.operator_required`. The clone states that soft limits are not enforced and that any
hardcoded coordinate is untrusted (docs/hardware.md:206-207), so the site supplies the safe envelope of its installed
tool and labware; `site-limits.example.json` shows the overlay and is an example, not a statement about any unit.

Safety: the e-stop and the safe-state action `x-cap.qte77.emergency_stop.v1` both send the firmware emergency stop
`M112` (docs/marlin-commands.md:58). No line of the clone documents an independent hardware e-stop, so
`estop_physical_ref` is not set; the safe-state action satisfies SAFE-045 for this R2 hardware driver. Both send the
command through the upstream `send()` path with `max_secs=1.0` instead of its 30.0 s default
(src/pipettebot/gantry.py:160) so a silent port does not hold the e-stop.

Not covered: fluid aspirate/dispense. The dPette is a second USB device on a 6-byte protocol delegated to the external
`dpette-usb-driver` package (docs/hardware.md:21-25); that package is not part of the clone and states no volume or flow
bound here, so this package does not claim `cap.fluid.aspirate.v1` or `cap.fluid.dispense.v1`.

Tags: gantry, cartesian, marlin, 3d-printer, pipetting-robot
