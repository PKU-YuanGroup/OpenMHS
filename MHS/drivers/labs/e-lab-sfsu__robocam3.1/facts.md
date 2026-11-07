# Facts and tags for gh.e-lab-sfsu/robocam3.1

Every fact cites the clone at commit `cc402f32f7b781c550a94dc9f78e54df3de7fd53`. The same facts are
written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from
this page.

| fact | source | ref |
|---|---|---|
| get_exposure returns the exposure in microseconds and set_exposure takes microseconds | upstream_code | robocam/camera.py:298-309 |
| get_gain returns the analogue gain multiplied by 100 on the Picamera2 backend | upstream_code | robocam/camera.py:334-342 |
| get_ae_enabled is Picamera2 only and returns False for the other backends | upstream_code | robocam/camera.py:357-361 |
| get_hqi returns the High Quality Image mode of the Player One backend | upstream_code | robocam/camera.py:371-377 |
| The USB bandwidth limit is a percentage in the range 35 to 100 | upstream_code | robocam/camera.py:386-400 |
| get_offset returns the sensor black-level offset | upstream_code | robocam/camera.py:402-408 |
| get_sensor_mode_index returns -1 when the camera has no mode selection | upstream_code | robocam/camera.py:434-442 |
| reset_capture_stats zeroes the get_raw_frame failure counters and get_capture_stats returns lock_timeout and sdk_timeout_or_error | upstream_code | robocam/camera.py:536-546 |
| get_dropped_frames_count is the SDK dropped-frame count and resets on stop | upstream_code | robocam/camera.py:548-556 |
| get_supported_resolutions returns the standard resolution list plus the native resolution | upstream_code | robocam/camera.py:453-478 |
| stop sets running to false and releases the active camera backend | upstream_code | robocam/camera.py:646-663 |
| With no backend argument the constructor auto-detects PlayerOne, then Picamera2, then OpenCV | upstream_code | robocam/camera.py:146-153 |

## Limits

`usb_bandwidth_percent` is bounded by the clone's stated 35 to 100 percent
(`robocam/camera.py:387`; the setter clamps to the same range at `robocam/camera.py:399`).

No text of the clone states a bound for `exposure_us`, `gain`, `offset` or `sensor_mode_index`, so
each is `Limit.operator_required`: the runtime refuses every write with
`MHS.SAFETY.LIMITS_UNSET` until the site overlay supplies the range of the installed camera.
`site-limits.example.json` is an example overlay, not a statement about any unit; its values are
operator placeholders and must be replaced with measured ranges.

## Safety

The native stop is `Camera.stop()` (`robocam/camera.py:646-663`): it sets `running` to false and
releases the active Player One, Picamera2 or OpenCV backend. The driver declares it as `@estop`;
the runtime latches first and then calls it. No text of the clone documents an independent
hardware e-stop, and this package is R1, so `estop_physical_ref` is not set.

This package binds the camera resource only. The repository's three-axis motion system and laser
output are separate classes and are not part of this device manifest.

## Coverage

The scalar camera settings and capture counters are served. The image and raw image arrays
(`Camera.get_frame` and `Camera.get_raw_frame`) are not exposed: the standard's image form is a
reference to an artifact the endpoint stores, and this package has no artifact store. The
application's motion and laser controls are not covered either.

Tags: camera, imaging, well-plate, playerone, picamera2, opencv
