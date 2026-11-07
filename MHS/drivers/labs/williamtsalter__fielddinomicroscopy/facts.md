# Facts and tags for gh.williamtsalter/fielddinomicroscopy

Every fact cites its source at commit `e67297f1822dbe3b5a385a41828fb5064cdf8b25`: `vendor_doc` (a text file such as
`README.MD`) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| DNX64.__init__ loads the vendor library with ctypes.CDLL(dll_path) and setup_methods assigns every signature in METHOD_SIGNATURES | upstream_code | dnx64.py:41-59 |
| Init() initializes the control object and reports False with a connection message when the DLL raises OSError | upstream_code | dnx64.py:61-76 |
| The FieldDino app hard-codes the vendor library path `C:\Program Files\DNX64\DNX64.dll` | upstream_code | app.py:61 |
| start_microscope creates DNX64(self.driver_path), sets the video device index, calls Init and reads GetVideoDeviceName | upstream_code | app.py:269-276 |
| GetVideoDeviceName returns the name of the video device for an index | upstream_code | dnx64.py:229-239 |
| GetDeviceID returns the unique device ID for an index | upstream_code | dnx64.py:146-156 |
| GetExposureValue returns the exposure value for the device index | upstream_code | dnx64.py:182-192 |
| SetExposureValue forwards the exposure value to the vendor DLL | upstream_code | dnx64.py:356-364 |
| The app's exposure spin box is set to the UI range 1 to 1000 | upstream_code | app.py:132-134 |
| GetAETarget returns the AE target value for the device index | upstream_code | dnx64.py:170-180 |
| SetAETarget documents the acceptable AE target range 16 to 20 | upstream_code | dnx64.py:313-321 |
| GetAutoExposure returns the auto exposure value, and its docstring says 0 = OFF and 1 = ON | upstream_code | dnx64.py:121-131 |
| SetAutoExposure accepts 0 and 1 | upstream_code | dnx64.py:323-331 |
| SetLEDState sets the LED state; it is controllable only while the camera preview is established and is not applicable to AM211, AM2011 and the Dino-Eye series | upstream_code | dnx64.py:388-399 |
| At start-up the app switches the LED on with SetLEDState(device_index, 1) | upstream_code | app.py:288 |
| toggle_led flips the app's boolean LED state and writes it to SetLEDState as an int | upstream_code | app.py:406-412 |
| SetFLCLevel documents that the FLC level accepts 1 to 6 | upstream_code | dnx64.py:378-386 |
| The README targets the Dino-Lite AM7515 series of USB microscopes | vendor_doc | README.MD:9 |
| The README says the app is Windows only for now | vendor_doc | README.MD:39 |
| The README asks for the Dino-Lite SDK licence agreement and says the SDK installs DNX64.dll at `C:\Program Files\DNX64\DNX64.dll` | vendor_doc | README.MD:115-120 |
| The README says the app was tested with USB cable connections only, not the WiFi Dino-Lite models | vendor_doc | README.MD:203 |
| The app reads live frames with cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW) at 2592 x 1944, separately from DNX64 | upstream_code | app.py:31-34 |
| The DNX64 method table lists control and metadata functions but no frame or image acquisition function | upstream_code | dnx64.py:8-39 |
| The README says axial illumination control was removed from the app because it gave very harsh reflections | vendor_doc | README.MD:167 |

## Limits

- `ae_target`: `Limit(min=16, max=20)`, from the `SetAETarget` docstring (`dnx64.py:319`).
- `set_flc_level` input `level`: `Limit(min=1, max=6)`, from the `SetFLCLevel` docstring (`dnx64.py:384`). The app's
  FLC spin box also offers 0 (`app.py:137-139`), but the called method's own docstring states 1 to 6, so the driver
  does not widen it; this is a deliberate narrowing, not a device bound.
- `exposure_value`: `Limit.operator_required`. No line of the clone states a device exposure range. The app's spin
  box offers 1 to 1000 (`app.py:132-134`), but that is a UI choice; `site-limits.example.json` shows an example
  overlay, not a statement about any unit.
- `auto_exposure`, `set_led`: boolean on/off states, so there is no numeric bound to declare.

## Safety

The microscope LED is a light source; MHS-004 section 2.1 lists LED illumination under R1, so `risk = "R1"`. The safe state
is the LED off: the `@estop` method and the safe-state action `x-cap.williamtsalter.switch_off_illumination.v1` both
call `SetLEDState(device_index, 0)`. The DNX64 wrapper has no independent hardware e-stop line in the clone and no
shutdown method; the LED state is the only output this wrapper controls.

The hardware path (`native.py` and the proprietary Windows DNX64.dll) was never run. This package is model-authored
and unreviewed and is checked on the fake backend only. The loader refuses the hardware backend of an unreviewed
model-written package only at R2 and R3; this driver is R1, so it does not claim that protection.

## Not covered

The live image frames. `dnx64.py` has no frame acquisition method (`dnx64.py:8-39`); the app reads 2592 x 1944 frames
through `cv2.VideoCapture` (`app.py:31-34`), which is not part of the upstream control class. No image capability is
bound and no pixel array is returned.

The axial illumination (`SetAXILevel`, `dnx64.py:333-343`), MicroTouch, EDOF lens movement, the video property API,
the WiFi image/resolution calls and the EFLC call (marked "Not Working", `dnx64.py:30`) are not served either: the
app removed axial illumination on purpose (`README.MD:167`), and the remaining controls are optional device features
whose ranges or units the clone does not state.

## Tags

microscope, dino-lite, usb, led, exposure, fielddino
