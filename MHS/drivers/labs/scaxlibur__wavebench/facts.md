# Facts, limits and tags for gh.scaxlibur/wavebench

The clone is a bench toolkit rather than a single instrument: `src/wavebench/drivers/` holds one class per device
family and `src/wavebench/services/` composes them into run plans. This package serves the signal source of the
toolkit, the RIGOL DG4000 series class `wavebench.drivers.dg4202:DG4202Source` (the toolkit's own driver for
"RIGOL DG4202 Function/Arbitrary Waveform Generator", src/wavebench/instruments/builtin.py:109-132).

Every fact cites its source at commit `44506c4975d8615ace0d2dbababe880b89567709`: `upstream_code` is a code line of
the clone, `vendor_doc` a text file of it. The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The DG4000 driver accepts the models DG4062, DG4102, DG4162 and DG4202, and it accepts configuration writes only on a DG4202 | upstream_code | src/wavebench/drivers/dg4202.py:30-31 |
| The generator has two output channels, 1 and 2 | upstream_code | src/wavebench/drivers/dg4202.py:52-54 |
| The identity query *IDN? is parsed into four comma-separated fields (manufacturer, model, serial number, firmware) and the manufacturer must be RIGOL TECHNOLOGIES | upstream_code | src/wavebench/drivers/dg4202.py:80-90 |
| A status snapshot reads the output state, the function, the frequency, the amplitude, the amplitude unit, the offset, the phase, the frequency mode, the sweep state, the APPLy response and the square-wave duty cycle | upstream_code | src/wavebench/drivers/dg4202.py:481-527 |
| An output is switched with ':OUTP<channel> ON' or ':OUTP<channel> OFF' and read back with ':OUTP<channel>?' | upstream_code | src/wavebench/drivers/dg4202.py:594-595 |
| A frequency is written as ':SOUR<channel>:FREQ <value>' after the frequency mode is switched to FIX when it is not FIX | upstream_code | src/wavebench/drivers/dg4202.py:550-556 |
| A function is written as ':SOUR<channel>:FUNC <FUNCTION>' with the canonical names SIN, SQU, RAMP, PULS, NOIS and DC (aliases such as SINE, SQUARE or TRI are accepted and normalized) | upstream_code | src/wavebench/drivers/dg4202.py:632-645 |
| An amplitude is written in Vpp: the driver first writes ':SOUR<channel>:VOLT:UNIT VPP', then ':SOUR<channel>:VOLT <value>' | upstream_code | src/wavebench/drivers/dg4202.py:675-682 |
| A square-wave duty cycle is written as ':SOUR<channel>:FUNC:SQU:DCYC <percent>' and read back with the same command followed by '?' | upstream_code | src/wavebench/drivers/dg4202.py:717-721 |
| The class refuses a frequency that is not > 0 Hz | upstream_code | src/wavebench/drivers/dg4202.py:538-539 |
| The class refuses an amplitude that is not > 0 V | upstream_code | src/wavebench/drivers/dg4202.py:669-670 |
| The class refuses a square-wave duty cycle that is not strictly between 0 and 100 percent | upstream_code | src/wavebench/drivers/dg4202.py:709-711 |
| A failed output transaction is recovered by forcing that channel OFF before the error is raised | upstream_code | src/wavebench/drivers/dg4202.py:240-243 |
| The clone leaves the source amplitude ceiling to the operator: SafetyLimitsConfig.max_source_vpp defaults to None | upstream_code | src/wavebench/config.py:167-168 |
| Setting a voltage, an amplitude or a frequency never switches an output on by itself | vendor_doc | README.md:102 |

## Limits

| parameter | unit | limit | source |
|---|---|---|---|
| frequency | Hz | operator_required: no text file of the clone states the frequency range; the code only refuses a value that is not > 0 (dg4202.py:538-539) | operator |
| amplitude | V | operator_required: no text file of the clone states the amplitude range; the code only refuses a value that is not > 0 (dg4202.py:669-670) and the ceiling is an operator setting (config.py:168) | operator |
| duty_cycle | % | 0 to 100 (the clone refuses exactly the two ends: strictly greater than 0 and less than 100, dg4202.py:709-711) | upstream_code: src/wavebench/drivers/dg4202.py:709-711 |
| function | | one of SIN, SQU, RAMP, PULS, NOIS, DC (dg4202.py:632-638) | upstream_code: src/wavebench/drivers/dg4202.py:635-638 |
| output | boolean | no numeric bound: an output switch | - |

The declared duty-cycle interval is closed (0 to 100 percent) while the clone refuses exactly 0 and 100 percent: a
write of one of those two values passes the runtime envelope and then fails in the native call. The overlay example
in `site-limits.example.json` narrows both operator-required ranges and the duty cycle for one bench.

## Safety

* The e-stop calls the native `set_output` for both channels: both outputs go OFF. The generator holds no other
  actuation this driver sets, and the clone itself forces a channel OFF when an output transaction fails
  (dg4202.py:240-243).
* The native class serialises every call on one re-entrant lock (dg4202.py:150); an e-stop issued while a long native
  call holds that lock waits for it, and the runtime's e-stop budget is 5000 ms.
* Hardware is never attached in the acceptance run; the package's hardware backend (`native.py`) was never opened.

## Tags

signal generator, function generator, waveform generator, dg4202, dg4000, scpi, wavebench
