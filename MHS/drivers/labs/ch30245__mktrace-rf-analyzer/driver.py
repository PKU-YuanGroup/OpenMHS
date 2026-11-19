"""OpenMHS driver for gh.ch30245/mktrace-rf-analyzer: the MKTrace network-analyzer client.

Shape and deviation from the card
---------------------------------
The card names the config-only ``ScpiDriver`` family.  This package is a direct :class:`mhs.driver.Driver` over the
card's entry symbol ``pna:NaClient`` instead.  The upstream client is not a one-line command map: every operation
opens its own session, builds channel-numbered SCPI commands from parts, moves a Touchstone file with a binary block
transfer and restores analyzer state with query-back writes (``pna.py:266-334``, ``pna.py:631-798``).  A
``ScpiDriver`` command table cannot express those sequences, so the driver calls the upstream methods and publishes
the file the native writes through the SDK's native-file artifacts.

* reads: the analyzer identity (``NaClient.identify``, a ``*IDN?`` query on a short-lived session);
* actions: ``x-cap.ch30245.configure-measurements.v1`` (``NaClient.configure_measurements``) and
  ``x-cap.ch30245.capture-trace.v1`` (``NaClient.capture``), which publishes the written Touchstone file;
* the e-stop attempts to close the active transport session (``NaClient.abort_active_session``), then fails closed:
  the upstream sends no sweep-abort command and provides no confirmation that the analyzer stopped.

Every Fact and Limit cites a line of the clone at the pinned commit 44169387a49c06994455e6c502ddae4edab8cabc.  This
package is model-authored and unreviewed (``driver.lock.json`` ``reviewed_by`` is null); it is checked on the fake
backend only and has never connected to an analyzer.
"""

import os
import shutil
import tempfile
from pathlib import Path

from mhs.driver import Cancelled, Driver, DriverFailed, Fact, Field, Limit, action, estop, read
from mhs.file_artifacts import NativeFileDirectory

SOURCE = "pna.py"

CONFIGURE = "x-cap.ch30245.configure-measurements.v1"
CAPTURE = "x-cap.ch30245.capture-trace.v1"

#: Package execution budget, chosen to equal the default per-I/O timeout (pna.py:179), not an upstream total bound.
IO_BOUND_MS = 180000
#: The SDK's absolute per-file artifact bound (docs/file-artifacts.md); the endpoint store may allow less.
MAX_FILE_BYTES = 16 * 1024 * 1024
#: Media types for the three Touchstone suffixes the upstream accepts (pna.py:121-141, pna.py:349-352).
TOUCHSTONE_MEDIA = {
    ".s1p": "application/x-touchstone",
    ".s2p": "application/x-touchstone",
    ".s4p": "application/x-touchstone",
}
#: The upstream port counts (pna.py:123-124, pna.py:149-150).
PORT_COUNT_LIMIT = Limit(allowed=[1, 2, 4], source="upstream_code", ref=f"{SOURCE}:123-124",
                         reason="the upstream rejects every other port count before opening the analyzer session")


