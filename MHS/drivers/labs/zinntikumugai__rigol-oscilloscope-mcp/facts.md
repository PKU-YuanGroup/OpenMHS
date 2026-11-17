# Facts and limits for gh.zinntikumugai/rigol-oscilloscope-mcp

Every fact below cites the clone at `54a1061e23910d31cb30335fa76600409d92b951`. The table matches driver.py; generated references come from that driver.

| fact | source | ref |
|---|---|---|
| ScopeDriver is the profile-driven driver that turns semantic operations into RIGOL SCPI and parses the replies | upstream_code | src/rigol_oscilloscope_mcp/driver/scope.py:836-837 |
| identify queries *IDN? and splits the reply into manufacturer, model, serial and firmware | upstream_code | src/rigol_oscilloscope_mcp/driver/scope.py:895-909 |
| get_channel reads the display, vertical scale, offset, coupling, impedance, probe ratio and bandwidth limit of one channel | upstream_code | src/rigol_oscilloscope_mcp/driver/scope.py:955-971 |
| get_timebase reads the main timebase scale and offset and the sample rate and memory depth | upstream_code | src/rigol_oscilloscope_mcp/driver/scope.py:978-987 |
| get_trigger reads the current trigger type's subtree plus the sweep mode and trigger status | upstream_code | src/rigol_oscilloscope_mcp/driver/scope.py:1025-1046 |
| measure queries :MEASure:ITEM? for each requested item and reports a sentinel value as unknown | upstream_code | src/rigol_oscilloscope_mcp/driver/scope.py:1082-1129 |
| configure_trigger writes the trigger mode first when asked, then each requested subtree item, and reads every setting back | upstream_code | src/rigol_oscilloscope_mcp/driver/scope.py:1449-1518 |
| set_channel_scale writes :CHANnelN:SCALe and returns the read-back value | upstream_code | src/rigol_oscilloscope_mcp/driver/scope.py:1358-1364 |
| set_timebase_scale writes :TIMebase:MAIN:SCALe and returns the read-back value | upstream_code | src/rigol_oscilloscope_mcp/driver/scope.py:1435-1439 |
| run writes :RUN and stop writes :STOP through the checked SCPI session | upstream_code | src/rigol_oscilloscope_mcp/driver/scope.py:3353-3357 |
| get_trigger_status queries :TRIGger:STATus? and strips and uppercases its reply | upstream_code | src/rigol_oscilloscope_mcp/driver/scope.py:1050-1052 |
| write_checked writes the command then calls check_error, which queries ERROR_QUERY and raises ScopeError on an error reply | upstream_code | src/rigol_oscilloscope_mcp/driver/session.py:96-122 |
| The generic profile declares four analog channels, the measurements frequency, period, vpp, vmax and vmin, edge trigger, screenshot and waveform download | upstream_code | src/rigol_oscilloscope_mcp/profiles/data/rigol-generic.yaml:6-24 |
| The screenshot and waveform reads return IEEE 488.2 binary blocks through query_binary | upstream_code | src/rigol_oscilloscope_mcp/driver/scope.py:1307-1346 |
| read_waveform writes the waveform source, mode and format, reads the preamble and then transfers :WAVeform:DATA? as a binary block | upstream_code | src/rigol_oscilloscope_mcp/driver/scope.py:1326-1346 |
| The LAN transport is a raw TCP socket whose default port is 5555 | upstream_code | src/rigol_oscilloscope_mcp/transport/lan.py:20-34 |
| The upstream connection resolves the model profile from the *IDN? reply and builds a ScopeDriver over the session | upstream_code | src/rigol_oscilloscope_mcp/service/connection.py:169-172 |

## Scope and limits

Channel 1, timebase, trigger status, five scalar measurement items, edge-trigger configuration and acquisition run/stop are served. The trigger action explicitly selects edge mode before applying supplied settings. Waveform and screenshot arrays, AFG, decode, math, cursor, histogram, meter and reference subsystems are omitted. An AFG output enabled elsewhere is unchanged by this package's stop.

Continuous vertical/timebase ranges and trigger level/holdoff are operator_required. The example overlay is illustrative only. Couplings, slopes and sweeps cite the clone's explicit token tables. The source list is a supported subset of the source parser's forms; the resolved model profile still validates analog channel count.

## Stop and native adapter

The e-stop and safe-state action send the checked native STOP and require get_trigger_status() to report STOP. A missing or different status fails with the latch held. This confirms the reported acquisition status only, not electrical isolation or any AFG state.

The source-only factory inspection verified LAN/USB constructor arguments, error-queue drain, identification and model-profile selection. Its transport wrapper serializes complete request/reply transactions because upstream transport buffers have no lock. A stop may wait for a query timeout and exceed the endpoint stop budget; no independent stop channel is claimed. Teardown closes session.transport. Adapter-only tests exercise the package wrapper without calling connect() or importing the upstream package.

The cited clone carries MIT. Evidence is contract_checked on the fake; reviewed_by remains null. No instrument or upstream code was run.
