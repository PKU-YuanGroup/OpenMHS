# Facts and tags for gh.fretchen/synqs_devices

Every fact cites its source at commit `ec4bb24639e9d0d4cb707e1c2a6296a47dfe9f02`: `upstream_code`
(`path/in/clone.py:LINE`) or `vendor_doc` (a text file of the clone). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

The package serves one of the independent devices of this repository: the Andor Solis camera reached by the card's
first entry symbol, `AndorSolis.blacs_workers:AndorCamera`. The README of the clone does not describe the Andor
Solis; the other devices (Mako G030-B, SynthHD, YunTemp, CustomArduino) are separate classes and separate packages.

| fact | source | ref |
|---|---|---|
| AndorCamera wraps the upstream AndorCam object and takes its default acquisition attributes as the attribute dictionary | upstream_code | AndorSolis/blacs_workers.py:20-22 |
| get_attribute returns the current value of one named acquisition attribute | upstream_code | AndorSolis/blacs_workers.py:33-34 |
| set_attribute stores a named acquisition attribute in the dictionary | upstream_code | AndorSolis/blacs_workers.py:27-28 |
| configure_acquisition hands the whole attribute dictionary to AndorCam.setup_acquisition | upstream_code | AndorSolis/blacs_workers.py:44-45 |
| snap configures the acquisition, acquires, downloads the images and returns them | upstream_code | AndorSolis/blacs_workers.py:36-42 |
| abort_acquisition calls the camera's abort and records that the abort happened | upstream_code | AndorSolis/blacs_workers.py:105-107 |
| stop_acquisition is a no-op (pass); abort_acquisition is the upstream stop path | upstream_code | AndorSolis/blacs_workers.py:102-107 |
| AndorCam.setup_acquisition accepts the acquisition modes single, accumulate, kinetic_series, fast_kinetics and run_till_abort | upstream_code | AndorSolis/andor_sdk/andor_utils.py:322-328 |
| AndorCam.setup_acquisition sets the exposure time with SetExposureTime and reads the actual timings back with GetAcquisitionTimings | upstream_code | AndorSolis/andor_sdk/andor_utils.py:350-358 |
| AndorCam.setup_trigger accepts the trigger modes internal, external, external_start and external_exposure, and the edges rising and falling | upstream_code | AndorSolis/andor_sdk/andor_utils.py:439-446 |
| enable_cooldown refuses a temperature set point outside self.temperature_range, which initialize_camera fills from GetTemperatureRange() | upstream_code | AndorSolis/andor_sdk/andor_utils.py:93-94 |
| enable_cooldown compares the requested set point with self.temperature_range before switching the cooler on | upstream_code | AndorSolis/andor_sdk/andor_utils.py:141-147 |
| AndorCam.shutdown refuses to shut down while the camera is armed | upstream_code | AndorSolis/andor_sdk/andor_utils.py:656-662 |
| The SDK binding loads atmcd64d.dll or atmcd32d.dll with ctypes and names the Andor SDK3 install directory only on Windows | upstream_code | AndorSolis/andor_sdk/andor_solis.py:21-44 |
| The upstream default acquisition attributes configure a 2560 x 2160 frame, 1 x 1 binning and a 20 ms exposure; they are defaults, not device limits | upstream_code | AndorSolis/andor_sdk/andor_utils.py:13-45 |

Limits:

| parameter | limit | source and ref |
|---|---|---|
| exposure_time (s) | operator_required: the clone passes the value to SetExposureTime and reads the actual timing back with GetAcquisitionTimings, but no text file states a numeric exposure range | AndorSolis/andor_sdk/andor_utils.py:350-358 |
| temperature_setpoint (Cel) | operator_required: enable_cooldown validates it against self.temperature_range, which is queried from the camera with GetTemperatureRange() at initialization | AndorSolis/andor_sdk/andor_utils.py:93-94, 141-147 |
| acquisition_mode | one of single, accumulate, kinetic_series, fast_kinetics, run_till_abort | AndorSolis/andor_sdk/andor_utils.py:322-327 |
| trigger_mode | one of internal, external, external_start, external_exposure | AndorSolis/andor_sdk/andor_utils.py:439-444 |
| trigger_edge | one of rising, falling | AndorSolis/andor_sdk/andor_utils.py:446 |
| snap.width (pixels) | operator_required: SetImage takes the ROI width but the clone states no numeric ROI range | AndorSolis/andor_sdk/andor_utils.py:540-547 |
| snap.height (pixels) | operator_required: SetImage takes the ROI height but the clone states no numeric ROI range | AndorSolis/andor_sdk/andor_utils.py:540-547 |
| snap.exposure_ms (ms) | operator_required: SetExposureTime takes the exposure but the clone states no numeric range | AndorSolis/andor_sdk/andor_utils.py:350-358 |

The `operator_required` bounds are supplied by the site in `site-limits.json`; without that overlay every call that
sets those fields is refused with `MHS.SAFETY.LIMITS_UNSET`. `site-limits.example.json` is an example of such an
overlay, and it only narrows.

Safety: the e-stop calls `abort_acquisition` (blacs_workers.py:105-107), which calls the camera's `AbortAcquisition`
(andor_utils.py:650-654) and records the abort. The camera is not a laser, robot, pump, heater or centrifuge, so the
risk is R1. The hardware backend needs the proprietary Andor SDK3 on Windows; this package is model-authored and
unreviewed and ran only on the fake backend.

Tags: camera, andor, solis, labscript, blacs, imaging
