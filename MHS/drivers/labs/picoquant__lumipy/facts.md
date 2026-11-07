# Facts and tags for gh.picoquant/lumipy

Every fact cites the pinned clone at commit `dc0fe266a55219811d171ccfc99a742e4eb4fffd`. The selected interface is
`libs/pqlumi.py:Measurement`, the concrete class behind the module-level `measurement` object. The same facts are
written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

## Deviation from the card

The card's family is `mcp-client` with `McpClientDriver`. That shape does not fit the pinned repository. The MCP
server (`MCPTool/lumipy_mcp_server.py`) exposes an arbitrary-Python-code bridge (`execute_python_code`,
`abort_code_execution`, `get_environment_info`, `get_system_config`, `get_context`, `get_last_response`) to a remote
execution server; it is not a finite set of device tools, and the code it runs selects its own LumiPy calls at run
time. The card's own hints list the `Measurement` methods, and the entry symbol is `libs.pqlumi:Measurement`. This
package therefore uses a direct `Driver` over that concrete object, with a `native.py` factory for the hardware
backend. `RESULT.json` records the deviation.

## Facts

| fact | source | ref |
|---|---|---|
| pqlumi defines the concrete Measurement class. | upstream_code | libs/pqlumi.py:502-517 |
| pqlumi binds one module-level measurement instance of that class. | upstream_code | libs/pqlumi.py:1071-1072 |
| When delphi_pqlumi cannot be imported, pqlumi sets is_fake and prints that it uses a fake module. | upstream_code | libs/pqlumi.py:13-18 |
| A laser assembly is made up of a laser head, attenuator, main attenuator and shutter, accessed through the pqdc module. | upstream_code | libs/pqlumi.py:1093-1097 |
| The MCP tool disclaimer warns that generated code can put connected microscope hardware, including lasers and scanners, in a hazardous operating condition. | vendor_doc | MCPTool/Disclaimer.md:7 |
| start_meas accepts only the measurement types "image", "line" and "point" in its docstring; it forwards the string to dm.start_meas. | upstream_code | libs/pqlumi.py:986-1000 |
| stop_meas returns at once when is_fake; otherwise it calls dm.stop_meas, raises on an error return and returns nothing; the docstring does not promise a stop readback. | upstream_code | libs/pqlumi.py:1020-1033 |
| meas_status returns False while a measurement is inactive or stopped and True while it is running. | upstream_code | libs/pqlumi.py:1002-1018 |
| get_elapsed_meas_time returns the elapsed measurement time in seconds. | upstream_code | libs/pqlumi.py:1035-1052 |
| scan_range_min_x/max_x/min_y/max_y are in meters. | upstream_code | libs/pqlumi.py:552-614 |
| scan_range_left/top/width/height are in meters. | upstream_code | libs/pqlumi.py:616-738 |
| path_to_ptu is the absolute path of the last PTU file written. | upstream_code | libs/pqlumi.py:771-785 |
| img_conf.scan_speed is a percentage, image_size is a pixel tuple, and num_frames is a count. | upstream_code | libs/pqlumi.py:36-158 |
| img_conf.photons_in_brightest_px is a count and img_conf.meas_time is in seconds. | upstream_code | libs/pqlumi.py:160-282 |
| point_conf exposes a photon count, measurement time, stop flags, point_list in meters and selected_point in meters. | upstream_code | libs/pqlumi.py:284-483 |
| write_ptu_file enables or disables PTU output during a scan. | upstream_code | libs/pqlumi.py:740-770 |
| set_next_measurement_name sets the next measurement name and has no getter. | upstream_code | libs/pqlumi.py:805-820 |
| get_analysis_names lists the live analysis names configured in Luminosa. | upstream_code | libs/pqlumi.py:822-835 |
| get_analysis_curve_types lists the curve types available for one analysis. | upstream_code | libs/pqlumi.py:837-853 |
| get_analysis_image_types lists the image types available for one analysis. | upstream_code | libs/pqlumi.py:898-914 |
| get_analysis_param_types lists the parameter types available for one analysis. | upstream_code | libs/pqlumi.py:949-965 |
| get_analysis_curve returns the documented 1-D curve plus optional FCS fit arrays. | upstream_code | libs/pqlumi.py:855-896 |
| get_analysis_image returns a 2-D image and x/y/z positions in meters. | upstream_code | libs/pqlumi.py:916-947 |
| get_analysis_param returns a dict whose keys depend on the analysis and parameter type. | upstream_code | libs/pqlumi.py:967-984 |
| The upstream is_fake fallback returns a five-point curve. | upstream_code | libs/pqlumi.py:882-891 |
| The upstream is_fake fallback returns a 3x3 image; those values are the upstream's own test fallback, not a size or measurement of a real system. | upstream_code | libs/pqlumi.py:934-942 |

