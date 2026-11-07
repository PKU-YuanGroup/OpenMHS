# Facts and tags for gh.eta-systems/labor-gpib

Every fact cites its source at commit `d5fe1b230344452bc32b756fc14567acde683c74`: `vendor_doc` (a text file of the
clone, here the README) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The NGMO2 is a dual-channel analyzer/power supply | vendor_doc | README.md:84 |
| device builds channel_a, channel_b, display, format and status objects in its constructor | upstream_code | src/devices/rohde_schwarz_ngmo2.py:16-27 |
| send_command writes one command to the bus for the device address | upstream_code | src/devices/rohde_schwarz_ngmo2.py:193-194 |
| Channel.voltage accepts 0 to 15 V and rounds to 1 mV | upstream_code | src/devices/rohde_schwarz_ngmo2.py:402-408 |
| Channel.current accepts 0 to 5 A and rounds to 1 mA; the comment says at most 2.5 A above 5 V | upstream_code | src/devices/rohde_schwarz_ngmo2.py:410-417 |
| Channel.measure_interval accepts 0.00001 to 1.0 s in 10 us steps | upstream_code | src/devices/rohde_schwarz_ngmo2.py:481-487 |
| Channel.set_averaging_samples accepts 1 to 10 samples | upstream_code | src/devices/rohde_schwarz_ngmo2.py:495-506 |
| Channel.on and Channel.off send :OUT:A ON and :OUT:A OFF | upstream_code | src/devices/rohde_schwarz_ngmo2.py:391-395 |
| Channel.is_on queries :OUTP:A:STAT? | upstream_code | src/devices/rohde_schwarz_ngmo2.py:397-400 |
| Channel.sense maps sense names to :SENS:A:FUNC | upstream_code | src/devices/rohde_schwarz_ngmo2.py:422-444 |
| Channel.get_sense queries :SENS:A:FUNC? | upstream_code | src/devices/rohde_schwarz_ngmo2.py:446-448 |
| Channel.current_range maps range names to :SENS:A:CURR:RANG:UPP | upstream_code | src/devices/rohde_schwarz_ngmo2.py:451-463 |
| Channel.get_current_range queries :SENS:A:CURR:DC:RANG:UPP? | upstream_code | src/devices/rohde_schwarz_ngmo2.py:466-468 |
| Channel.get_interval queries :SENS:A:MEAS:INT? and returns a float | upstream_code | src/devices/rohde_schwarz_ngmo2.py:490-493 |
| Channel.read_voltage selects the volt function, sends :MEAS:A? and reads until LF | upstream_code | src/devices/rohde_schwarz_ngmo2.py:569-573 |
| Channel.read_current selects the current function, sends :MEAS:A? and reads until LF | upstream_code | src/devices/rohde_schwarz_ngmo2.py:575-579 |
| device.set_output_format maps ascii, long, short and double to :FORMat:DATA | upstream_code | src/devices/rohde_schwarz_ngmo2.py:214-225 |
| device.get_output_format queries :FORMat:DATA? | upstream_code | src/devices/rohde_schwarz_ngmo2.py:227-229 |
| Display.enable writes :DISP:ENAB ON or OFF | upstream_code | src/devices/rohde_schwarz_ngmo2.py:246-252 |
| Display.enabled queries :DISP:ENAB? and returns a boolean | upstream_code | src/devices/rohde_schwarz_ngmo2.py:255-264 |
| device.get_idn sends *IDN? and its comment shows the reply format | upstream_code | src/devices/rohde_schwarz_ngmo2.py:188-191 |
| device.get_status sends *STB? | upstream_code | src/devices/rohde_schwarz_ngmo2.py:201-203 |
| device.arm sends *ARM | upstream_code | src/devices/rohde_schwarz_ngmo2.py:124-126 |
| device.reset sends *RST and then *CLS | upstream_code | src/devices/rohde_schwarz_ngmo2.py:80-89 |
| The comment on device.rst says it returns the power supply to the *RST default conditions | upstream_code | src/devices/rohde_schwarz_ngmo2.py:80 |
| The Prologix adapter accepts GPIB addresses 0 to 30 | upstream_code | src/interface/prologix_gpib.py:35-43 |
| The Prologix request writes the query and then ++read 10 | upstream_code | src/interface/prologix_gpib.py:85-99 |
| Display.set_channel builds a command but the TODO on line 281 shows it is never sent | upstream_code | src/devices/rohde_schwarz_ngmo2.py:266-281 |
| Channel.get_impedance queries the bandwidth command instead of an impedance query | upstream_code | src/devices/rohde_schwarz_ngmo2.py:553-555 |

