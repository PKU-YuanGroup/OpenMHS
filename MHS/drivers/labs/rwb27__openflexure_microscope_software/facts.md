# Facts and tags for gh.rwb27/openflexure_microscope_software

Every fact cites its source at commit `991e1b72b94d796a05caf4c896c0b001ea5a2c97`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The Microscope object holds a camera and a stage, and zeroes the stage backlash when it is created | upstream_code | openflexure_microscope/microscope.py:100-105 |
| close() shuts down the camera and the stage | upstream_code | openflexure_microscope/microscope.py:106-109 |
| rgb_image() captures a frame from the camera into a numpy array through picamera | upstream_code | openflexure_microscope/microscope.py:122-131 |
| freeze_camera_settings() turns off automatic exposure and white balance and sleeps around it | upstream_code | openflexure_microscope/microscope.py:132-147 |
| autofocus(dz, settle, metric_fn) moves the stage through the z positions in dz, sleeps settle seconds, captures an image at each and scores it with the sharpness metric, then moves back to the position with the highest score; it returns the positions and the scores | upstream_code | openflexure_microscope/microscope.py:148-170 |
| acquire_image_stack(step_displacement, n_steps, output_dir) captures one JPEG per scan point into output_dir | upstream_code | openflexure_microscope/microscope.py:172-202 |
| settings_dict() returns the camera attributes named in picamera_later_settings and picamera_init_settings: awb_mode, awb_gains, shutter_speed, brightness, contrast and resolution | upstream_code | openflexure_microscope/microscope.py:17-25 |
| settings_dict() is built from picamera_later_settings and picamera_init_settings | upstream_code | openflexure_microscope/microscope.py:204-209 |
| The zoom getter reports the scalar 2/(fov width + fov height) of the camera's zoom field of view: 1 means the whole sensor, more than 1 zooms in | upstream_code | openflexure_microscope/microscope.py:215-225 |
| The zoom setter raises a value below 1.0 to 1.0 and keeps the current image centre when it zooms | upstream_code | openflexure_microscope/microscope.py:227-243 |
| The upstream autofocus example builds dz in steps of 1000, 200, 100 and 50 and labels the position axis 'position (Microsteps)' | upstream_code | openflexure_microscope/microscope.py:343-351 |
| The clone ships a DummyStage stand-in for the stage and load_microscope(dummy_stage=True) uses it; the camera still has to be a real picamera | upstream_code | openflexure_microscope/microscope.py:281-291 |
| The interactive control offers zoom values 2**0 to 2**4 (1 to 16) and autofocus scans of 1280, 320 and 80 microsteps around the current position | upstream_code | openflexure_microscope/keyboard_control.py:223-230 |
| The software runs the OpenFlexure Microscope: a Raspberry Pi camera and an OpenFlexure motor controller on a Raspberry Pi | vendor_doc | README.rst:1-6 |
| The README says the camera module must be set up before use and the motor controller can be left out with --no_stage, which runs the camera without a motorised stage | vendor_doc | README.rst:17-59 |

Limits:

| capability | path | bound | source | ref |
|---|---|---|---|---|
| the `zoom` write | zoom (dimensionless) | min 1.0: the upstream setter raises a value below 1.0 to 1.0 | upstream_code | openflexure_microscope/microscope.py:227-231 |
| x-cap.rwb27.autofocus_scan.v1 | z_positions (microsteps) | operator_required: the clone states no stage travel range | | |

The clone states no maximum zoom and no stage travel range, so the zoom write is bounded only at its documented floor
and the scan positions are `Limit.operator_required`: the site declares them in `site-limits.json`
(`site-limits.example.json` is a template) and every scan is refused with `MHS.SAFETY.LIMITS_UNSET` until then.

Safety: the native stop is `close()`, which shuts the camera and the stage down (microscope.py:106-109); the driver's
`safe_state` is that shutdown and the device must be started again afterwards. The package declares `risk = "R1"`, the
card's floor, and needs no `estop_physical_ref` (an R2+ requirement).

Tags: microscope, openflexure, camera, zoom, autofocus
