# Facts and tags for gh.tongji-cdi/temi

Every fact cites its source at commit `ec0a395405df1583d3357fd944b0c43396b30a7c`: `vendor_doc` (a text file of the
clone) or `upstream_code` (`path/in/clone.py:LINE`).  The same facts are written into `driver.py` (`facts = [...]`);
the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The README describes the package as an unofficial Python library for remote-controlling the Temi robot via WebSocket | vendor_doc | README.md:2 |
| A Temi-side Android application creates a WebSocket server at ws://TEMI_IP:8175 and waits for connections from the Python API | vendor_doc | src/temi/README.md:2-3 |
| The client is constructed with the WebSocket URI of the Temi server: Temi(uri) | upstream_code | src/temi/api.py:9-11 |
| connect() retries with a default of 3 tries and 5 s between tries, then raises | upstream_code | src/temi/api.py:36-52 |
| Every command is a JSON object with a command name and a generated UUID id, and the reply must carry the same id | vendor_doc | src/temi/README.md:5-14 |
| command() sends the JSON over a new WebSocket connection and waits for a reply with the same id | upstream_code | src/temi/api.py:84-109 |
| The speak command takes a sentence and is answered with the id only | vendor_doc | src/temi/README.md:16-31 |
| The ask command speaks a sentence and answers with the recognized reply in an answer field | vendor_doc | src/temi/README.md:33-48 |
| The goto command names a saved location and answers with success true when Temi reached it and false otherwise | vendor_doc | src/temi/README.md:50-68 |
| The API format documents raise_head with an angle field | vendor_doc | src/temi/README.md:70-84 |
| The README lists turn by an angle and states no unit or range for it | vendor_doc | README.md:57-59 |
| The README states a screen tilt range of -25 to 55, gives no unit and then shows a turn call | vendor_doc | README.md:60-61 |
| The README says every command supports a timeout and that a goto which timed out may keep walking, after which the caller can command Temi to stop | vendor_doc | README.md:37-43 |
| The example opens a URL with interface(url=...) | upstream_code | src/temi/api.py:142 |
| run() gathers the tasks queued by the command templates | upstream_code | src/temi/api.py:119-124 |
| disconnect() closes the socket if it is still open | upstream_code | src/temi/api.py:54-57 |

Limits: none.  The clone states no unit or range for the turn angle and no unit for the screen tilt, and the
documented API has no numeric setting that this package could bound (README.md:57-61).  Turn and raise_head are
therefore not exposed; a numeric input without a unit and a sourced bound would not be honest.

Reads: none.  The documented API lists only commands (speak, ask, goto, turn, tilt) and no getter
(`src/temi/README.md:45-62`); `command()` returns the reply of the command that was sent, not a device state.
The package is action-only.

Safety: Temi is a mobile base, so the driver is R2 even though the card's floor is R0.  The independent stop is the
safe-state action `x-cap.tongji-cdi.stop.v1`, which sends the stop command; the `@estop` method sends the same
command.  The README says a timed-out goto may keep walking and that the caller can then command Temi to stop
(README.md:37-43), but it does not name the stop command: this package sends `{"command": "stop"}` and RESULT.json
records that inference.  No hardware emergency-stop reference is documented in the clone, so
`estop_physical_ref` is not declared; SAFE-045 is met by the safe-state action.  The runtime latches first and
refuses further commands until an operator reset.

Tags: mobile base, telepresence, navigation, speech, websocket, asyncio
