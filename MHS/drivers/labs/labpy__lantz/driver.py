"""OpenMHS driver for gh.labpy/lantz: a LabJack U12 USB DAQ through the Lantz wrapper.

A direct Driver (decorated methods) over the upstream class lantz.drivers.labjack._internal.u12:U12
(lantz/drivers/labjack/_internal/u12.py:395).  That class is the Lantz wrapper around the LabJack U12 command
library; its high-level methods are ``eAnalogIn`` (one analog input), ``eCount`` (the counter), ``aiBurst`` (a
block of analog input scans), ``eAnalogOut`` (both analog outputs), ``pulseOutStart`` (a pulse train on D0-D7),
``localID``/``rawReadLocalId`` (the local ID), the version queries and ``reset``.

* reads: the driver and firmware versions, analog input channel 0, the counter, the local ID and the streaming
  flag;
* one write: the local ID.  No text file of the clone states the local ID range, so the limit is
  ``Limit.operator_required``: every write is refused ``MHS.SAFETY.LIMITS_UNSET`` until the site supplies the range
  (``site-limits.example.json`` shows the overlay);
* capabilities: ``cap.measure.voltage.v1`` (one DC voltage sample on analog input channel 0), an extension action
  that acquires a block with ``aiBurst`` (its scan count and scan rate are bounded by the aiBurst docstring), an
  extension action that sets both analog outputs, an extension action that starts a pulse train, and an extension
  reset that is also the safe-state action;
* the native reset is the e-stop: the runtime latches first, then ``U12.reset`` returns the device to its power-up
  state.

Every Fact cites a line of the clone at the pinned commit (3e878e3f765a4295b0089d04e241d4beb7b8a65b).  This package
is model-authored and unreviewed: it is checked on the fake backend only, and the hardware backend was never opened.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

#: The upstream file of the native class, relative to the clone root.
MODULE = "lantz/drivers/labjack/_internal/u12.py"


class LabjackU12(Driver):
    device_id = "labjack-u12"
    device_kind = "instrument.dmm"
    mode = "hardware"
    risk = "R1"
    native = "lantz.drivers.labjack._internal.u12:U12"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeU12"}
    vendor, model = "LabJack", "U12"
    display_name = "LabJack U12 USB DAQ (Lantz U12)"
    tags = ["daq", "labjack", "u12", "analog input", "analog output", "pulse", "counter"]
    facts = [
        Fact("U12 is the LabJack U12 command class of the Lantz labjack driver", source="upstream_code",
             ref=f"{MODULE}:395-401"),
        Fact("eAnalogIn reads the voltage from one analog input", source="upstream_code",
             ref=f"{MODULE}:1908-1916"),
        Fact("eCount reads the counter (CNT); resetCounter selects whether it is reset after reading",
             source="upstream_code", ref=f"{MODULE}:1977-1983"),
        Fact("aiBurst reads a specified number of scans (up to 4096) at a scan rate up to 8192 Hz from 1, 2 or 4 "
             "analog inputs", source="upstream_code", ref=f"{MODULE}:2155-2159"),
        Fact("eAnalogOut sets the voltage of both analog outputs", source="upstream_code",
             ref=f"{MODULE}:1942-1947"),
        Fact("pulseOut creates pulses on any/all of D0-D7", source="upstream_code", ref=f"{MODULE}:2624-2628"),
        Fact("pulseOutStart takes a bit selection, a pulse count and four cycle-time values as an alternative to "
             "pulseOut", source="upstream_code", ref=f"{MODULE}:2645-2652"),
        Fact("reset causes the LabJack to reset after about 2 seconds", source="upstream_code",
             ref=f"{MODULE}:2729-2733"),
        Fact("localID changes the local ID of a specified LabJack", source="upstream_code",
             ref=f"{MODULE}:2584-2588"),
        Fact("rawReadLocalId reads the Local ID from internal memory and returns it as an integer",
             source="upstream_code", ref=f"{MODULE}:568-576"),
        Fact("getDriverVersion returns the version number of ljackuw.dll without hardware communication",
             source="upstream_code", ref=f"{MODULE}:2497-2501"),
        Fact("getFirmwareVersion retrieves the firmware version from the LabJack's processor",
             source="upstream_code", ref=f"{MODULE}:2510-2514"),
        Fact("For analog input channels below 8, bitsToVolts maps a 12-bit sample (0-4095) to "
             "(bits*20/4096)-10 volts", source="upstream_code", ref=f"{MODULE}:2388-2403"),
    ]
    safe_state = "device reset to its power-up state by U12.reset"

    # -- reads --------------------------------------------------------------------------------------------------
    @read("driver_version", type="number", unit="1",
          description="Version number of the LabJack driver library")
    def driver_version(self):
        return float(self.native.getDriverVersion())

    @read("firmware_version", type="number", unit="1",
          description="Firmware version reported by the LabJack processor")
    def firmware_version(self):
        return float(self.native.getFirmwareVersion()["firmware"])

    @read("analog_input_0", unit="V", description="Voltage on analog input channel 0 (AIN0)")
    def analog_input_0(self):
        return float(self.native.eAnalogIn(0)["voltage"])

    @read("counter", type="integer", unit="1", description="Counter value (CNT) reported by the U12")
    def counter(self):
        return int(self.native.eCount()["count"])

    @read("local_id", type="integer", unit="1", description="Local ID stored in the U12")
    def local_id(self):
        return int(self.native.rawReadLocalId())

    @read("streaming", type="boolean",
          description="True while the U12 reports a hardware-timed stream in progress")
    def streaming(self):
        return bool(self.native.streaming)

    # -- the one write ------------------------------------------------------------------------------------------
    @write("local_id", type="integer", unit="1",
           description="Local ID stored in the U12; it is read back after the write",
           limit=Limit.operator_required(
               "no text file of the clone states the local ID range of the U12 (the User's Guide is not in the "
               "clone); the site sets the range of its device"))
    def set_local_id(self, value):
        self.native.localID(int(value))
        return int(self.native.rawReadLocalId())

    # -- measurement capability ---------------------------------------------------------------------------------
    @action(cap="cap.measure.voltage.v1",
            description="Read one DC voltage sample from analog input channel 0",
            input={"dc": Field("boolean", description="True to read the DC (instantaneous) voltage; the U12 "
                                                      "eAnalogIn sample is not an RMS measurement")})
    def measure_voltage(self, dc=True):
        if not dc:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "the U12 eAnalogIn sample is an instantaneous (DC) voltage, not an RMS measurement")
        return {"voltage": float(self.native.eAnalogIn(0)["voltage"])}

    @action(name="x-cap.labpy.sample_voltages.v1",
            description="Acquire a block of analog input scans from channel 0 with aiBurst",
            input={
                "count": Field("integer", unit="1", description="Number of scans to acquire (aiBurst numScans)",
                               limit=Limit(max=4096, source="upstream_code",
                                           ref=f"{MODULE}:2159")),
                "scan_rate": Field("number", unit="Hz", description="Scan rate in hertz (aiBurst scanRate)",
                                   limit=Limit(max=8192, source="upstream_code",
                                               ref=f"{MODULE}:2159")),
            },
            output={
                "voltages": Field("array", items="number", unit="V",
                                  description="The acquired voltages in volts, in acquisition order"),
                "count": Field("integer", unit="1", description="Number of samples returned"),
            })
    def sample_voltages(self, count, scan_rate):
        if count < 1:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET", "count must be at least one scan")
        if scan_rate <= 0:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET", "scan_rate must be positive")
        result = self.native.aiBurst(1, [0], float(scan_rate), int(count))
        values = [float(item) for item in result["voltages"][0][:int(count)]]
        return {"voltages": values, "count": len(values)}

    # -- analog output capability -------------------------------------------------------------------------------
    @action(name="x-cap.labpy.set_analog_outputs.v1",
            description="Set both analog output voltages (U12.eAnalogOut)",
            input={
                "analog_output_0": Field("number", unit="V", description="Voltage to set AO0 to",
                                         limit=Limit.operator_required(
                                             "no text file of the clone states the analog output voltage range of "
                                             "the U12; the site sets the range of its unit")),
                "analog_output_1": Field("number", unit="V", description="Voltage to set AO1 to",
                                         limit=Limit.operator_required(
                                             "no text file of the clone states the analog output voltage range of "
                                             "the U12; the site sets the range of its unit")),
            },
            output={
                "analog_output_0": Field("number", unit="V", description="Applied AO0 voltage"),
                "analog_output_1": Field("number", unit="V", description="Applied AO1 voltage"),
            })
    def set_analog_outputs(self, analog_output_0, analog_output_1):
        self.native.eAnalogOut(float(analog_output_0), float(analog_output_1))
        return {"analog_output_0": float(analog_output_0), "analog_output_1": float(analog_output_1)}

    # -- pulse output capability --------------------------------------------------------------------------------
    @action(name="x-cap.labpy.pulse_out.v1",
            description="Start a pulse train on the selected D0-D7 bits (U12.pulseOutStart)",
            input={
                "bit_select": Field("integer", unit="1", description="Bit selection mask (D0-D7)",
                                    limit=Limit.operator_required(
                                        "no text file of the clone states the bit-selection range; the site sets "
                                        "the bits its wiring uses")),
                "num_pulses": Field("integer", unit="1", description="Number of pulses to generate",
                                    limit=Limit.operator_required(
                                        "no text file of the clone states the pulse-count range; the site sets the "
                                        "count its load tolerates")),
                "time_b1": Field("integer", unit="1", description="First cycle time B value",
                                 limit=Limit.operator_required(
                                     "no text file of the clone states the cycle-time range; the site sets the "
                                     "timing of its signal")),
                "time_c1": Field("integer", unit="1", description="First cycle time C value",
                                 limit=Limit.operator_required(
                                     "no text file of the clone states the cycle-time range; the site sets the "
                                     "timing of its signal")),
                "time_b2": Field("integer", unit="1", description="Second cycle time B value",
                                 limit=Limit.operator_required(
                                     "no text file of the clone states the cycle-time range; the site sets the "
                                     "timing of its signal")),
                "time_c2": Field("integer", unit="1", description="Second cycle time C value",
                                 limit=Limit.operator_required(
                                     "no text file of the clone states the cycle-time range; the site sets the "
                                     "timing of its signal")),
            },
            output={
                "bit_select": Field("integer", unit="1", description="Applied bit-selection mask"),
                "num_pulses": Field("integer", unit="1", description="Number of pulses requested"),
            })
    def pulse_out(self, bit_select, num_pulses, time_b1, time_c1, time_b2, time_c2):
        self.native.pulseOutStart(int(bit_select), int(num_pulses), int(time_b1), int(time_c1), int(time_b2),
                                  int(time_c2))
        return {"bit_select": int(bit_select), "num_pulses": int(num_pulses)}

    # -- reset and safety ---------------------------------------------------------------------------------------
    @action(name="x-cap.labpy.reset_device.v1", safe_state=True,
            description="Reset the U12 (U12.reset), the safe state; it takes no input",
            output={"reset": Field("boolean", description="True once the reset command was issued")})
    def reset_device(self):
        self.native.reset()
        return {"reset": True}

    @estop(native="reset")
    def emergency_stop(self):
        """The native reset: the runtime latches first, then U12.reset() returns the device to its power-up state."""
        self.native.reset()

    def teardown(self):
        self.native.close()
