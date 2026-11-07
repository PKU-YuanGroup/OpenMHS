"""OpenMHS driver for gh.natlabrockies/multi-tube-od-reader: a 16-port optical density reader.

A direct Driver over the upstream device class ``my_app.classes.device:Device`` (my_app/classes/device.py:34).
The clone is an application, not a vendor SDK: ``Device`` discovers, opens, renames and blinks one LabJack U3
and holds 16 ``Port`` objects (device.py:57-58); the actual hardware measurement is the module function
``timecourse.measure_voltage`` (timecourse.py:59-92), which opens the U3 through the same serial number and reads
the calibrated analog inputs.  This driver therefore uses the upstream ``Device.connect()`` (device.py:112-120),
which returns the LabJack U3 handle, and reads an analog input through that handle.  The per-read DAC power
sequence of timecourse.py:70-83 lives in ``native.py`` on the hardware path; the upstream n_reps average is not
reproduced (one calibrated sample per call).  The fake backend is an in-memory stand-in.

* reads: the device name and serial number from the LabJack firmware/identity, the 16 physical port positions and
  their usage flags;
* one write: the firmware device name (``Device.rename``, device.py:122-132), bound to
  ``cap.device.configure.v1``;
* one catalogue measurement: ``cap.measure.voltage.v1`` on a port 1..16, mapped to AIN0..AIN15 as the upstream
  measurement maps it (timecourse.py:65-68);
* one extension action: ``x-cap.natlabrockies.blink.v1``, the native indicator blink (device.py:134-148);
* the native stop opens and closes the U3 handle; no text of the clone documents an independent hardware e-stop,
  so ``estop_physical_ref`` is not set.  The card's floor is R1, not R2/R3.

Every Fact cites a line of the clone at the pinned commit (e3948da8586d40093ffb7cc64706f4c6defa6326).  This
package is model-authored and unreviewed: it is checked on the fake backend only, no hardware was attached, and
the hardware backend was never imported or run.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, action, estop, read, write

#: The clone creates one Port for each physical position 1 through 16 (my_app/classes/device.py:57-58).
PORT_COUNT = 16
PORT_CHANNELS = [str(position) for position in range(1, PORT_COUNT + 1)]


class MultiTubeOdReader(Driver):
    device_id = "multi-tube-od-reader"
    device_kind = "sensor"
    mode = "hardware"
    risk = "R1"
    native = "my_app.classes.device:Device"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeMultiTubeOdReader"}
    vendor, model = "NREL", "Multi-Tube-OD-Reader"
    display_name = "Multi-Tube-OD-Reader (my_app.classes.device.Device)"
    tags = ["optical density", "growth monitoring", "labjack u3", "analog input", "16-port"]
    facts = [
        Fact("Device is the Python object representing one Multi-Tube-OD-Reader instrument", source="upstream_code",
             ref="my_app/classes/device.py:34-43"),
        Fact("The Device constructor keeps a list of Port objects for physical positions 1 through 16",
             source="upstream_code", ref="my_app/classes/device.py:57-58"),
        Fact("Device.discovery enumerates connected U3 devices with u3.openAllU3() and creates one Device per "
             "serial number", source="upstream_code", ref="my_app/classes/device.py:89-108"),
        Fact("Device.connect opens u3.U3 by serial number and returns the LabJack U3 interface",
             source="upstream_code", ref="my_app/classes/device.py:112-120"),
        Fact("Device.rename writes the new name with U3.setName and updates the Device name",
             source="upstream_code", ref="my_app/classes/device.py:122-132"),
        Fact("Device.blink toggles the built-in LED and DAC0 in 25 passes with 0.15 s between passes",
             source="upstream_code", ref="my_app/classes/device.py:134-148"),
        Fact("The clone opens and closes the LabJack connection at each timepoint so parallel experiments can "
             "share the hardware", source="upstream_code", ref="my_app/classes/device.py:20-24"),
        Fact("After discovery the clone closes all U3 connections with Close() so other experiments can use the "
             "hardware", source="upstream_code", ref="my_app/classes/device.py:108"),
        Fact("measure_voltage maps port numbers to AIN positions (port number minus one) and sets the FIO/EIO "
             "analog masks for the requested ports", source="upstream_code", ref="my_app/timecourse.py:65-68"),
        Fact("DAC0 powers the LED/sensor relay and DAC1 the linear regulator to the sensors; the configured "
             "voltages are 5 V and 2.6 V", source="upstream_code", ref="my_app/timecourse.py:11-16"),
        Fact("measure_voltage sets the DAC voltages before sampling and returns both DACs to 0 after sampling",
             source="upstream_code", ref="my_app/timecourse.py:70-83"),
        Fact("measure_voltage averages n_reps calibrated analog voltage samples and returns one mean per "
             "requested port", source="upstream_code", ref="my_app/timecourse.py:75-92"),
        Fact("measure_temp reads the U3 internal temperature in Kelvin and converts it to Celsius",
             source="upstream_code", ref="my_app/timecourse.py:97-105"),
        Fact("The README states that the repository controls a 16-tube, in-line optical density monitoring device",
             source="vendor_doc", ref="README.md:6"),
        Fact("The README says raw measurements are voltages and that log10(voltage) is fitted to known optical "
             "densities offline", source="vendor_doc", ref="README.md:70-73"),
        Fact("The README requires a U3-compatible LabJack driver: UD on Windows, Exodriver on Linux/macOS",
             source="vendor_doc", ref="README.md:83-85"),
        Fact("The pinned requirements file lists LabJackPython 2.1.0", source="upstream_code",
             ref="my_app/requirements.txt:6"),
    ]
    safe_state = ("No actuation is active: each measurement is one analog input read whose U3 handle is closed "
                  "in a finally block, and the e-stop additionally opens and closes a handle.")

    # -- reads --------------------------------------------------------------------------------------------------
    @read("name", type="string", description="Device name stored in the LabJack firmware")
    def device_name(self):
        return str(self.native.name)

    @read("serial_number", type="string", description="LabJack U3 serial number of this device")
    def serial_number(self):
        return str(self.native.sn)

    @read("port_positions", type="array", items="integer", length=PORT_COUNT, unit="1",
          description="Physical port positions of this device, 1 through 16")
    def port_positions(self):
        return [int(port.position) for port in self.native.ports]

    @read("port_usage", type="array", items="integer", length=PORT_COUNT, unit="1",
          description="Port usage flags: 0 unused, 1 used as a test port")
    def port_usage(self):
        return [int(port.usage) for port in self.native.ports]

    # -- the one write ------------------------------------------------------------------------------------------
    @write("name", type="string", description="Device name written to the LabJack firmware by Device.rename")
    def set_name(self, value):
        self.native.rename(str(value))
        return str(self.native.name)

    # -- measurement capability -----------------------------------------------------------------------------------
    @action(cap="cap.measure.voltage.v1",
            description="Read one calibrated DC voltage from an optical sensor channel of the reader",
            input={"channel": Field(
                "string", description="Physical port number 1 to 16; it maps to LabJack AIN0 to AIN15",
                enum=PORT_CHANNELS, max_length=2)})
    def measure_voltage(self, channel):
        try:
            port = int(channel)
        except (TypeError, ValueError):
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               f"channel {channel!r} is not a port number 1 to {PORT_COUNT}")
        if not 1 <= port <= PORT_COUNT:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               f"channel {channel!r} is not a port number 1 to {PORT_COUNT}")
        handle = self.native.connect()
        try:
            position = port - 1
            fio = 1 << position if position <= 7 else 0
            eio = 1 << (position - 8) if position >= 8 else 0
            handle.configIO(FIOAnalog=fio, EIOAnalog=eio)
            voltage = handle.getAIN(position, negChannel=31, longSettle=True, quickSample=False)
        finally:
            handle.close()
        return {"voltage": float(voltage)}

    # -- identification action ------------------------------------------------------------------------------------
    @action(name="x-cap.natlabrockies.blink.v1",
            description="Blink the device indicator LED through the native Device.blink sequence",
            output={"blinked": Field("boolean",
                                     description="True after the native blink sequence returned")})
    def blink(self):
        self.native.blink()
        return {"blinked": True}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: open and close the U3 handle so no LabJack connection is left open."""
        self.native.connect().close()
