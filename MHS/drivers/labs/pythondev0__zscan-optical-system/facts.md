# Facts and tags for gh.pythondev0/zscan-optical-system

Every fact cites its source at commit `114c2838f5c3cc7a5a211ed34b38f0745c386f74`. `vendor_doc` is a text file of
the clone that documents the device; `upstream_code` is code or a comment of the clone. The same facts are written
into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The project synchronizes a Thorlabs DCC1545M camera with an Aerotech ANT130LZ nanopositioner | vendor_doc | README.md:10 |
| The hardware table names the Thorlabs DCC1545M (CMOS Monochrome, 1280 x 1024) and pyueye (uEye SDK) as the camera and its driver | vendor_doc | README.md:18 |
| The installation note says pyueye requires the IDS uEye SDK to be installed on the system | vendor_doc | README.md:85 |
| camera.py imports ueye from pyueye | upstream_code | camera.py:5 |
| camera.py defines the camera interface class ThorlabsCamera | upstream_code | camera.py:9 |
| ThorlabsCamera.__init__ takes a device_id argument whose default is 0; the default is a constructor default, not a device bound | upstream_code | camera.py:20-25 |
| The constructor sets width to 1280 and height to 1024 pixels | upstream_code | camera.py:28-29 |
| The constructor calls is_SetColorMode with IS_CM_MONO8 without checking its return status | upstream_code | camera.py:40 |
| The constructor calls is_AllocImageMem for a 1280 x 1024 8-bit buffer and is_SetImageMem without checking either return status | upstream_code | camera.py:43-47 |
| capture_image calls is_FreezeVideo(IS_WAIT) without checking its return status, then copies the active image memory with get_data and reshapes it to (height, width) | upstream_code | camera.py:62-67 |
| release calls is_FreeImageMem and is_ExitCamera without checking either return status | upstream_code | camera.py:69-72 |
| The experiment calls camera.capture_image once for each stage position | upstream_code | zscan.py:44-49 |
| The experiment constructs ThorlabsCamera(device_id=0) and AerotechStage(axis_name='Z') as separate objects | upstream_code | zscan.py:75-76 |
| AerotechStage is a separate stage class in stage.py | upstream_code | stage.py:9 |
| requirements.txt lists pyueye as the camera dependency | upstream_code | requirements.txt:5 |

## Limits

No `Limit` is declared. The served action has one optional string input, the catalogue's camera selector; the camera
class exposes no numeric command, exposure setter or motion parameter. The camera's configured allocation size is a
read, not a writable bound. `site-limits.example.json` is therefore not shipped.

## Safety

The camera is a data-only sensor and is declared R0, the card floor; MHS/spec/04-safety.md lists camera capture as R0.
The driver declares no `@estop` and no `estop_physical_ref`: the only native stop-shaped call is `release`
(`camera.py:69-72`), which frees the image memory and exits the camera and cannot be undone without constructing a new
`ThorlabsCamera`. The endpoint's software e-stop latches and refuses further captures; a native `is_FreezeVideo` call
that has already started is not aborted by this driver. `release` is the endpoint teardown, not a claimed physical
safe state.

## Scope and fidelity

- The package serves the card's camera entry symbol, `camera:ThorlabsCamera` (`camera.py:9`). The card's other entry
  symbol, `stage:AerotechStage` (`stage.py:9`), is NOT COVERED: one package has one `native` class, and the stage is a
  separate device and control path.
- The fake returns an 8 x 8 placeholder frame so receipts stay small. The real camera frame is 1280 x 1024 Mono8
  (`README.md:18`, `camera.py:43-46`); the action reports the actual captured array dimensions, and the reads report
  the constructor's allocation size.
- The card names `PythonObjectDriver`; this package uses a direct `Driver` because the primary output is an image
  artifact that the config-only command table cannot publish. This is recorded in RESULT.json.
- The package is model-authored and unreviewed (`reviewed_by` is null). It was checked on the fake backend only; no
  camera was attached, the upstream package was never imported or run while authoring, and no hardware run is claimed.

Tags: camera, monochrome, ueye, pyueye, zscan, imaging

## Checked native adapter

The production factory imports the pinned camera module for `ueye` and `np.reshape`, then uses the package
adapter instead of the upstream constructor/capture/release methods. It checks the SDK statuses for initialization,
Mono8 selection, memory allocation/selection, freezing and release before reporting success. A failed freeze
returns `MHS.DEVICE.FAULTED` without reading or publishing old image memory. Initialization failures attempt cleanup.
These are the same SDK calls and arguments as camera.py:27-72, with the source's `IS_SUCCESS` comparison at
camera.py:35-37 applied to each status. The adapter emits no upstream constructor/release prints on stdout.
`IS_WAIT` still has no source-backed finite timeout and the software latch cannot abort it; only fake and
SDK-shaped stub cases were executed. The separate Aerotech stage is not instantiated: its constructor enables
motion (stage.py:29-30), and its nominal wait only sleeps (stage.py:50-58), so camera validation says nothing
about stage stopping or settling.
