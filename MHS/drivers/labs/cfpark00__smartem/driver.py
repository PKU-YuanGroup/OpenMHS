"""OpenMHS driver for gh.cfpark00/smartem: the Thermo Fisher Verios SEM of the SmartEM acquisition pipeline.

A direct Driver (decorated methods) over the upstream device class
``smartem.online.microscope:ThermoFisherVerios``.  That class is a Python object over the proprietary
``autoscript_sdb_microscope_client`` vendor SDK (README.md:21): its constructor imports the SDK, ``initialize``
opens the vendor client and connects to ``params["ip"]`` (smartem/online/microscope.py:201-224), and every
device operation is a synchronous method on that object.  A SerialDriver or ScpiDriver command table cannot
express this interface, so the card's direct-driver shape is used.

* actions: acquire one electron image through ``get_image`` and write the returned array to a 16-bit PGM file
  in the system temporary directory; run ``auto_focus``; run ``prepare_acquisition``; move the specimen stage
  to an absolute raw stage position through ``move``;
* no writable state: the class exposes no property setter, and the image parameters are passed per call;
* every numeric action input is ``Limit.operator_required`` because no text file of the clone states a
  resolution, dwell time, pixel size or stage travel range: every call is refused ``MHS.SAFETY.LIMITS_UNSET``
  until the site supplies its own envelope (``site-limits.example.json`` shows the overlay);
* the native stop is ``close()``, which disconnects the vendor client and deletes the client handle
  (smartem/online/microscope.py:226-228).  The class exposes no blank, halt or stop method.  That native
  close is both the ``@estop`` and the ``safe_state=True`` action.

The microscope operates an electron beam and moves a specimen stage, so the declared risk is R3.  Every Fact
cites a line of the clone at the pinned commit bbabd6ac4dcdc4b77a46c0f0e21e056c82f193aa.  This package is
model-authored and unreviewed: it is checked on the fake backend only and never ran on hardware.
"""

import os
import tempfile

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop

_STAGE_REASON = ("the clone passes x, y, z, r and t to StagePosition with coordinate_system 'Raw' and states no "
                 "travel range or unit (smartem/online/microscope.py:387-399); the site supplies the stage "
                 "envelope in those native units")


def _image_rows(data):
    """The returned frame as rows of integers; raise DriverFailed when the vendor result is not a 2-D array."""
    if hasattr(data, "tolist"):
        data = data.tolist()
    if not isinstance(data, (list, tuple)) or not data:
        raise DriverFailed("MHS.DEVICE.FAULTED", "get_image returned no image data")
    rows = []
    for row in data:
        if hasattr(row, "tolist"):
            row = row.tolist()
        if not isinstance(row, (list, tuple)) or not row:
            raise DriverFailed("MHS.DEVICE.FAULTED", "get_image returned an image row that is not a sequence")
        try:
            rows.append([int(value) for value in row])
        except (TypeError, ValueError) as exc:
            raise DriverFailed("MHS.DEVICE.FAULTED", "get_image returned a non-numeric pixel") from exc
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise DriverFailed("MHS.DEVICE.FAULTED", "get_image returned rows of unequal length")
    return rows


def _write_pgm(rows):
    """Write one frame as a binary 16-bit PGM in the system temporary directory; return (path, width, height)."""
    height = len(rows)
    width = len(rows[0])
    pixels = bytearray()
    for row in rows:
        for value in row:
            number = max(0, min(65535, int(value)))
            pixels.append(number >> 8)
            pixels.append(number & 0xFF)
    handle, path = tempfile.mkstemp(prefix="smartem-", suffix=".pgm")
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


