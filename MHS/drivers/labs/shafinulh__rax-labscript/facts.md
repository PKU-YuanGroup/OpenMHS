# Facts and tags for gh.shafinulh/rax-labscript

The device is the Nuvu EMCCD camera behind `userlib/user_devices/NuvuCamera`, a ctypes wrapper of the Nuvu vendor SDK.
Every citation is from the clone at commit `c31964385d2e50f8a51b0a130cdb857bbf66779a`; `upstream_code` is code or a
comment/docstring of the clone and `vendor_doc` is documentation text of the clone. The reference file is generated
from `driver.py`, not from this page.

## Native interface (reads, writes, actions)

| Native member | Kind | Source |
|---|---|---|
| `NuvuCamUtils` inherits `nc_camera` | class | `userlib/user_devices/NuvuCamera/Nuvu_sdk/Nuvu_cam_utils.py:23` |
| `NuvuCamUtils.__init__` opens the camera with `openCam(nbBuff=4)` | constructor | `userlib/user_devices/NuvuCamera/Nuvu_sdk/Nuvu_cam_utils.py:52` |
| `cam_start(num_images)` / `cam_stop()` | actions | `userlib/user_devices/NuvuCamera/Nuvu_sdk/Nuvu_cam_utils.py:89-99` |
| `cam_close()` | action | `userlib/user_devices/NuvuCamera/Nuvu_sdk/Nuvu_cam_utils.py:101-102` |
| `get_image()` -> flush read queue then `getImg()` | read | `userlib/user_devices/NuvuCamera/Nuvu_sdk/Nuvu_cam_utils.py:202-205` |
| `getAllCamInfo()` -> dict of width, exposure, temperatures, modes and gains | read | `userlib/user_devices/NuvuCamera/Nuvu_sdk/nc_camera.py:607-671` |
| `camIsAcquring()` -> 1 while acquiring, 0 otherwise | read | `userlib/user_devices/NuvuCamera/Nuvu_sdk/nc_camera.py:335-352` |
| `isrunning` (set by `cam_start`, cleared by `cam_stop`) | state | `userlib/user_devices/NuvuCamera/Nuvu_sdk/Nuvu_cam_utils.py:89-99` |
| `set_exposure_time` / `set_readout_mode` / `set_trigger_mode` / `set_shutter_mode` | writes | `userlib/user_devices/NuvuCamera/Nuvu_sdk/Nuvu_cam_utils.py:151-192` |
| `set_calibrated_em_gain` / `set_target_detector_temp` | writes | `userlib/user_devices/NuvuCamera/Nuvu_sdk/Nuvu_cam_utils.py:180-188` |

## Cited facts

| fact | source | ref |
|---|---|---|
| NuvuCamUtils inherits nc_camera | upstream_code | userlib/user_devices/NuvuCamera/Nuvu_sdk/Nuvu_cam_utils.py:23 |
| The NuvuCamUtils constructor opens the camera with openCam(nbBuff=4) | upstream_code | userlib/user_devices/NuvuCamera/Nuvu_sdk/Nuvu_cam_utils.py:52 |
| NC_api selects libnuvu.so for ELF, nc_driver_x64.dll for 64-bit WindowsPE and nc_driver_Win32.dll for 32-bit WindowsPE using platform.architecture() | upstream_code | userlib/user_devices/NuvuCamera/Nuvu_sdk/NC_api.py:6-14 |
| camStart(nbrImg) starts acquisition of nbrImg images, and nbrImg 0 is continuous acquisition | upstream_code | userlib/user_devices/NuvuCamera/Nuvu_sdk/nc_camera.py:354-367 |
| camAbort stops all image acquisition on the camera | upstream_code | userlib/user_devices/NuvuCamera/Nuvu_sdk/nc_camera.py:369-378 |
| camIsAcquring queries the SDK with ncCamIsAcquiring and returns 1 while acquiring and 0 otherwise, despite a docstring copied from camStart | upstream_code | userlib/user_devices/NuvuCamera/Nuvu_sdk/nc_camera.py:335-352 |
| NuvuCamUtils.cam_stop calls camAbort and clears the wrapper's isrunning flag | upstream_code | userlib/user_devices/NuvuCamera/Nuvu_sdk/Nuvu_cam_utils.py:97-99 |
| get_image uses disconnect_if_error_real, flushes the read queue and returns getImg() | upstream_code | userlib/user_devices/NuvuCamera/Nuvu_sdk/Nuvu_cam_utils.py:201-205 |
| getImg reads an image and copies its uint16 pointer with shape (width, height) | upstream_code | userlib/user_devices/NuvuCamera/Nuvu_sdk/nc_camera.py:393-398 |
| The exposure time is set in milliseconds | upstream_code | userlib/user_devices/NuvuCamera/Nuvu_sdk/nc_camera.py:219-226 |
| The readout mode is documented as 0=nothing, 1=EM, 2=CONV | upstream_code | userlib/user_devices/NuvuCamera/Nuvu_sdk/nc_camera.py:152-159 |
| The trigger mode is documented as -3=CONT_HIGH_LOW, -2=EXT_HIGH_LOW_EXP, -1=EXT_HIGH_LOW, 0=INTERNAL, 1=EXT_LOW_HIGH, 2=EXT_LOW_HIGH_EXP, 3=CONT_LOW_HIGH | upstream_code | userlib/user_devices/NuvuCamera/Nuvu_sdk/nc_camera.py:180-192 |
| The shutter mode is documented as 0=NOT SET, 1=open, 2=closed, 3=auto | upstream_code | userlib/user_devices/NuvuCamera/Nuvu_sdk/nc_camera.py:41 |
| The target detector temperature range is queried from the camera at run time with getTargetDetectorTempRange | upstream_code | userlib/user_devices/NuvuCamera/Nuvu_sdk/nc_camera.py:415-425 |
| The calibrated EM gain range is queried from the camera at run time with getCalibratedEmGainRange | upstream_code | userlib/user_devices/NuvuCamera/Nuvu_sdk/nc_camera.py:559-568 |
| getAllCamInfo queries the camera and returns the widths, exposure, temperatures, shutter mode, calibrated EM gain, raw gain, target detector temperature and trigger mode in one dictionary | upstream_code | userlib/user_devices/NuvuCamera/Nuvu_sdk/nc_camera.py:607-671 |
| The repository's BLACS worker reads the detector temperature, raw and calibrated EM gain, exposure time and readout mode from getAllCamInfo | upstream_code | userlib/user_devices/NuvuCamera/blacs_workers.py:66-73 |
| The BLACS worker's configure_acquisition calls cam_stop before cam_start | upstream_code | userlib/user_devices/NuvuCamera/blacs_workers.py:57-63 |
| errorHandling closes the camera with noRaise=True and raises NuvuException for errors other than 27; error 27 raises without closing | upstream_code | userlib/user_devices/NuvuCamera/Nuvu_sdk/nc_camera.py:95-113 |
| The disconnect_if_error_real decorator closes the camera and re-raises on an exception | upstream_code | userlib/user_devices/NuvuCamera/Nuvu_sdk/Nuvu_cam_utils.py:76-84 |
| The upstream example acquires one image with cam_start(1), get_image(), cam_stop() and cam_close() | upstream_code | userlib/user_devices/NuvuCamera/Nuvu_sdk/Nuvu_cam_utils.py:250-263 |
| The README states that the repository implemented Nuvu Camera python drivers | vendor_doc | README.md:94 |

