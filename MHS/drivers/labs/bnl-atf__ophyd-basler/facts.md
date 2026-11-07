# Facts and tags for gh.bnl-atf/ophyd-basler

Upstream: `https://github.com/bnl-atf/ophyd-basler` at commit
`5573459ca330f931ce49a1e53f0e89b834db85cc` (BSD-3-Clause).  The clone is read-only.  Paths below are from the clone
root.

Tags: `camera`, `basler`, `pypylon`, `ophyd`, `imaging`, `bluesky`.

## Native reads

| fact | source | ref |
|---|---|---|
| `BaslerCamera` is an ophyd `Device` whose Components are `image`, `mean`, `exposure_time`, `user_defined_name`, `camera_model`, `serial_number`, `image_shape`, `pixel_level_min`, `pixel_level_max`, `active_format`, `payload_size` and `grab_timeout`. | `upstream_code` | `ophyd_basler/basler_camera.py:21-33` |
| `exposure_time` is a config Signal; the source comment states the unit is milliseconds. | `upstream_code` | `ophyd_basler/basler_camera.py:24` |
| The constructor opens a pylon `InstantCamera`, reads the user-defined name, model, serial number, image shape, pixel levels, active pixel format and payload size, sets trigger mode and pixel format, then closes the camera. | `upstream_code` | `ophyd_basler/basler_camera.py:73-94` |
| `image_shape` stores `(camera_object.Height(), camera_object.Width())`, so the pair is `(height, width)`. | `upstream_code` | `ophyd_basler/basler_camera.py:85` |
| The verbose output labels the grab timeout value in milliseconds. | `upstream_code` | `ophyd_basler/basler_camera.py:104` |
| The module imports `pylon` from `pypylon` at import time. | `upstream_code` | `ophyd_basler/basler_camera.py:14` |
| `available_devices` enumerates the pylon transport layer's devices. | `upstream_code` | `ophyd_basler/__init__.py:27-34` |
| `ExternalFileReference` is an ophyd `Signal` that describes an image stored in an external file. | `upstream_code` | `ophyd_basler/__init__.py:11-24` |

## Native acquisition and stop

| fact | source | ref |
|---|---|---|
| `grab_image` starts a one-frame grab, retrieves it with `grab_timeout`, raises when `GrabSucceeded()` is false, stops grabbing and returns the pylon array. | `upstream_code` | `ophyd_basler/basler_camera.py:146-162` |
| `trigger` calls `grab_image`, writes the frame into the HDF5 dataset and publishes the datum id and the frame mean. | `upstream_code` | `ophyd_basler/basler_camera.py:164-192` |
| `stage` creates the HDF5 resource and dataset, opens the camera, and writes `ExposureTimeAbs` (1e3 times `exposure_time`) only when that value lies within `ExposureTimeAbs.Min..Max`; a value outside is replaced in the `exposure_time` Signal by the minimum or maximum with a warning and is not written in that call. | `upstream_code` | `ophyd_basler/basler_camera.py:194-263` |
| `stage` opens a new HDF5 file with mode `'x'` at `root_dir/YYYY/MM/DD/<uid>.h5` and creates its image dataset with a first frame filled with NaN. | `upstream_code` | `ophyd_basler/basler_camera.py:196-227` |
| The upstream test fixture creates the dated directory tree under `/tmp/basler` with `make_dir_tree`. | `upstream_code` | `ophyd_basler/tests/conftest.py:37-38` |
| `unstage` closes the pylon camera and the HDF5 file. | `upstream_code` | `ophyd_basler/basler_camera.py:265-271` |
| `set_custom_images` configures the pylon emulated camera from an image array or an image directory. | `upstream_code` | `ophyd_basler/basler_camera.py:108-144` |

The native acquisition stop used by the driver is `self.native.camera_object.StopGrabbing()`, the same pylon call the
upstream `grab_image` makes after a frame (`ophyd_basler/basler_camera.py:158`).  The clone documents no independent
hardware emergency stop, so no `estop_physical_ref` is claimed.  What `StopGrabbing` does while another thread waits in
`RetrieveResult`, or on a camera that is not open (the upstream closes it outside a capture, lines 94 and 266), is
pylon behaviour outside the clone; the camera has no actuator, so the stop ends acquisition and proves no physical
state.

Model review note (2026-11-05): each capture calls `stage`, which creates a new HDF5 file under `root_dir` (default
`/tmp/basler`) in a dated `YYYY/MM/DD` directory that must already exist (the upstream test fixture and example create
it with `make_dir_tree`); the driver never calls `trigger`, so every such file keeps only its NaN-filled first frame.
When a requested exposure lies outside the camera's range, `stage` corrects the Signal but leaves the previous camera
exposure for that capture; the corrected value is written on the next capture.

## Units, limits and the operator envelope

- `exposure_time` is in milliseconds (`ophyd_basler/basler_camera.py:24`), but no text file of the clone states a
  numeric range.  The native `stage` reads `ExposureTimeAbs.Min` and `ExposureTimeAbs.Max` from the connected camera
  and clamps to them (`ophyd_basler/basler_camera.py:237-263`).  The driver therefore declares
  `Limit.operator_required`; without `site-limits.json` every exposure write is refused
  `MHS.SAFETY.LIMITS_UNSET`.  `site-limits.example.json` is an illustrative narrowing overlay, not a fact about a
  camera.
- `grab_timeout`, `image_shape`, the pixel levels and `payload_size` are reads only in this package.  Their values are
  queried from the connected pylon camera; the source's exposure and grab-timeout Signal values are constructor
  defaults, not bounds, and are not used as Limits.
- Width and height in the captured frame are the actual shape of the returned array, bounded by the image-artifact
  encoder at 1..8192 pixels per side.  The real camera size is the `image_shape` read; the fake uses an 8 x 8
  placeholder frame.

## Mock path and not covered

- The upstream tests set `PYLON_CAMEMU` and use the pylon emulated camera
  (`ophyd_basler/tests/test_emulated_camera.py:15-43`); that still needs pypylon and the Basler emulation runtime.
  This package's fake is a source-shaped in-memory stand-in for `BaslerCamera`; it imports no pypylon, ophyd or
  upstream code and returns a small placeholder frame.  It is not a recording.
- Not covered: `trigger` (the ophyd plan integration that also writes the HDF5 dataset), `collect_asset_docs`, the
  `image` datum-id signal, `available_devices`, and `set_custom_images` (emulation-only configuration).  The driver's
  capture uses `stage` -> `grab_image` -> `unstage` and publishes the frame as a PNG artifact instead of writing the
  upstream HDF5 dataset.  The standard's optional `width`, `height`, `exposure_ms` and `format` action inputs are not
  served: the upstream class exposes no documented resolution or pixel-format setter for them, and exposure is the
  separate `exposure_time` write.  The capture therefore uses the configured pylon frame and pixel format (Mono8 by the
  upstream constructor default) and applies the configured exposure through `stage`.
- The fake returns an 8 x 8 placeholder frame.  The real frame shape is the `image_shape` read.  The capture publishes a
  PNG through the endpoint-owned artifact store; the store's per-artifact bound applies (the SDK default is 2 MiB, and a
  larger frame needs an explicit store bound).  The driver refuses a frame outside 1..8192 pixels per side and a frame
  that is not a two-dimensional Mono image; a color or non-Mono pixel format is not covered.
- The upstream test uses the pylon emulated camera; that is test configuration, not a device bound.

The package is model-authored and unreviewed (`reviewed_by` is null).  It has run on the fake backend only; no camera
was attached, no hardware backend was started, and no human review or hardware test is claimed.
