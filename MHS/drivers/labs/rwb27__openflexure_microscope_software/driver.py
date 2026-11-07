"""OpenMHS driver for gh.rwb27/openflexure_microscope_software: an OpenFlexure Microscope on a Raspberry Pi.

A direct Driver over the upstream device class ``openflexure_microscope.microscope:Microscope``.  The class owns a
picamera ``camera`` and an OpenFlexure ``stage`` (openflexure_microscope/microscope.py:100-105) and offers one method
per microscope action, so every call here is a plain ``def`` on ``self.native``:

* reads: the camera's zoom (the class's scalar view of the sensor field of view, microscope.py:215-225), its
  resolution, shutter speed and white-balance mode (from ``settings_dict()``, microscope.py:204-209);
* one write: the zoom, bounded below by 1.0, the floor the upstream setter applies (microscope.py:227-231);
* one action, ``x-cap.rwb27.autofocus_scan.v1``: the class's autofocus scan over a list of stage z positions,
  which captures an image at every position, evaluates the sharpness and ends at the best one
  (microscope.py:148-170);
* the native stop is ``close()``, which shuts the camera and the stage down (microscope.py:106-109).

What the package does **not** carry is the image data itself: ``rgb_image()`` returns a numpy array
(microscope.py:122-131) and ``acquire_image_stack()`` writes JPEG files next to the caller (microscope.py:172-202),
and the standard has no channel for an image artifact, so no image capability is bound (see RESULT.json notes).

Units.  The stage API takes z positions in the stage's own unit; the upstream's own autofocus example labels the
position axis "Microsteps" (microscope.py:351), so the scan input is a dimensionless count of microsteps.  The
catalogue class ``cap.imaging.focus.v1`` measures search ranges and target positions in um, and the clone states no
conversion, so that class cannot bind this stage; the scan is an extension with an inline schema.

Limits.  The clone states no zoom maximum (the interactive control offers 1 to 16, keyboard_control.py:230) and no
stage travel range, so the scan's z positions are ``Limit.operator_required`` and the site declares them in
``site-limits.json``; until then every scan is refused with ``MHS.SAFETY.LIMITS_UNSET``.

This package is model-authored and unreviewed: the acceptance gate runs the fake backend only and nothing ran on a
microscope.  The pinned commit is 991e1b72b94d796a05caf4c896c0b001ea5a2c97.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

MICROSCOPE = "openflexure_microscope/microscope.py"
KEYBOARD = "openflexure_microscope/keyboard_control.py"
README = "README.rst"

STAGE_REASON = ("the clone states no stage travel range: the travel is the stage's (OpenFlexureStage, not in this "
                "repository) and the site's, so the site declares the z positions it will allow")

#: The sharpness metric the upstream autofocus uses when the caller names none (microscope.py:148).
DEFAULT_METRIC = "sharpness_sum_lap2"


class OpenFlexureMicroscope(Driver):
    device_id = "openflexure-microscope"
    device_kind = "instrument.microscope"
    mode = "hardware"
    risk = "R1"
    native = "openflexure_microscope.microscope:Microscope"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeMicroscope"}
    vendor, model = "OpenFlexure", "OpenFlexure Microscope (Raspberry Pi camera + OpenFlexure stage)"
    display_name = "OpenFlexure Microscope (openflexure_microscope.microscope:Microscope)"
    tags = ["microscope", "openflexure", "camera", "zoom", "autofocus"]
    facts = [
        Fact("The Microscope object holds a camera and a stage, and zeroes the stage backlash when it is created",
             source="upstream_code", ref=f"{MICROSCOPE}:100-105"),
        Fact("close() shuts down the camera and the stage", source="upstream_code", ref=f"{MICROSCOPE}:106-109"),
        Fact("rgb_image() captures a frame from the camera into a numpy array through picamera",
             source="upstream_code", ref=f"{MICROSCOPE}:122-131"),
        Fact("freeze_camera_settings() turns off automatic exposure and white balance and sleeps around it",
             source="upstream_code", ref=f"{MICROSCOPE}:132-147"),
        Fact("autofocus(dz, settle, metric_fn) moves the stage through the z positions in dz, sleeps settle seconds, "
             "captures an image at each and scores it with the sharpness metric, then moves back to the position "
             "with the highest score; it returns the positions and the scores",
             source="upstream_code", ref=f"{MICROSCOPE}:148-170"),
        Fact("acquire_image_stack(step_displacement, n_steps, output_dir) captures one JPEG per scan point into "
             "output_dir", source="upstream_code", ref=f"{MICROSCOPE}:172-202"),
        Fact("settings_dict() returns the camera attributes named in picamera_later_settings and "
             "picamera_init_settings: awb_mode, awb_gains, shutter_speed, brightness, contrast and resolution",
             source="upstream_code", ref=f"{MICROSCOPE}:17-25"),
        Fact("settings_dict() is built from picamera_later_settings and picamera_init_settings",
             source="upstream_code", ref=f"{MICROSCOPE}:204-209"),
        Fact("The zoom getter reports the scalar 2/(fov width + fov height) of the camera's zoom field of view: 1 "
             "means the whole sensor, more than 1 zooms in", source="upstream_code", ref=f"{MICROSCOPE}:215-225"),
        Fact("The zoom setter raises a value below 1.0 to 1.0 and keeps the current image centre when it zooms",
             source="upstream_code", ref=f"{MICROSCOPE}:227-243"),
        Fact("The upstream autofocus example builds dz in steps of 1000, 200, 100 and 50 and labels the position "
             "axis 'position (Microsteps)'", source="upstream_code", ref=f"{MICROSCOPE}:343-351"),
        Fact("The clone ships a DummyStage stand-in for the stage and load_microscope(dummy_stage=True) uses it; the "
             "camera still has to be a real picamera",
             source="upstream_code", ref=f"{MICROSCOPE}:281-291"),
        Fact("The interactive control offers zoom values 2**0 to 2**4 (1 to 16) and autofocus scans of 1280, 320 and "
             "80 microsteps around the current position",
             source="upstream_code", ref=f"{KEYBOARD}:223-230"),
        Fact("The software runs the OpenFlexure Microscope: a Raspberry Pi camera and an OpenFlexure motor controller "
             "on a Raspberry Pi", source="vendor_doc", ref=f"{README}:1-6"),
        Fact("The README says the camera module must be set up before use and the motor controller can be left out "
             "with --no_stage, which runs the camera without a motorised stage",
             source="vendor_doc", ref=f"{README}:17-59"),
    ]
    safe_state = ("camera and stage closed (the native close, microscope.py:106-109); the microscope software must be "
                  "started again before it can move or expose")

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("zoom", unit="1",
          description="The camera's zoom as the class reports it: 1 is the whole sensor field of view, more zooms in")
    def get_zoom(self):
        return float(self.native.zoom)

    @read("resolution", type="array", items="integer", length=2,
          description="Camera resolution as [width, height] in pixels (settings_dict)")
    def get_resolution(self):
        width, height = self._settings()["resolution"]
        return [int(width), int(height)]

    @read("shutter_speed", type="integer", unit="us",
          description="Camera shutter speed in microseconds as the camera reports it (0 while it is automatic)")
    def get_shutter_speed(self):
        return int(self._settings()["shutter_speed"])

    @read("awb_mode", type="string", description="Auto white balance mode the camera reports (settings_dict)")
    def get_awb_mode(self):
        return str(self._settings()["awb_mode"])

    # -- the write ------------------------------------------------------------------------------------------------
    @write("zoom", unit="1",
           description="Camera zoom, 1 is the whole sensor field of view; the setter keeps the image centre",
           limit=Limit(min=1.0, source="upstream_code", ref=f"{MICROSCOPE}:227-231",
                       reason="the upstream setter raises any value below 1.0 to 1.0, so 1.0 is the floor"))
    def set_zoom(self, value):
        self.native.zoom = value
        return float(self.native.zoom)               # the value the camera reports after the change

    # -- the autofocus scan ---------------------------------------------------------------------------------------
    @action(name="x-cap.rwb27.autofocus_scan.v1", long_running=True, max_duration_ms=600000,
            description="Run the microscope's autofocus over stage z positions and report the sharpness at each",
            input={"z_positions": Field(
                type="array", items="number", unit="1",
                description="Stage z positions to visit, in the stage's own unit (microsteps, microscope.py:351)",
                limit=Limit.operator_required(STAGE_REASON))},
            output={
                "positions": Field("array", items="number", unit="1",
                                   description="The stage z position of every measurement, in microsteps"),
                "sharpnesses": Field("array", items="number", unit="1",
                                     description="The sharpness the metric scored at every position"),
                "best_position": Field("number", unit="1",
                                       description="The z position with the highest sharpness, in microsteps"),
            })
    def autofocus_scan(self, z_positions):
        if not z_positions:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                               "an autofocus scan needs at least one z position")
        positions, sharpnesses = self.native.autofocus(list(z_positions))
        positions = [float(value) for value in positions]
        sharpnesses = [float(value) for value in sharpnesses]
        if len(positions) != len(sharpnesses) or not positions:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               f"autofocus returned {len(positions)} positions and {len(sharpnesses)} scores")
        best = max(range(len(sharpnesses)), key=lambda index: sharpnesses[index])
        return {"positions": positions, "sharpnesses": sharpnesses, "best_position": positions[best]}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop(native="close")
    def stop(self):
        """The native stop: the runtime latches first, then the camera and the stage are shut down."""
        self.native.close()

    def teardown(self):
        self.native.close()

    # -- helpers --------------------------------------------------------------------------------------------------
    def _settings(self):
        settings = self.native.settings_dict()
        if not isinstance(settings, dict):
            raise DriverFailed("MHS.DEVICE.FAULTED", "settings_dict did not return a dictionary")
        return settings
