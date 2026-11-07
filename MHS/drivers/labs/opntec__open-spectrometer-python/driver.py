"""OpenMHS driver for gh.opntec/open-spectrometer-python: one TCD1304 linear CCD on a PSLab.

A direct Driver (decorated methods) over the card's entry class TCD1304:TCD1304 (TCD1304.py:24), the module's
driver for a TCD1304 linear CCD connected to a PSLab.  The upstream class owns the PSLab connection: when it is
built without a device it creates a SerialHandler and composes the PWM generator, oscilloscope and power supply
over it (TCD1304.py:32-43); its constructor powers the CCD on and starts the three clocks (TCD1304.py:45-48).

* reads: the integration time per CCD element (the upstream ``integration_time`` attribute, converted from the
  upstream seconds to milliseconds) and the master clock frequency (the upstream ``master_clock_frequency``);
* one write: the same integration time, through ``cap.device.configure.v1``.  No text file of the clone states a
  range for it, so the bound is ``Limit.operator_required`` (``site-limits.example.json`` shows the overlay).
  The setter and the read action's one-shot input also call the native ``_start_sh_clock``, as the constructor
  does, so the SH clock follows the new value (TCD1304.py:45-48, TCD1304.py:72-73);
* ``cap.measure.intensity.v1`` (the class verb is read): one native ``read_signal`` capture, returning the
  largest raw sample of the captured CH1 waveform in arbitrary detector counts.  Its optional ``integration_ms``
  input applies a one-shot integration time before the capture (the same operator-required bound);
* the native stop is ``poweroff`` (``PowerSupply.pv1 = 0``, TCD1304.py:54-56).  A safety reset re-arms nothing
  (SAFE-042): ``poweron``, which restores the 5 V supply (TCD1304.py:50-52), is the declared re-enable
  ``x-cap.opntec.power_on.v1`` (``reenable=True``, CORE-086), a command of its own that the latch refuses.

The upstream ``read_signal`` returns only the raw waveform: it configures CH1, captures 3694 * 2 = 7388 samples
and returns the fetched array without a wavelength axis or a calibration (TCD1304.py:75-87).  This package
therefore does not bind ``cap.measure.spectrum.v1``: its wavelength_min/wavelength_max inputs could not be
applied, and inventing a pixel-to-wavelength map is not allowed.  The spectrum array is NOT COVERED; only the
scalar peak of one capture and the integration time cross the boundary.  The repository README documents a webcam
spectrometer and a manual pixel-to-wavelength calibration (README.md:8, README.md:46-55); it does not state a
TCD1304 calibration.

Every Fact cites a line of the clone at the pinned commit a15b67d9afb48713baeb748000433554adf26980.  This package
is model-authored and unreviewed: it is checked on the fake backend only, ``native.py`` was never imported, and no
hardware was attached.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

#: Why the integration time needs an operator bound: the constructor default is a default of the class, not a
#: bound of the device, and no text file of the clone states a range.
INTEGRATION_REASON = (
    "no text file of the clone states an integration time range: 10e-6 s is the constructor default of the "
    "upstream class (TCD1304.py:35), not a bound of the device, and the class documents no limits; the site "
    "supplies the per-element integration time range of its CCD")


class TCD1304Spectrometer(Driver):
    device_id = "tcd1304"
    device_kind = "instrument.spectrometer"
    mode = "hardware"
    risk = "R1"
    native = "TCD1304:TCD1304"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeTCD1304"}
    vendor, model = "OpnTec open spectrometer project", "TCD1304 linear CCD on PSLab"
    display_name = "TCD1304 linear CCD on a PSLab (open-spectrometer-python)"
    tags = ["spectrometer", "ccd", "tcd1304", "pslab", "optics", "intensity"]
    facts = [
        Fact("The module is a TCD1304 linear CCD driver for Open Spectrometer; its pin map assigns master_clock "
             "to SQ1, sh_clock to SQ2, icg_clock to SQ3, +5V to PV1, GND to GND and OS to CH1",
             source="upstream_code", ref="TCD1304.py:1-10"),
        Fact("The module imports SerialHandler, Oscilloscope, PowerSupply and PWMGenerator from the external "
             "pslab SDK", source="upstream_code", ref="TCD1304.py:15-18"),
        Fact("TCD1304 is a linear CCD suitable for visible spectrum analysis", source="upstream_code",
             ref="TCD1304.py:24-25"),
        Fact("The class declares 3694 integration elements, a CH1 range constant of 4, a trigger voltage constant "
             "of 2 and two samples per element", source="upstream_code", ref="TCD1304.py:27-30"),
        Fact("The constructor accepts a device, an integration time defaulting to 10e-6 and a master clock "
             "frequency defaulting to 2e6; without a device it creates SerialHandler and composes the PWM "
             "generator, oscilloscope and power supply over it", source="upstream_code", ref="TCD1304.py:32-43"),
        Fact("Construction powers the CCD on and starts the SQ3, master and SH clocks", source="upstream_code",
             ref="TCD1304.py:45-48"),
        Fact("poweron sets the PV1 supply to 5 and poweroff sets it to 0", source="upstream_code",
             ref="TCD1304.py:50-56"),
        Fact("poweron is documented as turning the TCD1304 on and poweroff as turning it off",
             source="upstream_code", ref="TCD1304.py:50-56"),
        Fact("The ICG readout waits 3694 * integration_time seconds before the waveform is fetched",
             source="upstream_code", ref="TCD1304.py:58-64"),
        Fact("The oscillator frequency constant is 128e6 and the microseconds constant is 1e6", source="upstream_code",
             ref="TCD1304.py:20-21"),
        Fact("The master clock prescaler is derived from the oscillator frequency and the master clock frequency",
             source="upstream_code", ref="TCD1304.py:66-70"),
        Fact("The SH clock is generated at 1 / integration_time with a 50 percent duty cycle", source="upstream_code",
             ref="TCD1304.py:72-73"),
        Fact("read_signal selects the CH1 range and trigger, captures 3694 * 2 samples with a time gap of "
             "integration_time / 2 in microseconds, starts the ICG clock and returns the fetched waveform",
             source="upstream_code", ref="TCD1304.py:75-87"),
        Fact("The README describes the repository's main components as analyse.py and calibrate.py for webcam "
             "spectrometer images; it does not document the TCD1304 class", source="vendor_doc", ref="README.md:8"),
        Fact("The README's calibration procedure assigns wavelength values to pixels by hand from a CFL "
             "reference; the TCD1304 class itself applies no wavelength calibration", source="vendor_doc",
             ref="README.md:46-55"),
    ]
    safe_state = ("CCD powered off (PowerSupply.pv1 = 0); a reset leaves it off until the declared re-enable "
                  "x-cap.opntec.power_on.v1 powers it on")

    # -- state ----------------------------------------------------------------------------------------------------
    @read("integration_time", unit="ms", native_unit="s",
          description="Integration time per TCD1304 element, as the upstream integration_time attribute holds it")
    def integration_time(self):
        return float(self.native.integration_time)

    @read("master_clock_frequency", unit="Hz",
          description="Master clock frequency applied on SQ1 (the upstream master_clock_frequency attribute)")
    def master_clock_frequency(self):
        return float(self.native.master_clock_frequency)

    @write("integration_time", unit="ms", native_unit="s",
           description="Integration time per TCD1304 element to set, in milliseconds",
           limit=Limit.operator_required(INTEGRATION_REASON))
    def set_integration_time(self, value):
        self._apply_integration_time(value)

    def _apply_integration_time(self, seconds):
        """Set the upstream attribute and regenerate the SH clock, as the constructor does."""
        self.native.integration_time = float(seconds)
        self.native._start_sh_clock()

    # -- measurement ----------------------------------------------------------------------------------------------
    @action(cap="cap.measure.intensity.v1",
            description="Capture one CH1 waveform with the native read_signal and return its largest raw sample "
                        "(arbitrary detector counts); the upstream applies no wavelength calibration, so no "
                        "wavelength or channel input is exposed",
            input={"integration_ms": Field(
                "number", unit="ms",
                description="Integration time per CCD element to apply before the capture, in milliseconds; leave "
                            "it out to capture with the integration time already on the device",
                limit=Limit.operator_required(INTEGRATION_REASON))})
    def measure_intensity(self, integration_ms=None):
        if integration_ms is not None:
            self._apply_integration_time(float(integration_ms) / 1000.0)
        samples = [float(item) for item in self.native.read_signal()]
        if not samples:
            raise DriverFailed("MHS.DEVICE.FAULTED", "read_signal returned no samples")
        return {"intensity": max(samples),
                "integration_ms": float(self.native.integration_time) * 1000.0}

    # -- safety ---------------------------------------------------------------------------------------------------
    @action(name="x-cap.opntec.power_on.v1", reenable=True,
            description="Power the CCD on again after a safety reset (the declared re-enable): poweron() sets the "
                        "PV1 supply to 5 V; it takes no input, is refused while the e-stop is latched and is never "
                        "run by the reset",
            output={"powered": Field("boolean", description="True once poweron() returned")})
    def power_on(self):
        """The new start command after a reset (SAFE-042, CORE-086): poweron, TCD1304.py:50-52."""
        self.native.poweron()
        return {"powered": True}

    @estop(native="poweroff")
    def emergency_stop(self):
        """The native stop: the runtime latches first, then poweroff() sets PV1 to 0."""
        self.native.poweroff()

    # No @reset: a safety reset releases the latch and re-arms nothing (SAFE-042).  The supply stays off until the
    # declared re-enable above is sent as its own command.
