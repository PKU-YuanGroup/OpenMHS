"""OpenMHS driver for gh.pycroscopy/dtmicroscope: a TEM through the upstream JSON-RPC client.

A direct Driver (decorated methods) over the upstream client class
``DTMicroscope.base.twisted_client:TEMClient``.  The client marshals one netstring-encoded JSON-RPC request per call
over ``socket.create_connection`` to a ``TEMServer`` (twisted_client.py:36-46); the server is the object that talks to
the microscope's AutoScript SDK (twisted_server.py:137-156).  The driver therefore translates each capability into the
client method of the same operation and never re-implements the wire format.

* reads: the detector names, the microscope status, the vacuum number and the five stage coordinates (x, y, z, a, b);
* writes: the absolute stage position and the beam position.  No text file of the clone states the travel range, the
  beam-shift range or the unit of those numbers, so both are ``Limit.operator_required``: every write is refused
  ``MHS.SAFETY.LIMITS_UNSET`` until the site supplies the ranges of its holder and column
  (``site-limits.example.json`` shows the overlay);
* actions: one image through ``cap.imaging.capture.v1`` (written to a 16-bit PGM in the system temporary directory),
  and one spectrum through ``x-cap.pycroscopy.acquire_spectrum.v1``;
* the native stop available to this client is ``TEMClient.close``, which sends the ``close`` RPC.  It closes the RPC
  link; the server's ``close`` only prints a message (twisted_server.py:290-292), so the driver does not claim that it
  blanks the beam or halts the stage.  The package is R1 (the card floor): it commands stage motion, beam shift and
  acquisitions but exposes no gun voltage, emission or column-valve control.

Every Fact cites a line of the clone at the pinned commit (17245ba6df4299aa3f13e2a8f33d9ba48a8000b4).  This package is
model-authored and unreviewed: it is checked on the fake backend only, and its evidence is ``contract_checked``, never
an MHS-Device level.  Nothing here ran on hardware.
"""

import os
import tempfile

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

#: The detector names ``TEMServer.__init__`` publishes (twisted_server.py:129-135).  It cannot add a detector through
#: ``device_settings`` (twisted_server.py:185-194), so this is the closed set of names the server accepts.
DETECTORS = ("flu_camera", "ceta_camera", "scan", "super_x")


def _floats(value, what):
    """``value`` as a list of floats (a numpy array is accepted through ``tolist``)."""
    if value is None:
        raise DriverFailed("MHS.DEVICE.FAULTED", f"{what} returned no value")
    if hasattr(value, "tolist"):
        value = value.tolist()
    try:
        return [float(item) for item in value]
    except (TypeError, ValueError) as exc:
        raise DriverFailed("MHS.DEVICE.FAULTED", f"{what} returned a non-numeric value") from exc


def _rows(value):
    """A two-dimensional image as a list of rows of numbers; ``acquire_image`` returns a numpy array."""
    if value is None:
        raise DriverFailed("MHS.DEVICE.FAULTED", "acquire_image returned no image for that detector")
    if hasattr(value, "tolist"):
        value = value.tolist()
    if not isinstance(value, (list, tuple)) or not value:
        raise DriverFailed("MHS.DEVICE.FAULTED", "acquire_image returned an empty image")
    rows = []
    for row in value:
        if hasattr(row, "tolist"):
            row = row.tolist()
        if not isinstance(row, (list, tuple)) or not row:
            raise DriverFailed("MHS.DEVICE.FAULTED", "acquire_image returned a non two-dimensional image")
        try:
            rows.append([float(item) for item in row])
        except (TypeError, ValueError) as exc:
            raise DriverFailed("MHS.DEVICE.FAULTED", "acquire_image returned a non-numeric pixel") from exc
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise DriverFailed("MHS.DEVICE.FAULTED", "acquire_image returned rows of unequal length")
    return rows


def _write_pgm(rows):
    """Write one frame as a binary 16-bit PGM in the system temporary directory; return (path, width, height)."""
    height = len(rows)
    width = len(rows[0])
    pixels = bytearray()
    for row in rows:
        for value in row:
            number = int(round(value))
            number = max(0, min(65535, number))
            pixels.append(number >> 8)
            pixels.append(number & 0xFF)
    handle, path = tempfile.mkstemp(prefix="dtmicroscope-", suffix=".pgm")
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(f"P5\n{width} {height}\n65535\n".encode("ascii"))
            stream.write(bytes(pixels))
    except BaseException:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise
    return path, width, height


