"""OpenMHS driver for gh.histedlab/scanimage-python-control: the ScanImage TCP/IP JSON client.

A direct Driver (decorated methods) over the upstream client ``py_json_client:ScanimageTcpipClient``.  The client
sends an 8-byte little-endian length followed by a JSON request to a ScanImage/Matlab server
(py_json_client.py:47-66): ``si_get`` reads one server property, ``si_set`` writes one, and ``si_eval``/``si_feval``
evaluate a Matlab expression or call a Matlab function.

* one read and one write: the ScanImage property ``hSI.hRoiManager.scanZoomFactor``, which the clone's own client
  examples get and set (JsonClientTest.m:12-19, test_matlab_jsonserver.py:30-31).  No text of the clone states an
  allowed range, so the write is ``Limit.operator_required``: every write is refused ``MHS.SAFETY.LIMITS_UNSET``
  until the site supplies the range of its ScanImage configuration (``site-limits.example.json`` shows the overlay).
* no action.  The clone's feval example ``hSI.startFocus`` (JsonClientTest.m:6-10) starts a focus acquisition, in
  which a two-photon microscope scans its laser over the sample, and ``close()``, the only teardown the client offers,
  does not stop it; no line of the clone names a ScanImage stop.  A model review therefore removed the action the
  author had bound (``x-cap.histedlab.start_focus.v1``): a driver must be able to stop what it starts.
* the native stop is ``close()`` (py_json_client.py:35-36), the teardown the client offers.  Closing the control
  socket stops this driver's commands; an acquisition already running on the ScanImage host is not stopped by it.

What the package does not carry: the client can evaluate arbitrary Matlab and get/set any server property.  No line
of the clone states a property name, a type or a range for photostimulation or imaging power, so those writes are not
bound (an unbounded string property input would be a path to the laser); the protocol carries no image data at all
(see RESULT.json notes).

Every Fact cites a line of the clone at the pinned commit 9de4309aef951b390ed4b5a1240797a54d1001d8.  This package is
model-authored and unreviewed: the acceptance gate runs the fake backend only, and nothing here ran on a microscope
or a ScanImage server.
"""

from mhs.driver import Driver, Fact, Limit, estop, read, write

#: The one ScanImage property the clone names for both a get and a set (JsonClientTest.m:14, 18).
SCAN_ZOOM = "hSI.hRoiManager.scanZoomFactor"


class ScanimageTcpip(Driver):
    device_id = "scanimage-tcpip"
    device_kind = "instrument.microscope"
    mode = "hardware"
    risk = "R1"
    native = "py_json_client:ScanimageTcpipClient"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeScanimageTcpipClient"}
    vendor, model = "Histed lab", "ScanImage TCP/IP JSON client"
    display_name = "ScanImage remote control (py_json_client.ScanimageTcpipClient)"
    tags = ["scanimage", "microscope", "remote-control", "tcpip", "json"]
    facts = [
        Fact("si_get sends a JSON get for one server property and returns the reply's value",
             source="upstream_code", ref="py_json_client.py:69-84"),
        Fact("si_set sends a JSON set and asserts that the reply value equals the requested value",
             source="upstream_code", ref="py_json_client.py:87-95"),
        Fact("si_eval sends a Matlab eval string with a required number of outputs",
             source="upstream_code", ref="py_json_client.py:97-106"),
        Fact("si_feval sends a Matlab feval with inputs named in000, in001, ... and a required number of outputs",
             source="upstream_code", ref="py_json_client.py:109-119"),
        Fact("close closes the socket, and the class is a context manager whose exit closes it",
             source="upstream_code", ref="py_json_client.py:35-43"),
        Fact("Requests and replies are an 8-byte little-endian length followed by the JSON body",
             source="upstream_code", ref="py_json_client.py:47-66"),
        Fact("The client examples get and set the ScanImage property hSI.hRoiManager.scanZoomFactor",
             source="upstream_code", ref="JsonClientTest.m:12-19"),
        Fact("The example feval message names hSI.startFocus with an empty input map and num_outputs 0",
             source="upstream_code", ref="JsonClientTest.m:6-10"),
        Fact("The README says the client changes photostimulation power, adjusts imaging power and runs imaging "
             "series over a network socket", source="vendor_doc", ref="README.md:3"),
        Fact("The README describes dummy_json_server.py as a Python fake of the Vidrio JsonServer that allows unit "
             "testing", source="vendor_doc", ref="README.md:13-16"),
    ]
    safe_state = ("control socket closed by the native close(); this client sends no further ScanImage command, "
                  "while an acquisition already running on the ScanImage host is not stopped by it")

    # -- the one property -----------------------------------------------------------------------------------------
    @read("scan_zoom_factor", unit="1",
          description="ScanImage scan zoom factor (the server property hSI.hRoiManager.scanZoomFactor)")
    def scan_zoom_factor(self):
        return self.native.si_get(SCAN_ZOOM)

    @write("scan_zoom_factor", unit="1",
           description="ScanImage scan zoom factor (the server property hSI.hRoiManager.scanZoomFactor)",
           limit=Limit.operator_required(
               "no text of the clone states an allowed range for hSI.hRoiManager.scanZoomFactor: "
               "JsonClientTest.m:18-19 shows one example set value (10) and test_matlab_jsonserver.py:31 comments "
               "the setter out, so the site supplies the range of its ScanImage configuration"))
    def set_scan_zoom_factor(self, value):
        self.native.si_set(SCAN_ZOOM, value)
        return value                       # si_set asserts that the server returned the requested value

    # -- safety ----------------------------------------------------------------------------------------------------
    @estop(native="close")
    def stop(self):
        """The native teardown: the runtime latches first, then the client closes its socket."""
        self.native.close()

    def teardown(self):
        self.native.close()
