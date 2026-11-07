# Facts and tags for gh.jrafolsr/pyinstruments (keysight33210A function generator)

Every fact cites its source at commit `631eb6fe6e61ca83e0d065aa3e36b04244c952b4`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

## Device and capabilities

The package covers the `keysight33210A` class of the clone: an Agilent/Keysight function generator controlled over
SCPI. It exposes the frequency, amplitude, offset, waveform function, output termination and output relay through
`cap.device.configure.v1`, and reads their current values through the resource state. Other instrument classes in
the clone (Keithley 24XX, Agilent U272xA, the multimeters and the DAQ) are not covered.

| fact | source | ref |
|---|---|---|
| The class requires the identity string to start with 'Agilent Technologies' | upstream_code | instruments/keysight33210A.py:16 |
| The waveform functions are SIN, SQU, RAMP, PULS, NOIS, DC and USER | upstream_code | instruments/keysight33210A.py:20 |
| The frequency setter accepts 1e-3 Hz to 10e6 Hz | upstream_code | instruments/keysight33210A.py:29-30 |
| The load setter accepts 50 ohm or the string 'INF' | upstream_code | instruments/keysight33210A.py:36 |
| The amplitude setter rejects amplitude <= 0 | upstream_code | instruments/keysight33210A.py:95-96 |
| The load-dependent Vmax is 5 V for 50 ohm and 10 V for INF | upstream_code | instruments/keysight33210A.py:34-47 |
| The offset setter refuses abs(offset) > Vmax - Vpp/2 with the load-dependent Vmax | upstream_code | instruments/keysight33210A.py:134-138 |
| The output relay commands are ':OUTP OFF' and ':OUTP ON' | upstream_code | instruments/keysight33210A.py:171-176 |
| FUNC? reads the current waveform function | upstream_code | instruments/keysight33210A.py:69 |
| :OUTP:LOAD? reads the output termination | upstream_code | instruments/keysight33210A.py:105 |
| VOLT? reads the current amplitude | upstream_code | instruments/keysight33210A.py:128 |
| A setting is sent as 'COMMAND value', for example 'FREQ {frequency:.4e}' | upstream_code | instruments/keysight33210A.py:87 |
| The offset command is 'VOLT:OFFS {offset:.4f}V' | upstream_code | instruments/keysight33210A.py:142 |
| The duty cycle setter accepts 20 to 80 percent and only when the function is SQU | upstream_code | instruments/keysight33210A.py:148-153 |
| The DC voltage setter writes FUNC DC then VOLT:OFFS and bounds the value by the current Vmax | upstream_code | instruments/keysight33210A.py:163-168 |

## Limits

| parameter | command | limit | ref |
|---|---|---|---|
| frequency (Hz) | FREQ | 1e-3 to 10e6 | instruments/keysight33210A.py:29-30 |
| amplitude (V) | VOLT | operator_required: only amplitude > 0 is stated; the maximum depends on the load and output configuration | instruments/keysight33210A.py:95-96 (the positivity check) |
| offset (V) | VOLT:OFFS | operator_required: the bound depends on the current amplitude and the load-dependent Vmax | instruments/keysight33210A.py:134-138 (the dynamic check) |
| function | FUNC | one of SIN, SQU, RAMP, PULS, NOIS, DC, USER | instruments/keysight33210A.py:20 |
| load | :OUTP:LOAD | one of '50', 'INF' | instruments/keysight33210A.py:36 |
| output | :OUTP | one of ON, OFF | instruments/keysight33210A.py:171-176 |

The two operator-required bounds are supplied by `site-limits.example.json` on an example bench. The overlay may
only narrow a bound; the runtime refuses every write of an operator-required field until the site supplies one
(`MHS.SAFETY.LIMITS_UNSET`).

## Not covered

- Duty cycle (`FUNC:SQU:DCYC`): the upstream setter also requires the current function to be SQU. A declarative
  SCPI command map has no per-field precondition, so the field is not exposed. The instrument would still accept
  the command if it were sent, but the driver does not offer it.
- DC voltage (`set_dc_voltage`): the upstream method sends two commands and uses the Vmax of the last load query.
  The field is not exposed; the same function can be reached with `function=DC` and `offset`.
- The amplitude unit selection (`VOLT:UNIT VPP|VRMS|DBM`) is not exposed; the upstream constructor defaults to VPP,
  and the driver reports the amplitude in volts without changing that selection.
- Other instrument classes of the clone are not covered by this package.
- The readback queries `FREQ?`, `VOLT:OFFS?` and `:OUTP?` are the standard SCPI query forms of settings the upstream
  class only writes; the clone does not show those three queries. They were not tried on an instrument.

## Safety

The output relay is the one output this driver controls. The e-stop and the safe-state command are `:OUTP OFF`
(`instruments/keysight33210A.py:173`). The driver is at R1: the function generator's output is low energy and
reversible, and no independent hardware stop is claimed or required at R1. The package is model-authored and
unreviewed (`driver.lock.json` `reviewed_by` is null); no hardware backend was run.

Tags: function generator, keysight, agilent, 33210a, scpi
