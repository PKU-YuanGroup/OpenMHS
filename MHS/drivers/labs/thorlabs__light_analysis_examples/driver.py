"""OpenMHS driver for gh.thorlabs/light_analysis_examples: a Thorlabs BC207/BC210 beam profiler.

A direct Driver (decorated methods) over the upstream ctypes wrapper
``pyfile:Python/Thorlabs BC207 BC210 Beam Profiler/TLBC2.py#TLBC2``.  The upstream class loads the Thorlabs
Beam SDK DLL (TLBC2_64.dll on 64-bit Python), keeps a VISA session and exposes every measurement through a
``TLBC2_*`` entry point that returns a ViStatus code and writes its results through ctypes output parameters
(TLBC2.py:158-188, 494-505).

The SDK forbids importing ctypes from package code (G3 FORBIDDEN).  The production adapter ``native.py`` owns
that conversion: it calls the upstream methods with real ctypes pointers and fills one-element Python lists for
the driver.  ``fake.py`` mirrors that adapted surface, method for method, and the upstream method names are kept
so gate G7 can check them against the pinned class.

* reads: sensor geometry and pixel pitch, exposure (ms), wavelength (nm), precision mode, binning, ROI and the
  sensor temperature (Cel);
* writes: exposure and wavelength, whose ranges the instrument reports at run time (``Limit.operator_required``,
  filled by the site), precision mode (0/1) and binning (1, 2, 4, 8 or 16), both with bounds stated by the clone;
* actions: ``cap.sensing.image.v1`` requests a measurement and returns the raw image the device sends, and
  ``x-cap.thorlabs.measure_beam.v1`` requests a measurement and returns the beam analysis values (no catalogue
  class carries beam width, centroid, peak, saturation and power together);
* stop: ``close()`` closes the owned session after active native calls settle; reset cannot reopen it.
  The e-stop is declared terminal (``estop_terminal``, CORE-087): after it the endpoint refuses every reset
  with ``terminal_estop`` and keeps the latch, and recovery is a new endpoint with a new session.
  This is not an optical-source shutdown or a physical safety certification.

Every Fact cites a line of the clone at the pinned commit (1e7f3aa6fe29ca9739c582464bf870232232567b).  This
package is model-authored and has no human review. Native-shaped tests use controlled doubles only.
Nothing here ran on hardware; the hardware path needs Windows,
the Thorlabs Beam SDK DLL and the IVI VISA runtime the upstream sample adds to the DLL search path
(TLBC2_sample_2D_output.py:34).
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

TLBC2 = "Python/Thorlabs BC207 BC210 Beam Profiler/TLBC2.py"
PROFILER_README = "Python/Thorlabs BC207 BC210 Beam Profiler/README.md"
SAMPLE = "Python/Thorlabs BC207 BC210 Beam Profiler/TLBC2_sample_2D_output.py"


def _slot():
    """One native output parameter: the adapter fills element 0 (the ctypes pointer of the hardware path)."""
    return [None]


def _read_one(method):
    """Call a native getter that has one output parameter and return the value it filled."""
    out = _slot()
    method(out)
    return out[0]


def _read_many(method, count):
    """Call a native getter with ``count`` output parameters and return the values in order."""
    slots = [_slot() for _ in range(count)]
    method(*slots)
    return [slot[0] for slot in slots]


class Tlbc2BeamProfiler(Driver):
    device_id = "tlbc2"
    device_kind = "sensor.camera"
    mode = "hardware"
    risk = "R1"
    native = "pyfile:" + TLBC2 + "#TLBC2"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeTLBC2"}
    vendor, model = "Thorlabs", "BC207/BC210 beam profiler"
    display_name = "Thorlabs BC207/BC210 beam profiler (TLBC2.py)"
    tags = ["beam-profiler", "camera", "thorlabs", "bc207", "bc210", "ctypes", "windows"]
    facts = [
        Fact("The repository's beam profiler examples cover the BC207VIS, BC210CV and BC210CU",
             source="vendor_doc", ref="README.md:12"),
        Fact("TLBC2.py is the Python wrapper for the BC207 or BC210 beam profiler and loads the DLL for it",
             source="vendor_doc", ref=PROFILER_README + ":3-6"),
        Fact("The upstream class takes a resource name, an identification-query flag and a reset flag and loads "
             "TLBC2_32.dll on 32-bit or TLBC2_64.dll on 64-bit Python", source="upstream_code",
             ref=TLBC2 + ":158-181"),
        Fact("get_exposure_time returns a status code and writes exposure through a c_double output pointer",
             source="upstream_code",
             ref=TLBC2 + ":494-505"),
        Fact("The exposure time is in ms, and the supported range is queried from the instrument with "
             "get_exposure_time_range", source="upstream_code", ref=TLBC2 + ":476-514"),
        Fact("The gain is in dB, and the supported range is queried from the instrument",
             source="upstream_code", ref=TLBC2 + ":393-432"),
        Fact("The precision mode values are 0 = Fast and 1 = Precise", source="upstream_code",
             ref=TLBC2 + ":529-530"),
        Fact("The binning modes are 1, 2, 4, 8 and 16", source="upstream_code", ref=TLBC2 + ":582-589"),
        Fact("The ROI is at most the full sensor size and at least 32 x 32 pixels; set_roi requires width and "
             "height multiples of 4", source="upstream_code", ref=TLBC2 + ":622-660"),
        Fact("The sensor information reports pixel counts and the horizontal and vertical pixel pitch in um",
             source="upstream_code", ref=TLBC2 + ":594-608"),
        Fact("get_image requires a 2448*2048*2 byte output buffer and reports "
             "width, height and bytes per pixel (1 in fast mode, 2 in precision mode)", source="upstream_code",
             ref=TLBC2 + ":1508-1517"),
        Fact("request_new_measurement reads a new image and stores the calculations internally for the get_XXXX "
             "functions", source="upstream_code", ref=TLBC2 + ":1498-1506"),
        Fact("The scan-data structure stores fourSigmaX and fourSigmaY as standard deviations in pixels",
             source="upstream_code", ref=TLBC2 + ":97-98"),
        Fact("get_beam_width_4_sigma returns the second moment multiplied by 4 in x and y, the rotated widths, "
             "the azimuth angle and the ellipticity", source="upstream_code", ref=TLBC2 + ":1665-1679"),
        Fact("get_centroid returns the centroid pixel position relative to the top left corner of the image",
             source="upstream_code", ref=TLBC2 + ":1609-1621"),
        Fact("get_peak reports the peak intensity in digits, maximal 4096 in precision mode and 255 in fast mode",
             source="upstream_code", ref=TLBC2 + ":1571-1581"),
        Fact("get_saturation reports ratios in the range 0.0 to 1.0", source="upstream_code",
             ref=TLBC2 + ":1589-1599"),
        Fact("get_power returns the total power in dBm", source="upstream_code", ref=TLBC2 + ":1623-1628"),
        Fact("get_temperature returns the sensor temperature in Celsius degrees", source="upstream_code",
             ref=TLBC2 + ":1798-1803"),
        Fact("get_wavelength and set_wavelength operate in nm", source="upstream_code",
             ref=TLBC2 + ":906-924"),
        Fact("close closes the instrument session and the instrument must be reinitialized to use it again",
             source="upstream_code", ref=TLBC2 + ":229-239"),
        Fact("open initializes the instrument driver session: it opens a session, can query the identification, "
             "resets the instrument to a known state and sends it initialization commands",
             source="upstream_code", ref=TLBC2 + ":201-208"),
        Fact("The sample adds the IVI Foundation VISA DLL directory before it loads the beam profiler DLL",
             source="upstream_code", ref=SAMPLE + ":34"),
    ]
    safe_state = "owned instrument session closed after native calls settle; no optical-source shutdown claim"
    # CORE-087.  Upstream: a closed session must be reinitialized, and open() resets and initializes the
    # instrument (the two Facts above).  Package policy: a reset only re-establishes communication that changes
    # nothing on the device, so it never reopens the session; recovery is a new endpoint.
    estop_terminal = ("close() ends the TLBC2 instrument session and the instrument must be reinitialized before it "
                      "is used again (TLBC2.py:229-239), and reinitializing it with open() resets the instrument and "
                      "sends it initialization commands (TLBC2.py:201-208), so only a new native session on a new "
                      "endpoint recovers it")

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("sensor_pixels_x", type="integer", unit="1", description="Sensor width in pixels")
    def sensor_pixels_x(self):
        return int(_read_many(self.native.get_sensor_information, 4)[0])

    @read("sensor_pixels_y", type="integer", unit="1", description="Sensor height in pixels")
    def sensor_pixels_y(self):
        return int(_read_many(self.native.get_sensor_information, 4)[1])

    @read("pixel_pitch_horizontal", unit="um", description="Horizontal distance between pixel edges in um")
    def pixel_pitch_horizontal(self):
        return float(_read_many(self.native.get_sensor_information, 4)[2])

    @read("pixel_pitch_vertical", unit="um", description="Vertical distance between pixel edges in um")
    def pixel_pitch_vertical(self):
        return float(_read_many(self.native.get_sensor_information, 4)[3])

    @read("roi_left", type="integer", unit="1", description="Left border of the region of interest in pixels")
    def roi_left(self):
        return int(_read_many(self.native.get_roi, 4)[0])

    @read("roi_top", type="integer", unit="1", description="Top border of the region of interest in pixels")
    def roi_top(self):
        return int(_read_many(self.native.get_roi, 4)[1])

    @read("roi_width", type="integer", unit="1", description="Width of the region of interest in pixels")
    def roi_width(self):
        return int(_read_many(self.native.get_roi, 4)[2])

    @read("roi_height", type="integer", unit="1", description="Height of the region of interest in pixels")
    def roi_height(self):
        return int(_read_many(self.native.get_roi, 4)[3])

    @read("exposure_time", unit="ms", description="Exposure time in ms")
    def exposure_time(self):
        return float(_read_one(self.native.get_exposure_time))

    @read("wavelength", unit="nm", description="Operating wavelength in nm")
    def wavelength(self):
        return float(_read_one(self.native.get_wavelength))

    @read("precision_mode", type="integer", unit="1",
          description="Precision mode: 0 = Fast (8 bit), 1 = Precise (12/16 bit)")
    def precision_mode(self):
        return int(_read_one(self.native.get_precision_mode))

    @read("binning", type="integer", unit="1", description="Binning factor in each dimension")
    def binning(self):
        return int(_read_one(self.native.get_binning))

    @read("sensor_temperature", unit="Cel", description="Temperature near the camera sensor")
    def sensor_temperature(self):
        return float(_read_one(self.native.get_temperature))

    # -- writes ---------------------------------------------------------------------------------------------------
    @write("exposure_time", unit="ms", description="Exposure time in ms",
           limit=Limit.operator_required(
               "the clone states the exposure is in ms and that the supported range is queried from the instrument "
               "with get_exposure_time_range (TLBC2.py:476-514); no text file of the clone states a numeric range, "
               "so the site supplies it"))
    def set_exposure_time(self, value):
        self.native.set_exposure_time(float(value))
        return float(_read_one(self.native.get_exposure_time))

    @write("wavelength", unit="nm", description="Operating wavelength in nm",
           limit=Limit.operator_required(
               "the clone states the wavelength range is queried from the instrument with get_wavelength_range "
               "(TLBC2.py:884-904) and lists only typical VIS/UV values; the site supplies the range of its unit"))
    def set_wavelength(self, value):
        self.native.set_wavelength(float(value))
        return float(_read_one(self.native.get_wavelength))

    @write("precision_mode", type="integer", unit="1",
           description="Precision mode: 0 = Fast, 1 = Precise",
           limit=Limit(allowed=[0, 1], source="upstream_code", ref=TLBC2 + ":529-530"))
    def set_precision_mode(self, value):
        self.native.set_precision_mode(int(value))
        return int(_read_one(self.native.get_precision_mode))

    @write("binning", type="integer", unit="1", description="Binning factor in each dimension",
           limit=Limit(allowed=[1, 2, 4, 8, 16], source="upstream_code", ref=TLBC2 + ":582-589"))
    def set_binning(self, value):
        self.native.set_binning(int(value))
        return int(_read_one(self.native.get_binning))

    # -- actions --------------------------------------------------------------------------------------------------
    @action(cap="cap.sensing.image.v1",
            description="Request a new measurement and return the raw image buffer the beam profiler sends, "
                        "with actual geometry; opaque raw8/raw16 preserves bytes without endian inference",
            input={
                "width": Field("integer", unit="1",
                               description="Requested ROI width in pixels; omit it to keep the configured ROI",
                               limit=Limit.operator_required(
                                   "the clone states the ROI is at most the full sensor size, at least 32 x 32 "
                                   "pixels and a width multiple of 4 (TLBC2.py:622-660); the sensor size is queried "
                                   "from the instrument, so the site supplies the range")),
                "height": Field("integer", unit="1",
                                description="Requested ROI height in pixels; omit it to keep the configured ROI",
                                limit=Limit.operator_required(
                                    "the clone states the ROI is at most the full sensor size, at least 32 x 32 "
                                    "pixels and a height multiple of 4 (TLBC2.py:622-660); the sensor size is "
                                    "queried from the instrument, so the site supplies the range")),
                "exposure_ms": Field("number", unit="ms",
                                     description="Exposure for this capture in ms; omit it to keep the configured "
                                                 "exposure",
                                     limit=Limit.operator_required(
                                         "the clone states the exposure is in ms and that the supported range is "
                                         "queried from the instrument with get_exposure_time_range "
                                         "(TLBC2.py:476-514); the site supplies it")),
            })
    def capture(self, width=None, height=None, exposure_ms=None):
        # Fail before native mutation when the endpoint has no authorized artifact publisher.
        try:
            from mhs.artifacts import publisher_from_context
        except ImportError as exc:
            raise DriverFailed("MHS.DEVICE.NOT_READY", "image artifact SDK support is not installed") from exc
        publisher = publisher_from_context(self.ctx)
        if publisher is None:
            raise DriverFailed("MHS.DEVICE.NOT_READY", "capture requires an endpoint-owned artifact store")
        if exposure_ms is not None:
            self.native.set_exposure_time(float(exposure_ms))
            self.check_cancelled()
        if width is not None or height is not None:
            left, top, current_width, current_height = _read_many(self.native.get_roi, 4)
            self.check_cancelled()
            self.native.set_roi(int(left), int(top),
                                int(width if width is not None else current_width),
                                int(height if height is not None else current_height))
            self.check_cancelled()
        self.native.request_new_measurement()
        self.check_cancelled()
        pixels_x, pixels_y = _read_many(self.native.get_sensor_information, 4)[:2]
        self.check_cancelled()
        precision = int(_read_one(self.native.get_precision_mode))
        self.check_cancelled()
        bytes_per_pixel = 2 if precision == 1 else 1
        if not (1 <= int(pixels_x) <= 2448 and 1 <= int(pixels_y) <= 2048 and precision in (0, 1)):
            raise DriverFailed("MHS.DEVICE.FAULTED", "sensor geometry or precision mode is invalid")
        # TLBC2.py:1513 requires this capacity even when the ROI is much smaller.
        buffer = bytearray(2448 * 2048 * 2)
        width, height, bpp = _slot(), _slot(), _slot()
        self.native.get_image(buffer, width, height, bpp)
        self.check_cancelled()
        actual_width, actual_height, actual_bpp = int(width[0]), int(height[0]), int(bpp[0])
        if not (1 <= actual_width <= 2448 and 1 <= actual_height <= 2048 and actual_bpp in (1, 2)):
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               "get_image returned an unusable image geometry",
                               native_code=[actual_width, actual_height, actual_bpp])
        used = actual_width * actual_height * actual_bpp
        if used > len(buffer):
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               "get_image reported more bytes than the fixed vendor buffer",
                               native_code=used)
        image = bytes(memoryview(buffer)[:used])
        if bytes_per_pixel != actual_bpp:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               "get_image reported a bytes-per-pixel value the precision mode does not allow",
                               native_code=actual_bpp)
        exposure = float(_read_one(self.native.get_exposure_time))
        self.check_cancelled()
        # These package-specific opaque formats preserve every byte. raw16 states
        # sample width, not byte order, calibration or a display interpretation.
        media_type = "application/vnd.thorlabs.tlbc2.raw%d" % (actual_bpp * 8)
        descriptor = publisher.publish(image, media_type)
        return {
            "image_ref": descriptor["uri"],
            "width": actual_width,
            "height": actual_height,
            "media_type": media_type,
            "exposure_ms": exposure,
        }

    @action(name="x-cap.thorlabs.measure_beam.v1",
            description="Request a new measurement and return the 4-sigma beam widths, centroid, peak, "
                        "saturation and total power the instrument calculated",
            output={
                "beam_width_4sigma_x": Field("number", unit="1",
                                             description="4-sigma beam width in x, in pixels"),
                "beam_width_4sigma_y": Field("number", unit="1",
                                             description="4-sigma beam width in y, in pixels"),
                "beam_width_4sigma_x_rotated": Field("number", unit="1",
                                                     description="4-sigma width in the rotated x direction, in pixels"),
                "beam_width_4sigma_y_rotated": Field("number", unit="1",
                                                     description="4-sigma width in the rotated y direction, in pixels"),
                "azimuth_angle": Field("number",
                                       description="Native reported azimuth; the pinned API does not specify its unit"),
                "ellipticity": Field("number", unit="1", description="Ellipticity from the second moments"),
                "centroid_x": Field("number", unit="1", description="Centroid x position, in pixels"),
                "centroid_y": Field("number", unit="1", description="Centroid y position, in pixels"),
                "peak_intensity": Field("integer", unit="1",
                                        description="Peak intensity in digits (maximal 4096 precise, 255 fast)"),
                "peak_position_x": Field("integer", unit="1", description="Peak x position, in pixels"),
                "peak_position_y": Field("integer", unit="1", description="Peak y position, in pixels"),
                "saturation": Field("number", unit="1", description="Saturation ratio in the range 0.0 to 1.0"),
                "saturated_pixel_ratio": Field("number", unit="1",
                                               description="Ratio of saturated pixels in the calculation area"),
                "total_power_dbm": Field("number",
                                         description="Total power in dBm as the device reports it"),
                "sensor_temperature": Field("number", unit="Cel", description="Temperature near the camera sensor"),
            })
    def measure_beam(self):
        self.native.request_new_measurement()
        self.check_cancelled()
        widths = _read_many(self.native.get_beam_width_4_sigma, 6)
        self.check_cancelled()
        centroid = _read_many(self.native.get_centroid, 2)
        self.check_cancelled()
        peak = _read_many(self.native.get_peak, 3)
        self.check_cancelled()
        saturation = _read_many(self.native.get_saturation, 2)
        self.check_cancelled()
        power = float(_read_one(self.native.get_power))
        self.check_cancelled()
        temperature = float(_read_one(self.native.get_temperature))
        self.check_cancelled()
        return {
            "beam_width_4sigma_x": float(widths[0]),
            "beam_width_4sigma_y": float(widths[1]),
            "beam_width_4sigma_x_rotated": float(widths[2]),
            "beam_width_4sigma_y_rotated": float(widths[3]),
            "azimuth_angle": float(widths[4]),
            "ellipticity": float(widths[5]),
            "centroid_x": float(centroid[0]),
            "centroid_y": float(centroid[1]),
            "peak_intensity": int(peak[0]),
            "peak_position_x": int(peak[1]),
            "peak_position_y": int(peak[2]),
            "saturation": float(saturation[0]),
            "saturated_pixel_ratio": float(saturation[1]),
            "total_power_dbm": power,
            "sensor_temperature": temperature,
        }

    # -- safety ----------------------------------------------------------------------------------------------------
    @estop(native="close")
    def stop(self):
        """The native stop: close the instrument session (TLBC2.py:229-239)."""
        self.native.close()

    # No @reset hook: TLBC2.py:233 requires reinitialization and this package never reopens the session.  After
    # this endpoint's e-stop the runtime refuses every reset itself (terminal_estop, estop_terminal above) without
    # calling the bridge; a latch that a new endpoint restored is reset there with nothing to reopen, and the
    # session's closing state is irreversible (session.py), so a closed session never runs another native call.

    def teardown(self):
        """Release the vendor SDK when the server closes (TLBC2.py:241-248)."""
        self.native.closeSDK()
