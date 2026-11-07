# Facts and tags for gh.slietar/nikon

Every fact cites its source at commit `d53b4e261ae487f237a65048cf1931a40e39794b`: `vendor_doc` (a text file of the
clone, here `readme.md`) or `upstream_code` (`nikon/microscope.py:LINE`).  The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The package controls the Nikon Ti2-E microscope over the reverse-engineered USB protocol through PyUSB, without the Nikon SDK | vendor_doc | readme.md:3 |
| MicroscopeDevice is constructed from a usb.core.Device and owns the asyncio lock its commands share | upstream_code | nikon/microscope.py:94-102 |
| StatusEvent reports the condenser (0-6), filter (0-5), objective (0-5), optical path (0-3), diaphragm opening (0-1), light, shutter, x and y [0.1 um], z [0.01 um] and the zoom code | upstream_code | nikon/microscope.py:28-61 |
| set_condenser accepts an index from 0 to 6 | upstream_code | nikon/microscope.py:366-374 |
| set_dia accepts a diaphragm opening from 0.0 to 1.0 | upstream_code | nikon/microscope.py:380-387 |
| set_filter accepts an index from 0 to 5 | upstream_code | nikon/microscope.py:392-400 |
| set_objective accepts an index from 0 to 5 | upstream_code | nikon/microscope.py:415-422 |
| set_optical_path accepts an index from 0 to 3 | upstream_code | nikon/microscope.py:427-435 |
| set_x and set_y send a signed 32-bit position in 0.1 um and set_z sends one in 0.01 um | upstream_code | nikon/microscope.py:327-355 |
| The x and y stage bounds and the z stage bound are queried from the device at run time; the clone states no fixed travel | upstream_code | nikon/microscope.py:241-275 |
| get_status returns the next StatusEvent and get_stable_status returns the last one once no newer event arrives within idle_duration (0.5 s by default) | upstream_code | nikon/microscope.py:299-313 |
| get_firmware_cpu_version returns five ASCII bytes as the CPU version | upstream_code | nikon/microscope.py:163-168 |
| set_light and set_shutter take a boolean that enables or disables the light and the shutter | upstream_code | nikon/microscope.py:405-449 |
| On macOS and Linux a firmware bug makes get_event and other status calls return with a minimum delay of 4.096 s, and queued events may not be up to date | vendor_doc | readme.md:16 |

## Limits

The condenser (0 to 6), filter (0 to 5), objective (0 to 5), optical path (0 to 3) and diaphragm opening (0.0 to 1.0)
limits come from the asserts and docstrings of the upstream setters cited above.

The stage x, y and z positions are `Limit.operator_required`: the clone can query the installed stage's bounds
(`get_x_bounds`, `get_y_bounds`, `get_z_bound`, `nikon/microscope.py:241-275`) but states no constant travel range.
The operator supplies the um range of the stage in `site-limits.json`; until then every stage write is refused with
`MHS.SAFETY.LIMITS_UNSET`.  `site-limits.example.json` is an example overlay with values that are not a statement
about any stage.

The stage positions are published in um: the driver converts the device's 0.1 um (x, y) and 0.01 um (z) counts at
the native call, as the StatusEvent and setter docstrings state.

## Safety

The e-stop and the safe state are the native `set_light(False)` and `set_shutter(False)`: illumination off and the
shutter disabled.  The clone has no stop command and does not brake the stage, so an e-stop cannot stop a stage motion
that was already sent; the driver does not claim otherwise.  The package is R1, model-authored and unreviewed, and
nothing ran on a microscope.  No independent hardware e-stop is cited because no text of the clone documents one.

## What is not covered

- The label and objective-metadata getters (`get_condenser_labels`, `get_filter_labels`, `get_optical_path_labels`,
  `get_zoom_labels`, `get_objective_infos`) are not exposed: each upstream getter issues one request per element, and
  the README reports a 4.096 s firmware delay for the status path.
- `set_button_function` is not exposed: the clone documents the index range but no function codes.
- The clone has no camera or image API, so no image array is bound.
- The hardware path (`native.py`, PyUSB, the 4.096 s timing) was never run.

Tags: microscope, nikon, ti2-e, stage, optics, asyncio
