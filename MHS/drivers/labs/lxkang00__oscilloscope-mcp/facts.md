# Facts and tags for gh.lxkang00/oscilloscope-mcp

Every fact and limit cites the pinned clone at commit `3eebcdfb3c339d7038b80a9a31573538bc84a331`. The selected
source file is `server.py`. The source and every limit are also written into `driver.py`; `reference.json` is
generated from the driver, not from this page.

## Scope and shape

The card names `McpClientDriver`, but the pinned server does not register one decorated function per tool. It
publishes a `TOOLS` list and dispatches a generic `call_tool` through `HANDLERS` (`server.py:1327-1352`). The
McpClientDriver source proof requires a unique top-level function with a literal `@<receiver>.tool()` decorator
for every selected tool, so it cannot be used for this pin. DEVIATION FROM THE CARD: this package is a direct
`Driver` over the upstream `server:OscilloscopeConnection` class (`server.py:99-225`) and sends the same SCPI
commands the handlers send. The card's `family-config`/`mcp-client` helper is not changed in `task.json`, which
is read-only.

The exposed surface is the primary oscilloscope control: identity, run/stop/autoset/force-trigger/reset,
channel, timebase, trigger, acquisition, automatic measurements and statistics, waveform metadata, display,
cursors, math, digital, setup save/recall, frequency counter, status and the error queue. The raw
`send_command` escape is not bound. The waveform array and screenshot are not bound: `get_waveform_data`
returns only a text summary (`server.py:889-941`) and `get_screenshot` writes a local file and returns a
200-character base64 prefix (`server.py:943-1047`). NOT COVERED: the waveform sample array, the screenshot
image and the arbitrary-SCPI `send_command` tool.

## Facts

| fact | source | ref |
|---|---|---|
| The pinned server is one MCP server script that controls a Siglent SDS2000X Plus over raw TCP SCPI on port 5024. | upstream_code | server.py:1-9 |
| SCPI_PORT is 5024. | upstream_code | server.py:47 |
| OscilloscopeConnection is a persistent TCP socket wrapper with connect, disconnect, send, query and safe_query. | upstream_code | server.py:99-170 |
| send() appends a newline and reads a response when the command contains a question mark. | upstream_code | server.py:148-157 |
| query() appends a question mark when the command does not end with one. | upstream_code | server.py:159-163 |
| measure passes ':MEASure:<item>? <source>', which ends with the source and not with a question mark, to query(). | upstream_code | server.py:844 |
| get_id queries *IDN?. | upstream_code | server.py:651-652 |
| run and stop send :RUN and :STOP; neither queries a stopped state. | upstream_code | server.py:663-670 |
| reset sends *RST and sleeps for three seconds. | upstream_code | server.py:655-658 |
| configure_channel writes display, invert, scale, offset, coupling, bandwidth limit, probe, skew, unit and label commands under :CHANnelN:. | upstream_code | server.py:686-716 |
| get_channel queries eight channel settings; the pinned handler swallows each query error as N/A. | upstream_code | server.py:719-732 |
| configure_timebase writes :TIMebase:SCALe, :DELay and :MODE, and get_timebase queries them. | upstream_code | server.py:737-749 |
| configure_trigger writes sweep and type first and then source, level, slope and coupling under the selected trigger type; holdoff is written under :TRIGger:HOLDoff. | upstream_code | server.py:754-785 |
| configure_acquisition writes mode, memory depth and interpolation under :ACQuire: and average count under :ACQuire:AVERage. | upstream_code | server.py:809-819 |
| measure sends :MEASure:<item>? <sources>, or :MEASure:ALL? for the ALL item. | upstream_code | server.py:834-846 |
| get_measure_stats queries count, mean, min, max and standard deviation. | upstream_code | server.py:849-857 |
| get_waveform_preamble sends :WAVeform:SOURce and queries :WAVeform:PREamble?, parsing ten comma-separated fields. | upstream_code | server.py:867-886 |
| get_waveform_data requests ASCII data and returns only a text summary with min, max, mean and the first and last ten values; it does not return the array. | upstream_code | server.py:889-941 |
| get_screenshot writes a PNG to a local file and returns only a 200-character base64 prefix. | upstream_code | server.py:943-1047 |
| configure_display, configure_cursors, get_cursor_values, configure_math and configure_digital write the corresponding :DISPlay, :CURSor, :MATH and :DIGital subsystems. | upstream_code | server.py:1049-1150 |
| save_setup and recall_setup validate a 1-40 character filename and send :STORe:SETup or :RECAll:SETup with the resulting path. | upstream_code | server.py:1160-1185 |
| get_frequency_counter queries :COUNter:CURRent?, :COUNter:MODE? and :COUNter:SOURce?. | upstream_code | server.py:1188-1199 |
| get_status queries acquisition state, trigger state, *OPC? and *ESR?. | upstream_code | server.py:1202-1210 |
| get_next_error queries :SYSTem:ERRor?. | upstream_code | server.py:1212-1217 |
| list_tools returns TOOLS and call_tool dispatches HANDLERS by name; the tools are not separate decorated functions. | upstream_code | server.py:1327-1352 |
| send_command passes the caller's command string unchanged to send(), an arbitrary SCPI escape. | upstream_code | server.py:647-648 |
| The socket reader returns what it has read, possibly an empty string, when the reply times out. | upstream_code | server.py:185-205 |
| _sanitize_label rejects semicolons and enforces at most 20 characters. | upstream_code | server.py:64-71 |
| _validate_filename accepts only 1-40 letters, digits, spaces, hyphens and underscores. | upstream_code | server.py:74-83 |
| The channel input schema declares minimum 1 and maximum 4. | upstream_code | server.py:295 |
| The get_channel input schema declares minimum 1 and maximum 4. | upstream_code | server.py:316 |
| The display intensity input schema declares minimum 0 and maximum 100. | upstream_code | server.py:482 |

