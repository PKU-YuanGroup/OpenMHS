# Facts and tags for gh.cfpark00/smartem

Every fact cites the upstream clone at commit `bbabd6ac4dcdc4b77a46c0f0e21e056c82f193aa`. The same facts are
written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| ThermoFisherVerios implements the SmartEM microscope interface for a Thermo Fisher scanning electron microscope and depends on the proprietary autoscript_sdb_microscope_client package | vendor_doc | README.md:21 |
| initialize creates SdbMicroscopeClient, connects to params['ip'], sets the stage RAW coordinate system and unblanks the electron beam | upstream_code | smartem/online/microscope.py:217-224 |
| close calls disconnect and deletes the microscope client handle | upstream_code | smartem/online/microscope.py:226-228 |
| prepare_acquisition runs auto contrast/brightness, auto focus, auto lens alignment, auto stig, auto focus and auto contrast/brightness | upstream_code | smartem/online/microscope.py:236-242 |
| auto_focus sets the horizontal field width, runs the vendor autofocus (Volumescope settings when baseline is false), reads the working distance and restores the baseline focus after an exception | upstream_code | smartem/online/microscope.py:244-275 |
| get_image sets the scanning resolution and horizontal field width from resolution and pixel_size, uses bit_depth 16 and returns the vendor frame data | upstream_code | smartem/online/microscope.py:306-385 |
| move builds a StagePosition with x, y, z, r and t in coordinate_system 'Raw' and calls specimen.stage.absolute_move | upstream_code | smartem/online/microscope.py:387-399 |
| The plotting code labels a dwell time after multiplying it by 1e9 with ns, so dwell_time is in seconds | upstream_code | smartem/smartem.py:280 |
| The example imaging parameters use a 2048 x 1768 resolution and a pixel_size of 4.0e-09 | upstream_code | examples/default_smartem_params.json:2-10 |
| acquire_grid builds a coordinate from dx and dy and calls microscope.move with x, y, z, r and t | upstream_code | smartem/smartem.py:124-125 |
| The caller computes fov = resolution * pixel_size and passes dx = fov[0] * 0.8 and dy = fov[1] * 0.8 to acquire_grid | upstream_code | smartem/smartem.py:176-184 |

Limits: every numeric action input is `Limit.operator_required`. No text file of the clone states a supported
scanning resolution, dwell time, pixel size or stage travel range, so the site supplies those bounds
(`site-limits.example.json` is an example overlay only, not a statement about an instrument). Width, height,
pixel size and the five stage coordinates are declared with unit `1` because the clone does not name their
native unit; dwell time is declared in seconds because the plotting code labels it in nanoseconds after
multiplying by 1e9.

Safety: the upstream class exposes no blank, halt or stop method. Its only shutdown is `close()`, which calls
`disconnect()` and deletes the client handle. That native close is both the `@estop` and the `safe_state=True`
action `x-cap.cfpark00.release_microscope.v1`; no independent hardware e-stop is documented in the clone, so
`estop_physical_ref` is not set. The e-stop and the safe-state action must not call `close()` twice, so the
driver guards it with an instance flag.

The declared risk is R3: the microscope drives an electron beam and moves a specimen stage, and it operates at
the high voltage of a scanning electron column. This package is model-authored and unreviewed; the loader
refuses its hardware backend until a human signs `reviewed_by` (enforced at R2 and R3).

Tags: sem, electron-microscope, smartem, imaging, stage, high-voltage
