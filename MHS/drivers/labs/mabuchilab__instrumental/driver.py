"""OpenMHS driver for gh.mabuchilab/instrumental: a Thorlabs DCx (UC480) camera.

A direct Driver (decorated methods) over the upstream device class
``instrumental.drivers.cameras.uc480:UC480_Camera``.  The upstream class is a uc480 API wrapper with a Windows
event loop for image completion (uc480.py:4-5, 13, 32): it opens the camera in the constructor (uc480.py:578-615),
starts a finite sequence with ``start_capture`` and returns the array(s) from ``get_captured_image`` (uc480.py:
807-858), or runs continuous acquisition with ``start_live_video``/``stop_live_video`` (uc480.py:861-892).

* reads: the trigger mode and level, the trigger delay, the auto-* switches, exposure, gamma, the line stride, the
  image width and height, and the camera open flag;
* writes: the auto exposure switch, the trigger delay, exposure and gamma.  The clone queries the exposure range
  from the camera at run time (uc480.py:943-946) and states no trigger-delay range, so those two numeric writes are
  ``Limit.operator_required`` and are refused ``MHS.SAFETY.LIMITS_UNSET`` until the site supplies a range
  (``site-limits.example.json`` shows the overlay).  Gamma has the range 1.0 to 10.0 in the upstream facet
  (uc480.py:1094-1097);
* actions: the full trigger configuration (mode and edge, uc480.py:973-1001), one finite capture reported by its
  frame shape, live video start/stop, and the safe-state close.  The capture action returns the frame dimensions,
  not the pixel array; the standard has no array carrier and the array is not all this camera gives (its scalar
  settings are the other functions);
* safety: the native stop is ``close()`` (uc480.py:732-752), which releases the image memory and exits the camera;
  the safe-state action ``x-cap.mabuchilab.close_camera.v1`` calls it, and ``@reset`` reopens the camera.

Every Fact cites a line of the clone at the pinned commit (64272832594964a26ba05ee220a2b56042d04b62).  This package
is model-authored and unreviewed: it is checked on the fake backend only and its evidence is ``contract_checked``,
never an MHS-Device level.  Nothing here ran on hardware: the upstream module loads the Windows uc480 DLL at import
and needs the vendor runtime (docs/uc480-cameras.rst:14-27).
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, reset, write


def _milliseconds(value):
    """A native exposure value in milliseconds: a pint Quantity on hardware, a number on the fake."""
    return float(value.m_as("ms")) if hasattr(value, "m_as") else float(value)


def _microseconds(value):
    """A native trigger-delay value in microseconds: a pint Quantity on hardware, a number on the fake."""
    return float(value.m_as("us")) if hasattr(value, "m_as") else float(value)


def _frame_shape(image):
    """``(width, height, frames)`` of what ``grab_image`` returned, without carrying the pixel array."""
    frames = image if isinstance(image, tuple) else (image,)
    if not frames:
        raise DriverFailed("MHS.DEVICE.FAULTED", "grab_image returned no frame")
    first = frames[0]
    shape = getattr(first, "shape", None)
    if shape is not None and len(shape) >= 2:
        height, width = int(shape[0]), int(shape[1])
    else:
        try:
            height = len(first)
            width = len(first[0]) if height else 0
        except (TypeError, IndexError) as exc:
            raise DriverFailed("MHS.DEVICE.FAULTED", "grab_image returned an unusable frame") from exc
    if width < 1 or height < 1:
        raise DriverFailed("MHS.DEVICE.FAULTED", "grab_image returned an empty frame")
    return int(width), int(height), len(frames)


class UC480Camera(Driver):
    device_id = "uc480-camera"
    device_kind = "sensor.camera"
    mode = "hardware"
    risk = "R1"
    native = "instrumental.drivers.cameras.uc480:UC480_Camera"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeUC480Camera"}
    vendor, model = "Thorlabs", "DCx (UC480) camera"
    display_name = "Thorlabs DCx (UC480) camera (Instrumental UC480_Camera)"
    tags = ["camera", "uc480", "thorlabs", "ids", "imaging", "windows"]
    facts = [
        Fact("UC480_Camera is the uc480-supported camera class; its constructor sets the trigger mode off and "
             "opens the camera", source="upstream_code",
             ref="src/instrumental/drivers/cameras/uc480.py:573-615"),
        Fact("close releases the image memory and exits the camera; a second close without force returns",
             source="upstream_code", ref="src/instrumental/drivers/cameras/uc480.py:732-752"),
        Fact("grab_image starts a capture sequence and returns get_captured_image's array(s)", source="upstream_code",
             ref="src/instrumental/drivers/cameras/uc480.py:856-858"),
        Fact("get_captured_image returns one 2-D array or a tuple of arrays and stops live video",
             source="upstream_code", ref="src/instrumental/drivers/cameras/uc480.py:833-854"),
        Fact("set_trigger accepts 'off', 'software' or 'hardware' and the hardware edges 'rising' or 'falling'",
             source="upstream_code", ref="src/instrumental/drivers/cameras/uc480.py:973-995"),
        Fact("get_trigger_level returns the hardware trigger status; a value of 0 means the signal is low",
             source="upstream_code", ref="src/instrumental/drivers/cameras/uc480.py:1020-1028"),
        Fact("set_trigger_delay takes a time Quantity in microseconds and get_trigger_delay returns microseconds",
             source="upstream_code", ref="src/instrumental/drivers/cameras/uc480.py:1030-1052"),
        Fact("gamma has the range 1.0 to 10.0 and is stored as an integer percentage", source="upstream_code",
             ref="src/instrumental/drivers/cameras/uc480.py:1094-1102"),
        Fact("exposure is read and written in milliseconds; a float value passed to the setter is milliseconds",
             source="upstream_code", ref="src/instrumental/drivers/cameras/uc480.py:925-941"),
        Fact("The exposure range is queried from the camera at run time", source="upstream_code",
             ref="src/instrumental/drivers/cameras/uc480.py:943-946"),
        Fact("The auto-* Facets read and write one uc480 auto parameter", source="upstream_code",
             ref="src/instrumental/drivers/cameras/uc480.py:554-564"),
        Fact("auto_gain, auto_sensor_gain, auto_exposure, auto_sensor_exposure, auto_whitebalance, "
             "auto_sensor_whitebalance, auto_framerate and auto_sensor_framerate are the auto-* Facets",
             source="upstream_code", ref="src/instrumental/drivers/cameras/uc480.py:1139-1170"),
        Fact("bytes_per_line, width, height and trigger_mode are read-only properties", source="upstream_code",
             ref="src/instrumental/drivers/cameras/uc480.py:1181-1196"),
        Fact("start_live_video and stop_live_video start and stop continuous acquisition; live video uses the "
             "off trigger mode", source="upstream_code",
             ref="src/instrumental/drivers/cameras/uc480.py:861-892"),
        Fact("The UC480 page instructs installing the Thorlabs uc480 API, adding the uc480 DLL to PATH, and "
             "running pip install pywin32 nicelib", source="vendor_doc", ref="docs/uc480-cameras.rst:14-17"),
        Fact("The upstream module is Windows-only", source="upstream_code",
             ref="src/instrumental/drivers/cameras/uc480.py:4-5"),
    ]
    safe_state = "camera closed and its image memory released; no further frames are acquired"

    # -- reads ------------------------------------------------------------------------------------------------
    @read("trigger_mode", type="string",
          description="Trigger mode reported by the camera: off, software or hardware")
    def trigger_mode(self):
        return str(self.native.trigger_mode)

    @read("trigger_level", type="integer", unit="1",
          description="Hardware trigger level; 0 means the signal is low")
    def trigger_level(self):
        return int(self.native.get_trigger_level())

    @read("trigger_delay", unit="us", description="Delay from a hardware trigger to the exposure")
    def trigger_delay(self):
        return _microseconds(self.native.get_trigger_delay())

    @read("exposure_time", unit="ms", description="Requested exposure time in milliseconds")
    def exposure_time(self):
        return _milliseconds(self.native.exposure)

    @read("gamma", unit="1", description="Gamma correction factor the camera applies")
    def gamma(self):
        return float(self.native.gamma)

    @read("auto_exposure", type="boolean", description="True while the auto exposure shutter is enabled")
    def auto_exposure(self):
        return bool(self.native.auto_exposure)

    @read("auto_gain", type="boolean", description="True while automatic gain is enabled")
    def auto_gain(self):
        return bool(self.native.auto_gain)

    @read("auto_framerate", type="boolean", description="True while automatic framerate is enabled")
    def auto_framerate(self):
        return bool(self.native.auto_framerate)

    @read("auto_whitebalance", type="boolean", description="True while automatic white balance is enabled")
    def auto_whitebalance(self):
        return bool(self.native.auto_whitebalance)

    @read("auto_sensor_exposure", type="boolean", description="True while sensor-based automatic exposure is enabled")
    def auto_sensor_exposure(self):
        return bool(self.native.auto_sensor_exposure)

    @read("auto_sensor_framerate", type="boolean", description="True while sensor-based automatic framerate is enabled")
    def auto_sensor_framerate(self):
        return bool(self.native.auto_sensor_framerate)

    @read("auto_sensor_gain", type="boolean", description="True while sensor-based automatic gain is enabled")
    def auto_sensor_gain(self):
        return bool(self.native.auto_sensor_gain)

    @read("auto_sensor_whitebalance", type="boolean",
          description="True while sensor-based automatic white balance is enabled")
    def auto_sensor_whitebalance(self):
        return bool(self.native.auto_sensor_whitebalance)

    @read("bytes_per_line", type="integer", unit="1", description="Bytes used by each line of the image")
    def bytes_per_line(self):
        return int(self.native.bytes_per_line)

    @read("width", type="integer", unit="1", description="Width of the current image area in pixels")
    def width(self):
        return int(self.native.width)

    @read("height", type="integer", unit="1", description="Height of the current image area in pixels")
    def height(self):
        return int(self.native.height)

    @read("is_open", type="boolean", description="True while the camera connection is open")
    def is_open(self):
        return bool(self.native.is_open)

    # -- writes -------------------------------------------------------------------------------------------------
    @write("auto_exposure", type="boolean", description="Enable or disable the auto exposure shutter")
    def write_auto_exposure(self, value):
        self.native.set_auto_exposure(bool(value))
        return bool(self.native.auto_exposure)

    @write("trigger_delay", unit="us", description="Delay from a hardware trigger to the exposure",
           limit=Limit.operator_required(
               "the clone states only that the trigger delay has microsecond resolution and states no numeric range; "
               "the camera may be configured differently, so the site supplies the bound"))
    def write_trigger_delay(self, value):
        self.native.set_trigger_delay(f"{float(value)} us")
        return _microseconds(self.native.get_trigger_delay())

    @write("exposure_time", unit="ms", description="Requested exposure time in milliseconds",
           limit=Limit.operator_required(
               "the clone queries the exposure range from the camera at run time and states no fixed range; the site "
               "supplies the bound of its unit"))
    def write_exposure_time(self, value):
        self.native.exposure = float(value)
        return _milliseconds(self.native.exposure)

    @write("gamma", unit="1", description="Gamma correction factor the camera applies",
           limit=Limit(min=1.0, max=10.0, source="upstream_code",
                       ref="src/instrumental/drivers/cameras/uc480.py:1094"))
    def write_gamma(self, value):
        self.native.gamma = float(value)
        return float(self.native.gamma)

    # -- actions -------------------------------------------------------------------------------------------------
    @action(name="x-cap.mabuchilab.configure_trigger.v1",
            description="Set the camera trigger mode and, for hardware triggering, the edge",
            input={"mode": Field("string", enum=["off", "software", "hardware"],
                                 description="Trigger source: off, software or hardware"),
                   "edge": Field("string", enum=["rising", "falling"],
                                 description="Edge used when the mode is hardware: rising or falling")},
            output={"trigger_mode": Field("string", description="Trigger mode the camera reports after the change"),
                    "edge": Field("string", description="Trigger edge the action applied")})
    def configure_trigger(self, mode, edge):
        self.native.set_trigger(mode, edge)
        return {"trigger_mode": str(self.native.trigger_mode), "edge": str(edge)}

    @action(name="x-cap.mabuchilab.capture.v1",
            description="Capture one finite sequence and report the frame dimensions; the pixel array is not carried",
            output={"width": Field("integer", unit="1", description="Width of the captured frame in pixels"),
                    "height": Field("integer", unit="1", description="Height of the captured frame in pixels"),
                    "frames": Field("integer", unit="1", description="Number of frames in the captured sequence")})
    def capture(self):
        width, height, frames = _frame_shape(self.native.grab_image())
        return {"width": width, "height": height, "frames": frames}

    @action(name="x-cap.mabuchilab.start_live_video.v1",
            description="Start continuous acquisition",
            output={"trigger_mode": Field("string", description="Trigger mode the camera reports after the change")})
    def start_live_video(self):
        self.native.start_live_video()
        return {"trigger_mode": str(self.native.trigger_mode)}

    @action(name="x-cap.mabuchilab.stop_live_video.v1",
            description="Stop continuous acquisition",
            output={"trigger_mode": Field("string", description="Trigger mode the camera reports after the change")})
    def stop_live_video(self):
        self.native.stop_live_video()
        return {"trigger_mode": str(self.native.trigger_mode)}

    @action(name="x-cap.mabuchilab.close_camera.v1", safe_state=True,
            description="Close the camera and release its image memory (the native safe state); it takes no input",
            output={"is_open": Field("boolean", description="False once the camera connection is closed")})
    def close_camera(self):
        self.native.close()
        return {"is_open": bool(self.native.is_open)}

    # -- safety --------------------------------------------------------------------------------------------------
    @estop(native="close")
    def stop(self):
        """The native stop: the runtime latches first, then closes the camera (uc480.py:732-752)."""
        self.native.close()

    @reset
    def reopen(self):
        """Native recovery after an operator reset: open the camera again (uc480.py:670-696)."""
        self.native.open()

    def teardown(self):
        self.native.close()
