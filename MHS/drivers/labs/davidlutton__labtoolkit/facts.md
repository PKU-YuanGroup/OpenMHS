# Facts and tags for gh.davidlutton/labtoolkit

Every fact cites its source at commit `1c27b35490002822f9860f45a86235cce949c172`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The registry maps the Agilent PSA models E4440A, E4443A, E4445A, E4447A, E4446A and E4448A to AgilentE44nn | upstream_code | src/labtoolkit/drivers.py:94-99 |
| AgilentE44nn wraps a pyvisa instrument: __init__ stores it in self.inst, sets the read and write termination to a newline and calls __post__ | upstream_code | src/labtoolkit/Instrument.py:13-21 |
| The upstream loader opens the VISA resource and passes it to the driver class: driver(self.rm.open_resource(instrument.Resource)) | upstream_code | src/labtoolkit/__init__.py:96-99 |
| IDN is the *IDN? query reply | upstream_code | src/labtoolkit/IEEE488.py:36-38 |
| frequency_center reads :FREQuency:CENT? and writes :FREQuency:CENT; frequency_span reads :FREQuency:SPAN? and writes :FREQuency:SPAN | upstream_code | src/labtoolkit/SpectrumAnalyser/AgilentE44nn.py:58-74 |
| The trace's frequency axis is labelled 'Frequency (Hz)' and is built from frequency_start, frequency_stop and sweep_points | upstream_code | src/labtoolkit/SpectrumAnalyser/AgilentE44nn.py:338-346 |
| sweep_points reads :SWEep:POINts? and writes :SWEep:POINts as a whole number; the class's comment gives the E4440A range 101 to 8192 points, and 2 to 8192 in zero span | upstream_code | src/labtoolkit/SpectrumAnalyser/AgilentE44nn.py:99-104 |
| resolution_bandwidth reads :BANDwidth:RESolution? and writes it with the setter's unit keyword, which states 'Hz' | upstream_code | src/labtoolkit/SpectrumAnalyser/AgilentE44nn.py:158-171 |
| video_bandwidth reads :BANDwidth:VIDeo? and writes :BANDwidth:VIDeo | upstream_code | src/labtoolkit/SpectrumAnalyser/AgilentE44nn.py:173-184 |
| continuous reads :INIT:CONTinuous? through query_bool and writes it as a boolean | upstream_code | src/labtoolkit/SpectrumAnalyser/AgilentE44nn.py:242-248 |
| The README's manual driver demo opens GPIB0::18::INSTR with pyvisa and passes the resource to AgilentE44nn | vendor_doc | README.md:46-47 |
| The README sets frequency_center to 1e9, frequency_span to 10e6 and sweep_points to 8192 in its demo | vendor_doc | README.md:49-51 |
| The trace data is read as binary values after FORM:DATA REAL,32 and FORM:BORD SWAP, by TRAC:DATA? TRACE1 | upstream_code | src/labtoolkit/SpectrumAnalyser/AgilentE44nn.py:289-300 |
| The README returns the trace as a DataFrame of the trace data | vendor_doc | README.md:53-54 |

## Limits

- `sweep_points` (writable state field, integer): `Limit(min=101, max=8192, source=upstream_code,
  ref=src/labtoolkit/SpectrumAnalyser/AgilentE44nn.py:101-102)`. The comment in the setter gives the E4440A range
  "101 to 8192, 2 to 8192 in zero span"; declaring the minimum as 101 refuses 2 to 100 points in zero span as well,
  which narrows the accepted values rather than widening them.
- `frequency_center`, `frequency_span`, `resolution_bandwidth`, `video_bandwidth` (writable state fields):
  `Limit.operator_required`. No line of the clone states a frequency or a bandwidth range of the E44nn family: the
  registry maps six PSA models whose top frequencies run from 6.7 GHz to 50 GHz
  (src/labtoolkit/drivers.py:94-99) and the class does not report which one is attached, and the bandwidth comments
  in the class name the N9030B, another model (src/labtoolkit/SpectrumAnalyser/AgilentE44nn.py:161-165, 176-177).
  The site supplies the range of its analyser (`site-limits.example.json` shows the overlay; until then every call
  that sets one of the four fields is refused `MHS.SAFETY.LIMITS_UNSET`).
- `continuous` (writable state field, boolean): no numeric bound, so no limit.

## Safety

The analyser measures and actuates nothing outside its own settings; the driver has no interlock and no permit. The
native stop is the continuous sweep switched off: `@estop` sets the upstream `continuous` property to False
(`INIT:CONTinuous OFF`, src/labtoolkit/SpectrumAnalyser/AgilentE44nn.py:242-248), and the safe-state action
`x-cap.davidlutton.stop_sweep.v1` (`safe_state=True`, no input) makes the same call so the runtime has a declared
safe state. `estop_physical_ref` is not set: no line of the clone documents an independent hardware stop, and the
card's risk floor is R1, so SAFE-045 (R2 and above) does not apply.

## Not covered

The trace itself: `trace_data` reads the analyser's binary trace array
(src/labtoolkit/SpectrumAnalyser/AgilentE44nn.py:289-300) and the README returns it as a DataFrame
(README.md:53-54); this package exposes the sweep settings only and no measurement value. The amplitude settings
(reference level, input attenuation, the power unit and the detector) and the screenshot method are not exposed
either.

Tags: spectrum-analyser, psa, scpi, sweep, spectrum
