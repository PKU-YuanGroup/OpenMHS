# Facts and limits for gh.valiantandupright/oscilloscope-mcp

Every fact below cites the clone at `20c25de5a2f01cdf037b10c7d68a170bc233f4c4`. The table matches driver.py; generated references come from that driver.

| fact | source | ref |
|---|---|---|
| The project targets a Keysight DSOX1204A and other benchtop oscilloscopes supporting USBTMC and SCPI | vendor_doc | README.md:34 |
| The module is the SCPI driver layer of the Keysight InfiniiVision series and depends only on pyvisa over NI-VISA USBTMC | upstream_code | osc/scope.py:1-4 |
| The connection is a pyvisa ResourceManager and an open VISA resource with newline terminators and a timeout from config.TIMEOUT_MS | upstream_code | osc/scope.py:122-131 |
| The SCPI timeout defaults to 10000 ms and can be overridden with SCOPE_TIMEOUT_MS | upstream_code | osc/config.py:31-32 |
| write sends one command line and query returns one stripped reply line | upstream_code | osc/scope.py:158-170 |
| identify queries *IDN? and splits the reply into manufacturer, model, serial and firmware | upstream_code | osc/scope.py:185-194 |
| status reads the timebase, all channels, the edge trigger and the acquisition type and points | upstream_code | osc/scope.py:206-239 |
| autoscale, run, stop and single send :AUToscale, :RUN, :STOP and :SINGle | upstream_code | osc/scope.py:242-252 |
| configure_channel writes scale, offset, coupling, display and probe ratio on a channel | upstream_code | osc/scope.py:254-274 |
| ChannelSetting documents scale in V/div and offset in V | upstream_code | osc/scope.py:94-101 |
| configure_timebase sets the mode and the s/div scale and position in seconds | upstream_code | osc/scope.py:276-288 |
| configure_trigger writes the edge source, level, slope and sweep | upstream_code | osc/scope.py:290-304 |
| capture asks for :WAVeform:POINts?, transfers :WAVeform:DATA? as 8-bit samples, converts the preamble and decimates the envelope using max_return | upstream_code | osc/scope.py:307-386 |
| The clone declares NO_MEASUREMENT=9.9e36 for measurements that cannot be made | upstream_code | osc/scope.py:38-40 |
| The numeric parser returns None for an absent or unparsable value and values whose absolute value is at least half of NO_MEASUREMENT | upstream_code | osc/scope.py:60-70 |
| measure queries :MEASure:<item>? CHANnel<n> for each requested item | upstream_code | osc/scope.py:388-405 |
| The V/div table spans 1 mV/div to 5 V/div and the s/div table 2 ns/div to 50 s/div in 1-2-5 steps | upstream_code | osc/scales.py:15-23 |
| The web control accepts coupling DC/AC, slope POS/NEG/EITH, sweep AUTO/NORM, timebase mode MAIN/XY/ROLL, and probe ratios 1/10/100/1000 | upstream_code | web/server.py:119-123 |
| The web trigger-source parser accepts CHANNELn or CHANn when n is within config.CHANNEL_COUNT, plus EXT | upstream_code | web/server.py:157-170 |
| The channel count is configurable with SCOPE_CHANNEL_COUNT and defaults to four | upstream_code | osc/config.py:34-36 |
| errors queries :SYSTem:ERRor? up to 32 times, stops at a reply beginning +0 and returns other replies | upstream_code | osc/scope.py:196-204 |
| The web control clamps a trigger level to -1000 V and 1000 V before sending it | upstream_code | web/server.py:224-225 |
| The clone requests 2000 waveform points and decimates to at most 500 by default | upstream_code | osc/config.py:38-42 |
| A logged session shows the automatic measurement commands as :MEASure:VPP? CHANnel1 and :MEASure:FREQuency? CHANnel1 | vendor_doc | README.md:418-420 |

## Scope and limits

The package serves channel-1 configuration plus scalar measurements, channel/timebase/trigger actions and waveform capture. The PNG screenshot is omitted because this package has no artifact store. Capture returns the upstream envelope-decimated data and its approximate decimated time axis (osc/scope.py:361-366); it is not a trace of the exact original extremum timestamps. Default point counts are configurable upstream values, not fixed device limits. The fake returns eight placeholder samples.

Channel indices and trigger sources are operator_required: osc/config.py:34-36 makes channel count configurable, and the former citation to channel colours was not a bound. Trigger level is also operator_required; the web control's +/-1000 V guard is not an instrument rating. Vertical scale, offset, timebase scale and position remain operator_required. The example overlay contains illustrative values only and does not qualify an installed instrument.

## Stop and error handling

Every setting/acquisition command checks the upstream error queue. Capture errors returned in warnings fail the command rather than disappearing, and missing acquisition metadata is refused rather than replaced with zero or empty arrays. STOP is accepted only after an empty error queue; there is no upstream acquisition-state query, so safe_state reports command acceptance and the latch, not sensed quiescence or electrical isolation. The shared VISA lock and up to 32 error queries can exceed the endpoint stop budget; that run must remain failed and latched. This package controls no source output.

The clone has no licence file; its NOASSERTION licence and publish_review=required remain publication decisions for the owner. The hardware factory was read as source only. Evidence is contract_checked on a stand-in fake; reviewed_by remains null.
