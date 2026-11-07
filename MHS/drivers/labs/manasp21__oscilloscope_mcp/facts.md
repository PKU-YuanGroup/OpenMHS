# Facts and tags for gh.manasp21/oscilloscope_mcp

Every fact cites its source at commit `49b9c4a7b06b0a98688f5f9cd689ec21c25d3eeb`.  The same facts are written
into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.
`upstream_code` is a file and line of the clone; `vendor_doc` is the clone's README.

| fact | source | ref |
|---|---|---|
| EthernetOscilloscope is a stub: its constructor logs that Ethernet is not implemented and every method delegates to a SimulatedOscilloscope | upstream_code | src/oscilloscope_mcp/hardware/ethernet_backend.py:18-55 |
| The simulated oscilloscope initializes four channels with a default timebase and trigger | upstream_code | src/oscilloscope_mcp/hardware/simulation.py:39-70 |
| configure_channels raises ValueError for a channel outside range(4) | upstream_code | src/oscilloscope_mcp/hardware/simulation.py:88-91 |
| set_timebase clamps the sample rate to max_sample_rate and the record length to max_memory_depth | upstream_code | src/oscilloscope_mcp/hardware/simulation.py:121-129 |
| The capability record states max_sample_rate 1e9, max_bandwidth 500e6, max_channels 4 and max_memory_depth 1e9 | upstream_code | src/oscilloscope_mcp/hardware/base.py:178-182 |
| The capability record states a voltage range of 0.001 to 100.0 and lists DC, AC and GND coupling and 50 and 1M impedance | upstream_code | src/oscilloscope_mcp/hardware/base.py:183-186 |
| The supported trigger types are edge, pulse, pattern and protocol | upstream_code | src/oscilloscope_mcp/hardware/base.py:187 |
| get_status reports initialized, acquisition_active, channels, timebase and trigger_config | upstream_code | src/oscilloscope_mcp/hardware/simulation.py:269-277 |
| setup_trigger stores the source, type, level, edge and holdoff in trigger_config | upstream_code | src/oscilloscope_mcp/hardware/simulation.py:152-158 |
| acquire_waveform builds waveform_data with a shared time axis and per-channel voltage arrays | upstream_code | src/oscilloscope_mcp/hardware/simulation.py:212-260 |
| stop_acquisition sets acquisition_active to False | upstream_code | src/oscilloscope_mcp/hardware/simulation.py:264-267 |
| cleanup stops the acquisition before marking the oscilloscope uninitialized | upstream_code | src/oscilloscope_mcp/hardware/simulation.py:279-283 |
| The README describes multi-channel acquisition with 4 channels and configurable sample rates | vendor_doc | README.md:8 |

Limits: the sample-rate maximum (1e9), record-length maximum (1e9), voltage range (0.001 to 100.0 V), coupling set
(DC, AC, GND), impedance set (50, 1M) and channel set (0 to 3) come from the capability record and the simulated
backend's channel check.  The trigger level, trigger holdoff and acquisition timeout have no bound in the clone:
they are `Limit.operator_required`, and `site-limits.example.json` shows an operator overlay that fills them.

Safety: the e-stop and the safe-state action `x-cap.manasp21.stop_acquisition.v1` both call the native
`stop_acquisition` (simulation.py:264-267).  The upstream Ethernet backend is a simulation stub, so no independent
hardware e-stop is documented; this R1 package declares no `estop_physical_ref` and claims no hardware run.

NOT COVERED: the waveform array.  The clone returns a `record_length`-long time axis and per-channel voltage arrays
(simulation.py:212-260); no catalogue class carries a trace array, so the package exposes only the settings, the
status and a scalar summary of one acquired channel.

Tags: oscilloscope, instrument, acquisition, simulation, asyncio
