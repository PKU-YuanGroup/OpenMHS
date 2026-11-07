# Facts and tags for gh.diamondlightsource/dodal

Every fact cites its source at commit `f96fef4e72a734de6bb523b4229410254e7e8eab` (`upstream_code`, a line range of the
clone). The reference file is generated from `driver.py`, not from this page; the table repeats the declarations there.

| fact | source | ref |
|---|---|---|
| EigerDetector is a classic ophyd Device that implements Stageable | upstream_code | src/dodal/devices/eiger.py:48 |
| cam is an EigerDetectorCam Component with the CAM: suffix and odin is an EigerOdin Component | upstream_code | src/dodal/devices/eiger.py:55-56 |
| stale_params and bit_depth are EpicsSignalRO Components on CAM:StaleParameters_RBV and CAM:BitDepthImage_RBV | upstream_code | src/dodal/devices/eiger.py:58-59 |
| detector_params is a class attribute that defaults to None | upstream_code | src/dodal/devices/eiger.py:62 |
| EigerTimeouts defaults to a 10 s general status timeout and a 60 s arming timeout; the i03 entry uses 20 s and 60 s | upstream_code | src/dodal/devices/eiger.py:20-45 |
| The constructor takes the beamline (default i03), uses that beamline's timeouts or the i03 ones, and sets disarming_status to None | upstream_code | src/dodal/devices/eiger.py:67-87 |
| set_detector_parameters stores the DetectorParams and raises when they are None or lack the detector size constants or the beam centre converter | upstream_code | src/dodal/devices/eiger.py:101-120 |
| async_stage sets disarming_status to None, clears Odin errors, raises when Odin is not initialised and starts the arming chain | upstream_code | src/dodal/devices/eiger.py:122-132 |
| is_armed returns true only when odin.fan.ready is 1 and cam.acquire is 1 | upstream_code | src/dodal/devices/eiger.py:134-135 |
| stage waits for a started arming and, when the detector is not armed, waits up to the arming timeout for async_stage | upstream_code | src/dodal/devices/eiger.py:137-147 |
| unstage sets a new disarming_status, waits for arming, stops Odin after all frames in free-run mode, sets the file writer start timeout and waits 30 s for filewriters_finished; in a finally block it disarms, checks Odin's state and disables ROI mode; it finishes disarming_status and returns the Odin state only when no exception was raised | upstream_code | src/dodal/devices/eiger.py:161-184 |
| stop runs its cleanup only when disarming_status is None: it waits for any arming, stops Odin, sets the file writer start timeout, disarms the detector, disables ROI mode, waits for the combined status and turns off dev/shm streaming, and finishes disarming_status in a finally block | upstream_code | src/dodal/devices/eiger.py:186-211 |
| When disarming_status is set and not done, stop only waits for it up to the arming timeout and runs no cleanup | upstream_code | src/dodal/devices/eiger.py:189-191 |
| When disarming_status is set and done, stop only logs Already disarmed, doing nothing | upstream_code | src/dodal/devices/eiger.py:212-213 |
| change_roi_mode asserts detector_params is not None and, for a disable, sets roi_mode 0 and the image size and chunks of the file writer to the detector's full size | upstream_code | src/dodal/devices/eiger.py:221-249 |
| set_odin_pvs sets the Odin file path to DetectorParams.directory and the file name to full_filename, and returns a status that also waits for the meta listener file name and the acquisition id to report that name | upstream_code | src/dodal/devices/eiger.py:286-306 |
| _wait_fan_ready stores Odin's writers-finished status as filewriters_finished and returns a status that waits for the fan ready flag | upstream_code | src/dodal/devices/eiger.py:404-407 |
| disarm_detector clears cam.acquire and waits for the general status timeout | upstream_code | src/dodal/devices/eiger.py:425-426 |
| The arming chain asserts detector_params and runs Odin stop, dev/shm, threshold, camera, Odin, MX settings, trigger counts, stale parameters, Odin status, set_cam_acquire and the fan-ready wait without blocking | upstream_code | src/dodal/devices/eiger.py:436-469 |
| set_cam_pvs sets the camera trigger mode to EXTERNAL_SERIES | upstream_code | src/dodal/devices/eiger.py:272-276 |
| The meta listener's ready signal reads Writing_RBV and the file writer's id reads AcquisitionID_RBV | upstream_code | src/dodal/devices/eiger_odin.py:27-39 |
| Each of the four Odin file-writer nodes has a writing signal on Writing_RBV | upstream_code | src/dodal/devices/eiger_odin.py:45-65 |
| create_finished_status is done when the meta listener's ready and every node's writing equal 0 | upstream_code | src/dodal/devices/eiger_odin.py:125-129 |
| Odin stop sets the file writer capture to 0 and the meta listener stop_writing to 1 | upstream_code | src/dodal/devices/eiger_odin.py:169-174 |
| DetectorParams validates that directory is an existing directory and stores it with a trailing slash | upstream_code | src/dodal/devices/detector/detector.py:83-88 |
| run_number is a property: override_run_number when it is set, else get_run_number of the directory and prefix | upstream_code | src/dodal/devices/detector/detector.py:62-68 |
| get_run_number lists the directory's .nxs files that start with the prefix and returns 1 or the highest run number found plus 1 | upstream_code | src/dodal/utils.py:128-142 |
| full_filename is the prefix and the run number joined by an underscore | upstream_code | src/dodal/devices/detector/detector.py:135-137 |
| beam_xy_converter builds a DetectorDistanceToBeamXYConverter from det_dist_to_beam_converter_path and the global config client | upstream_code | src/dodal/devices/detector/detector.py:56-60 |
| The converter reads its lookup table through the config client when it is built | upstream_code | src/dodal/devices/detector/det_dist_to_beam_converter.py:17-22 |
| The i03 module builds the classic EigerDetector with the EA-EIGER-01 prefix and builds the FastCS Eiger only with skip=True | upstream_code | src/dodal/beamlines/i03.py:185-200 |
| The i03 config client is built from the URL in the CONFIG_SERVER_URL_ENV_VAR environment variable (or a default endpoint) and set as the global config client | upstream_code | src/dodal/beamlines/i03.py:102-110 |

