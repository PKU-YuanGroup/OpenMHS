# Facts and tags for gh.aimoda/rigol-dho824-mcp

Every fact cites its source at commit `2b177ae161463c911dce3608ab37e8cadcefc4f6`: `vendor_doc` (a text file of the
clone such as README.md or manuals/*.md) or `upstream_code` (`path/in/clone:LINE`). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The clone supports only the DHO804 and DHO824 oscilloscopes (identical hardware) | vendor_doc | README.md:16 |
| The clone's supported firmware version is 00.01.04 | vendor_doc | README.md:22 |
| The class RigolDHO824 manages communication with the Rigol DHO824 oscilloscope | upstream_code | src/rigol_dho824_mcp/server.py:1297-1298 |
| The constructor creates pyvisa's ResourceManager | upstream_code | src/rigol_dho824_mcp/server.py:1308 |
| connect() opens self.resource_string with pyvisa's exclusive_lock access mode | upstream_code | src/rigol_dho824_mcp/server.py:1503-1506 |
| A checked write sends the command with pyvisa's write and then queries ':SYSTem:ERRor?' | upstream_code | src/rigol_dho824_mcp/server.py:1348-1349 |
| A checked query sends the command with pyvisa's query and then queries ':SYSTem:ERRor?' | upstream_code | src/rigol_dho824_mcp/server.py:1374-1375 |
| get_identity() queries '*IDN?' when no identity is cached | upstream_code | src/rigol_dho824_mcp/server.py:1572-1588 |
| The identity string has the format 'RIGOL TECHNOLOGIES,<model>,<serial>,<version>' | upstream_code | src/rigol_dho824_mcp/server.py:1601 |
| The DVM is enabled or disabled with ':DVM:ENABle ON' or ':DVM:ENABle OFF' | upstream_code | src/rigol_dho824_mcp/server.py:1702-1705 |
| DVMMode defines the values ACRM (AC RMS), DC (DC average) and DCRM (AC+DC RMS) | upstream_code | src/rigol_dho824_mcp/server.py:295-297 |
| The current DVM voltage is queried with ':DVM:CURRent?' and parsed as a float in volts | upstream_code | src/rigol_dho824_mcp/server.py:1739-1746 |
| The channel configuration queries ':CHAN<n>:' display, coupling, probe, bandwidth limit, scale, offset and invert | upstream_code | src/rigol_dho824_mcp/server.py:2440-2446 |
| The main timebase scale and offset are queried with ':TIM:MAIN:SCAL?' and ':TIM:MAIN:OFFS?' | upstream_code | src/rigol_dho824_mcp/server.py:2578-2579 |
| A run, stop or single acquisition is requested with ':RUN', ':STOP' or ':SING', after which the trigger status is queried with ':TRIG:STAT?' | upstream_code | src/rigol_dho824_mcp/server.py:2679-2721 |
| The trigger status query returns TD, WAIT, RUN, AUTO, or STOP | vendor_doc | manuals/DHO800900_ProgrammingGuide_EN.md:14189 |
| At a 1X probe ratio, the DHO800 series vertical scale ranges from 500 uV/div to 10 V/div | vendor_doc | manuals/DHO800900_ProgrammingGuide_EN.md:3856 |
| The probe ratio affects the value and settable range of the current vertical scale | vendor_doc | manuals/DHO800900_ProgrammingGuide_EN.md:3892 |
| The DHO800 series time base range is 5 ns/div to 500 s/div | vendor_doc | manuals/DHO800_DataSheet_EN.md:162 |
| The channel coupling values are AC, DC and GND | vendor_doc | manuals/DHO800900_ProgrammingGuide_EN.md:3686 |
| The programming guide lists discrete probe attenuation ratios from 0.001 to 50000 | vendor_doc | manuals/DHO800900_ProgrammingGuide_EN.md:3886 |
| The bandwidth limit query returns 20M or OFF | vendor_doc | manuals/DHO800900_ProgrammingGuide_EN.md:3664 |
| Waveform capture selects WORD format and reads ':WAV:DATA?' with _query_binary_values_checked | upstream_code | src/rigol_dho824_mcp/server.py:2220-2273 |

Limits:

| parameter | command | limit | ref |
|---|---|---|---|
| channel1_scale (V/div) | :CHAN1:SCAL | operator_required | A 1X range is stated at manuals/DHO800900_ProgrammingGuide_EN.md:3856; line 3892 says the probe ratio changes the range |
| timebase_scale (s/div) | :TIM:MAIN:SCAL | 5e-09 to 500 | manuals/DHO800_DataSheet_EN.md:162 |
| channel1_probe | :CHAN1:PROB | one of 0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000 | manuals/DHO800900_ProgrammingGuide_EN.md:3886 |
| channel1_coupling | :CHAN1:COUP | AC, DC or GND | manuals/DHO800900_ProgrammingGuide_EN.md:3686 |
| channel1_bandwidth_limit | :CHAN1:BWL | 20M or OFF | manuals/DHO800900_ProgrammingGuide_EN.md:3664 |
| dvm_mode | :DVM:MODE | ACRM, DC or DCRM | src/rigol_dho824_mcp/server.py:295-297 |
| acquisition_status | :RUN / :STOP | RUN or STOP | src/rigol_dho824_mcp/server.py:2679-2697 |

Vertical-scale writes are refused with `MHS.SAFETY.LIMITS_UNSET` until the operator supplies a range appropriate to
the configured channel and every permitted probe ratio. The guide gives 0.0005 to 10 V/div only for a 1X probe;
applying that range while allowing every probe ratio is not a universally valid narrowing. The example overlay is
explicitly for a channel already configured at 1X with a voltage axis and permits only 1X probe writes. It does not
verify initial settings or prevent changes from the front panel or another client. It is not applied automatically.
The offset range depends on the current vertical scale (data sheet line 150), so offset is read-only here.

Safety: the e-stop writes `:STOP`, the stop command of the clone's stop_acquisition tool
(`src/rigol_dho824_mcp/server.py:2697`). The programming guide describes this command as stopping the oscilloscope
(`manuals/DHO800900_ProgrammingGuide_EN.md:1070-1078`). The SCPI bridge's safety path confirms only that the write
returned; it does not check the error queue or read back `:TRIG:STAT?`. Reset releases the software latch without
sending `:RUN`. No electrical isolation or circuit-under-test shutdown is confirmed. The device is a measurement
instrument; this package drives no output or actuator.

Fake gaps: probe-dependent scale/offset changes, state-dependent setting rejection, acquisition timing and DVM
measurement behavior are not simulated. The fake's numeric readings are placeholders. Ordinary resource reads also
omit the upstream's post-query error-queue check; configure writes check the error queue, and the explicit read-error
action returns an error entry as data. Waveforms, screenshots, other channels and the source selections remain out of scope.

Tags: oscilloscope, rigol, dho824, dho804, scpi, visa, instrument
