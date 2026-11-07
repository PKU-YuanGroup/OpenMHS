# Facts and tags for gh.histedlab/scanimage-python-control

Every fact cites its source at commit `9de4309aef951b390ed4b5a1240797a54d1001d8`: `upstream_code` (a file of the
clone) or `vendor_doc` (README.md).  The same facts are written into `driver.py` (`facts = [...]`); the reference
file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| si_get sends a JSON get for one server property and returns the reply's value | upstream_code | py_json_client.py:69-84 |
| si_set sends a JSON set and asserts that the reply value equals the requested value | upstream_code | py_json_client.py:87-95 |
| si_eval sends a Matlab eval string with a required number of outputs | upstream_code | py_json_client.py:97-106 |
| si_feval sends a Matlab feval with inputs named in000, in001, ... and a required number of outputs | upstream_code | py_json_client.py:109-119 |
| close closes the socket, and the class is a context manager whose exit closes it | upstream_code | py_json_client.py:35-43 |
| Requests and replies are an 8-byte little-endian length followed by the JSON body | upstream_code | py_json_client.py:47-66 |
| The client examples get and set the ScanImage property hSI.hRoiManager.scanZoomFactor | upstream_code | JsonClientTest.m:12-19 |
| The example feval message names hSI.startFocus with an empty input map and num_outputs 0 | upstream_code | JsonClientTest.m:6-10 |
| The README says the client changes photostimulation power, adjusts imaging power and runs imaging series over a network socket | vendor_doc | README.md:3 |
| The README describes dummy_json_server.py as a Python fake of the Vidrio JsonServer that allows unit testing | vendor_doc | README.md:13-16 |

Limits: the scan zoom factor is `Limit.operator_required`.  The clone names the property but states no allowed range
(`JsonClientTest.m:18-19` is one example set value; `test_matlab_jsonserver.py:31` comments the setter out), so the
site supplies the range of its ScanImage configuration.  `site-limits.example.json` is only a template.

Safety: the native stop is `close()` (`py_json_client.py:35-36`), the only teardown the client offers.  The e-stop
closes the control socket; an acquisition already running on the ScanImage host is not stopped by it.  No line of
the clone documents an independent hardware e-stop, so `estop_physical_ref` is not claimed (the card's floor is R0
and the bound capability set is R1).

Mock path: the card prefers an upstream simulator, but the clone's stand-in is `dummy_json_server.py`, a TCP server
that waits for a socket connection (`dummy_json_server.py:97-105`); the acceptance gate runs without network, so the
package ships an in-package recording fake of the client object (`fake.py`) whose methods and reply shapes follow
the upstream client and dummy server.

Tags: scanimage, microscope, remote-control, tcpip, json
