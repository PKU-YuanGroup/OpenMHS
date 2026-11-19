# Facts and tags for gh.daylily-informatics/zebra_day

Every fact cites the pinned clone at commit `d46df53ff3d9b7fbe78aef837a5299656573ba14`.  The same facts are in
`driver.py` (`facts = [...]`); the generated reference is built from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| send_command opens one AF_INET/SOCK_STREAM socket per call, connects to the printer address and port, sends the encoded command with sendall, reads one recv and returns the decoded reply; TimeoutError, ConnectionRefusedError and OSError are caught and become None | upstream_code | zebra_day/cmd_mgr.py:31-41 |
| get_host_identification sends ~HI and parses a comma-separated reply into model, firmware, dpi, memory and options | upstream_code | zebra_day/cmd_mgr.py:60-82 |
| get_serial_number sends ~HQSN and returns the first non-header line of the reply | upstream_code | zebra_day/cmd_mgr.py:84-100 |
| get_error_status sends ~HQES and returns the first non-header line as raw, with errors and warnings left as empty lists because the flag parsing is not implemented | upstream_code | zebra_day/cmd_mgr.py:102-133 |
| get_odometer sends ~HQOD and parses LABEL: and TOTAL INCHES: values into label_count and total_inches | upstream_code | zebra_day/cmd_mgr.py:135-170 |
| get_host_status sends ~HS and parses paused, paper_out, head_up and ribbon_out from the first comma-separated line | upstream_code | zebra_day/cmd_mgr.py:172-211 |
| get_configuration sends ^XA^HH^XZ; set_configuration sends the supplied configuration body and then ^XA^JUS^XZ to save it | upstream_code | zebra_day/cmd_mgr.py:43-54 |
| get_full_status queries host identification, serial number, error status, odometer and host status, and stamps the result with time.time() | upstream_code | zebra_day/cmd_mgr.py:213-276 |
| The hardware guide says network-attached Zebra printers that obtain an IP address and accept ZPL are supported, and that USB-only printers are not communicated with | vendor_doc | zebra_day/docs/hardware_config_guide.md:6-7 |
| The hardware guide's initial printer configuration list includes increasing the darkness and decreasing print speed to 2 or 3 IPS | vendor_doc | zebra_day/docs/hardware_config_guide.md:64-66 |
| The ZD620/ZD420 user guide lists both shutdown and delayed sleep after a 4-9 second POWER-button hold, and automatic power-on in Power Failure Recovery Mode | vendor_doc | zebra_day/docs/zd620-zd420-ug-en.pdf:57 |
| The ZD620/ZD420 user guide documents PAUSE stopping print and media movement after the current label and CANCEL cancelling the next format, or all pending formats while paused | vendor_doc | zebra_day/docs/zd620-zd420-ug-en.pdf:59 |
| The ZD620/ZD420 user guide warns that the printhead may be hot and could cause severe burns | vendor_doc | zebra_day/docs/zd620-zd420-ug-en.pdf:62 |

The model review read PDF pages 57, 59 and 62 locally. The gate still reports these binary citations as
`UNVERIFIABLE_CITATION` under the strict collector; no signature or waiver is applied by the model review.

## Limits

There is no numeric bound.  The only write is the raw ZPL configuration body of `set_configuration` (the upstream
interface itself takes a string); no text of the clone or the cited manual states a bound for that string.  The
driver therefore does not invent one.  It is not an `operator_required` numeric field because it is not numeric.
The raw string can include print commands as well as darkness or speed settings, so it is not a bounded
configuration interface. `set_configuration` discards the first command's result and returns only the save
command's result (`zebra_day/cmd_mgr.py:47-54`); `send_command` swallows transport errors as `None`
(`zebra_day/cmd_mgr.py:31-41`). The driver therefore reports an unknown outcome for configuration writes,
including the fake's unacknowledged write, rather than claiming the configuration was applied.

## Safety and stop

`risk = "R2"`: the user guide warns that the printhead can be hot and cause severe burns (page 62).
The POWER-button table lists delayed sleep after the current job, shutdown and Power Failure Recovery Mode
with automatic power-on (page 57); it does not establish an independent emergency stop for this package.
PAUSE completes the current label and can resume queued jobs when pressed again; CANCEL is functional only
while paused (page 59). The unverified `~JA` command and its fake cancellation behaviour have been removed.
The `@estop` now reports `MHS.SAFETY.SAFE_STATE_UNREACHED`, keeping the endpoint latch engaged without claiming
that printing or heating stopped. No `estop_physical_ref` or `@reset` hook is declared. This hardware route
remains blocked pending a source-backed, acknowledged stop and a bounded configuration interface.

Tags: zebra, label-printer, zpl, tcp, printer, status, configuration