## What is exposed

The package is a direct `Driver` over the card's entry symbol `dodal.devices.eiger:EigerDetector`, the classic ophyd
Device the i03 beamline module builds (src/dodal/beamlines/i03.py:185-190). Re-authored on 2026-11-05 (model review)
so that the stop carries `DetectorParams` and the frames' files can be published:

- Reads: `armed` (`is_armed`), `bit_depth` and `stale_params` (fresh `get()` of the two EpicsSignalRO Components) and
  `acquisition_id` (Odin's `AcquisitionID_RBV`, the file-name prefix of the last armed collection).
- `x-cap.diamondlightsource.eiger-stage.v1`: the upstream `stage()`, which runs the arming chain with the operator's
  `DetectorParams` unless the detector is armed (`armed_here` says which). The parameters (exposure, omega, triggers,
  directory, file prefix, ROI, energy) are the operator's; the agent sets none of them, so no numeric input or limit
  exists. The camera trigger mode is EXTERNAL_SERIES: frames come only when the beamline's trigger source fires, which
  this package does not control.
- `x-cap.diamondlightsource.eiger-unstage.v1`: the upstream `unstage()` for a collection this connection armed (it
  waits for the Odin writers, disarms, checks Odin and disables ROI mode; `odin_ok` is its result). Without such a
  collection only `disarm_detector()` runs (`staged` false): upstream `unstage` waits on `filewriters_finished`, which
  only the arming chain creates (eiger.py:174, 405), and would raise after disarming.
- `x-cap.diamondlightsource.eiger-disarm.v1`: `disarm_detector()`, the safe-state action, run after every e-stop.
- `x-cap.diamondlightsource.eiger-files.v1`: the files of the acquisition Odin reports, published as one ZIP artifact
  through `mhs.file_artifacts` (MHS/sdk/docs/file-artifacts.md): the regular `.h5` files directly in
  `DetectorParams.directory` whose names start with the acquisition id and `_`, at most 8, each at most 16 MiB and the
  whole bundle within the endpoint store's per-artifact bound (2 MiB by default, 16 MiB at most), refused while an
  arming chain runs or the detector is armed (`is_armed`, eiger.py:134-135; integrator v4, 2026-11-05: between the
  arming and the first frame `Writing_RBV` may still be 0) and while the meta listener or any node reports
  `Writing_RBV` 1 (the condition of `create_finished_status`). The receipt carries
  the bundle's sha256 and media type and each file's name, size, sha256 and `application/x-hdf5`. The files stay where
  Odin wrote them (cleanup `keep`). The directory is resolved once when the driver opens; no link is followed after
  that and a replaced directory refuses publication. A directory the helper refuses (for example one every user may
  write) disables only this action (`MHS.DEVICE.NOT_READY`), never the stop.
- `@estop`: the native `stop()`.

The earlier `armed` write (which called `set_cam_acquire` outside the arming chain) is removed.

## Stop path and what it leaves

`stop()` (eiger.py:186-213) needs `DetectorParams` for `disable_roi_mode`; `native.connect` applies the operator's with
`set_detector_parameters` (eiger.py:101-120) and the driver refuses to open without them. On the e-stop the runtime
latches, calls `stop()` and then the disarm action. Left behind: the camera acquire cleared; when `stop()` ran its
cleanup, also Odin stopped (capture 0, meta stop_writing 1), the file writer start timeout set, ROI mode disabled at
the full detector size and dev/shm streaming off. What the e-stop reports:

- `stop()` first waits for a started arming (up to the arming timeout, 60 s) and for an unfinished unstage (60 s),
  and its cleanup waits on status calls of up to the general status timeout (20 s on i03). A stop that has not
  returned within the endpoint's 1 s default e-stop budget reports `SAFE_STATE_UNREACHED` with the latch held and is
  retried in the background.
- The safe-state disarm (`disarm_detector`) waits for the camera acquire to clear for up to the general status timeout
  (eiger.py:425-426; 20 s on i03). A disarm that has not finished within the same 1 s budget also reports
  `SAFE_STATE_UNREACHED` with the latch held and is retried. The package declares no `estop_latency_ms`: no source
  states how long these waits take on a working detector, and a declared budget of 60 s or more would only delay the
  report.
- After any finished stop or unstage, `stop()` only logs "Already disarmed, doing nothing" until the next arming; the
  disarm action still clears the acquire.
- If the arming wait timed out, the upstream `finally` marks the disarm finished, so later `stop()` calls are no-ops
  while the arming chain, which ends with `set_cam_acquire`, may still run: the driver reports the stop unconfirmed
  (`OutcomeUnknown`, hence `SAFE_STATE_UNREACHED`) while `arming_status` is not done.
- An `unstage` that raised (for example writers that never finish within 30 s) leaves `disarming_status` unfinished:
  every later `stop()` waits for it and fails, so the e-stop stays unreached until an operator reset and a new arming.

No independent hardware e-stop is claimed; R1 does not require one. The detector emits nothing; the X-ray beam and
its shutter belong to other beamline devices.

## Not covered and residual gaps

- Which names Odin gives its files is not stated in the clone. The package publishes `<acquisition id>_*.h5`; if Odin
  names them otherwise, the file action fails (no file) and publishes nothing else. A human reviewer confirms the
  naming from Odin's configuration.
- A full-size Eiger 16M collection exceeds the artifact bounds and is refused (`file_size`); its files stay on the
  beamline's file system. The endpoint host must see `DetectorParams.directory` (the same path Odin writes).
- Each collection arms with the same parameters and so the same acquisition id; a new run number needs a new
  connection (`native.connect` refuses parameters without `run_number`). What Odin does with an existing file of the
  same name is not stated in the clone. Files an earlier collection of the same connection left under that id cannot
  be told apart from the last collection's: the file action publishes every matching file that is there once the
  collection ended.
- `native.connect` needs the deployment's config server (the beam-centre lookup table) and the EPICS IOC; neither was
  contacted. ROI enabling, thresholds, MX settings and the FastCS Eiger (ophyd-async, `skip=True` in i03) are not
  exposed. The other entry symbols of the card (Tetramm, undulator gap, energy lookup) are other device classes.

## Units

The source states no engineering unit for `bit_depth` (the PV name says BitDepthImage) or `stale_params` (a count), so
neither declares a unit. `armed` is boolean; `acquisition_id` is text.

## Tags

`ophyd`, `epics`, `eiger`, `odin`, `area-detector`, `acquisition`, `hdf5`

## Fidelity of the fake backend

The fake follows the pinned `stage`, `async_stage`, `unstage`, `stop`, `disable_roi_mode`/`change_roi_mode`,
`disarm_detector`, `set_cam_acquire` and `is_armed`, the `disarming_status`/`arming_status`/`filewriters_finished`
logic and Odin's `stop` and writers-finished condition (eiger.py, eiger_odin.py). Its arming chain applies only the steps
that change what the package reads (Odin file path, file name and acquisition id, writers started, camera acquire, fan
ready). Odin's frames are not modelled: when its writers finish (at `unstage` or an Odin stop) the fake writes two
placeholder files, `<acquisition id>_000001.h5` and `<acquisition id>_meta.h5`, with placeholder bytes (not HDF5) into
its own temporary directory, removed when the fake is garbage-collected (a gate child process that ends with
`os._exit` can leave a few of these small directories behind); it starts disarmed with one earlier collection on disk.
An unfinished status raises at once instead of after its timeout. Every value and counter is a placeholder. No hardware, EPICS, Odin or config-server
connection was made; evidence is `contract_checked` on the fake only.
