# Facts and tags for gh.zhenwei2972/model-hardware-standard-bambu-labs

Every fact cites the pinned clone at commit `e945c3ed88927760b082c3068b1233c276f17f96`: `vendor_doc` (a text file
of the clone, such as README.md or docs/*.md) or `upstream_code` (`path/in/clone.py:LINE`).  The same table is in
`driver.py` (`facts = [...]`); `reference.json` is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| BambuPrinter builds one BambuMqtt, one BambuFiles and one BambuCamera from the configured host, serial and access code | upstream_code | src/mhs/drivers/bambu/printer.py:66-92 |
| The MQTT transport defines device/<serial>/request and device/<serial>/report topic names | upstream_code | src/mhs/drivers/bambu/mqtt.py:54-55 |
| The MQTT client uses username bblp and the printer access code | upstream_code | src/mhs/drivers/bambu/mqtt.py:78 |
| publish_and_wait publishes and waits up to 6 s for a report with the same sequence_id; a missing acknowledgement is returned as acknowledged false rather than raised | upstream_code | src/mhs/drivers/bambu/mqtt.py:171-202 |
| pause, resume and stop are print commands carrying an empty param | upstream_code | src/mhs/drivers/bambu/commands.py:52-61 |
| start_print refuses unless the printer accepts a new job and reports no fatal or serious alert, then publishes project_file and waits for its report | upstream_code | src/mhs/drivers/bambu/printer.py:176-205 |
| project_file needs a .3mf, .gcode or .gcode.3mf path and a plate index of at least 1 | upstream_code | src/mhs/drivers/bambu/commands.py:182-184 |
| set_temperature rejects a nozzle target outside 0-300 C and a bed target outside 0-120 C | upstream_code | src/mhs/drivers/bambu/commands.py:95-101 |
| Temperatures are sent as M104 and M140 gcode because the firmware has no dedicated JSON temperature command | upstream_code | src/mhs/drivers/bambu/commands.py:91-101 |
| The firmware speed presets are 1 silent, 2 standard, 3 sport and 4 ludicrous | upstream_code | src/mhs/drivers/bambu/commands.py:11 |
| set_light sends ledctrl for the chamber_light or work_light node with led_mode on or off | upstream_code | src/mhs/drivers/bambu/commands.py:107-120 |
| calibrate refuses an active printer, calls commands.calibration with its keyword arguments and publishes the result | upstream_code | src/mhs/drivers/bambu/printer.py:247-252 |
| The printer module declares _MIN_PUSHALL_INTERVAL=300.0 and _STALE_AFTER=90.0 | upstream_code | src/mhs/drivers/bambu/printer.py:55-58 |
| status refreshes stale telemetry with force=True, waits 1 s and returns the merged cached status | upstream_code | src/mhs/drivers/bambu/printer.py:153-160 |
| _refresh skips requests within the minimum interval only when force is false | upstream_code | src/mhs/drivers/bambu/printer.py:126-134 |
| The A1/P1 chamber camera streams 1280x720 JPEG frames at roughly 1 fps over a TLS socket | upstream_code | src/mhs/drivers/bambu/camera.py:1-5 |
| The camera declares a 16-byte header size and an 8 MiB maximum frame size | upstream_code | src/mhs/drivers/bambu/camera.py:29-30 |
| The printer moves fast and reaches 220 C or more: it can burn, pinch and start a fire if left unattended with a fault | upstream_code | src/mhs/printer.py:53-54 |
| The bed rating depends on the model: 80 C for the A1 mini, 100 C for the A1/P1P/P1S and 110 C for the X1 Carbon | upstream_code | src/mhs/specs.py:107-148 |
| Firmware 01.05 and newer on the A1 series silently ignores start, stop and heat commands unless Developer Mode is enabled | vendor_doc | README.md:235-236 |
| The README safety model puts start_print, upload_and_print, stop_print and send_gcode behind a confirmation gate | vendor_doc | README.md:359-361 |
| A stopped Bambu print job cannot be resumed | vendor_doc | docs/MHS_ALIGNMENT.md:81 |

## Limits

| field | limit | source | ref |
|---|---|---|---|
| `nozzle_target_temperature` | 0 to 300 Cel | upstream_code | src/mhs/drivers/bambu/commands.py:95-96 |
| `print_speed_level` | 1 to 4 (unit 1) | upstream_code | src/mhs/drivers/bambu/commands.py:11 |
| `bed_target_temperature` | operator required | operator | no static range fits every supported model |

The bed rating differs per model: 80 C for the A1 mini (`src/mhs/specs.py:113`), 100 C for the A1/P1P/P1S
(`src/mhs/specs.py:130`, `:136`, `:140`) and 110 C for the X1 Carbon (`src/mhs/specs.py:145`).  A single driver-wide
number would either exceed the A1 mini or block the X1 Carbon, so the field is `Limit.operator_required` and the
operator supplies the range of the installed printer in `site-limits.json`.  The write also refuses a value above
`BambuPrinter.spec.max_bed_temp_c`, the rating of the configured model, after the runtime has checked the overlay.

## Safety

This package is blocked on `NO_HARDWARE_FREE_PATH`. `stop_print` publishes `print.stop` and waits up to 6 s for a
sequence-id echo (`printer.py:218-219`, `mqtt.py:171-202`); this does not prove physical stopping. Status is a merged
cache, and a report need not refresh each heater target (`state.py:77-89`). The e-stop concurrently requests
`print.stop` and zero heater targets, then fails `MHS.SAFETY.SAFE_STATE_UNREACHED` with the latch held even when both
requests are acknowledged. The clone documents no independent physical stop. A hot printer remains hot after a
zero-target request.

`safe_stop` is an ordinary action, not a safe-state action. Its output names cached zero heater targets, rather than
claiming heaters are off, and it refuses missing/non-finite/nonzero targets, offline/unknown job states and active
jobs. Cached read-back cannot establish a physical safe state. The action is refused while latched. A safety reset
runs no native hook and starts no job. The stock gate test remains unchanged and is expected to fail for this block.

Optional progress/layer/time fields stay absent when unreported; missing or invalid temperature values are refused instead of
being replaced by 0. Firmware M104/M140 builders truncate fractional Celsius (`commands.py:95-101`); the write result
reports that integer target. The fake enforces the upstream busy-start and busy-calibration preflights. Its immediate
state transitions, placeholder temperatures and 1x1 JPEG remain analytic test data, without physical fidelity.

## Not covered

- File listing, upload and deletion (`BambuFiles`, FTPS 990) are not exposed; the driver starts files that are already
  on the printer.
- The slicer, the MCP server, the scheduler, the print monitor and the Roborock vacuum half of the repository are not
  part of this package.
- Raw gcode is not exposed.  The upstream `send_gcode` goes through an allow-list but the MHS package only serves the
  controls named above.
- The camera's live stream (`stream_frames`) is not exposed; the package captures one frame per
  `cap.sensing.image.v1` call.  The real frames are 1280x720 JPEG; the fake returns a 1x1 placeholder.
- The upstream package installs the top-level Python package `mhs`, the same name as the OpenMHS SDK, so the hardware
  factory needs a renamed or separately bridged copy; see `native.py`.

Tags: 3d printer, fdm, bambu lab, lan mqtt, print job, camera, asyncio

The TCP 6000 camera is the A1/A1 mini/P1 client. The clone says X1/H2 use RTSPS instead
(`src/mhs/drivers/bambu/camera.py:1-5`); that separate camera transport is not implemented by this package.
