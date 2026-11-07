# Facts and tags for gh.bernardokyotoku/pydcu

Every fact cites its source at commit `ff9557e701e348c4be9a01dbf7a84fd467f8c20d`: `vendor_doc` is a text file of
the clone (`README` here) and `upstream_code` is a code or comment line of the clone.  The same facts are written
into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The README points the user to the IDS uEye driver package, to /usr/lib/libueye_api.so, and to `from uc480 import pycam`, `camera = pycam()`, `camera.snapshot('some_name.bmp')` | vendor_doc | README:1-15 |
| On POSIX the module resolves the vendor library name ueye_api and loads it with ctypes at import time; when find_library returns None the module prints an error and LoadLibrary(None) fails | upstream_code | ueye.py:23-29 |
| The module is Python 2 source: line 27 is a print statement and line 40 compares with unicode, so the Python 3 ast parser cannot read the file | upstream_code | ueye.py:27-40 |
| `class pycam` creates a `camera(camera_id)` and an `image` wrapper and then allocates and activates image memory | upstream_code | ueye.py:118-123 |
| `pycam.snapshot` captures a frame with IS.WAIT, stops live video with IS.WAIT and calls `SaveImage(filename)` | upstream_code | ueye.py:128-132 |
| `class camera` wraps the SDK handle and initializes it with `is_InitCamera` | upstream_code | ueye.py:140-145 |
| The camera constructor sets width 1024 and height 768 and allocates a NumPy image buffer; these are constructor defaults, not a sensor limit | upstream_code | ueye.py:146-149 |
| `SetImageSize` reads the current AOI width or height when the x argument has the 0x8000 bit set and returns the queried value, otherwise it sets the size | upstream_code | ueye.py:344-362 |
| `SetImagePos` reads the current AOI x or y position when x has the 0x8000 bit set and returns the queried value, otherwise it sets the position | upstream_code | ueye.py:453-457 |
| `CaptureVideo` digitizes a frame into the image memory allocated by `AllocImageMem` and activated by `SetImageMem`; IS.WAIT waits until acquisition begins | upstream_code | ueye.py:459-483 |
| `StopLiveVideo` stops live video; with IS.WAIT it waits until the image is completely acquired | upstream_code | ueye.py:493-507 |
| `SaveImage` writes the active image memory to the named file through `is_SaveImage` | upstream_code | ueye.py:437-441 |
| `ExitCamera` closes the camera handle through `is_ExitCamera` | upstream_code | ueye.py:509-511 |
| The IS module defines GET_IMAGE_SIZE_X 0x8000 and GET_IMAGE_SIZE_Y 0x8001 for the size queries and GET_IMAGE_POS_X 0x8001 and GET_IMAGE_POS_Y 0x8002 for the position queries | upstream_code | IS.py:341-350 |
| The IS module defines WAIT 0x0001 and DONT_WAIT 0x0000 | upstream_code | IS.py:237-238 |
| `setup.py` installs only the top-level modules `ueye` and `IS` and declares no licence | upstream_code | setup.py:1-6 |

Limits: width, height, image_x, image_y and the capture inputs width, height and exposure_ms are all
`Limit.operator_required`.  The clone says the size range is queried from the installed camera with
`IS.GET_IMAGE_SIZE_X_MIN/MAX/INC` and `IS.GET_IMAGE_SIZE_Y_MIN/MAX/INC` (ueye.py:344-362), that `SetImagePos`
forwards two integers to the SDK (ueye.py:453-457), and only that `Exposure` "Sets the exposure time (in ms)"
(ueye.py:542-544); no text file of the clone states a numeric pixel, position, sensor or exposure range.  The
constructor defaults 1024 x 768 (ueye.py:146-149) are not a device bound.  `site-limits.example.json` is an example
operator overlay that fills these bounds; it is not a statement about any camera.

Action and fake: `cap.sensing.image.v1` follows the clone's snapshot path (ueye.py:128-132) and writes one BMP file
to the system temporary directory; the receipt carries its path and the current AOI size, not the pixel array.  The
fake writes a 1 x 1 BMP placeholder and reports its current AOI size; every value in `fake.py` is test data marked
`# placeholder`, not a fact or a limit.

Safety: the capture class `cap.sensing.image.v1` is R0, but the bound `cap.device.configure.v1` class is R1, so
the device's effective risk is R1 (the catalogue class floor); the driver declares R1.  The native stop is
`ExitCamera` (ueye.py:509-511); the e-stop calls it and the safe state is the closed camera.  The clone documents no
independent hardware e-stop, and at R1 SAFE-045 does not ask for one.  This package is model-authored and
unreviewed; nothing here ran on a camera.

The clone cannot be parsed by the gate's Python 3 AST (ueye.py:27), so G7 cannot resolve `ueye:camera` and the
package is blocked `PLATFORM_UNSUPPORTED`; see `RESULT.json`.

Tags: camera, ids, ueye, ctypes, imaging, aoi
