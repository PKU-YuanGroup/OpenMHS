# Facts and tags for gh.biologytools/bioimager (Cobolt laser)

Every fact cites its source at commit `149b45255d628cc4118b3829cd7c5b10c9c6cb07`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page. The upstream
class is `PythonMicroscope/microscope/lights/cobolt.py:CoboltLaser`, which builds on the `microscope.abc.LightSource`
contract in `PythonMicroscope/microscope/abc.py`.

| fact | source | ref |
|---|---|---|
| CoboltLaser is a diode-pumped laser and supports only TriggerMode.SOFTWARE | upstream_code | PythonMicroscope/microscope/lights/cobolt.py:37-43 |
| The constructor sends sn?, @cobas 0 to disable autostart and gmlp? to read the maximum power | upstream_code | PythonMicroscope/microscope/lights/cobolt.py:57-65 |
| The serial connection is 115200 baud, 8 data bits, one stop bit and no parity by default | upstream_code | PythonMicroscope/microscope/lights/cobolt.py:47-56 |
| get_status queries l?, p?, pa?, f? and hrs? and returns the five replies with their labels | upstream_code | PythonMicroscope/microscope/lights/cobolt.py:87-99 |
| clearFault sends cf and returns get_status() | upstream_code | PythonMicroscope/microscope/lights/cobolt.py:82-85 |
| initialize sends @cobasdr 0 (leave direct-control mode) and @cob1 (force autostart) | upstream_code | PythonMicroscope/microscope/lights/cobolt.py:108-115 |
| _do_enable sends l1 and returns False unless get_is_on() then reports emission on | upstream_code | PythonMicroscope/microscope/lights/cobolt.py:117-130 |
| disable sends l0 | upstream_code | PythonMicroscope/microscope/lights/cobolt.py:132-136 |
| get_is_on sends l? and treats the reply b'1' as emission on | upstream_code | PythonMicroscope/microscope/lights/cobolt.py:138-142 |
| _get_power_mw returns 0.0 while emission is off, otherwise reads pa? in W and returns 1000 times it | upstream_code | PythonMicroscope/microscope/lights/cobolt.py:144-154 |
| _set_power_mw writes @cobasp with the power in W to four decimals and accepts any non-negative value | upstream_code | PythonMicroscope/microscope/lights/cobolt.py:156-162 |
| _do_set_power multiplies the fraction by the head maximum and _do_get_power divides by it | upstream_code | PythonMicroscope/microscope/lights/cobolt.py:164-168 |
| LightSource.power is the fraction of maximum power in the [0, 1] interval and its setter clips to it | upstream_code | PythonMicroscope/microscope/abc.py:1232-1244 |

Limits: the driver exposes power as a fraction of the head maximum, as the upstream `power` property does. The
upstream contract states the [0, 1] interval and its setter clips to it (`abc.py:1232-1244`), so the driver's
`power_setpoint` write carries that sourced limit. No text file of the clone states the maximum optical power of a
head: the constructor reads it from the device with `gmlp?` (`cobolt.py:65`), so no milliwatt bound is invented.

Risk: the clone does not state the laser class. Cobolt's datasheets and owner's manuals class the 04-01 series heads as Class 3B (IEC 60825-1) and higher-power heads as Class 4, so a model review declared the device and its `emission` write R3 (`MHS/spec/04-safety.md`: class 3B+ laser).

Safety: `safe_state` is emission off. The e-stop `stop` and the safe-state action
`x-cap.biologytools.disable_laser.v1` both call the native `disable()`, which sends `l0` (`cobolt.py:132-136`). The
clone states no independent hardware e-stop, so `estop_physical_ref` is not set and the safe-state action is the
independent stop required of this R3 driver. The package is model-authored and unreviewed; the loader refuses its
hardware backend until a human signs `driver.lock.json` `reviewed_by`.

Tags: laser, light-source, cobolt, serial
