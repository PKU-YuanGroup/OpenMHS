"""OpenMHS driver for gh.williamtsalter/fielddinomicroscopy: a Dino-Lite USB microscope.

A direct Driver (decorated methods) over the upstream ``dnx64:DNX64`` class, a ctypes wrapper around the proprietary
Windows ``DNX64.dll`` (dnx64.py:41-59).  The wrapper exposes the microscope's control surface, not its video stream;
the FieldDino app reads live frames with ``cv2.VideoCapture`` separately (app.py:31-34, 278).  This package therefore
serves the wrapper's scalar controls:

* reads: device name, device ID, exposure value, AE target and auto-exposure state;
* writes: exposure value, AE target and auto-exposure;
* actions: ``x-cap.williamtsalter.set_led.v1`` (LED on/off), ``x-cap.williamtsalter.set_flc_level.v1`` (FLC level)
  and ``x-cap.williamtsalter.switch_off_illumination.v1``, the safe-state action;
* the native stop is ``SetLEDState(device_index, 0)``: it turns the illumination off.

NOT COVERED: the live image frames.  The DNX64 method table has no frame or image acquisition function
(dnx64.py:8-39); the app captures 2592 x 1944 frames with OpenCV (app.py:31-34) and the standard has no frame-array
transport for this package, so no image capability is bound.

Limits.  The AE target is 16 to 20 as the upstream docstring states (dnx64.py:319); the FLC level is 1 to 6
(dnx64.py:384).  No line of the clone states an exposure range: the app's spin box offers 1 to 1000
(app.py:132-134), but that is a UI choice, so exposure is ``Limit.operator_required`` and
``site-limits.example.json`` shows the overlay.  Exposure, AE target and FLC level are dimensionless values in this
API, and the LED and auto-exposure controls are on/off states: the clone states no unit for any of them.

Safety.  The LED is a light source, which MHS-004 lists under R1, so the driver is R1.  Its safe state is the LED off;
the ``@estop`` method calls ``SetLEDState(0)`` and ``switch_off_illumination`` makes the same call as the safe-state
action.  The hardware path (``native.py`` and the vendor DLL) was never run.  This package is model-authored and
unreviewed, and it is checked on the fake backend only.  The loader refuses the hardware backend of an unreviewed
model-written package only at R2 and R3, so at R1 it does not refuse this one; no human review and no hardware run
are claimed.

Every Fact cites a line of the clone at the pinned commit e67297f1822dbe3b5a385a41828fb5064cdf8b25.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write


class DinoLite(Driver):
    device_id = "dino-lite"
    device_kind = "instrument.microscope"
    mode = "hardware"
    risk = "R1"
    native = "dnx64:DNX64"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeDNX64"}
    vendor = "Dino-Lite"
    model = "AM7515 series USB digital microscope"
    display_name = "Dino-Lite AM7515 USB microscope (dnx64.DNX64)"
    tags = ["microscope", "dino-lite", "usb", "led", "exposure", "fielddino"]
    facts = [
        Fact("DNX64.__init__ loads the vendor library with ctypes.CDLL(dll_path) and setup_methods assigns every "
             "signature in METHOD_SIGNATURES", source="upstream_code", ref="dnx64.py:41-59"),
        Fact("Init() initializes the control object and reports False with a connection message when the DLL raises "
             "OSError", source="upstream_code", ref="dnx64.py:61-76"),
        Fact("The FieldDino app hard-codes the vendor library path C:\\Program Files\\DNX64\\DNX64.dll",
             source="upstream_code", ref="app.py:61"),
        Fact("start_microscope creates DNX64(self.driver_path), sets the video device index, calls Init and reads "
             "GetVideoDeviceName", source="upstream_code", ref="app.py:269-276"),
        Fact("GetVideoDeviceName returns the name of the video device for an index", source="upstream_code",
             ref="dnx64.py:229-239"),
        Fact("GetDeviceID returns the unique device ID for an index", source="upstream_code",
             ref="dnx64.py:146-156"),
        Fact("GetExposureValue returns the exposure value for the device index", source="upstream_code",
             ref="dnx64.py:182-192"),
        Fact("SetExposureValue forwards the exposure value to the vendor DLL", source="upstream_code",
             ref="dnx64.py:356-364"),
        Fact("The app's exposure spin box is set to the UI range 1 to 1000", source="upstream_code",
             ref="app.py:132-134"),
        Fact("GetAETarget returns the AE target value for the device index", source="upstream_code",
             ref="dnx64.py:170-180"),
        Fact("SetAETarget documents the acceptable AE target range 16 to 20", source="upstream_code",
             ref="dnx64.py:313-321"),
        Fact("GetAutoExposure returns the auto exposure value, and its docstring says 0 = OFF and 1 = ON",
             source="upstream_code", ref="dnx64.py:121-131"),
        Fact("SetAutoExposure accepts 0 and 1", source="upstream_code", ref="dnx64.py:323-331"),
        Fact("SetLEDState sets the LED state; it is controllable only while the camera preview is established and "
             "is not applicable to AM211, AM2011 and the Dino-Eye series", source="upstream_code",
             ref="dnx64.py:388-399"),
        Fact("At start-up the app switches the LED on with SetLEDState(device_index, 1)", source="upstream_code",
             ref="app.py:288"),
        Fact("toggle_led flips the app's boolean LED state and writes it to SetLEDState as an int",
             source="upstream_code", ref="app.py:406-412"),
        Fact("SetFLCLevel documents that the FLC level accepts 1 to 6", source="upstream_code",
             ref="dnx64.py:378-386"),
        Fact("The README targets the Dino-Lite AM7515 series of USB microscopes", source="vendor_doc",
             ref="README.MD:9"),
        Fact("The README says the app is Windows only for now", source="vendor_doc", ref="README.MD:39"),
        Fact("The README asks for the Dino-Lite SDK licence agreement and says the SDK installs DNX64.dll at "
             "C:\\Program Files\\DNX64\\DNX64.dll", source="vendor_doc", ref="README.MD:115-120"),
        Fact("The README says the app was tested with USB cable connections only, not the WiFi Dino-Lite models",
             source="vendor_doc", ref="README.MD:203"),
        Fact("The app reads live frames with cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW) at 2592 x 1944, "
             "separately from DNX64", source="upstream_code", ref="app.py:31-34"),
        Fact("The DNX64 method table lists control and metadata functions but no frame or image acquisition function",
             source="upstream_code", ref="dnx64.py:8-39"),
        Fact("The README says axial illumination control was removed from the app because it gave very harsh "
             "reflections", source="vendor_doc", ref="README.MD:167"),
    ]
    safe_state = ("LED off (SetLEDState(device_index, 0)); the microscope stays dark until an operator turns the LED "
                  "on again")

    # -- helpers --------------------------------------------------------------------------------------------------
    def _device_index(self) -> int:
        """The video device index the operator gave the backend (the app defaults to 0, app.py:63)."""
        return int(self.options.get("device_index", 0))

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("device_name", type="string", description="Name of the video device, from GetVideoDeviceName")
    def device_name(self):
        return str(self.native.GetVideoDeviceName(self._device_index()))

    @read("device_id", type="string", description="Unique device ID, from GetDeviceID")
    def device_identifier(self):
        return str(self.native.GetDeviceID(self._device_index()))

    @read("exposure_value", type="integer", unit="1",
          description="Exposure value, from GetExposureValue; the API states no unit")
    def exposure_value(self):
        return int(self.native.GetExposureValue(self._device_index()))

    @read("ae_target", type="integer", unit="1",
          description="Auto-exposure target, from GetAETarget; the upstream docstring gives 16 to 20")
    def ae_target(self):
        return int(self.native.GetAETarget(self._device_index()))

    @read("auto_exposure", type="boolean", description="True while automatic exposure is on (GetAutoExposure)")
    def auto_exposure(self):
        return bool(self.native.GetAutoExposure(self._device_index()))

    # -- writes ---------------------------------------------------------------------------------------------------
    @write("exposure_value", type="integer", unit="1", description="Exposure value written with SetExposureValue",
           limit=Limit.operator_required(
               "no line of the clone states a device exposure range; the app's spin box offers 1 to 1000 "
               "(app.py:132-134) but that is a UI choice, so the site supplies the range its microscope and sample "
               "tolerate"))
    def set_exposure_value(self, value):
        self.native.SetExposureValue(self._device_index(), int(value))
        return int(self.native.GetExposureValue(self._device_index()))

    @write("ae_target", type="integer", unit="1",
           description="Auto-exposure target written with SetAETarget; the upstream docstring gives 16 to 20",
           limit=Limit(min=16, max=20, source="upstream_code", ref="dnx64.py:319",
                       reason="the SetAETarget docstring states the acceptable range 16 to 20"))
    def set_ae_target(self, value):
        self.native.SetAETarget(self._device_index(), int(value))
        return int(self.native.GetAETarget(self._device_index()))

    @write("auto_exposure", type="boolean",
           description="Turn automatic exposure on or off with SetAutoExposure (0 = off, 1 = on)")
    def set_auto_exposure(self, value):
        self.native.SetAutoExposure(self._device_index(), int(bool(value)))
        return bool(self.native.GetAutoExposure(self._device_index()))

    # -- actions --------------------------------------------------------------------------------------------------
    @action(name="x-cap.williamtsalter.set_led.v1", risk="R1",
            description="Turn the microscope LED on or off (SetLEDState)",
            input={"enabled": Field("boolean", description="True turns the LED on, false turns it off")},
            output={"enabled": Field("boolean", description="The LED state the driver applied")})
    def set_led(self, enabled):
        self.native.SetLEDState(self._device_index(), 1 if enabled else 0)
        return {"enabled": bool(enabled)}

    @action(name="x-cap.williamtsalter.set_flc_level.v1", risk="R1",
            description="Set the FLC level (SetFLCLevel)",
            input={"level": Field("integer", unit="1", description="FLC level, 1 to 6 (dnx64.py:384)",
                                  limit=Limit(min=1, max=6, source="upstream_code", ref="dnx64.py:384",
                                              reason="the SetFLCLevel docstring accepts 1 to 6"))},
            output={"level": Field("integer", unit="1", description="The FLC level the driver applied")})
    def set_flc_level(self, level):
        self.native.SetFLCLevel(self._device_index(), int(level))
        return {"level": int(level)}

    @action(name="x-cap.williamtsalter.switch_off_illumination.v1", safe_state=True, risk="R1",
            description="Turn the LED off (SetLEDState 0), the safe state; it takes no input",
            output={"led_on": Field("boolean", description="False once the LED was switched off")})
    def switch_off_illumination(self):
        self.native.SetLEDState(self._device_index(), 0)
        return {"led_on": False}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop(native="SetLEDState")
    def stop(self):
        """The native stop: the runtime latches first, then SetLEDState turns the illumination off."""
        self.native.SetLEDState(self._device_index(), 0)