class Dtmicroscope(Driver):
    device_id = "dtmicroscope"
    device_kind = "instrument.microscope"
    mode = "hardware"
    risk = "R1"
    native = "DTMicroscope.base.twisted_client:TEMClient"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeTEMClient"}
    vendor, model = "pycroscopy", "DTMicroscope TEM client (AutoScript-backed twisted server)"
    display_name = "DTMicroscope TEM client (DTMicroscope.base.twisted_client.TEMClient)"
    tags = ["electron-microscope", "tem", "digital-twin", "json-rpc", "stage"]
    facts = [
        Fact("TEMClient sends a netstring-encoded JSON-RPC request over socket.create_connection and raises "
             "RuntimeError when the server reply carries an error",
             source="upstream_code", ref="DTMicroscope/base/twisted_client.py:36-46"),
        Fact("TEMClient.set_stage sends stage_positions and relative to the server",
             source="upstream_code", ref="DTMicroscope/base/twisted_client.py:61-64"),
        Fact("TEMClient.acquire_image reconstructs the (list, shape, dtype) tuple the server returns into a numpy "
             "array", source="upstream_code", ref="DTMicroscope/base/twisted_client.py:66-74"),
        Fact("TEMClient.get_vacuum and TEMClient.get_microscope_status are plain RPC calls",
             source="upstream_code", ref="DTMicroscope/base/twisted_client.py:88-92"),
        Fact("TEMClient.close sends the close RPC", source="upstream_code",
             ref="DTMicroscope/base/twisted_client.py:97-98"),
        Fact("TEMServer initializes the detectors flu_camera, ceta_camera, scan and super_x",
             source="upstream_code", ref="DTMicroscope/server/twisted_server.py:129-135"),
        Fact("TEMServer constructs auto_script.TemMicroscopeClient and connects it to 127.0.0.1:9095",
             source="upstream_code", ref="DTMicroscope/server/twisted_server.py:137-156"),
        Fact("TEMServer.get_stage returns five float coordinates read from specimen.stage.position; b is 0 for a "
             "SingleTilt holder", source="upstream_code", ref="DTMicroscope/server/twisted_server.py:196-213"),
        Fact("TEMServer.set_stage writes the x, y, z, a and b directions into a StagePosition and calls "
             "relative_move_safe or absolute_move_safe", source="upstream_code",
             ref="DTMicroscope/server/twisted_server.py:215-226"),
        Fact("TEMServer.acquire_image calls microscope.acquisition.acquire_camera_image and returns "
             "serialize(image.data), a list with its shape and dtype", source="upstream_code",
             ref="DTMicroscope/server/twisted_server.py:230-242"),
        Fact("TEMServer.acquire_spectrum returns a 2048-sample float32 zero array", source="upstream_code",
             ref="DTMicroscope/server/twisted_server.py:255-258"),
        Fact("TEMServer.get_vacuum returns 1e-5 and TEMServer.get_microscope_status returns 'Idle'; the code states "
             "no unit for the vacuum number", source="upstream_code",
             ref="DTMicroscope/server/twisted_server.py:280-284"),
        Fact("TEMServer.close prints a message and returns 1; it does not command the electron beam or the stage",
             source="upstream_code", ref="DTMicroscope/server/twisted_server.py:290-292"),
        Fact("The server main listens on 0.0.0.0 port 9093", source="upstream_code",
             ref="DTMicroscope/server/twisted_server.py:389-392"),
    ]
    safe_state = ("RPC link closed through TEMClient.close; this client does not command the electron beam, the stage "
                  "or the column valves")

    # -- reads -----------------------------------------------------------------------------------------------------
    @read("detectors", type="array", items=Field("string"),
          description="Detector names the server publishes")
    def detectors(self):
        return self.native.get_detectors()

    @read("microscope_status", type="string", description="Status line the server reports for the microscope")
    def microscope_status(self):
        return self.native.get_microscope_status()

    @read("vacuum", unit="1",
          description="Vacuum reading as returned by the server; the clone does not state its unit")
    def vacuum(self):
        return self.native.get_vacuum()

    @read("stage", type="array", unit="1", items=Field("number"), length=5,
          description="Stage coordinates x, y, z, a, b as returned by the server")
    def stage(self):
        return _floats(self.native.get_stage(), "get_stage")

    # -- writes ----------------------------------------------------------------------------------------------------
    @write("stage", type="array", unit="1", items=Field("number"), length=5,
           description="Absolute stage position x, y, z, a, b",
           limit=Limit.operator_required(
               "no text file of the clone states the travel range or the unit of the five stage coordinates "
               "(x, y, z, a, b); the holder and the AutoScript configuration set them, so the site supplies the "
               "absolute travel limits of its stage"))
    def set_stage(self, value):
        positions = [float(item) for item in value]
        self.native.set_stage(positions, relative=False)
        return _floats(self.native.get_stage(), "get_stage")

    @write("beam_position", type="array", unit="1", items=Field("number"), length=2,
           description="Beam position x, y",
           limit=Limit.operator_required(
               "no text file of the clone states the range or the unit of the beam position (x, y); the AutoScript "
               "configuration sets it, so the site supplies the beam-shift limits of its column"))
    def set_beam_position(self, value):
        x, y = (float(item) for item in value)
        code = self.native.set_beam_position(x, y)
        if code != 1:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"set_beam_position returned {code}", native_code=code)
        return [x, y]

    # -- actions ---------------------------------------------------------------------------------------------------
    @action(cap="cap.imaging.capture.v1",
            description="Acquire one image from a detector and write it to a 16-bit PGM artifact",
            input={"camera": Field("string", description="Detector to acquire the image from",
                                   enum=list(DETECTORS))})
    def acquire_image(self, camera):
        rows = _rows(self.native.acquire_image(camera))
        path, width, height = _write_pgm(rows)
        return {"image_ref": path, "width": width, "height": height, "channel": camera}

    @action(name="x-cap.pycroscopy.acquire_spectrum.v1",
            description="Acquire one spectrum from a detector and return its samples",
            input={"device": Field("string", description="Detector to acquire the spectrum from",
                                   enum=list(DETECTORS))},
            output={"device": Field("string", description="Detector the spectrum was requested from"),
                    "intensities": Field("array", unit="1", items=Field("number"),
                                         description="Spectrum samples as returned by the server"),
                    "sampled_at": Field("string", description="Time the spectrum was acquired")})
    def acquire_spectrum(self, device):
        values = _floats(self.native.acquire_spectrum(device), "acquire_spectrum")
        return {"device": device, "intensities": values}

    # -- safety ----------------------------------------------------------------------------------------------------
    @estop(native="close")
    def stop(self):
        """The native stop this client has: send the close RPC and drop the RPC link."""
        self.native.close()
