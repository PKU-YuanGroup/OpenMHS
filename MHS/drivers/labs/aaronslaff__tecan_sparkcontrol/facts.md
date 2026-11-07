# Facts and tags for gh.aaronslaff/tecan_sparkcontrol

Every fact cites the clone at commit `d2272c6d0e0d4ded08a3af457ed19918a1e66446`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The client sends JSON over HTTP to a base URL and authenticates with a bearer API key or HTTP basic credentials | upstream_code | spark_control_automation.py:113-177 |
| get_instrument_status reads GET /api/v1/status and get_available_apps reads GET /api/v1/apps | upstream_code | spark_control_automation.py:186-194 |
| start_method posts /api/v1/methods/start with a method_id and an optional plate_config | upstream_code | spark_control_automation.py:374-395 |
| get_method_status reads GET /api/v1/methods/{method_id}/status and stop_method posts to /api/v1/methods/{method_id}/stop | upstream_code | spark_control_automation.py:397-405 |
| get_measurement_results reads GET /api/v1/methods/{method_id}/results | upstream_code | spark_control_automation.py:407-410 |
| get_instrument_settings reads GET /api/v1/settings and get_plate_geometry reads GET /api/v1/plate-geometry | upstream_code | spark_control_automation.py:431-444 |
| calibrate_instrument posts /api/v1/calibrate with a calibration type | upstream_code | spark_control_automation.py:446-462 |
| A method strip can be an injection with a volume in microliters and a speed in microliters per second | upstream_code | spark_control_automation.py:307-329 |
| A shaking strip takes a duration in seconds, a frequency in rpm and an amplitude in mm | upstream_code | spark_control_automation.py:350-372 |
| The measurement parameters carry an optional temperature | upstream_code | spark_control_automation.py:69-86 |
| The supported plate types are 96-well, 384-well and 1536-well microplates and a cell chip | upstream_code | spark_control_automation.py:61-67 |
| The scripts target SparkControl V2.4 (Document Part No. 30245640) | upstream_code | spark_control_automation.py:13 |

## Limits

The exposed actions have no numeric input: `calibration_type` and `method_id` are strings. No text file of the clone
states a numeric range for any exposed field, and the free-form JSON documents returned by the client are not
described, so the package declares no Limit and needs no site overlay. The injection volume and speed are shown in
the facts only to explain the R2 classification; they are not exposed as bounded inputs because the clone states no
range for them.

## What is exposed and what is not

The driver exposes the instrument status, available apps, instrument settings, plate geometry, and the status and
results of the method it last started or stopped. The actions calibrate, start and stop a method, and stop the
tracked method as the safe-state action.

`update_instrument_settings` is not exposed: its request is a free-form dictionary and no text file of the clone
describes its schema or numeric bounds. Method creation and the strip builders are not exposed: they take upstream
dataclasses and no text file gives their parameter ranges. `get_measurement_results` and `get_method_status` need a
method id, so the no-input reads return the documents of the tracked method and an empty object before any method is
tracked. The driver never invents a method id.

## Safety

The only stop path in the client is `stop_method(method_id)` (spark_control_automation.py:402-405); there is no
global stop request. The e-stop and the safe-state action `x-cap.aaronslaff.stop_active_method.v1` stop the method
the driver last started or stopped. Without a tracked method they query the instrument status, because the client
cannot address an unknown method; the safe-state output then reports `stopped: false`. No text file of the clone
documents an independent hardware e-stop, so `estop_physical_ref` is not set. The device can inject reagent and set a
measurement temperature, so it is declared R2 even though the card floor is R1.

This package is model-authored and unreviewed. The hardware backend was never run and the fake is an in-memory
object, not a recording of a device; the package is checked on the fake backend only.

Tags: microplate-reader, plate-reader, luminescence, absorbance, fluorescence, tecan, http
