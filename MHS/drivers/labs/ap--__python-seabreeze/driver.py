"""OpenMHS driver for gh.ap/python-seabreeze: one Ocean Optics spectrometer over the SeaBreeze backends.

A direct Driver (decorated methods) over the upstream class seabreeze.spectrometers:Spectrometer
(src/seabreeze/spectrometers.py:97), the model independent interface to the spectrometers the SeaBreeze backends
support.  The class is opened from the first available device (Spectrometer.from_first_available,
src/seabreeze/spectrometers.py:140) or from a serial number (Spectrometer.from_serial_number,
src/seabreeze/spectrometers.py:155) by ``native.py``.

* reads: the number of detector pixels, the maximum intensity the device can return, the serial number and the model
  type of the opened spectrometer;
* ``cap.measure.intensity.v1`` (the class verb is read): the intensity the detector sees, in the arbitrary
  intensity units of the upstream (src/seabreeze/spectrometers.py:212-213).  With a declared wavelength the value is
  the intensity of the detector pixel whose calibrated wavelength (Spectrometer.wavelengths,
  src/seabreeze/spectrometers.py:187-190) is nearest; without one it is the intensity of the brightest detector
  pixel, the peak over the whole detector.  A declared integration time is applied before the read;
* ``x-cap.ap.set_integration_time.v1``: the detector integration time, converted from milliseconds to the whole
  microseconds the upstream call takes (src/seabreeze/spectrometers.py:305);
* the native stop is ``Spectrometer.close`` (src/seabreeze/spectrometers.py:413): the class has no separate
  acquisition stop, an acquisition is the blocking ``intensities()`` read, and closing the device ends it.

What this package does not expose: the spectral array itself (the full wavelength/intensity arrays of all pixels).
The standard has no artifact transport, and a fake cannot reproduce the model-dependent pixel count of a real
detector, so an array capability would either ship a truncated spectrum or need the artifact store
(cap.measure.spectrum.v1 expects an artifact_ref for large spectra).  The GPIO, pixel-binning, optical-bench and
Wi-Fi feature classes of the card's entry_symbols are definitions in the pyseabreeze backend (the module is marked
TODO and every method raises NotImplementedError, src/seabreeze/pyseabreeze/features/gpio.py:7), are reached
through the device's feature dictionary rather than through Spectrometer, and bind io resource kinds that an
instrument.spectrometer does not declare; they are not exposed.  The trigger mode is not exposed either: the
upstream states that its value is the one in the device's datasheet (src/seabreeze/spectrometers.py:344-351) and the
class has no getter that would report an applied mode.

Every Fact cites a line of the clone at the pinned commit (3de4fdd6bbb533a701309c746c94cac2ffc05be0).  This package
is model-authored and unreviewed: it is checked on the fake backend only, and nothing here ran on a spectrometer.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read

#: The upstream module of the native class, relative to the clone root.
SPECTROMETERS = "src/seabreeze/spectrometers.py"
#: The per-model declarations of the pyseabreeze backend (integration time bounds, pixel count).
DEVICES = "src/seabreeze/pyseabreeze/devices.py"

#: Why an operator must state the two bounds this package cannot source (see site-limits.example.json).
INTEGRATION_REASON = (
    "no line of the clone states one integration time range for the device: the bounds are declared per "
    "spectrometer model in the pyseabreeze backend (src/seabreeze/pyseabreeze/devices.py:503-504, 579-580) and the "
    "class reads them from the device at runtime (Spectrometer.integration_time_micros_limits, "
    "src/seabreeze/spectrometers.py:334-342); the site states the range of its spectrometer")
WAVELENGTH_REASON = (
    "no line of the clone states the wavelength range of the device: it is held in the wavelength calibration of "
    "the detector and is read at runtime (Spectrometer.wavelengths, src/seabreeze/spectrometers.py:187-190); the "
    "site states the range of its spectrometer")


class SeaBreezeSpectrometer(Driver):
    device_id = "seabreeze-spectrometer"
    device_kind = "instrument.spectrometer"
    mode = "hardware"
    risk = "R1"
    native = "seabreeze.spectrometers:Spectrometer"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeSpectrometer"}
    vendor, model = "Ocean Optics", "SeaBreeze spectrometer"
    display_name = "Ocean Optics spectrometer (python-seabreeze Spectrometer)"
    tags = ["spectrometer", "ocean-optics", "seabreeze", "spectroscopy", "intensity"]
    facts = [
        Fact("Spectrometer is the model independent interface to all spectrometers the backends support",
             source="upstream_code", ref=f"{SPECTROMETERS}:97-98"),
        Fact("from_first_available opens the first available unopened spectrometer", source="upstream_code",
             ref=f"{SPECTROMETERS}:140-141"),
        Fact("from_serial_number opens the spectrometer with the given serial number and refuses one that is "
             "already open", source="upstream_code", ref=f"{SPECTROMETERS}:155-185"),
        Fact("wavelengths() returns the wavelength in (nm) that corresponds to each pixel of the spectrometer",
             source="upstream_code", ref=f"{SPECTROMETERS}:187-190"),
        Fact("intensities() returns the measured intensities in arbitrary units (a.u.), and the measuring behavior "
             "can be adjusted by setting the trigger mode", source="upstream_code", ref=f"{SPECTROMETERS}:202-205"),
        Fact("The intensities are in arbitrary units and their range depends on the ADC bit resolution of the "
             "hardware of the specific spectrometer", source="upstream_code", ref=f"{SPECTROMETERS}:212-213"),
        Fact("max_intensity is the maximum intensity the spectrometer can return in (a.u.); the spectrometer may "
             "saturate at lower values", source="upstream_code", ref=f"{SPECTROMETERS}:265-271"),
        Fact("integration_time_micros() sets the detector integration time, in microseconds", source="upstream_code",
             ref=f"{SPECTROMETERS}:305-310"),
        Fact("integration_time_micros_limits returns the min and max integration time in microseconds that the "
             "device reports", source="upstream_code", ref=f"{SPECTROMETERS}:334-342"),
        Fact("The trigger mode value is the one the device's datasheet defines; the class states no enumeration for "
             "a generic device", source="upstream_code", ref=f"{SPECTROMETERS}:344-351"),
        Fact("serial_number is the spectrometer's serial number and model is its model type", source="upstream_code",
             ref=f"{SPECTROMETERS}:356-363"),
        Fact("pixels is the number of pixels of the spectrometer's detector", source="upstream_code",
             ref=f"{SPECTROMETERS}:366-367"),
        Fact("features returns a dictionary of all supported features of the spectrometer and gives direct access "
             "to the features provided by the backend interface", source="upstream_code",
             ref=f"{SPECTROMETERS}:372-376"),
        Fact("close() closes the connection to the SeaBreezeDevice", source="upstream_code",
             ref=f"{SPECTROMETERS}:413-414"),
        Fact("The pyseabreeze backend declares the integration time bounds per spectrometer model: USB2000PLUS "
             "1000 and 655350000 microseconds", source="upstream_code", ref=f"{DEVICES}:503-504"),
        Fact("The pyseabreeze backend declares different integration time bounds for the USB2000: 3000 and "
             "655350000 microseconds", source="upstream_code", ref=f"{DEVICES}:579-580"),
        Fact("The GPIO feature class of the pyseabreeze backend is a definition only: the module is marked TODO and "
             "every method raises NotImplementedError", source="upstream_code",
             ref="src/seabreeze/pyseabreeze/features/gpio.py:7"),
        Fact("The pixel-binning feature class of the pyseabreeze backend is a definition only: the module is marked "
             "TODO and every method raises NotImplementedError", source="upstream_code",
             ref="src/seabreeze/pyseabreeze/features/pixelbinning.py:7"),
        Fact("The README acquires a spectrum by setting the integration time and then calling wavelengths() and "
             "intensities()", source="vendor_doc", ref="README.md:56-67"),
    ]
    safe_state = "acquisition ended and the device connection closed (Spectrometer.close)"

    # -- state ----------------------------------------------------------------------------------------------------
    @read("pixel_count", type="integer", unit="1", description="Number of pixels of the spectrometer's detector")
    def pixel_count(self):
        return int(self.native.pixels)

    @read("max_intensity", unit="1",
          description="The maximum intensity the spectrometer can return, in arbitrary intensity units (a.u.)")
    def max_intensity(self):
        return float(self.native.max_intensity)

    @read("serial_number", type="string", description="Serial number of the opened spectrometer")
    def serial_number(self):
        return str(self.native.serial_number)

    @read("model_name", type="string", description="Model type of the opened spectrometer")
    def model_name(self):
        return str(self.native.model)

    # -- measurement and configuration -----------------------------------------------------------------------------
    @action(cap="cap.measure.intensity.v1",
            description="Measure the intensity the detector sees: with a declared wavelength the intensity of the "
                        "detector pixel nearest to it, without one the intensity of the brightest detector pixel "
                        "(the peak over the whole detector), in arbitrary units (a.u.)",
            input={"wavelength_nm": Field(
                       "number", unit="nm",
                       description="Wavelength in nanometres; the driver reads the detector pixel whose calibrated "
                                   "wavelength is nearest to it. Leave it out to read the brightest pixel",
                       limit=Limit.operator_required(WAVELENGTH_REASON)),
                   "integration_ms": Field(
                       "number", unit="ms",
                       description="Integration time to apply before the measurement, in milliseconds; leave it out "
                                   "to measure with the integration time the device already has",
                       limit=Limit.operator_required(INTEGRATION_REASON))})
    def measure_intensity(self, wavelength_nm=None, integration_ms=None):
        output = {}
        if integration_ms is not None:
            micros = int(round(float(integration_ms) * 1000.0))
            self.native.integration_time_micros(micros)
            output["integration_ms"] = micros / 1000.0
        intensities = [float(item) for item in self.native.intensities()]
        if wavelength_nm is None:
            output["intensity"] = float(max(intensities))
            return output
        wavelengths = [float(item) for item in self.native.wavelengths()]
        target = float(wavelength_nm)
        index = min(range(len(wavelengths)), key=lambda item: abs(wavelengths[item] - target))
        output["intensity"] = intensities[index]
        return output

    @action(name="x-cap.ap.set_integration_time.v1",
            description="Set the detector integration time (Spectrometer.integration_time_micros); the value is "
                        "given in whole microseconds after the conversion from milliseconds",
            input={"integration_ms": Field(
                "number", unit="ms", description="Integration time to set, in milliseconds",
                limit=Limit.operator_required(INTEGRATION_REASON))},
            output={"integration_ms": Field(
                "number", unit="ms",
                description="The integration time the driver applied, in milliseconds (whole microseconds)")})
    def set_integration_time(self, integration_ms):
        micros = int(round(float(integration_ms) * 1000.0))
        self.native.integration_time_micros(micros)
        return {"integration_ms": micros / 1000.0}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop(native="close")
    def stop(self):
        """The native stop: the runtime latches first, then Spectrometer.close() closes the device connection."""
        self.native.close()

    def teardown(self):
        self.native.close()
