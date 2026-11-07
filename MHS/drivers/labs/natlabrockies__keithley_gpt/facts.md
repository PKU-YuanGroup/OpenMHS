# Facts and tags for gh.natlabrockies/keithley_gpt

Every fact cites its source at commit `4cad464fd26eac9684d3b2df8ed88c17a6dff972`: `upstream_code`
(`path/in/clone.py:LINE`) or `vendor_doc` (a text file of the clone). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The upstream controller class is Keithley2400Controller | upstream_code | Keithley2400GPT.py:3 |
| identify() returns the reply to the SCPI identity query *IDN? | upstream_code | Keithley2400GPT.py:17-18 |
| Measurement mode 2 selects 2-wire sensing with ':SYST:RSEN OFF'; mode 4 selects 4-wire sensing with ':SYST:RSEN ON' | upstream_code | Keithley2400GPT.py:28-34 |
| set_current_compliance writes ':SENS:CURR:PROT <compliance>' | upstream_code | Keithley2400GPT.py:118-120 |
| set_source_current_range writes ':SOUR:CURR:RANG <range>' | upstream_code | Keithley2400GPT.py:106-107 |
| set_source_voltage_range writes ':SOUR:VOLT:RANG <range>' | upstream_code | Keithley2400GPT.py:109-110 |
| set_measure_current_range writes ':SENS:CURR:RANG <range>' | upstream_code | Keithley2400GPT.py:112-113 |
| set_measure_voltage_range writes ':SENS:VOLT:RANG <range>' | upstream_code | Keithley2400GPT.py:115-116 |
| set_nplc writes ':SENS:CURR:NPLC <nplc>' for CURR and ':SENS:VOLT:NPLC <nplc>' for VOLT | upstream_code | Keithley2400GPT.py:122-128 |
| iv_sweep enables the source output with ':OUTP ON' and disables it after the reading with ':OUTP OFF' | upstream_code | Keithley2400GPT.py:94-99 |
| The README names the device a Keithley 2400 series Source Measure Unit (SMU) | vendor_doc | README.md:3 |

## Limits

The clone writes every numeric setting but states no compliance, range or NPLC bound. The source current range,
source voltage range, measurement current range, measurement voltage range, current compliance and both NPLC
settings therefore use `Limit.operator_required`: a write is refused with `MHS.SAFETY.LIMITS_UNSET` until an
operator supplies the bench bounds in `site-limits.json`. `site-limits.example.json` is an example overlay only.

The 2-/4-wire sensing mode is the boolean `four_wire`: the clone maps mode 2 to `:SYST:RSEN OFF` and mode 4 to
`:SYST:RSEN ON` (Keithley2400GPT.py:28-34), and the SCPI line is what this driver writes.

The read-back queries (`:SENS:CURR:PROT?`, `:SOUR:VOLT:RANG?`, and so on) are the standard query forms of the
commands the clone writes; the clone itself only shows the setting form and the `*IDN?` query. They have not been
tried on an instrument.

## Safety

The source output is off in the driver's declared safe state. The e-stop writes `:OUTP OFF`
(Keithley2400GPT.py:99). The upstream enables the output only inside `iv_sweep` (`:OUTP ON`, line 95); this driver
does not bind `iv_sweep` and has no output-on command, so its capabilities only configure ranges, compliance,
sensing mode and integration time. The clone states no hardware e-stop and none is needed at R1.

The upstream constructor's `resource_name` and `timeout` arguments (Keithley2400GPT.py:4) are configuration
defaults, not device bounds. The hardware backend is opened with the operator's `visa_resource` (or `host`/`port`)
option; the package does not import the upstream module.

Tags: source measure unit, smu, keithley 2400, scpi
