# Facts and tags for gh.pycroscopy/dtmicroscope

Every fact cites its source at commit `17245ba6df4299aa3f13e2a8f33d9ba48a8000b4`: `upstream_code`
(`path/in/clone.py:LINE`).  The same facts are written into `driver.py` (`facts = [...]`); the reference file is
generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| TEMClient sends a netstring-encoded JSON-RPC request over socket.create_connection and raises RuntimeError when the server reply carries an error | upstream_code | DTMicroscope/base/twisted_client.py:36-46 |
| TEMClient.set_stage sends stage_positions and relative to the server | upstream_code | DTMicroscope/base/twisted_client.py:61-64 |
| TEMClient.acquire_image reconstructs the (list, shape, dtype) tuple the server returns into a numpy array | upstream_code | DTMicroscope/base/twisted_client.py:66-74 |
| TEMClient.get_vacuum and TEMClient.get_microscope_status are plain RPC calls | upstream_code | DTMicroscope/base/twisted_client.py:88-92 |
| TEMClient.close sends the close RPC | upstream_code | DTMicroscope/base/twisted_client.py:97-98 |
| TEMServer initializes the detectors flu_camera, ceta_camera, scan and super_x | upstream_code | DTMicroscope/server/twisted_server.py:129-135 |
| TEMServer constructs auto_script.TemMicroscopeClient and connects it to 127.0.0.1:9095 | upstream_code | DTMicroscope/server/twisted_server.py:137-156 |
| TEMServer.get_stage returns five float coordinates read from specimen.stage.position; b is 0 for a SingleTilt holder | upstream_code | DTMicroscope/server/twisted_server.py:196-213 |
| TEMServer.set_stage writes the x, y, z, a and b directions into a StagePosition and calls relative_move_safe or absolute_move_safe | upstream_code | DTMicroscope/server/twisted_server.py:215-226 |
| TEMServer.acquire_image calls microscope.acquisition.acquire_camera_image and returns serialize(image.data), a list with its shape and dtype | upstream_code | DTMicroscope/server/twisted_server.py:230-242 |
| TEMServer.acquire_spectrum returns a 2048-sample float32 zero array | upstream_code | DTMicroscope/server/twisted_server.py:255-258 |
| TEMServer.get_vacuum returns 1e-5 and TEMServer.get_microscope_status returns 'Idle'; the code states no unit for the vacuum number | upstream_code | DTMicroscope/server/twisted_server.py:280-284 |
| TEMServer.close prints a message and returns 1; it does not command the electron beam or the stage | upstream_code | DTMicroscope/server/twisted_server.py:290-292 |
| The server main listens on 0.0.0.0 port 9093 | upstream_code | DTMicroscope/server/twisted_server.py:389-392 |

Limits: the absolute stage position (x, y, z, a, b) and the beam position (x, y) are `Limit.operator_required`.
No text file of the clone states a travel range, a beam-shift range or the unit of those numbers (the server copies
`specimen.stage.position` and forwards the numbers without a unit, twisted_server.py:196-226; the beam call only prints
`Moving beam to (x, y)`, twisted_server.py:276-278).  The example overlay in `site-limits.example.json` is an example
only; the site supplies the ranges of its holder and column.

Safety: the native stop this client has is `close` (twisted_client.py:97-98), which sends the `close` RPC; the server's
`close` only prints a message (twisted_server.py:290-292).  The driver therefore does not claim that the stop blanks the
beam or halts the stage, and it declares no independent hardware e-stop because no text file of the clone does.  The
package is R1: it commands absolute stage motion and beam shift, both of which are refused without an operator overlay,
and it exposes no gun voltage, emission or column-valve control.  A wrong move is recoverable within the site's declared
travel envelope; the driver never clamps or retries.

Tags: electron-microscope, tem, digital-twin, json-rpc, stage
