"""OpenMHS driver for gh.drmcnelson/linear-ccd-with-ltspice-kicad-firmware-and-python-library.

A direct Driver over the upstream serial controller
``TCD1304Rev2_Python.TCD1304Rev2Controller:LCCDCONTROLLER`` (line 494).  The upstream class is a command-line
controller for a Toshiba TCD1304 linear CCD: it sends ASCII commands to a serial port, reads text responses up to
``DONE`` and lets a background reader queue completed frames (``read_to_done_``, ``read_nowait`` and the
``dataqueue`` attribute).  The card names the serial family; a command table cannot express the frame read, whose
reply is an array queued by the reader rather than a parsed line, so this package uses a direct Driver over the
upstream class (DEVIATION FROM THE CARD: family-config SerialDriver -> direct Driver; see RESULT.json notes).

* reads: the identifier, the configuration line, the pixel count, the dark-pixel count and the sensor name the
  controller parses from that line;
* ``cap.measure.intensity.v1``: one clocked frame.  The action sends ``clock 1 <shutter>`` (the shutter in whole
  microseconds), takes the next completed frame from the reader's ``dataqueue``, converts the scaled samples back to
  ADC counts with the device's ``vperbit`` and returns either the brightest pixel or the pixel whose calibrated
  coordinate is nearest a declared wavelength.  The full wavelength/intensity array is NOT COVERED;
* the e-stop sends the firmware ``stop`` command (help.txt:6-7).

Every Fact and Limit cites a line of the clone at the pinned commit
fcda5364d1ec63bc1b0e17efc40508b7fdef76b3.  This package is model-authored and unreviewed; only the fake backend was
exercised and no hardware run was made.  The upstream controller imports pyserial, numpy, scipy and matplotlib and
starts a reader process, so the hardware backend is untested here.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read

#: Upstream controller module, relative to the clone root.
CONTROLLER = "TCD1304Rev2_Python/TCD1304Rev2Controller.py"
#: Firmware command help, relative to the clone root.
HELP = "TCD1304Rev2_Python/help.txt"

#: How long the action waits for the reader to queue one completed frame.  This is a driver wait bound, not a device
#: timing fact: the clone states the readout itself (README.md:186) but no host wait.
READ_TIMEOUT_S = 10.0

INTEGRATION_REASON = (
    "the clone states that the clock command takes its shutter time in microseconds (help.txt:49-52) and that one "
    "record takes about 7.4 ms to read at a 2 MHz master clock (README.md:186), but states no minimum or maximum "
    "integration time; the site supplies the range of its detector")
WAVELENGTH_REASON = (
    "the clone maps pixel numbers to a calibrated coordinate only through coefficients supplied by the device at "
    "runtime (TCD1304Rev2Controller.py:602-620, 669-684); it states no wavelength range, so the site supplies the "
    "calibrated range of its spectrometer")
HOLDOFF_REASON = (
    "the clone states that the firmware holdoff command takes microseconds (help.txt:82) but states no minimum or "
    "maximum; the site supplies the holdoff range of its timing setup")


class LinearCcd(Driver):
    device_id = "tcd1304-linear-ccd"
    device_kind = "instrument.spectrometer"
    mode = "hardware"
    risk = "R0"
    native = "TCD1304Rev2_Python.TCD1304Rev2Controller:LCCDCONTROLLER"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeLCCDController"}
    vendor, model = "Mitchell C. Nelson", "TCD1304 linear CCD controller"
    display_name = "TCD1304 linear CCD (TCD1304Rev2Controller)"
    tags = ["linear ccd", "tcd1304", "spectrometer", "spectroscopy", "serial"]
    facts = [
        Fact("The design is based on the Toshiba TCD1304 (3648/3694 pixels)", source="vendor_doc",
             ref="README.md:12"),
        Fact("The device appears as a serial port with commands and responses in ASCII and frames returned as "
             "binary or formatted", source="vendor_doc", ref="README.md:18"),
        Fact("The controller writes each command followed by a newline and reads lines until a line starts with "
             "DONE", source="upstream_code", ref=f"{CONTROLLER}:690-703"),
        Fact("On connect the controller sends stop, reads the identifier and reads the configuration line",
             source="upstream_code", ref=f"{CONTROLLER}:561-583"),
        Fact("The configuration line carries PIXELS, DARK, INVERT and SENSOR, and optionally VPERBIT, BITS and VFS",
             source="upstream_code", ref=f"{CONTROLLER}:579-593"),
        Fact("The reader scales each ADC sample by vperbit and subtracts the mean of the first darklength samples "
             "when baseline subtraction is on", source="upstream_code", ref=f"{CONTROLLER}:1024-1028"),
        Fact("A completed frame is queued as [[data], shutter, interval, clock, counter, outercounter, frames, sets, "
             "every, mode, elapsed, 0, timestamp]", source="upstream_code", ref=f"{CONTROLLER}:891-898"),
        Fact("The clock command takes the shutter time in microseconds: 'clock <n> <shutter>' reads n frames",
             source="vendor_doc", ref=f"{HELP}:49-52"),
        Fact("The stop command stops clocks, triggers and gate", source="vendor_doc", ref=f"{HELP}:6-7"),
        Fact("The send command sends the contents of the current buffer", source="vendor_doc", ref=f"{HELP}:28-30"),
        Fact("The holdoff time is set with 'set holdoff usecs'", source="vendor_doc", ref=f"{HELP}:82"),
        Fact("The full detector record has 12 dummy outputs, 13 light-shielded elements, 3 shadowed elements, 3648 "
             "effective elements and 14 dummy elements", source="vendor_doc", ref="README.md:223"),
        Fact("The master clock is 800 kHz to 4 MHz and the data readout rate is one quarter of it, 200 kS/s to "
             "1 MS/s (500 kS/s below 4 V)", source="vendor_doc", ref="README.md:69"),
        Fact("At a 2 MHz master clock one record takes about 7.4 ms to read; transfer to the host adds 5 ms on a "
             "Teensy 3.x and about 120 us on a Teensy 4.x", source="vendor_doc", ref="README.md:186"),
    ]
    safe_state = "readout and clocking stopped by the firmware 'stop' command"

    # -- state -------------------------------------------------------------------------------------------------
    @read("identifier", type="string", description="Identifier string reported by the firmware")
    def identifier(self):
        line = self.native.rawcommand("identifier", "Identifier")
        if not line:
            raise DriverFailed("MHS.DEVICE.FAULTED", "the controller did not report an Identifier line")
        parts = str(line).split(maxsplit=1)
        return parts[1] if len(parts) > 1 else ""

    @read("configuration", type="string",
          description="Configuration line the controller parses: PIXELS, DARK, INVERT, SENSOR and optional "
                      "VPERBIT, BITS and VFS")
    def configuration(self):
        line = self.native.rawcommand("configuration", "PIXELS")
        if not line:
            raise DriverFailed("MHS.DEVICE.FAULTED", "the controller did not report a PIXELS configuration line")
        return str(line)

    @read("pixel_count", type="integer", unit="1",
          description="Number of pixels in the frame, from the PIXELS field of the configuration line")
    def pixel_count(self):
        value = self.native.datalength
        if value is None:
            raise DriverFailed("MHS.DEVICE.FAULTED", "the controller has no PIXELS value")
        return int(value)

    @read("dark_pixel_count", type="integer", unit="1",
          description="Number of leading dark pixels used by the controller's baseline subtraction, from the DARK "
                      "field of the configuration line")
    def dark_pixel_count(self):
        value = self.native.darklength
        if value is None:
            raise DriverFailed("MHS.DEVICE.FAULTED", "the controller has no DARK value")
        return int(value)

    @read("sensor", type="string",
          description="Sensor name reported by the firmware's SENSOR configuration field")
    def sensor(self):
        value = self.native.sensor
        return "" if value is None else str(value)

    # -- measurement -------------------------------------------------------------------------------------------
    @action(cap="cap.measure.intensity.v1",
            description="Read the intensity of one frame, in ADC counts after the controller's vperbit scaling is "
                        "undone: the brightest pixel, or the pixel whose calibrated wavelength is nearest to "
                        "wavelength_nm.  With integration_ms the driver clocks a new frame; without it the firmware "
                        "sends the current buffer.  The full frame array is not returned",
            input={
                "integration_ms": Field(
                    "number", unit="ms",
                    description="Shutter/integration time of a new frame in milliseconds; converted to the whole "
                                "microseconds the firmware's clock command takes.  Leave it out to read the current "
                                "buffer",
                    limit=Limit.operator_required(INTEGRATION_REASON)),
                "wavelength_nm": Field(
                    "number", unit="nm",
                    description="Wavelength in nanometres; the driver reads the pixel whose calibrated coordinate "
                                "nearest matches it.  Leave it out to read the brightest pixel",
                    limit=Limit.operator_required(WAVELENGTH_REASON)),
            })
    def measure_intensity(self, integration_ms=None, wavelength_nm=None):
        applied_ms = None
        self.native.clear()
        if integration_ms is None:
            self.native.write("send\n")
        else:
            shutter_us = int(round(float(integration_ms) * 1000.0))
            if shutter_us <= 0:
                raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                                   "integration_ms must be at least one microsecond")
            self.native.write("clock 1 %d\n" % shutter_us)
            applied_ms = shutter_us / 1000.0
        try:
            record = self.native.dataqueue.get(timeout=READ_TIMEOUT_S)
        except Exception as exc:  # the queue's Empty is a different class in queue and multiprocessing
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               "no completed frame was queued within %g s: %s" % (READ_TIMEOUT_S, exc)) from exc
        samples = [float(value) for value in record[0][0]]
        vperbit = float(self.native.vperbit)
        if not vperbit:
            raise DriverFailed("MHS.DEVICE.FAULTED", "the controller reported a zero vperbit")
        counts = [value / vperbit for value in samples]
        if wavelength_nm is None:
            intensity = max(counts)
        else:
            coefficients = list(self.native.coefficients or [])
            if not coefficients:
                raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                                   "the controller has no wavelength calibration coefficients")
            index = self._nearest_pixel(coefficients, len(counts), float(wavelength_nm))
            intensity = counts[index]
        bits = int(self.native.bits)
        saturated = intensity >= (2 ** bits) - 1
        output = {"intensity": intensity, "saturated": saturated}
        if applied_ms is not None:
            output["integration_ms"] = applied_ms
        return output

    @action(name="x-cap.drmcnelson.set_holdoff.v1",
            description="Set the firmware sync holdoff time, the delay the firmware's 'set holdoff usecs' command "
                        "configures (help.txt:82)",
            input={"holdoff_us": Field(
                "integer", unit="us", description="Holdoff time in microseconds",
                limit=Limit.operator_required(HOLDOFF_REASON))},
            output={"holdoff_us": Field("integer", unit="us",
                                        description="Holdoff time written to the firmware, in microseconds")})
    def set_holdoff(self, holdoff_us):
        applied = int(holdoff_us)
        self.native.write("set holdoff %d\n" % applied)
        return {"holdoff_us": applied}

    @staticmethod
    def _nearest_pixel(coefficients, count, target):
        """The pixel whose upstream ``generate_x_vector`` coordinate is nearest to target.

        The controller evaluates the coefficients on ``np.linspace(0, datalength, datalength)``
        (TCD1304Rev2Controller.py:104-112, 604), so pixel i sits at i * count / (count - 1) before the polynomial.
        """
        if count <= 1:
            return 0
        step = count / (count - 1)
        best_index = 0
        best_distance = None
        for index in range(count):
            x = index * step
            wavelength = 0.0
            for power, coefficient in enumerate(coefficients):
                wavelength += float(coefficient) * (x ** power)
            distance = abs(wavelength - target)
            if best_distance is None or distance < best_distance:
                best_index, best_distance = index, distance
        return best_index

    # -- safety -------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The firmware stop: the runtime latches first, then this writes 'stop' without waiting for DONE."""
        self.native.write("stop\n")

    def teardown(self):
        self.native.close()