class MktraceRfAnalyzer(Driver):
    device_id = "mktrace-rf-analyzer"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "pna:NaClient"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeNaClient"}
    vendor, model = "Keysight / Rohde & Schwarz", "PNA-family / ZVA-family network analyzer"
    display_name = "MKTrace RF network analyzer (NaClient)"
    tags = ["network analyzer", "vna", "s-parameter", "touchstone", "scpi", "keysight pna", "rohde schwarz zva"]

    facts = [
        Fact("NaClient is the analyzer client class; its constructor stores host and port and defaults the port to "
             "5025", source="upstream_code", ref=f"{SOURCE}:236-241"),
        Fact("A session is a raw TCP socket to host:port with a 10 s connect timeout and a default 180 s I/O timeout",
             source="upstream_code", ref=f"{SOURCE}:178-182"),
        Fact("Every SCPI command is sent as ASCII terminated by a newline", source="upstream_code",
             ref=f"{SOURCE}:203-204"),
        Fact("identify opens a short-lived session, queries *IDN? and closes the session",
             source="upstream_code", ref=f"{SOURCE}:254-264"),
        Fact("The supported identity gate accepts Keysight PNA/N522/N523/N524/N526/N529 and Rohde & Schwarz "
             "ZVA/ZVB/ZVT identities only", source="upstream_code", ref=f"{SOURCE}:167-175"),
        Fact("capture accepts only 1, 2 or 4 ports and rejects every other port count before opening a session",
             source="upstream_code", ref=f"{SOURCE}:274-279"),
        Fact("capture reads *IDN? and dispatches to the Keysight or the Rohde & Schwarz capture sequence",
             source="upstream_code", ref=f"{SOURCE}:280-299"),
        Fact("The Keysight capture selects the measurement, starts a single sweep, saves a Touchstone file and "
             "transfers it back with MMEM:TRAN?", source="upstream_code", ref=f"{SOURCE}:696-716"),
        Fact("The Rohde & Schwarz capture turns continuous sweep off, starts an immediate sweep and saves/transfers "
             "a Touchstone file", source="upstream_code", ref=f"{SOURCE}:831-844"),
        Fact("configure_measurements adds missing Keysight S-parameter measurements without replacing existing ones",
             source="upstream_code", ref=f"{SOURCE}:304-333"),
        Fact("configure_measurements refuses non-Keysight analyzers without changing analyzer state",
             source="upstream_code", ref=f"{SOURCE}:320-324"),
        Fact("abort_active_session closes the active I/O session; it sends no SCPI abort command",
             source="upstream_code", ref=f"{SOURCE}:247-252"),
        Fact("The upstream validates a received Touchstone payload before atomically replacing the target file",
             source="upstream_code", ref=f"{SOURCE}:343-363"),
        Fact("The default capture file name is a timestamped MKTrace name with the .s1p, .s2p or .s4p suffix",
             source="upstream_code", ref=f"{SOURCE}:125-128"),
        Fact("The README says the MKCal calibration workflow is simulator-only", source="vendor_doc",
             ref="README.md:5-7"),
        Fact("The README says the automated tests do not contact real hardware", source="vendor_doc",
             ref="README.md:67-69"),
    ]

    safe_state = ("unconfirmed: closing the active TCP session does not confirm stopped analyzer sweeps or RF output; "
                  "the endpoint latch refuses new commands and the e-stop reports SAFE_STATE_UNREACHED")

    _capture_dir = None
    _files = None
    _temporary_dir = None

    def setup(self):
        """Declare the directory the native writes captures into, once, before any command."""
        configured = self.options.get("capture_dir")
        if configured is not None:
            directory = os.path.abspath(os.path.expanduser(os.fspath(configured)))
            os.makedirs(directory, mode=0o700, exist_ok=True)
        elif self.backend == "fake":
            # The fake backend writes into a private temporary directory of this endpoint.
            directory = tempfile.mkdtemp(prefix="openmhs-mktrace-fake-")
            self._temporary_dir = directory
        else:
            raise DriverFailed("MHS.DEVICE.NOT_READY",
                               "the hardware backend needs capture_dir, the existing directory the native writes "
                               "Touchstone captures into (an operator deployment option)")
        directory = os.path.realpath(directory)
        try:
            self._files = NativeFileDirectory(directory, media_types=TOUCHSTONE_MEDIA,
                                              max_file_bytes=MAX_FILE_BYTES, max_files=1, cleanup="keep")
        except ValueError as exc:
            raise DriverFailed("MHS.DEVICE.NOT_READY", f"capture directory {directory!r} cannot publish files: "
                                                       f"{exc}") from exc
        self._capture_dir = Path(directory)

    def teardown(self):
        try:
            self.native.abort_active_session()
        except Exception:
            pass
        if self._temporary_dir is not None:
            shutil.rmtree(self._temporary_dir, ignore_errors=True)

    # -- reads -------------------------------------------------------------------------------------------------
    @read("identity", type="string",
          description="Analyzer identity returned by *IDN? (NaClient.identify in a short-lived session)")
    def identity(self):
        return self.native.identify()

    # -- actions -----------------------------------------------------------------------------------------------
    @action(name=CONFIGURE, long_running=True, max_duration_ms=IO_BOUND_MS, cancellable=True,
            description="Add the missing Keysight S-parameter measurements of the requested port count to the "
                        "active channel; existing measurements and the selected measurement are restored",
            input={"port_count": Field("integer", unit="1",
                                       description="Number of analyzer ports (1, 2 or 4)",
                                       limit=PORT_COUNT_LIMIT)},
            output={"idn": Field("string", description="Analyzer identity from *IDN?"),
                    "channel": Field("integer", unit="1", description="Active channel the setup modified"),
                    "created_measurements": Field(
                        "array", items=Field("object", properties={
                            "name": Field("string", description="Measurement name created on the analyzer"),
                            "parameter": Field("string", description="S-parameter of the measurement")}),
                        description="Measurements this call created"),
                    "final_catalog": Field(
                        "array", items=Field("object", properties={
                            "name": Field("string", description="Measurement name in the final catalog"),
                            "parameter": Field("string", description="S-parameter of the measurement")}),
                        description="Measurement catalog after the call")})
    def configure_measurements(self, port_count):
        cancel_event = self.ctx.cancel_event if self.ctx is not None else None
        try:
            result = self.native.configure_measurements(int(port_count), cancel_event=cancel_event)
        except Exception as exc:
            self._raise_capture_failure(exc)
        self.check_cancelled()
        return {
            "idn": str(result.idn),
            "channel": int(result.channel),
            "created_measurements": [{"name": str(name), "parameter": str(parameter)}
                                     for name, parameter in result.created_measurements],
            "final_catalog": [{"name": str(name), "parameter": str(parameter)}
                              for name, parameter in result.final_catalog],
        }

    @action(name=CAPTURE, long_running=True, max_duration_ms=IO_BOUND_MS, cancellable=True,
            description="Start one fresh sweep on the analyzer and publish the Touchstone file the native wrote "
                        "as a local artifact",
            input={"port_count": Field("integer", unit="1",
                                       description="Number of analyzer ports (1, 2 or 4)",
                                       limit=PORT_COUNT_LIMIT)},
            output={"artifact_ref": Field("string",
                                          description="Local artifact reference of the captured Touchstone file"),
                    "file_name": Field("string", description="File name the native wrote in the capture directory"),
                    "port_count": Field("integer", unit="1", description="Number of ports in the capture"),
                    "idn": Field("string", description="Analyzer identity from *IDN?"),
                    "correction_warning": Field("boolean",
                                                description="True when the capture data reports correction off"),
                    "restoration_warnings": Field(
                        "array", items=Field("string"),
                        description="State-restoration warnings the upstream returned after the capture")})
    def capture_trace(self, port_count):
        if self._files is None:
            raise DriverFailed("MHS.DEVICE.NOT_READY", "the capture directory was not declared in setup")
        cancel_event = self.ctx.cancel_event if self.ctx is not None else None
        try:
            result = self.native.capture(self._capture_dir, int(port_count), cancel_event=cancel_event)
        except Exception as exc:
            self._raise_capture_failure(exc)
        self.check_cancelled()
        path = Path(result.path)
        name = path.name
        published = self._files.publish(self.ctx, name)
        return {
            "artifact_ref": published["artifact_ref"],
            "file_name": name,
            "port_count": int(port_count),
            "idn": str(result.idn),
            "correction_warning": bool(result.correction_warning),
            "restoration_warnings": [str(item) for item in result.restoration_warnings],
        }

    def _raise_capture_failure(self, exc):
        """Translate a native failure, keeping cancellation and the native type visible."""
        if self.cancelled() or type(exc).__name__ in {"OperationCancelled", "_OperationCancelled"}:
            raise Cancelled(f"analyzer operation cancelled ({type(exc).__name__})") from exc
        raise DriverFailed("MHS.DEVICE.FAULTED",
                           f"analyzer operation failed: {type(exc).__name__}: {exc}") from exc

    # -- safety ------------------------------------------------------------------------------------------------
    @estop(native="abort_active_session")
    def stop(self):
        """Interrupt I/O without certifying the analyzer's physical state."""
        self.native.abort_active_session()
        raise DriverFailed("MHS.SAFETY.SAFE_STATE_UNREACHED",
                           "the upstream closes TCP I/O but neither aborts the analyzer sweep nor confirms a "
                           "stopped output; the e-stop must remain unconfirmed")
