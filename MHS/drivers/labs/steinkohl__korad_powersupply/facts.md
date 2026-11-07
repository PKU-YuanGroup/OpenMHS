# Facts and tags for gh.steinkohl/korad_powersupply

Every fact cites its source at commit `fd2e8b7c59a4dd9f9e609bdacf15b3d7bc1b3d5e`: `vendor_doc` (a text file of the
clone) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| KC3405P is the class of the Korad KC3405 power supply controlled over Ethernet | vendor_doc | README.md:2 |
| KC3405P opens a UDP socket and binds it to the configured port (constructor default 18190) | upstream_code | korad.py:33-36 |
| _send_command sends the command followed by CRLF over the UDP socket | upstream_code | korad.py:38-41 |
| get_device_info queries ':SYST:DEVINFO?' and reads eight reply lines into a dictionary | upstream_code | korad.py:49-68 |
| get_status reads 'STATUS?' and maps its bits to CV/CC mode and on/off output for channels 1 to 4 | upstream_code | korad.py:71-90 |
| The measured voltage and current are queried with VOUT<channel>? and IOUT<channel>? | upstream_code | korad.py:92-102 |
| The voltage and current setpoints are queried with VSET<channel>? and ISET<channel>? | upstream_code | korad.py:104-114 |
| set_voltage writes VSET<channel>:<value> with three decimals and verifies the readback within 0.01 V | upstream_code | korad.py:116-124 |
| set_current writes ISET<channel>:<value> with three decimals and verifies the readback within 0.01 A | upstream_code | korad.py:126-134 |
| enable_output(0) writes OUT1234:1 and disable_output(0) writes OUT1234:0; a channel number writes OUT<channel>:1 or OUT<channel>:0 | upstream_code | korad.py:144-182 |
| The overcurrent protection setting is read with OCPSET<channel>? and written with OCPSET<channel>:<value> | upstream_code | korad.py:184-197 |
| The overvoltage protection setting is read with OVPSET<channel>? and written with OVPSET<channel>:<value> | upstream_code | korad.py:199-212 |
| OCP<channel>? reads the overcurrent protection state; OCP<channel>:1 and OCP<channel>:0 enable and disable it | upstream_code | korad.py:214-234 |
| OVP<channel>? reads the overvoltage protection state; OVP<channel>:1 and OVP<channel>:0 enable and disable it | upstream_code | korad.py:236-256 |
| get_settings reads the device information, the status and, for each channel 1 to 4, the protection settings and states, the voltage and current setpoints and the measured voltage and current | upstream_code | korad.py:334-357 |
| The clone's _check_channel states that a channel must be between 1 and 4 | upstream_code | korad.py:21-25 |
| get_settings iterates the channels with range(1, 5) | upstream_code | korad.py:338 |

## Limits

No text of the clone states an output voltage range, an output current range, an overvoltage protection range or an
overcurrent protection range. `set_voltage` and `set_current` pass the caller's value straight into the command
(korad.py:116-134), and `set_overvoltage_protection` / `set_overcurrent_protection` do the same (korad.py:184-212).
The class constants `_default_voltage`, `_default_current`, `_default_ocp` and `_default_ovp` (korad.py:29-32) are
starting values of a reset, not device bounds, so no Limit is copied from them.

All four numeric writes are therefore `Limit.operator_required`: the operator supplies the range of the installed
unit in `site-limits.json`, and `site-limits.example.json` shows the shape with example values only. Until that
overlay is written, every setpoint and protection-setting write is refused `MHS.SAFETY.LIMITS_UNSET`. The boolean
writes (output on/off and protection on/off) carry no numeric bound.

## Safety

The native stop is `KC3405P.disable_output(0)`, which writes `OUT1234:0` and then verifies that all four output bits
are off (korad.py:164-182). The driver sends the same `OUT1234:0` line through the native `_send_command` path
(korad.py:38-41) in the `@estop` method and in the `x-cap.steinkohl.output_off.v1` safe-state action. That path
does not wait for a `STATUS?` reply on the blocking receive (korad.py:43-44, 71-76); `disable_output(0)` would
wait, and a silent device must not hold the e-stop. The driver controls one channel selected at deployment by the
backend option `channel` (default 1); the e-stop and the safe-state action address all four channels. The hardware
backend was never opened; the acceptance gate checks the fake backend only. OpenMHS is not a safety certification
and the physical stop stays authoritative.

The upstream `set_overcurrent_protection` and `set_overvoltage_protection` read back the current/voltage setpoint
rather than the protection setting they wrote (korad.py:193-196 and 208-211). The driver calls those public methods
and then reads the protection setting itself, so a native exception is never hidden; a spurious upstream
verification error would surface as a failed write. This package is model-authored and unreviewed.

## Kind

The catalogue has no dedicated power-supply resource kind. `instrument.smu` is the closest defined kind whose
resource kinds let `cap.measure.voltage.v1` and `cap.measure.current.v1` bind, so it is the declared `device_kind`.

Tags: power supply, psu, udp, voltage, current, protection.
