"""OpenMHS driver for gh.labjack/labjackpython: a LabJack U3 USB DAQ.

A direct Driver (decorated methods) over the upstream device class u3:U3 (src/u3.py:63).  The clone is the
LabJackPython package: a U3 object sends the U3 command set over USB or an LJSocket and exposes the convenience
methods used here -- ``getAIN`` (one calibrated analog input voltage, src/u3.py:588), ``getTemperature`` (the
internal sensor in Kelvin, src/u3.py:570), ``configIO`` (the FIO/EIO analog masks, src/u3.py:312), ``setDOState`` /
``getDIOState`` (one digital line, src/u3.py:513 and src/u3.py:551) and ``reset`` (src/u3.py:954).

* reads: analog input AIN0, the internal temperature, the FIOAnalog and EIOAnalog masks, and the states of the 20
  digital I/O lines;
* writes: the FIOAnalog and EIOAnalog masks (0-255, 8 bits, one bit per line).  The mask is read back after the
  write, so the applied value is observable in the state;
* capabilities: ``cap.measure.voltage.v1`` (one DC voltage sample on AIN0), an extension action that drives one
  digital line, and an extension reset that is also the safe-state action.  The catalogue class
  ``cap.actuation.gpio.v1`` binds only ``io.gpio`` / ``io.digital`` and cannot be declared together with the
  ``instrument.dmm`` kind that ``cap.measure.voltage.v1`` needs, so the digital output uses an extension id;
* the native stop is ``U3.reset``: the runtime latches first, then the soft reset returns the device to its
  power-up state, so the digital lines stop driving.

The card's ``hints`` come from a name scan and mix methods of several device classes (UE9, U12 and U3).  The U12
streaming and pulse methods (``U12.aiStreamStart``, ``U12.pulseOutStart``) do not exist on U3; the register,
default-block and name methods the card names through UE9 do exist on U3 (inherited from ``Device`` or defined on
U3) but are not the convenience subset this package exposes.  Every Fact cites a line of the clone at the pinned
commit (a2f13eb548cca6416b1d44b08b63f7c5fd7f943b).  This package is model-authored and unreviewed: it is checked on
the fake backend only, and the hardware backend was never opened.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

#: The upstream file of the native class, relative to the clone root.
MODULE = "src/u3.py"


class LabjackU3(Driver):
    device_id = "labjack-u3"
    device_kind = "instrument.dmm"
    mode = "hardware"
    risk = "R1"
    native = "u3:U3"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeU3"}
    vendor, model = "LabJack", "U3"
    display_name = "LabJack U3 USB DAQ (LabJackPython U3)"
    tags = ["daq", "labjack", "u3", "analog input", "digital io", "usb"]
    facts = [
        Fact("U3 is the LabJack U3 class of the LabJackPython package", source="upstream_code",
             ref=f"{MODULE}:63-65"),
        Fact("The U3 names 20 digital I/O lines FIO0-FIO7, EIO0-EIO7 and CIO0-CIO3 (0-19)",
             source="upstream_code", ref=f"{MODULE}:43-45"),
        Fact("getAIN is a convenience method that reads one analog input and returns its calibrated voltage",
             source="upstream_code", ref=f"{MODULE}:588-631"),
        Fact("getTemperature reads the U3 internal temperature sensor and returns the temperature in Kelvin",
             source="upstream_code", ref=f"{MODULE}:570-586"),
        Fact("configIO sends the configIO command and returns the FIOAnalog and EIOAnalog masks; with no argument "
             "it reads the current configuration", source="upstream_code", ref=f"{MODULE}:312-421"),
        Fact("The analog and digital configuration parameters are binary-encoded 8-bit values, one bit per line; "
             "the configU3 example uses FIOAnalog = 255 and EIOAnalog = 255", source="upstream_code",
             ref=f"{MODULE}:160-186"),
        Fact("setDOState writes the state of one digital I/O line (0-19) and also sets its direction to output; "
             "state 1 is high and 0 is low", source="upstream_code", ref=f"{MODULE}:513-530"),
        Fact("getDIOState reads the state of one digital I/O line (0-19) without changing its direction",
             source="upstream_code", ref=f"{MODULE}:551-568"),
        Fact("U3.reset causes a soft or hard reset; a soft reset re-initializes most variables without "
             "re-enumeration", source="upstream_code", ref=f"{MODULE}:954-977"),
        Fact("Device.close closes the device handle", source="upstream_code",
             ref="src/LabJackPython.py:655-681"),
    ]
    safe_state = "device soft-reset to its power-up state by U3.reset; the digital lines stop driving"

    # -- reads --------------------------------------------------------------------------------------------------
    @read("analog_input_0", unit="V",
          description="Voltage measured on analog input AIN0 (single-ended, negative channel 31)")
    def analog_input_0(self):
        return float(self.native.getAIN(0))

    @read("internal_temperature", unit="K",
          description="Temperature of the U3 internal temperature sensor, in Kelvin")
    def internal_temperature(self):
        return float(self.native.getTemperature())

    @read("fio_analog", type="integer", unit="1",
          description="FIOAnalog mask: bit n makes FIO line n analog (1) or digital (0)")
    def fio_analog(self):
        return int(self.native.configIO()["FIOAnalog"])

    @read("eio_analog", type="integer", unit="1",
          description="EIOAnalog mask: bit n makes EIO line n analog (1) or digital (0)")
    def eio_analog(self):
        return int(self.native.configIO()["EIOAnalog"])

    @read("dio_states", type="array", items="integer", length=20, unit="1",
          description="States of the 20 digital I/O lines, indexed by line number 0-19 "
                      "(FIO0-FIO7, EIO0-EIO7, CIO0-CIO3); 1 is high and 0 is low")
    def dio_states(self):
        return [int(self.native.getDIOState(number)) for number in range(20)]

    # -- writes ---------------------------------------------------------------------------------------------------
    @write("fio_analog", type="integer", unit="1",
           description="FIOAnalog mask: bit n makes FIO line n analog (1) or digital (0); read back after the write",
           limit=Limit(min=0, max=255, source="upstream_code", ref=f"{MODULE}:160-186"))
    def set_fio_analog(self, value):
        return int(self.native.configIO(FIOAnalog=int(value))["FIOAnalog"])

    @write("eio_analog", type="integer", unit="1",
           description="EIOAnalog mask: bit n makes EIO line n analog (1) or digital (0); read back after the write",
           limit=Limit(min=0, max=255, source="upstream_code", ref=f"{MODULE}:160-186"))
    def set_eio_analog(self, value):
        return int(self.native.configIO(EIOAnalog=int(value))["EIOAnalog"])

    # -- measurement capability -----------------------------------------------------------------------------------
    @action(cap="cap.measure.voltage.v1",
            description="Read one DC voltage sample from analog input AIN0",
            input={"dc": Field("boolean",
                               description="True to read the instantaneous (DC) voltage; the U3 getAIN sample is "
                                           "not an RMS measurement")})
    def measure_voltage(self, dc: bool = True):
        if not dc:
            raise DriverFailed(
                "MHS.DEVICE.PRECONDITION_UNMET",
                "the U3 getAIN sample is an instantaneous (DC) voltage, not an RMS measurement")
        return {"voltage": float(self.native.getAIN(0))}

    # -- digital output capability --------------------------------------------------------------------------------
    @action(name="x-cap.labjack.set_digital_output.v1",
            description="Drive one U3 digital I/O line high or low; the line is also set to output",
            input={
                "pin": Field("integer", unit="1",
                             description="Digital I/O line number 0-19 (FIO0-FIO7, EIO0-EIO7, CIO0-CIO3)",
                             limit=Limit(min=0, max=19, source="upstream_code", ref=f"{MODULE}:519-521")),
                "value": Field("number", unit="1", description="Output state: 1 is high and 0 is low",
                               limit=Limit(min=0, max=1, allowed=[0, 1], source="upstream_code",
                                           ref=f"{MODULE}:520")),
            },
            output={
                "applied": Field("boolean", description="True once the line state was written"),
                "pin": Field("integer", unit="1", description="Line number that was written"),
                "value": Field("number", unit="1", description="State written to the line"),
            })
    def set_digital_output(self, pin, value):
        state = int(value)
        self.native.setDOState(int(pin), state)
        return {"applied": True, "pin": int(pin), "value": state}

    # -- reset and safety -----------------------------------------------------------------------------------------
    @action(name="x-cap.labjack.reset.v1", safe_state=True,
            description="Soft-reset the U3 to its power-up state (the native reset); it takes no input",
            output={
                "fio_analog": Field("integer", unit="1", description="FIOAnalog mask after the reset"),
                "eio_analog": Field("integer", unit="1", description="EIOAnalog mask after the reset"),
            })
    def reset_device(self):
        self.native.reset()
        configuration = self.native.configIO()
        return {"fio_analog": int(configuration["FIOAnalog"]),
                "eio_analog": int(configuration["EIOAnalog"])}

    @estop(native="reset")
    def stop(self):
        """The native stop: the runtime latches first, then U3.reset() returns the device to its power-up state."""
        self.native.reset()

    def teardown(self):
        self.native.close()