## Limits

| input | bound | source | ref |
|---|---|---|---|
| configure_channel `channel` | 1 to 4 | upstream_code | server.py:295 (`minimum: 1`, `maximum: 4`) |
| get_channel `channel` | 1 to 4 | upstream_code | server.py:316 (`minimum: 1`, `maximum: 4`) |
| configure_display `intensity` | 0 to 100 | upstream_code | server.py:482 (`minimum: 0`, `maximum: 100`) |
| configure_channel `scale`, `offset`, `probe`, `skew` | `Limit.operator_required` | none | the tool schema has descriptions but no numeric range (server.py:297-306) |
| configure_timebase `scale`, `delay` | `Limit.operator_required` | none | the tool schema has descriptions but no numeric range (server.py:326-330) |
| configure_trigger `level`, `holdoff` | `Limit.operator_required` | none | the tool schema has descriptions but no numeric range (server.py:354-357) |
| configure_acquisition `average_count` | `Limit.operator_required` | none | the description says 4-1024 (server.py:382) but the schema declares no minimum or maximum, so the description is not used as an enforced limit |
| configure_math `scale`, `offset` | `Limit.operator_required` | none | the tool schema has descriptions but no numeric range (server.py:523-524) |
| configure_digital `position`, `height`, `threshold` | `Limit.operator_required` | none | the tool schema has descriptions but no numeric range (server.py:537-543) |

`site-limits.example.json` is an example operator overlay only. Its numbers are one bench's choices, not
Siglent specifications, and a deployment must replace them.

## Risk

R0, checked against `MHS/spec/04-safety.md` section 2.1: R0 is data only with no physical effect. Every
exposed write changes how the scope acquires, triggers, displays or measures its own inputs; none sources a
signal, moves anything, dispenses or heats. The worst consequences are a wrong configuration, undone by
reconfiguring, and loss of an unsaved on-screen acquisition during run, autoset or reset. The raw
`send_command` escape could reach arbitrary SCPI but is deliberately not bound.

## Stop path

The e-stop sends `:STOP` and then requires a fresh `:TRIGger:STATus?` of `STOP`; it is not a proof that an
in-flight SCPI command or a pending front-panel operation has ended. The pinned `stop` tool itself sends
`:STOP` and returns a fixed text without reading back (`server.py:668-670`). At R0 this stop is a recovery
path, not a safety-rated interlock.

Tags: oscilloscope, scpi, siglent, mcp-server, fake-only
