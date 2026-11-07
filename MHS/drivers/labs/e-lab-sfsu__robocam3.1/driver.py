"""OpenMHS driver for gh.e-lab-sfsu/robocam3.1: the camera resource of RoboCam 3.1.

A direct Driver over ``robocam.camera:Camera``, the uniform camera abstraction of the upstream
application (README.md:356-361).  The class selects one of three backends at construction: the
Player One SDK, Picamera2, or OpenCV (robocam/camera.py:137-153); the driver reads and writes the
scalar controls the class presents for all of them and leaves the image arrays to the application.

* reads: exposure in microseconds, gain, auto-exposure state, HQI state, USB bandwidth percentage,
  sensor black-level offset, sensor mode index, resolution, supported resolutions, the raw-burst
  capture failure counters and the SDK dropped-frame count;
* writes: exposure, gain, auto-exposure, HQI, USB bandwidth, offset and sensor mode index.  The
  clone states a range only for the USB bandwidth (35 to 100 percent, robocam/camera.py:387,395);
  for the other numeric settings no text states a bound, so they are ``Limit.operator_required``
  and every write is refused ``MHS.SAFETY.LIMITS_UNSET`` until the site overlay supplies one;
* ``reset_capture_stats`` is an extension action because the catalogue has no class for a
  capture-counter reset; it returns the counters after zeroing them;
* the native ``Camera.stop()`` (robocam/camera.py:646-663) is the e-stop: it sets ``running`` to
  false and releases the active backend.

This package binds the camera resource only.  The upstream repository also drives a three-axis
motion system and a laser output through other classes; those actuators are not part of this
device manifest.  The package is model-authored and unreviewed, so its evidence is
``contract_checked`` and never a hardware run or an MHS-Device level.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write


class RoboCamCamera(Driver):
    device_id = "robocam"
    device_kind = "sensor.camera"
    mode = "hardware"
    risk = "R1"
    native = "robocam.camera:Camera"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeCamera"}
    vendor, model = "e-lab-sfsu", "RoboCam 3.1 camera"
    display_name = "RoboCam 3.1 camera (robocam.camera:Camera)"
    tags = ["camera", "imaging", "well-plate", "playerone", "picamera2", "opencv"]
    facts = [
        Fact("get_exposure returns the exposure in microseconds and set_exposure takes microseconds",
             source="upstream_code", ref="robocam/camera.py:298-309"),
        Fact("get_gain returns the analogue gain multiplied by 100 on the Picamera2 backend",
             source="upstream_code", ref="robocam/camera.py:334-342"),
        Fact("get_ae_enabled is Picamera2 only and returns False for the other backends",
             source="upstream_code", ref="robocam/camera.py:357-361"),
        Fact("get_hqi returns the High Quality Image mode of the Player One backend",
             source="upstream_code", ref="robocam/camera.py:371-377"),
        Fact("The USB bandwidth limit is a percentage in the range 35 to 100",
             source="upstream_code", ref="robocam/camera.py:386-400"),
        Fact("get_offset returns the sensor black-level offset", source="upstream_code",
             ref="robocam/camera.py:402-408"),
        Fact("get_sensor_mode_index returns -1 when the camera has no mode selection",
             source="upstream_code", ref="robocam/camera.py:434-442"),
        Fact("reset_capture_stats zeroes the get_raw_frame failure counters and get_capture_stats "
             "returns lock_timeout and sdk_timeout_or_error", source="upstream_code",
             ref="robocam/camera.py:536-546"),
        Fact("get_dropped_frames_count is the SDK dropped-frame count and resets on stop",
             source="upstream_code", ref="robocam/camera.py:548-556"),
        Fact("get_supported_resolutions returns the standard resolution list plus the native resolution",
             source="upstream_code", ref="robocam/camera.py:453-478"),
        Fact("stop sets running to false and releases the active camera backend", source="upstream_code",
             ref="robocam/camera.py:646-663"),
        Fact("With no backend argument the constructor auto-detects PlayerOne, then Picamera2, then OpenCV",
             source="upstream_code", ref="robocam/camera.py:146-153"),
    ]
    safe_state = "camera capture stopped and the active camera backend released"

    # -- reads ------------------------------------------------------------------------------------------------
    @read("running", type="boolean", description="True while the camera is running")
    def running(self):
        return bool(self.native.running)

    @read("exposure_us", type="integer", unit="us", description="Exposure time in microseconds")
    def exposure_us(self):
        return self.native.get_exposure()

    @read("gain", type="integer", unit="1",
          description="Gain in the native scale (Picamera2 reports analogue gain times 100)")
    def gain(self):
        return self.native.get_gain()

    @read("ae_enabled", type="boolean",
          description="True while auto-exposure/auto-gain is enabled (Picamera2 only)")
    def ae_enabled(self):
        return self.native.get_ae_enabled()

    @read("hqi", type="boolean",
          description="True while the Player One High Quality Image mode is enabled")
    def hqi(self):
        return self.native.get_hqi()

    @read("usb_bandwidth_percent", type="integer", unit="%",
          description="Player One USB bandwidth limit in percent")
    def usb_bandwidth_percent(self):
        return self.native.get_usb_bandwidth()

    @read("offset", type="integer", unit="1", description="Sensor black-level offset")
    def offset(self):
        return self.native.get_offset()

    @read("sensor_mode_index", type="integer", unit="1",
          description="Active sensor mode index; -1 when the camera has no mode selection")
    def sensor_mode_index(self):
        return self.native.get_sensor_mode_index()

    @read("resolution", type="array", items="integer", length=2,
          description="Current resolution as [width, height] in pixels")
    def resolution(self):
        return [int(self.native.resolution[0]), int(self.native.resolution[1])]

    @read("supported_resolutions", type="array", items="string",
          description="Supported resolutions, each written as WIDTHxHEIGHT")
    def supported_resolutions(self):
        return [f"{int(width)}x{int(height)}" for width, height in self.native.get_supported_resolutions()]

    @read("capture_lock_timeouts", type="integer", unit="1",
          description="Count of get_raw_frame lock timeouts since the last reset")
    def capture_lock_timeouts(self):
        return int(self.native.get_capture_stats()["lock_timeout"])

    @read("capture_sdk_errors", type="integer", unit="1",
          description="Count of get_raw_frame SDK timeouts or errors since the last reset")
    def capture_sdk_errors(self):
        return int(self.native.get_capture_stats()["sdk_timeout_or_error"])

    @read("dropped_frames", type="integer", unit="1",
          description="SDK-side dropped-frame count; it resets on stop")
    def dropped_frames(self):
        return self.native.get_dropped_frames_count()

    # -- writes -----------------------------------------------------------------------------------------------
    @write("exposure_us", type="integer", unit="us", description="Exposure time in microseconds",
           limit=Limit.operator_required(
               "no text file of the clone states the exposure range of the installed camera; the site "
               "supplies it in the operator overlay"))
    def set_exposure_us(self, value):
        self.native.set_exposure(value)

    @write("gain", type="integer", unit="1",
           description="Gain in the native scale (Picamera2 interprets gain/100 as analogue gain)",
           limit=Limit.operator_required(
               "no text file of the clone states the gain range of the installed camera; the site "
               "supplies it in the operator overlay"))
    def set_gain(self, value):
        self.native.set_gain(value)

    @write("ae_enabled", type="boolean",
           description="Enable or disable auto-exposure/auto-gain (Picamera2 only)")
    def set_ae_enabled(self, value):
        self.native.set_ae_enabled(value)

    @write("hqi", type="boolean",
           description="Enable or disable the Player One High Quality Image mode")
    def set_hqi(self, value):
        self.native.set_hqi(value)

    @write("usb_bandwidth_percent", type="integer", unit="%",
           description="Player One USB bandwidth limit in percent",
           limit=Limit(min=35, max=100, unit="%", source="upstream_code", ref="robocam/camera.py:387"))
    def set_usb_bandwidth_percent(self, value):
        self.native.set_usb_bandwidth(value)

    @write("offset", type="integer", unit="1", description="Sensor black-level offset",
           limit=Limit.operator_required(
               "no text file of the clone states the offset range of the installed camera; the site "
               "supplies it in the operator overlay"))
    def set_offset(self, value):
        self.native.set_offset(value)

    @write("sensor_mode_index", type="integer", unit="1",
           description="Active sensor mode index; -1 when the camera has no mode selection",
           limit=Limit.operator_required(
               "the clone lists no sensor mode count for the installed camera; the site supplies the "
               "valid index range in the operator overlay"))
    def set_sensor_mode_index(self, value):
        self.native.set_sensor_mode(value)

    # -- actions ----------------------------------------------------------------------------------------------
    @action(name="x-cap.e-lab-sfsu.reset_capture_stats.v1",
            description="Reset the capture failure counters and return the zeroed counts",
            output={"lock_timeout": Field("integer", description="Lock timeouts since the reset"),
                    "sdk_timeout_or_error": Field("integer", description="SDK timeouts or errors since the reset")})
    def reset_capture_stats(self):
        self.native.reset_capture_stats()
        return self.native.get_capture_stats()

    # -- safety -----------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: set running false and release the active camera backend."""
        self.native.stop()
