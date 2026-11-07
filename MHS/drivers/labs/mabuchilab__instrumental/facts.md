# Facts and tags for gh.mabuchilab/instrumental

Every fact cites its source at commit `64272832594964a26ba05ee220a2b56042d04b62`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| UC480_Camera is the uc480-supported camera class; its constructor sets the trigger mode off and opens the camera | upstream_code | src/instrumental/drivers/cameras/uc480.py:573-615 |
| close releases the image memory and exits the camera; a second close without force returns | upstream_code | src/instrumental/drivers/cameras/uc480.py:732-752 |
| grab_image starts a capture sequence and returns get_captured_image's array(s) | upstream_code | src/instrumental/drivers/cameras/uc480.py:856-858 |
| get_captured_image returns one 2-D array or a tuple of arrays and stops live video | upstream_code | src/instrumental/drivers/cameras/uc480.py:833-854 |
| set_trigger accepts 'off', 'software' or 'hardware' and the hardware edges 'rising' or 'falling' | upstream_code | src/instrumental/drivers/cameras/uc480.py:973-995 |
| get_trigger_level returns the hardware trigger status; a value of 0 means the signal is low | upstream_code | src/instrumental/drivers/cameras/uc480.py:1020-1028 |
| set_trigger_delay takes a time Quantity in microseconds and get_trigger_delay returns microseconds | upstream_code | src/instrumental/drivers/cameras/uc480.py:1030-1052 |
| gamma has the range 1.0 to 10.0 and is stored as an integer percentage | upstream_code | src/instrumental/drivers/cameras/uc480.py:1094-1102 |
| exposure is read and written in milliseconds; a float value passed to the setter is milliseconds | upstream_code | src/instrumental/drivers/cameras/uc480.py:925-941 |
| The exposure range is queried from the camera at run time | upstream_code | src/instrumental/drivers/cameras/uc480.py:943-946 |
| The auto-* Facets read and write one uc480 auto parameter | upstream_code | src/instrumental/drivers/cameras/uc480.py:554-564 |
| auto_gain, auto_sensor_gain, auto_exposure, auto_sensor_exposure, auto_whitebalance, auto_sensor_whitebalance, auto_framerate and auto_sensor_framerate are the auto-* Facets | upstream_code | src/instrumental/drivers/cameras/uc480.py:1139-1170 |
| bytes_per_line, width, height and trigger_mode are read-only properties | upstream_code | src/instrumental/drivers/cameras/uc480.py:1181-1196 |
| start_live_video and stop_live_video start and stop continuous acquisition; live video uses the off trigger mode | upstream_code | src/instrumental/drivers/cameras/uc480.py:861-892 |
| The UC480 page instructs installing the Thorlabs uc480 API, adding the uc480 DLL to PATH, and running pip install pywin32 nicelib | vendor_doc | docs/uc480-cameras.rst:14-17 |
| The upstream module is Windows-only | upstream_code | src/instrumental/drivers/cameras/uc480.py:4-5 |

Limits: gamma is the only numeric bound the clone states; it is 1.0 to 10.0 in the facet's limits
(`src/instrumental/drivers/cameras/uc480.py:1094`). The trigger delay states only microsecond resolution, and the
exposure range is queried from the camera at run time (`src/instrumental/drivers/cameras/uc480.py:943-946`), so both
writes use `Limit.operator_required` and are refused `MHS.SAFETY.LIMITS_UNSET` until the site supplies a range
(`site-limits.example.json` shows the overlay).

Safety: the e-stop and the safe-state action `x-cap.mabuchilab.close_camera.v1` both call the native `close()`
(`src/instrumental/drivers/cameras/uc480.py:732-752`), which releases image memory and exits the camera. The clone
documents no independent hardware e-stop, and this is an R1 camera, so no `estop_physical_ref` is claimed. The
`@reset` method reopens the camera with `open()` (`src/instrumental/drivers/cameras/uc480.py:670-696`). Nothing here
ran on hardware; the acceptance gate runs the fake backend.

Coverage: the image array itself is not carried by the driver. The capture action returns the frame width, height and
count; the fake's frame is a small placeholder, while the real size follows the configured AOI (`uc480.py:921-923`).
All scalar settings and the capture trigger path are exposed.

Tags: camera, uc480, thorlabs, ids, imaging, windows