## Limits

All limits are `upstream_code` and apply to the channel A binding.

| parameter | command | bound | ref |
|---|---|---|---|
| voltage_setpoint (V) | :SOUR:A:VOLT | 0 to 15 | src/devices/rohde_schwarz_ngmo2.py:405 |
| current_limit (A) | :SOUR:A:CURR:LIM | 0 to 5 | src/devices/rohde_schwarz_ngmo2.py:413 |
| measurement_interval (s) | :SENS:A:MEAS:INT | 0.00001 to 1.0 | src/devices/rohde_schwarz_ngmo2.py:482 |
| averaging_samples (1) | :SENS:A:MEAS:AVER:COUN | 1 to 10 | src/devices/rohde_schwarz_ngmo2.py:504 |
| sense_function | :SENS:A:FUNC | volt, curr, dvm, avg, peak, min, high, low, rms | src/devices/rohde_schwarz_ngmo2.py:424-441 |
| current_range | :SENS:A:CURR:RANG:UPP | auto, high, medium, low | src/devices/rohde_schwarz_ngmo2.py:454-461 |
| output_format | :FORMat:DATA | ascii, long, short, double | src/devices/rohde_schwarz_ngmo2.py:216-223 |

The current comment on line 410 states a 2.5 A maximum above 5 V. The code on line 413 enforces 0 to 5 A for every
voltage; the driver declares the code's bound and states the conditional derating here instead of inventing a second
conditional limit the runtime cannot express.

## Safety

The e-stop and the safe-state action send `:OUT:A OFF`, the channel A output-disable command of the clone
(src/devices/rohde_schwarz_ngmo2.py:394-395). No text of the clone documents an independent hardware emergency stop,
so there is no `estop_physical_ref`; the safe-state action is the declared stop path. The device can source voltage
and current, so the binding is R2. OpenMHS is not a safety certification and not a safety-rated channel; the physical
stop stays authoritative.

The safety reset sends nothing. `device.reset` (src/devices/rohde_schwarz_ngmo2.py:85-86) calls `rst` (lines 81-83),
which writes `*RST` and then calls `cls`. `cls` (lines 30-31) writes `*CLS`. The comment on line 80 says that
returns the supply to the `*RST` default conditions. It does not state whether an output is enabled or what the
voltage, current and averaging become, so the call is not a reset step and not a declared re-enable (SAFE-042).
It is the ordinary command `x-cap.eta-systems.scpi_rst.v1`. The operator sends it explicitly and then confirms the
instrument. The three cached set points are refused before `device.reset` is called, including when that call
raises after `*RST`, until this driver writes them again. The command is not a safe-state action: an e-stop must
not send `*RST`.

## Not covered

Channel B is not bound by this package. The driver controls channel A only. `Display.set_channel` is not exposed
because the upstream method builds the command but never sends it (line 281), and `Channel.get_impedance` is not
exposed because it queries the bandwidth command (line 554). The voltage and current set points and the averaging
count have no upstream query; the driver reports the last values it applied. After `x-cap.eta-systems.scpi_rst.v1`
those three reads are refused until written again, because line 80 states no default number.

Tags: power supply, source measure unit, ngmo2, gpib, prologix, channel a
