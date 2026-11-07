# Facts and tags for gh.naqslab/naqslab_devices

Every fact cites its source at commit `2c0ac4fb715ec7ad71c6f0061cd3c7e3d6583b69`. All facts below are
`upstream_code` from the SR865 entry symbol this package exposes. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The SR865 is a lock-in amplifier; the upstream class is described as 'SR865 Lock-In Amplifier' | upstream_code | SR865/labscript_device.py:28-29 |
| The valid sensitivities are the 28 values of the sens array, from 1 V down to 1 nV | upstream_code | SR865/labscript_device.py:20-22 |
| The valid time constants are the 22 values of the tau array, from 1 us up to 30 ks | upstream_code | SR865/labscript_device.py:24-26 |
| set_tau rejects a value that is not exactly one of the tau array values | upstream_code | SR865/labscript_device.py:50-53 |
| set_tau converts a valid time constant to its OFLT index with np.digitize(tau_constant, tau, right=True), so 1 us is index 0 | upstream_code | SR865/labscript_device.py:50-51 |
| set_sens rejects a value that is not exactly one of the sens array values | upstream_code | SR865/labscript_device.py:62-65 |
| set_sens converts a valid sensitivity to its SCAL index with np.digitize(sensitivity, sens), so 1 V is index 0 | upstream_code | SR865/labscript_device.py:62-63 |
| The phase reference is in degrees; the device auto-converts it to the -180,180 range | upstream_code | SR865/labscript_device.py:67-69 |
| The worker programs the three settings with 'OFLT {:d};SCAL {:d};PHAS {:.6f}' | upstream_code | SR865/blacs_worker.py:22 |
| The worker reads the three settings with 'OFLT?;SCAL?;PHAS?' | upstream_code | SR865/blacs_worker.py:23 |
| The worker sends '*ESE 122;*CLS;' during initialization | upstream_code | SR865/blacs_worker.py:53 |

Limits (all `upstream_code`):

| parameter | command | limit | ref |
|---|---|---|---|
| time_constant (s) | OFLT | one of the 22 values of the tau array | SR865/labscript_device.py:24-26 |
| sensitivity (V) | SCAL | one of the 28 values of the sens array | SR865/labscript_device.py:20-22 |
| phase (deg) | PHAS | -180 to 180 (the range the docstring says the device converts into) | SR865/labscript_device.py:67-69 |

The `OFLT` and `SCAL` values are translated to the 0-based indexes the upstream `numpy.digitize` calls compute:
`np.digitize(tau_constant, tau, right=True)` for the time constant and `np.digitize(sensitivity, sens)` for the
sensitivity. The reads report those indexes (`tau_index`, `sens_index`), because the upstream worker receives the
indexes and converts them back to seconds or volts with `tau[int(tau_i)]` and `sens[int(sens_i)]`
(`SR865/blacs_worker.py:60-64`).

Safety: this driver controls no output. The e-stop binding writes `*CLS`, the status-clear command the upstream
worker also sends at initialization (`SR865/blacs_worker.py:53`); the measurement settings are left alone.

Tags: lock-in amplifier, sr865, scpi, labscript
