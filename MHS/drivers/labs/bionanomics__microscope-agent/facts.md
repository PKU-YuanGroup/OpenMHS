# Facts and tags for gh.bionanomics/microscope-agent

Every fact cites the pinned clone at commit `3aef391397deb42f0a1b814091eb2e4b3fe8ed5a`. The selected file is
`acquisition/backends/baumer_genicam.py`; `upstream_code` means code or a comment of that file, and `ref` is
`path/in/clone.py:LINE`. The same facts are written into `driver.py` (`facts = [...]`); `reference.json` is generated
from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The clone's module comment makes BaumerGenICam.capture the primary capture path, called by mcp_server.loop_tools.get_image() | upstream_code | acquisition/backends/baumer_genicam.py:16-21 |
| BaumerGenICam is capture-only and explicitly has no stage control | upstream_code | acquisition/backends/baumer_genicam.py:73-80 |
| The constructor finds GenTL .cti producers and raises RuntimeError when no producer or no camera is found; it then creates and starts one acquirer | upstream_code | acquisition/backends/baumer_genicam.py:82-103 |
| get_settings reads the live GenICam node map: ExposureTime value and min/max, Gain value and min/max, PixelFormat and, when exposed, BalanceWhiteAuto | upstream_code | acquisition/backends/baumer_genicam.py:105-140 |
| The get_settings docstring records a live VCXU-23C ExposureTime range of 28 to 60,000,000 us and a unitless Gain range of 1.0 to 251.1875 | upstream_code | acquisition/backends/baumer_genicam.py:111-117 |
| set_settings forces ExposureAuto and GainAuto to Off and raises ValueError, never clamping, when a requested exposure or gain is outside the camera-reported range | upstream_code | acquisition/backends/baumer_genicam.py:142-181 |
| capture drains queued frames, fetches a live frame with a 5 s timeout, dispatches on PixelFormat and saves an RGB PNG named with a timestamp and the capture count | upstream_code | acquisition/backends/baumer_genicam.py:183-258 |
| capture supports BGR8, RGB8, Mono8 and Bayer formats and raises RuntimeError for any other PixelFormat | upstream_code | acquisition/backends/baumer_genicam.py:218-255 |
| close stops and destroys the acquirer and resets the harvester | upstream_code | acquisition/backends/baumer_genicam.py:260-263 |
| The constructor creates the acquirer with harvester.create(0) and starts it | upstream_code | acquisition/backends/baumer_genicam.py:101-102 |
| capture's drain loop fetches with a 0.01 s timeout and leaves the loop only when a fetch raises | upstream_code | acquisition/backends/baumer_genicam.py:206-211 |
| The README describes an MCP server for a Nikon Ti2-E microscope and a Baumer GenICam camera | vendor_doc | README.md:3-5 |
| CAPTURE_DIR is acquisition.paths.captures_dir(), so the output directory follows the upstream data-root selection rather than this driver | upstream_code | acquisition/backends/baumer_genicam.py:41-44 |
| The camera path depends on the optional harvesters, genicam and opencv-python packages | upstream_code | acquisition/backends/baumer_genicam.py:24-28 |

## Limits

| input | bound | source | ref |
|---|---|---|---|
| `exposure_time_us` write | 28 to 60,000,000 us | upstream_code | acquisition/backends/baumer_genicam.py:112 |
| `gain` write | 1.0 to 251.1875, camera's own unitless scale | upstream_code | acquisition/backends/baumer_genicam.py:112-113 |

These are the live ranges the clone records for the VCXU-23C and the only numeric settings the class exposes. The
upstream `set_settings` re-reads the connected camera's node-map min/max and raises `ValueError` outside them, so a
different body may report a narrower or wider range; the cited values are not a substitute for that runtime check.
`site-limits.example.json` is an illustrative narrowing overlay, not a device specification.

## Scope and safety

The package exposes the one camera object this upstream class serves: its settings reads, the two settings writes
and one `cap.sensing.image.v1` capture. It does not expose stage motion, the MCP server's `get_pos`/`move` tools,
timelapse scheduling or any other repository component. The image is the exact PNG `capture()` wrote; the driver
reads its width and height from the PNG IHDR and publishes the bytes through the endpoint-owned artifact store. A PNG
above the store's per-artifact bound is refused rather than truncated.

The declared risk is R1, the card floor. A camera capture does not move a stage, dispense fluid, heat a sample, emit a
laser or drive a robot, but it is a physical measurement with a privacy hazard (`cap.sensing.image.v1` lists
`privacy`), so the floor is not lowered. The native stop is `close()`, which stops and destroys the acquirer and
resets the harvester; the clone documents no independent hardware emergency stop, so no `estop_physical_ref` is
claimed. Only the constructor creates the acquirer, so after an e-stop the upstream object cannot read settings or
capture again: an operator reset clears the latch, and the backend must be loaded again before the next capture. The
default fake keeps serving after `close` because the gate's conformance suite reads the state after its e-stop (a
faithful fake then fails G8 TSAFE-001 and SAFE-014); the fake's `destroy_on_close` switch models the upstream object,
and `test_after_an_estop_the_upstream_camera_object_cannot_capture_again` uses it.

NOT COVERED: the repository's MCP server drives a Nikon Ti2-E stage as well as this camera (README.md:3-5). The stage
(`acquisition/backends/nis_sdk.py`), its file-flag e-stop and the five MCP tools are outside this package, which
serves the card's one entry symbol. `capture` drains queued frames with a 0.01 s fetch timeout and leaves that loop
only when a fetch raises (`baumer_genicam.py:206-211`): a camera that delivers frames more often than every 0.01 s
keeps it draining. Each capture also leaves its PNG in the upstream capture directory. The package is model-authored and unreviewed (`reviewed_by` is null), was checked on the fake backend only,
and no camera was attached. The fake's 4 x 4 frame, settings and ranges are placeholders, not device facts.

Tags: camera, baumer, genicam, gentl, imaging, microscope
