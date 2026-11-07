# Facts and tags for gh.andmorifa/instrument-control-python

Every fact cites its source at commit `0622a4aee5cf8b7a4704711d1fdf81fe35b0b6ff`.  The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| RedPitayaClient is a class for SCPI communication with Red Pitaya hardware over TCP/IP | upstream_code | src/redpitaya_client.py:9-13 |
| connect opens an AF_INET/SOCK_STREAM socket, sets is_connected True after connecting, and sets it False and re-raises when the connection fails | upstream_code | src/redpitaya_client.py:30-39 |
| send_cmd appends CRLF to the command and sends it as UTF-8 bytes | upstream_code | src/redpitaya_client.py:50-52 |
| query sends the command and returns the decoded, stripped response read from the socket | upstream_code | src/redpitaya_client.py:55-62 |
| close closes the socket and sets is_connected to False | upstream_code | src/redpitaya_client.py:64-71 |
| get_mock_data generates a synthetic sine wave with noise for testing without physical hardware | upstream_code | src/redpitaya_client.py:73-81 |
| The README names SCPI over TCP/IP as the protocol and a Mock Mode that simulates signal acquisition without physical hardware | vendor_doc | README.md:17-19 |

Limits: none.  The driver has a boolean read and a string invoke input; there is no numeric write or invoke input to
bound.  The clone states no numeric device limit, and none is invented.

Safety: the native stop is `RedPitayaClient.close` (`src/redpitaya_client.py:64-71`).  It closes the TCP socket and
clears `is_connected`, so `send_cmd` refuses further commands (`src/redpitaya_client.py:47-48`).  An operator reset
runs `reconnect`, which calls the upstream `connect` and opens a new socket (`src/redpitaya_client.py:26-39`).  No
independent hardware e-stop is documented in the clone, and the card's risk floor is R0, so `estop_physical_ref` is
not set and no hardware protection is claimed.  This package is model-authored and unreviewed; `reviewed_by` stays
null.

The clone has no device-specific command table or acquisition command; the only command text is the reset example
`GEN:RST` in the send_cmd docstring (`src/redpitaya_client.py:44`).  `get_mock_data` generates synthetic test data,
not a measurement, so it is not exposed as a read.  The package exposes the upstream's generic query path as the
extension `x-cap.andmorifa.scpi_query.v1`; the caller supplies the SCPI command and the driver forwards it verbatim.

Tags: red pitaya, scpi, tcp, signal acquisition, connection
