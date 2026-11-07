# Facts and tags for gh.christofferkrook/laserphysics_devices

Every fact cites its source at commit `7af657f90b192af988610525ead54bb2cc83a11d`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository controls an Ando AQ-6315A Optical Spectrum Analyzer | upstream_code | OSA/old_osa/README.md:1 |
| The Ando class opens a pyvisa GPIB resource for the OSA | upstream_code | OSA/old_osa/Ando.py:13-17 |
| set_current_trace writes ACTV0 for A, ACTV1 for B and ACTV2 for C | upstream_code | OSA/old_osa/Ando.py:59-66 |
| get_sweep_status maps reply 0 to STOP, 1 to SINGLE, 2 and 3 to AUTO and 4 to SEGMENT_MEASURE | upstream_code | OSA/old_osa/Ando.py:105-117 |
| set_sweep_status writes STP for STOP, SGL for SINGLE, RPT for AUTO and MEAS for SEGMENT_MEASURE | upstream_code | OSA/old_osa/Ando.py:121-130 |
| set_start_wl and set_stop_wl send the value with the STAWL and STPWL commands and append '.00' | upstream_code | OSA/old_osa/Ando.py:140-153 |
| set_center_wl and set_span send the CTRWL and SPAN commands | upstream_code | OSA/old_osa/Ando.py:167-179 |
| The GUI labels the wavelength axis and the start, stop, center and span values in nm | upstream_code | OSA/old_osa/controller.py:233-460 |
| The trace plot labels power in dBm for LOG scale and mW for LIN scale | upstream_code | OSA/old_osa/controller.py:234-237 |
| The resolution menu offers 0.05, 0.1, 0.2, 0.5, 1, 2, 5 and 10 | upstream_code | OSA/old_osa/OSAview.py:134 |
| get_trace returns the intensity and wavelength arrays for traces A, B and C | upstream_code | OSA/old_osa/Ando.py:225-256 |
| The GUI changes the measurement state through set_sweep_status | upstream_code | OSA/old_osa/controller.py:521-531 |

Limits: the start, stop, centre and span wavelengths and the average count are `Limit.operator_required`: the clone
names no absolute wavelength range and no average-count range for this OSA. The resolution is narrowed to the eight
values the clone's control program offers (`OSA/old_osa/OSAview.py:134`); the scale, active trace and sweep state are
limited to the names the Ando wrapper maps (`OSA/old_osa/Ando.py:59-66`, `121-130`, `204-223`). Resolution and
average count carry the dimensionless unit `1` because the clone states no unit for them.

Safety: the e-stop calls `set_sweep_status('STOP')`, the native stop (`STP`, `OSA/old_osa/Ando.py:121-130`); this is
also the safe state. The device is a passive spectrum analyzer at R1; the clone documents no independent hardware
e-stop, so `estop_physical_ref` is not set.

Not covered: the trace arrays returned by `get_trace` (`OSA/old_osa/Ando.py:225-256`). The standard carries scalar
state here; the array size follows the configured sweep and is not exposed.

Tags: spectrum-analyzer, optical, gpib, spectrometer
