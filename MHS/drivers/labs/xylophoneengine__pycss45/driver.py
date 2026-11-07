"""OpenMHS driver for gh.xylophoneengine/pycss45: a Gigahertz-Optik CSS45 spectral sensor.

A direct Driver (decorated methods) over the upstream class ``pycss45:CSS45`` (pycss45.py:438), the
cross-platform driver for the CSS45/MSC15 spectral sensor.  The upstream class owns the wire protocol; the
device is opened over USB HID (default) or RS232/RS485 by ``native.py``.

* reads: the serial number, the firmware version, the status word, the PCB temperature, the CCT, the
  photopic and PAR integrals, the radiometric unit, the integration time of the last measurement and the
  two wavelength borders of the per-pixel mapping;
* ``cap.measure.spectrum.v1``: one automatic-integration-time measurement (``CSS45.measure``, pycss45.py:786)
  and the device's per-pixel wavelengths and spectral values inside the requested range.  The class output
  field ``intensities`` has the catalogue unit ``1``; the upstream spectrum is ``W m^-2 nm^-1`` per the
  vendor calibration (pycss45.py:138), so the values are those calibrated spectral values;
* the device only observes light: no method of the upstream class sets an output, a heater or a motor.  The
  driver is therefore R0 (observational, MHS/spec/04-safety.md) and declares no native e-stop; the runtime
  still latches a software-only e-stop.

Every Fact cites a line of the clone at the pinned commit (e4364bae4d889efd579ffb3c4947099405becb27).  This
package is model-authored and unreviewed: it is checked on the fake backend only and nothing here ran on a
spectrometer.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, read

#: The README line that states the wavelength borders of the device.
RANGE_REF = "README.md:102"
RANGE_REASON = (
    "the README states the wavelength borders of the CSS45 are 360-830 nm (verified on a live CSS45); the "
    "per-pixel borders are read from the device at runtime by get_wl_borders()"
)


class CSS45(Driver):
    device_id = "css45"
    device_kind = "instrument.spectrometer"
    mode = "hardware"
    risk = "R0"
    native = "pycss45:CSS45"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeCSS45"}
    vendor, model = "Gigahertz-Optik", "CSS45 (MSC15 family)"
    display_name = "Gigahertz-Optik CSS45 spectral sensor (pycss45.CSS45)"
    tags = ["spectrometer", "spectral-sensor", "optical", "gigahertz-optik", "css45", "msc15"]
    facts = [
        Fact("The module is a cross-platform driver for the Gigahertz-Optik CSS45/MSC15 spectral sensor and "
             "speaks the wire protocol over USB HID or RS232/RS485",
             source="upstream_code", ref="pycss45.py:1-9"),
        Fact("The spectral unit has 288 pixels (N_PIXELS)", source="upstream_code", ref="pycss45.py:31"),
        Fact("A Measurement holds the wavelengths in nm, the spectrum in W m^-2 nm^-1 per vendor calibration, "
             "the integration time in s, the CCT in K, the photopic integral and PAR",
             source="upstream_code", ref="pycss45.py:136-142"),
        Fact("measure() is the automatic integration time measurement (wire G07200, Ihi, G17) and returns a "
             "Measurement", source="upstream_code", ref="pycss45.py:786-789"),
        Fact("get_cct reads G22 in K, get_photopic reads G2R and get_par reads G2L",
             source="upstream_code", ref="pycss45.py:859-872"),
        Fact("get_temperature returns the PCB temperature in deg C; the unit is unverified",
             source="upstream_code", ref="pycss45.py:779-780"),
        Fact("get_wl_borders returns the first and last wavelength of the per-pixel mapping in nm",
             source="upstream_code", ref="pycss45.py:830-836"),
        Fact("get_radiometric_unit reads IhcU and returns W or W/m2", source="upstream_code",
             ref="pycss45.py:896-899"),
        Fact("get_last_integration_time reads Ihi in microseconds and returns seconds", source="upstream_code",
             ref="pycss45.py:811-815"),
        Fact("get_serial_number returns the USB descriptor serial on the hid transport and an empty string on "
             "the serial transport", source="upstream_code", ref="pycss45.py:751-759"),
        Fact("get_firmware_version sends P and returns the reply string", source="upstream_code",
             ref="pycss45.py:761-765"),
        Fact("get_status reads the I0 status word; positive codes are warnings and negative codes raise",
             source="upstream_code", ref="pycss45.py:767-777"),
        Fact("The README states the measured spectrum plots as nm vs W m^-2 nm^-1", source="vendor_doc",
             ref="README.md:58-66"),
        Fact("The README states the wavelength borders of the CSS45 are 360-830 nm, verified on a live "
             "CSS45", source="vendor_doc", ref="README.md:100-103"),
        Fact("The README states the GUI shows the photopic integral in lx and the radiometric integral in W/m2",
             source="vendor_doc", ref="README.md:119-120"),
        Fact("The README states the fixed integration times run from 12 us to 2.56 s", source="vendor_doc",
             ref="README.md:105-106"),
    ]

    # -- identity and state -----------------------------------------------------------------------------------
    @read("serial_number", type="string", description="Serial number of the device")
    def serial_number(self):
        return str(self.native.get_serial_number())

    @read("firmware_version", type="string", description="Firmware version reported by the device")
    def firmware_version(self):
        return str(self.native.get_firmware_version())

    @read("status", type="integer", unit="1",
          description="Device status word (I0); positive values are warnings, zero is success")
    def status(self):
        return int(self.native.get_status())

    @read("temperature", unit="Cel", description="PCB temperature of the device")
    def temperature(self):
        return float(self.native.get_temperature())

    @read("cct", unit="K", description="Correlated colour temperature of the last measurement")
    def cct(self):
        return float(self.native.get_cct())

    @read("photopic", unit="lx", description="Photopic integral of the last measurement")
    def photopic(self):
        return float(self.native.get_photopic())

    @read("par", description="Photosynthetically active radiation (PAR) of the last measurement; no text file "
                             "of the clone states its unit")
    def par(self):
        return float(self.native.get_par())

    @read("radiometric_unit", type="string",
          description="Unit of the radiometric values as the device reports it (W or W_PER_M2)")
    def radiometric_unit(self):
        unit = self.native.get_radiometric_unit()
        return str(getattr(unit, "name", unit))

    @read("last_integration_time", unit="s", description="Integration time of the last measurement")
    def last_integration_time(self):
        return float(self.native.get_last_integration_time())

    @read("wavelength_start", unit="nm", description="First wavelength of the per-pixel mapping")
    def wavelength_start(self):
        return float(self.native.get_wl_borders()[0])

    @read("wavelength_end", unit="nm", description="Last wavelength of the per-pixel mapping")
    def wavelength_end(self):
        return float(self.native.get_wl_borders()[1])

    # -- measurement ------------------------------------------------------------------------------------------
    @action(
        cap="cap.measure.spectrum.v1",
        description="Measure the spectrum with the automatic integration time and return the device's "
                    "per-pixel wavelengths and spectral values inside the requested range.  The spectral "
                    "values are the calibrated W m^-2 nm^-1 values of the upstream spectrum; the catalogue "
                    "unit of the intensities field is 1",
        input={
            "wavelength_min": Field(
                "number", unit="nm",
                description="Lower end of the requested wavelength range, in nanometres",
                limit=Limit(min=360, max=830, unit="nm", source="vendor_doc", ref=RANGE_REF,
                            reason=RANGE_REASON)),
            "wavelength_max": Field(
                "number", unit="nm",
                description="Upper end of the requested wavelength range, in nanometres",
                limit=Limit(min=360, max=830, unit="nm", source="vendor_doc", ref=RANGE_REF,
                            reason=RANGE_REASON)),
        },
    )
    def measure_spectrum(self, wavelength_min, wavelength_max):
        measurement = self.native.measure()
        low, high = sorted((float(wavelength_min), float(wavelength_max)))
        wavelengths = []
        intensities = []
        for wavelength, value in zip(measurement.wavelengths, measurement.spectrum):
            wavelength = float(wavelength)
            if low <= wavelength <= high:
                wavelengths.append(wavelength)
                intensities.append(float(value))
        if not wavelengths:
            # A range between two pixels of the device grid: return the nearest pixel, so the receipt never
            # carries an empty spectrum for a range the device accepted.
            midpoint = (low + high) / 2.0
            nearest = min(
                range(len(measurement.wavelengths)),
                key=lambda index: abs(float(measurement.wavelengths[index]) - midpoint),
            )
            wavelengths = [float(measurement.wavelengths[nearest])]
            intensities = [float(measurement.spectrum[nearest])]
        return {"wavelengths": wavelengths, "intensities": intensities}

    # -- lifecycle --------------------------------------------------------------------------------------------
    def teardown(self):
        self.native.disconnect()
