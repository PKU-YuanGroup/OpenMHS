"""OpenMHS driver for gh.jordvl/pylabrobot-open-science-nd1000: the Thermo Fisher NanoDrop 1000.

A direct Driver over the clone's concrete ``Code/nanodrop.py:NanoDrop1000`` class, the USB transport for the NanoDrop
1000 spectrophotometer.  The card names the PyLabRobot helper, but this instrument is not a PyLabRobot
``LiquidHandler``: it is a spectrophotometer with a binary USB command mailbox (``Code/nanodrop.py:59-68``), so the
helper's ``PlrProfile`` cannot express it and this package uses a direct Driver (DEVIATION FROM THE CARD, recorded in
RESULT.json notes) with ``native.py`` as the hardware factory.

The clone exposes a synchronous, self-contained class: ``connect`` opens the USB device and downloads the factory
calibration (``Code/nanodrop.py:23-44``); ``take_blank`` captures the dark and blank baselines
(``Code/nanodrop.py:134-153``); ``measure_absorbance`` returns the 2048-point wavelength axis and the Beer-Lambert
absorbance (``Code/nanodrop.py:155-179``); ``get_raw_spectrum`` returns the raw detector frame
(``Code/nanodrop.py:111-131``).  The second card entry, ``ThermoFisherNanoDrop1000``, is a PyLabRobot ``Device``
wrapper over the same transport (``Code/ThermoFisherNanoDrop1000_PLR_V1.py:220-243``); it imports a PyLabRobot
device API that the clone does not vendor, so this package names the self-contained class instead.

Covered:

* reads/writes through ``cap.device.configure.v1``: the lamp, the sample-arm magnet and the integration time.  The
  integration-time bound 3 through 65535 ms is the range the clone's docstring states (``Code/nanodrop.py:71``);
  the lamp and magnet are booleans and have no numeric bound;
* ``cap.measure.spectrum.v1``: one absorbance spectrum after a blank, filtered to the requested wavelength range.
  No line of the clone states the detector's wavelength bounds, so both range inputs are
  ``Limit.operator_required``; ``site-limits.example.json`` is only an example operator overlay;
* ``x-cap.jordvl.take_blank.v1``: the dark and blank baseline acquisition the absorbance measurement needs;
* ``x-cap.jordvl.raw_spectrum.v1``: one raw 2048-pixel detector frame;
* safety: the e-stop turns the lamp and the sample-arm magnet off (``set_lamp(False)`` and ``set_magnet(False)``,
  the commands the upstream ``close()`` sends), the declared safe state.  The clone comments only the magnet-on
  command ("Arm down", ``Code/nanodrop.py:140``) and states nothing about the arm after the magnet is released.
  The clone documents no independent hardware e-stop, so ``estop_physical_ref`` is not set.
  The stop does not interrupt a USB read already in flight; that limitation is stated in RESULT.json notes.

Every Fact and every sourced Limit cites a line of the clone at the pinned commit
db60b66494230b65d0c88bca07ce1304a1a974ee; the two wavelength bounds are operator_required because no line of the
clone states the detector range.  The package is model-authored and unreviewed: only the fake backend was
exercised, and no hardware run is claimed.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, write

#: The clone's set_integration_time docstring states the valid exposure range (Code/nanodrop.py:71).
INTEGRATION_LIMIT = Limit(
    min=3,
    max=65535,
    unit="ms",
    source="upstream_code",
    ref="Code/nanodrop.py:71",
    reason="the set_integration_time docstring states the valid range 3 to 65535 ms",
)

#: No line of the clone states the detector's wavelength range; the site overlay supplies the requested range.
WAVELENGTH_MIN_LIMIT = Limit.operator_required(
    "no line of the clone states the wavelength range of the detector; the site supplies the range it will allow"
)
WAVELENGTH_MAX_LIMIT = Limit.operator_required(
    "no line of the clone states the wavelength range of the detector; the site supplies the range it will allow"
)


def _whole_milliseconds(value):
    """The integration time as an int: the upstream setter splits it into two bytes with ``&`` and ``>>``
    (Code/nanodrop.py:79-81), which a float cannot pass, so a fractional value is refused instead of rounded."""
    number = float(value)
    if not number.is_integer():
        raise DriverFailed(
            "MHS.CAPABILITY.INPUT_INVALID",
            f"integration time {value!r} ms is not a whole number of milliseconds; the upstream setter splits the "
            "value into two bytes (Code/nanodrop.py:79-81)",
        )
    return int(number)


class NanoDrop1000Spectrophotometer(Driver):
    device_id = "nanodrop-1000"
    device_kind = "instrument.spectrophotometer"
    mode = "hardware"
    risk = "R1"
    native = "Code.nanodrop:NanoDrop1000"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeNanoDrop1000"}
    vendor, model = "Thermo Fisher Scientific", "NanoDrop 1000"
    display_name = "Thermo Fisher NanoDrop 1000 spectrophotometer (Code/nanodrop.py:NanoDrop1000)"
    tags = ["spectrophotometer", "spectrometer", "absorbance", "uv-vis", "nanodrop", "usb", "pylabrobot"]
    safe_state = ("lamp command off (0x03 0x00) and sample-arm magnet command off (0x0F 0x00), the commands the "
                  "upstream close() sends; both are unacknowledged USB writes, the clone states nothing about the arm "
                  "position after the magnet is released, and a USB read already in flight is not interrupted")
    facts = [
        Fact(
            "NanoDrop1000 is a USB device with VID 0x2457, PID 0x1002, a command endpoint, a spectrum endpoint "
            "and a text/status endpoint",
            source="upstream_code",
            ref="Code/nanodrop.py:7-12",
        ),
        Fact(
            "connect() finds the device by VID/PID, sets its configuration, clears the three endpoint halts, sends "
            "the wake command 0x08 and the init command 0x01, then downloads the factory coefficients and "
            "calculates the wavelength axis",
            source="upstream_code",
            ref="Code/nanodrop.py:23-44",
        ),
        Fact(
            "close() turns the lamp and magnet off, resets the USB device and disposes the USB resources",
            source="upstream_code",
            ref="Code/nanodrop.py:46-56",
        ),
        Fact(
            "set_lamp(state) writes command 0x03 with 0xFF for on and 0x00 for off",
            source="upstream_code",
            ref="Code/nanodrop.py:62-64",
        ),
        Fact(
            "set_magnet(state) writes command 0x0F with 0xFF for on and 0x00 for off",
            source="upstream_code",
            ref="Code/nanodrop.py:66-68",
        ),
        Fact(
            "take_blank sets the magnet True before its dark reading, with the comment 'Arm down'",
            source="upstream_code",
            ref="Code/nanodrop.py:139-143",
        ),
        Fact(
            "measure_absorbance sets the magnet True before its sample reading",
            source="upstream_code",
            ref="Code/nanodrop.py:160-162",
        ),
        Fact(
            "set_integration_time(ms) documents the valid range 3 to 65535 ms, clamps outside it and writes command "
            "0x02 with a 16-bit little-endian exposure",
            source="upstream_code",
            ref="Code/nanodrop.py:70-81",
        ),
        Fact(
            "_calculate_x_axis builds a 2048-element wavelength array in nanometres from factory coefficients 1 "
            "through 4",
            source="upstream_code",
            ref="Code/nanodrop.py:103-108",
        ),
        Fact(
            "get_raw_spectrum() flushes stale image data, writes command 0x09 and decodes 64 reads of 64 bytes into "
            "2048 16-bit pixels",
            source="upstream_code",
            ref="Code/nanodrop.py:111-131",
        ),
        Fact(
            "take_blank(integration_ms=20) acquires a dark frame with the lamp off, then a blank frame with the lamp "
            "on, and turns the lamp and magnet off afterwards",
            source="upstream_code",
            ref="Code/nanodrop.py:134-153",
        ),
        Fact(
            "measure_absorbance(integration_ms=20) requires a stored dark and blank spectrum, arms the magnet, turns "
            "the lamp on, reads one frame and returns the wavelength axis with -log10((sample-dark)/(blank-dark))",
            source="upstream_code",
            ref="Code/nanodrop.py:155-179",
        ),
        Fact(
            "The example script plots the active sensor area roughly from 220 nm to 750 nm",
            source="upstream_code",
            ref="Code/main.py:22-28",
        ),
        Fact(
            "The installation guide says the NanoDrop uses an older USB 1.1 microcontroller and that its Python "
            "driver is installed with Zadig's libusb-win32 replacement",
            source="vendor_doc",
            ref="Code/NanoDropInstalInstructions.txt:3-20",
        ),
        Fact(
            "The PyLabRobot wrapper class ThermoFisherNanoDrop1000 constructs one ThermoFisherNanoDrop1000Driver and "
            "one absorbance backend sharing it",
            source="upstream_code",
            ref="Code/ThermoFisherNanoDrop1000_PLR_V1.py:220-235",
        ),
    ]

    # -- configuration -----------------------------------------------------------------------------------------
    @write(
        "lamp",
        type="boolean",
        description="Switch the instrument lamp on (True) or off (False); the clone sends USB command 0x03",
    )
    def set_lamp_state(self, value):
        self.native.set_lamp(bool(value))
        return bool(value)

    @write(
        "magnet",
        type="boolean",
        description="Switch the sample-arm magnet on (True) or off (False) with USB command 0x0F; the clone comments "
        "the magnet-on command 'Arm down' (Code/nanodrop.py:140) and states nothing about the arm after a release",
    )
    def set_magnet_state(self, value):
        self.native.set_magnet(bool(value))
        return bool(value)

    @write(
        "integration_time",
        unit="ms",
        description="Detector exposure time in milliseconds; the clone sends USB command 0x02",
        limit=INTEGRATION_LIMIT,
    )
    def set_integration_time_value(self, value):
        milliseconds = _whole_milliseconds(value)
        self.native.set_integration_time(milliseconds)
        return milliseconds

    # -- measurement -------------------------------------------------------------------------------------------
    @action(
        cap="cap.measure.spectrum.v1",
        description="Acquire one absorbance spectrum after a blank and return the wavelengths and absorbance inside "
        "the requested range",
        input={
            "wavelength_min": Field(
                "number",
                unit="nm",
                description="Lower bound of the returned wavelength range",
                limit=WAVELENGTH_MIN_LIMIT,
            ),
            "wavelength_max": Field(
                "number",
                unit="nm",
                description="Upper bound of the returned wavelength range",
                limit=WAVELENGTH_MAX_LIMIT,
            ),
            "integration_ms": Field(
                "number",
                unit="ms",
                description="Optional exposure time; the clone defaults to 20 ms when it is omitted",
                limit=INTEGRATION_LIMIT,
            ),
        },
    )
    def measure_spectrum(self, wavelength_min, wavelength_max, integration_ms=None):
        if float(wavelength_min) > float(wavelength_max):
            raise DriverFailed(
                "MHS.CAPABILITY.INPUT_INVALID",
                f"wavelength_min {wavelength_min!r} is greater than wavelength_max {wavelength_max!r}",
            )
        self.check_cancelled()
        try:
            if integration_ms is None:
                wavelengths, absorbance = self.native.measure_absorbance()
            else:
                wavelengths, absorbance = self.native.measure_absorbance(_whole_milliseconds(integration_ms))
        except ValueError as exc:
            raise DriverFailed(
                "MHS.DEVICE.PRECONDITION_UNMET",
                "the instrument has no dark and blank baseline: run x-cap.jordvl.take_blank.v1 first",
            ) from exc
        self.check_cancelled()
        if len(wavelengths) != len(absorbance):
            raise DriverFailed(
                "MHS.DEVICE.FAULTED",
                f"the native spectrum has {len(wavelengths)} wavelengths but {len(absorbance)} absorbance values",
            )
        low, high = float(wavelength_min), float(wavelength_max)
        pairs = [
            (float(wavelength), float(value))
            for wavelength, value in zip(wavelengths, absorbance)
            if low <= float(wavelength) <= high
        ]
        return {
            "wavelengths": [item[0] for item in pairs],
            "intensities": [item[1] for item in pairs],
        }

    @action(
        name="x-cap.jordvl.take_blank.v1",
        description="Acquire the dark and blank baselines the absorbance measurement needs",
        input={
            "integration_ms": Field(
                "number",
                unit="ms",
                description="Optional exposure time for both baseline frames; the clone defaults to 20 ms",
                limit=INTEGRATION_LIMIT,
            ),
        },
        output={
            "blanked": Field(
                "boolean",
                description="True once the dark and blank spectra were captured",
            ),
        },
    )
    def take_blank(self, integration_ms=None):
        self.check_cancelled()
        if integration_ms is None:
            self.native.take_blank()
        else:
            self.native.take_blank(_whole_milliseconds(integration_ms))
        self.check_cancelled()
        return {"blanked": True}

    @action(
        name="x-cap.jordvl.raw_spectrum.v1",
        verb="read",
        description="Acquire one raw 2048-pixel detector frame in the current lamp state",
        output={
            "intensities": Field(
                "array",
                items=Field("number", unit="1", description="Raw 16-bit detector count"),
                length=2048,
                description="Raw detector counts in the clone's pixel order",
            ),
        },
    )
    def raw_spectrum(self):
        self.check_cancelled()
        values = [float(item) for item in self.native.get_raw_spectrum()]
        if len(values) != 2048:
            raise DriverFailed(
                "MHS.DEVICE.FAULTED",
                f"get_raw_spectrum returned {len(values)} pixels, not the 2048 of the clone",
            )
        return {"intensities": values}

    # -- safety ------------------------------------------------------------------------------------------------
    @estop(native="set_lamp")
    def stop(self):
        """Turn the lamp and the magnet off; both commands are attempted even when one fails."""
        errors = []
        try:
            self.native.set_lamp(False)
        except Exception as exc:  # noqa: BLE001 - try the second safe-state command, then report
            errors.append(exc)
        try:
            self.native.set_magnet(False)
        except Exception as exc:  # noqa: BLE001 - report after both commands
            errors.append(exc)
        if errors:
            raise DriverFailed(
                "MHS.DEVICE.FAULTED",
                f"the native stop did not complete: {errors[0]!r}",
            ) from errors[0]

    def teardown(self):
        self.native.close()
