# Facts and tags for gh.chilaslasers/pychilaslasers

Every fact cites its source at commit `ec9470e0042ccb86edb196e9834508f38dbf1b1a`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| PyChilasLasers is the Python library for controlling the Chilas Atlas and Comet tunable lasers | vendor_doc | README.md:4 |
| The laser is powered on with a side button and a key switch before the library connects to it | vendor_doc | docs/quickstart.md:65 |
| During initialization the Laser constructor turns the laser on to read component information such as maximum values | upstream_code | src/pychilaslasers/laser.py:99-102 |
| Laser.system_state reads SYST:STAT? and writes SYST:STAT 0 or SYST:STAT 1 | upstream_code | src/pychilaslasers/laser.py:232-259 |
| Laser.turn_on sets the system state to True and Laser.turn_off sets it to False | upstream_code | src/pychilaslasers/laser.py:555-567 |
| The diode drive current is read with LSR:ILEV? and written with LSR:ILEV | upstream_code | src/pychilaslasers/laser_components/diode.py:76-106 |
| The diode minimum current is 0.0 mA, its maximum is read from LSR:IMAX?, and its unit is mA | upstream_code | src/pychilaslasers/laser_components/diode.py:50-52 |
| The diode state is read with LSR:STAT? and written with LSR:STAT 0 or LSR:STAT 1 | upstream_code | src/pychilaslasers/laser_components/diode.py:56-74 |
| Diode.turn_off sets the emission state to False and Diode.turn_on sets it to True | upstream_code | src/pychilaslasers/laser_components/diode.py:152-164 |
| The TEC target temperature is read with TEC:TTGT? and written with TEC:TTGT, and the unit is degrees Celsius | upstream_code | src/pychilaslasers/laser_components/tec.py:57-83 |
| The TEC target range is read from the laser at construction time (TEC:CFG:TMIN? and TEC:CFG:TMAX?) | upstream_code | src/pychilaslasers/laser_components/tec.py:50-52 |
| The measured TEC temperature is read with TEC:TEMP? and reported in degrees Celsius | upstream_code | src/pychilaslasers/laser_components/tec.py:85-88 |
| The TEC current is read with TEC:ITEC? in mA | upstream_code | src/pychilaslasers/laser_components/tec.py:104-111 |
| Laser.trigger_pulse delegates to Trigger.pulse, which writes DRV:CYC:TRIG 1 then DRV:CYC:TRIG 0 | upstream_code | src/pychilaslasers/laser_components/trigger.py:36-39 |
| Laser.model returns the calibration model (ATLAS or COMET) and Laser.calibrated reports whether calibration data is loaded | upstream_code | src/pychilaslasers/laser.py:482-500 |

Limits: the diode drive current and the TEC target temperature are `Limit.operator_required`. The clone gives no
numeric range: each component queries the connected laser at construction time (`LSR:IMAX?`, `TEC:CFG:TMIN?` and
`TEC:CFG:TMAX?`) and the device may be configured differently, so the site supplies the rated range of its unit in
`site-limits.json`. `site-limits.example.json` is an example of that overlay, not a statement about any laser.

Safety: `turn_off` (`x-cap.chilaslasers.turn_off.v1`, `safe_state=True`) disables the system output (`SYST:STAT 0`)
and the diode emission (`LSR:STAT 0`); the `@estop` method calls both. No line of the clone documents an independent
hardware e-stop, so `estop_physical_ref` is not set and the safe-state action satisfies SAFE-045 for this R2 driver.
The quickstart says the unit is powered on with a side button and a key switch (docs/quickstart.md:65); it does not
describe that switch as an emergency stop, so it is not cited as one.

Risk: R2. MHS-004, `MHS/spec/04-safety.md` section 2.1, classes a laser above class 1 as R2. The clone states no IEC laser
class (README.md and docs/ describe the product but give no class), so the driver does not claim class 1 and does not
claim R3 without a class 3B or 4 statement.

Tags: laser, tunable-laser, photonic-integrated-circuit, laser-diode, tec, serial