## Limits

| Limit | Bound | Source |
|---|---|---|
| `readout_mode` | allowed 0, 1, 2 | upstream_code `userlib/user_devices/NuvuCamera/Nuvu_sdk/nc_camera.py:155` |
| `trigger_mode` | allowed -3, -2, -1, 0, 1, 2, 3 | upstream_code `userlib/user_devices/NuvuCamera/Nuvu_sdk/nc_camera.py:181-191` |
| `shutter_mode` | allowed 0, 1, 2, 3 | upstream_code `userlib/user_devices/NuvuCamera/Nuvu_sdk/nc_camera.py:41` |
| `exposure_time`, `cap.sensing.image.v1.exposure_ms` | operator required | no exposure range is stated; the site supplies it |
| `target_detector_temperature` | read only | no temperature unit is stated; the setter is not exposed |
| `em_gain` | operator required | no numeric range is stated; the range is queried from the camera |

## Stop and hardware limitations

Exposure is documented in milliseconds. No text of the Nuvu camera wrapper states a temperature unit; detector and
target temperatures are therefore exposed as read-only raw SDK values without a `Cel` label. The target-temperature
setter and its example envelope are omitted: G8 requires a declared unit for a numeric hardware input, and `1`
would falsely describe temperature as dimensionless. Adding this control needs a source-backed unit and
operator-supplied bounds from the deployment's camera documentation.

The stop action, e-stop and capture cleanup call `cam_stop` and require `camIsAcquring()` to return the documented
integer 0 (`nc_camera.py:335-352`). An active acquisition, missing/invalid state or read error fails the stop;
the e-stop remains latched with `MHS.SAFETY.SAFE_STATE_UNREACHED`. The wrapper's `isrunning` flag is not the
confirmation. The declared safe state covers acquisition only: cooling targets, EM gain and shutter settings remain
unchanged. Repeated stop calls are used by the runtime; the source's `configure_acquisition` calls `cam_stop` before
each start, but live abort timing and vendor behavior were not tested.

The native SDK error handler closes the camera on most failures (`nc_camera.py:95-113`), and `get_image` has an
additional close-on-error decorator (`Nuvu_cam_utils.py:76-84,201-205`). The cleanup abort can therefore encounter an
already-closed handle. Such errors propagate; a new native session is required, and releasing the latch does not
reopen the camera. The fake does not model these vendor failure/handle-lifetime effects or blocking readout.

The platform selector in `NC_api.py:6-14` supplies ELF and WindowsPE libraries and has no Mach-O branch. The card's
`platform: any` does not establish a macOS hardware path. Hardware construction also needs NumPy, matplotlib, the
vendor runtime and the clone's `userlib` import root. No upstream import or hardware call was made in model review.
The artifact path was exercised with the fake's 8 by 8 placeholder frame; real sensor geometry, orientation, timing
and artifact-size requirements remain deployment checks.

## Tags

`camera`, `emccd`, `imaging`, `nuvu`, `labscript`