## Limits

Every numeric writable parameter is `Limit.operator_required`: the pinned source states the unit but no range, and
neither the constructor nor a catalogue class default is a device limit. The operator overlay in
`site-limits.example.json` fills example ranges; its numbers are one bench's choice, not Luminosa specifications.

| input | bound | source | ref |
|---|---|---|---|
| scan_range_left, scan_range_top, scan_range_width, scan_range_height (cap.device.configure.v1) | `Limit.operator_required` | none | unit stated at libs/pqlumi.py:616-738; no range stated |
| scan_speed (cap.device.configure.v1) | `Limit.operator_required` | none | unit stated at libs/pqlumi.py:36-65; no range stated |
| image_size[*] (cap.device.configure.v1) | `Limit.operator_required` | none | pixels stated at libs/pqlumi.py:67-96; no range stated |
| num_frames, photons_in_brightest_px, img_meas_time (x-cap.picoquant.configure_image_stop.v1) | `Limit.operator_required` | none | counts/time described at libs/pqlumi.py:129-282; no range stated |
| point_num_photons, point_meas_time (x-cap.picoquant.configure_point_stop.v1) | `Limit.operator_required` | none | counts/time described at libs/pqlumi.py:392-483; no range stated |

## Scope and completeness

The driver binds the Measurement state that the hints name: the version, scan range, image and point stop conditions,
PTU output, running status and elapsed time; the writable image and point settings; and the analysis name/type/curve/
parameter queries. Measurement start, stop, the next-measurement name and the analysis queries are extension
actions because no catalogue class expresses them. The image/point stop conditions and PTU output are extension
configuration actions rather than members of `cap.device.configure.v1`: that keeps each MCP tool's input schema
within the 2048-byte tool bound while every state field remains readable. The curve is returned as the complete
`data_x`/`data_y` arrays plus the documented optional fit arrays; no array is truncated. NOT COVERED (model review):
`get_analysis_image`, whose complete 2-D `img_data` follows the configured `image_size` and would be returned inline:
large data that needs an artifact path (NEEDS_ARTIFACTS); the image type list stays readable. The fake's five-point
curve is a placeholder.

The driver does not bind `load_user_setting`, `block_airy_adjustment`, `point_list`, `selected_point` or `lumi_finder`.
It also does not bind the `pqdc`/`pqscan` laser, shutter, attenuator or stage interfaces. Those are separate modules
and separate device surfaces; this package's native symbol is the Measurement class only.

## Safety and risk

Risk is R2 (model review, 2026-11-05; the author declared R1). A Luminosa measurement is a laser-scanning
measurement: the instrument's laser assemblies (laser head, attenuators, main attenuator and shutter,
`libs/pqlumi.py:1093-1097`) excite the sample during the scan, and the clone states no laser class, so the hazard
table's "laser above class 1" applies until a human states the class. Every `Measurement` call forwards to the
closed Luminosa bridge `delphi_pqlumi`, so the clone does not show whether starting or stopping a measurement switches
a laser or a shutter; the earlier statement that this interface "does not switch a laser, shutter, attenuator or
stage" was not provable and is withdrawn. The upstream disclaimer names lasers and scanners among the hardware that
generated code can put in a hazardous condition (`MCPTool/Disclaimer.md:7`). At R2 the loader refuses the hardware
backend until a human signs `reviewed_by`.

The native stop is `Measurement.stop_meas` (`libs/pqlumi.py:1020-1033`), which raises on an error return. The `@estop`
and the safe-state action `x-cap.picoquant.stop_measurement.v1` both call it and then read `meas_status()` until it
is False, for at most 0.5 s; a measurement still reported running is `MHS.SAFETY.SAFE_STATE_UNREACHED` with the latch
held (the fake's `stop_ignored` switch tests it). That confirms the measurement stopped as the Luminosa software
reports it; it does not prove that lasers or shutters are off, and the `pqdc` laser/shutter interface is not bound.
`estop_physical_ref` is not set because no line of the clone documents an independent hardware e-stop. The fake's
running flag is a controlled state model, not evidence that a real Luminosa stops.

Tags: microscope, confocal, lumipy, luminosa, measurement, fake-only