class SmartemVerios(Driver):
    device_id = "smartem-verios"
    device_kind = "instrument.microscope"
    mode = "hardware"
    risk = "R3"
    native = "smartem.online.microscope:ThermoFisherVerios"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeThermoFisherVerios"}
    vendor, model = "Thermo Fisher", "Verios scanning electron microscope (SmartEM)"
    display_name = "Thermo Fisher Verios SEM (smartem.online.microscope:ThermoFisherVerios)"
    tags = ["sem", "electron-microscope", "smartem", "imaging", "stage", "high-voltage"]
    facts = [
        Fact("ThermoFisherVerios implements the SmartEM microscope interface for a Thermo Fisher scanning "
             "electron microscope and depends on the proprietary autoscript_sdb_microscope_client package",
             source="vendor_doc", ref="README.md:21"),
        Fact("initialize creates SdbMicroscopeClient, connects to params['ip'], sets the stage RAW coordinate "
             "system and unblanks the electron beam", source="upstream_code",
             ref="smartem/online/microscope.py:217-224"),
        Fact("close calls disconnect and deletes the microscope client handle", source="upstream_code",
             ref="smartem/online/microscope.py:226-228"),
        Fact("prepare_acquisition runs auto contrast/brightness, auto focus, auto lens alignment, auto stig, "
             "auto focus and auto contrast/brightness", source="upstream_code",
             ref="smartem/online/microscope.py:236-242"),
        Fact("auto_focus sets the horizontal field width, runs the vendor autofocus (Volumescope settings when "
             "baseline is false), reads the working distance and restores the baseline focus after an exception",
             source="upstream_code", ref="smartem/online/microscope.py:244-275"),
        Fact("get_image sets the scanning resolution and horizontal field width from resolution and pixel_size, "
             "uses bit_depth 16 and returns the vendor frame data", source="upstream_code",
             ref="smartem/online/microscope.py:306-385"),
        Fact("move builds a StagePosition with x, y, z, r and t in coordinate_system 'Raw' and calls "
             "specimen.stage.absolute_move", source="upstream_code",
             ref="smartem/online/microscope.py:387-399"),
        Fact("The plotting code labels a dwell time after multiplying it by 1e9 with ns, so dwell_time is in "
             "seconds", source="upstream_code", ref="smartem/smartem.py:280"),
        Fact("The example imaging parameters use a 2048 x 1768 resolution and a pixel_size of 4.0e-09",
             source="upstream_code", ref="examples/default_smartem_params.json:2-10"),
        Fact("acquire_grid builds a coordinate from dx and dy and calls microscope.move with x, y, z, r and t",
             source="upstream_code", ref="smartem/smartem.py:124-125"),
        Fact("The caller computes fov = resolution * pixel_size and passes dx = fov[0] * 0.8 and "
             "dy = fov[1] * 0.8 to acquire_grid", source="upstream_code", ref="smartem/smartem.py:176-184"),
    ]
    safe_state = ("none: the upstream class has no stage stop and no beam blank, and close() only disconnects "
                  "the vendor client while a stage move goes on and the beam initialize() unblanked stays on "
                  "(the model review blocked the package, RESULT.json)")

    # -- lifecycle ----------------------------------------------------------------------------------------------
    def setup(self):
        self._released = False
        self.native.initialize()

    def teardown(self):
        self._release()

    # -- image acquisition ----------------------------------------------------------------------------------------
    @action(name="x-cap.cfpark00.acquire_image.v1",
            description="Acquire one electron image with the native get_image and write it as a 16-bit PGM",
            input={
                "width": Field("integer", unit="1", description="Scanning width in pixels",
                               limit=Limit.operator_required(
                                   "the clone takes the resolution from the caller and states no supported "
                                   "scanning size (smartem/online/microscope.py:306-315); the site supplies the "
                                   "resolution envelope of its column")),
                "height": Field("integer", unit="1", description="Scanning height in pixels",
                                limit=Limit.operator_required(
                                    "the clone takes the resolution from the caller and states no supported "
                                    "scanning size (smartem/online/microscope.py:306-315); the site supplies the "
                                    "resolution envelope of its column")),
                "dwell_time": Field("number", unit="s",
                                    description="Dwell time per pixel in seconds (the clone labels dwell_time "
                                                "in ns after multiplying it by 1e9)",
                                    limit=Limit.operator_required(
                                        "the clone passes dwell_time to GrabFrameSettings and create_bitmap "
                                        "without a bound (smartem/online/microscope.py:357-379); the site "
                                        "supplies the dwell-time envelope of its detector")),
                "pixel_size": Field("number", unit="1",
                                    description="Pixel size in the native coordinate unit of the imaging "
                                                "parameters (the example uses 4.0e-09)",
                                    limit=Limit.operator_required(
                                        "the clone multiplies pixel_size by the resolution to obtain the field "
                                        "of view and states no bound (smartem/online/microscope.py:309-311); "
                                        "the site supplies the pixel-size envelope of its column")),
                "invert": Field("boolean",
                                description="Invert the returned pixel values (the native get_image invert flag)"),
            },
            output={
                "image_ref": Field("string",
                                   description="Path of the 16-bit PGM image in the system temporary directory"),
                "width": Field("integer", unit="1", description="Width of the returned image in pixels"),
                "height": Field("integer", unit="1", description="Height of the returned image in pixels"),
                "media_type": Field("string", description="Media type of image_ref"),
            })
    def acquire_image(self, width, height, dwell_time, pixel_size, invert=False):
        self.check_cancelled()
        params = {"resolution": (int(width), int(height)),
                  "pixel_size": float(pixel_size),
                  "dwell_time": float(dwell_time)}
        if invert:
            params["invert"] = True
        rows = _image_rows(self.native.get_image(params))
        path, image_width, image_height = _write_pgm(rows)
        return {"image_ref": path, "width": image_width, "height": image_height,
                "media_type": "image/x-portable-graymap"}

    # -- setup and focus actions -----------------------------------------------------------------------------------
    @action(name="x-cap.cfpark00.auto_focus.v1",
            description="Run the native autofocus with its non-baseline Volumescope settings",
            output={"applied": Field("boolean",
                                     description="True when the native auto_focus returned; its own exception "
                                                 "handler restores the baseline focus and warns")})
    def auto_focus(self):
        self.check_cancelled()
        self.native.auto_focus()
        return {"applied": True}

    @action(name="x-cap.cfpark00.prepare_acquisition.v1",
            description="Run the native prepare_acquisition sequence (contrast, focus, lens alignment, stig)",
            output={"prepared": Field("boolean",
                                      description="True when the native prepare_acquisition returned")})
    def prepare_acquisition(self):
        self.check_cancelled()
        self.native.prepare_acquisition()
        return {"prepared": True}

    # -- stage motion ---------------------------------------------------------------------------------------------
    @action(name="x-cap.cfpark00.move_stage.v1",
            description="Move the specimen stage to an absolute raw stage position with the native move",
            input={
                "x": Field("number", unit="1", description="Stage x in the native raw coordinate unit",
                           limit=Limit.operator_required(_STAGE_REASON)),
                "y": Field("number", unit="1", description="Stage y in the native raw coordinate unit",
                           limit=Limit.operator_required(_STAGE_REASON)),
                "z": Field("number", unit="1", description="Stage z in the native raw coordinate unit",
                           limit=Limit.operator_required(_STAGE_REASON)),
                "r": Field("number", unit="1", description="Stage r (rotation) in the native raw coordinate unit",
                           limit=Limit.operator_required(_STAGE_REASON)),
                "t": Field("number", unit="1", description="Stage t (tilt) in the native raw coordinate unit",
                           limit=Limit.operator_required(_STAGE_REASON)),
            },
            output={"applied": Field("boolean",
                                     description="True when the native absolute_move returned")})
    def move_stage(self, x, y, z, r, t):
        self.check_cancelled()
        self.native.move(x=float(x), y=float(y), z=float(z), r=float(r), t=float(t))
        return {"applied": True}

    # -- safety ---------------------------------------------------------------------------------------------------
    @action(name="x-cap.cfpark00.release_microscope.v1",
            description="Release the vendor client with the native close (the safe state); it takes no input",
            output={"released": Field("boolean",
                                      description="True once the native close has been called")})
    def release_microscope(self):
        self._release()
        return {"released": True}


    def _release(self):
        if not getattr(self, "_released", False):
            self.native.close()
            self._released = True
