"""OpenMHS driver for gh.wetenschaap/pycrofluidics: the Elveflow OB1 pressure controller.

A direct Driver over the upstream Python object ``pycrofluidics.elveob:OB1elve``.  The upstream class wraps the
Elveflow DLL with ctypes (``pycrofluidics/elveob.py:106-116``); ``native.py`` opens it.  This driver reads the four
pressure channels and the four flow-sensor channels, writes the pressure goal of one channel, and starts or stops the
upstream remote control loop.

Safety: an OB1 applies pressure to liquid, so the device is R2.  No text file of the clone states a pressure range
for a configured unit: the range follows the regulator type installed and selected in ``deviceRegulators``, and the
constructor default ``[0, 0, 0, 0]`` means "non-installed" (``pycrofluidics/elveob.py:34-37``, ``:543-553``).  Every
pressure write is therefore ``Limit.operator_required`` and is refused ``MHS.SAFETY.LIMITS_UNSET`` until the site
supplies the range of its unit (``site-limits.example.json`` shows the overlay).  The e-stop and the safe-state action
``x-cap.wetenschaap.stop_remote.v1`` stop the remote loop and command all four pressure channels to 0 mbar.  This
package is model-authored and unreviewed: it is checked on the fake backend only (driver.lock.json).
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write

#: The upstream _channelCheck accepts 1 to 4 (pycrofluidics/elveob.py:464-470); every channel below uses that range.
CHANNELS = (1, 2, 3, 4)

PRESSURE_RANGE_OPERATOR = (
    "the pressure range follows the regulator type installed and selected in deviceRegulators; the clone lists the "
    "regulator options (pycrofluidics/elveob.py:543-553) but states no bound of this configured unit, so the site "
    "supplies the range of the channel"
)


class ElveflowOB1(Driver):
    device_id = "elveflow-ob1"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R2"
    native = "pycrofluidics.elveob:OB1elve"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeOB1elve"}
    vendor, model = "Elveflow", "OB1 pressure controller (Mk4)"
    display_name = "Elveflow OB1 pressure controller (pycrofluidics.OB1elve)"
    tags = ["pressure-controller", "microfluidics", "elveflow", "ob1", "flow-sensor"]
    facts = [
        Fact("setPressure() calls OB1_Set_Press and getPressure() calls OB1_Get_Press; both convert through the "
             "calibration array", source="upstream_code", ref="pycrofluidics/elveob.py:180-215"),
        Fact("The pressure set point is in mbar", source="vendor_doc", ref="readme.md:27"),
        Fact("The recorded pressure columns are in mbar", source="upstream_code",
             ref="pycrofluidics/protocols.py:167"),
        Fact("getFlowUniversal() returns the flow sensor readout in uL/min", source="upstream_code",
             ref="pycrofluidics/elveob.py:479-480"),
        Fact("getSensorData() returns the sensor reading in its native units, probably uL/min", source="upstream_code",
             ref="pycrofluidics/elveob.py:282-284"),
        Fact("A channel number is 1 to 4", source="upstream_code", ref="pycrofluidics/elveob.py:464-470"),
        Fact("startRemote() starts the background control loop and sets insideRemote", source="upstream_code",
             ref="pycrofluidics/elveob.py:305-314"),
        Fact("stopRemote() stops the background control loop and clears insideRemote", source="upstream_code",
             ref="pycrofluidics/elveob.py:316-327"),
        Fact("remoteGetData() returns the pressure and sensor reading inside the remote loop", source="upstream_code",
             ref="pycrofluidics/elveob.py:329-352"),
        Fact("setPressure() and getPressure() refuse while the remote loop is running", source="upstream_code",
             ref="pycrofluidics/elveob.py:193-210"),
        Fact("getSensorData() refuses while the remote loop is running", source="upstream_code",
             ref="pycrofluidics/elveob.py:296-297"),
        Fact("The pressure range depends on the installed regulator type; printRegulatorTypes() lists the regulator "
             "options, including non-installed 0", source="upstream_code", ref="pycrofluidics/elveob.py:543-553"),
        Fact("The constructor default deviceRegulators is [0, 0, 0, 0]", source="upstream_code",
             ref="pycrofluidics/elveob.py:34-37"),
        Fact("loadCallibration() loads the pressure calibration array into self.calib", source="upstream_code",
             ref="pycrofluidics/elveob.py:118-139"),
        Fact("close() stops a running remote loop and then calls OB1_Destructor", source="upstream_code",
             ref="pycrofluidics/elveob.py:93-104"),
        Fact("The module controls the Elveflow OB1 pressure controller, tested on Mk4", source="vendor_doc",
             ref="readme.md:9"),
    ]
    safe_state = "remote control loop stopped and all four pressure channels commanded to 0 mbar"

    # -- reads ------------------------------------------------------------------------------------------------
    @read("pressure_1", unit="mbar", description="Pressure measured in channel 1")
    def pressure_1(self):
        return self.native.getPressureUniversal(1)

    @read("pressure_2", unit="mbar", description="Pressure measured in channel 2")
    def pressure_2(self):
        return self.native.getPressureUniversal(2)

    @read("pressure_3", unit="mbar", description="Pressure measured in channel 3")
    def pressure_3(self):
        return self.native.getPressureUniversal(3)

    @read("pressure_4", unit="mbar", description="Pressure measured in channel 4")
    def pressure_4(self):
        return self.native.getPressureUniversal(4)

    @read("flow_1", unit="uL/min", description="Flow-sensor reading of channel 1")
    def flow_1(self):
        return self.native.getFlowUniversal(1)

    @read("flow_2", unit="uL/min", description="Flow-sensor reading of channel 2")
    def flow_2(self):
        return self.native.getFlowUniversal(2)

    @read("flow_3", unit="uL/min", description="Flow-sensor reading of channel 3")
    def flow_3(self):
        return self.native.getFlowUniversal(3)

    @read("flow_4", unit="uL/min", description="Flow-sensor reading of channel 4")
    def flow_4(self):
        return self.native.getFlowUniversal(4)

    @read("remote", type="boolean",
          description="True while the upstream remote control loop (startRemote) is running")
    def remote(self):
        return bool(self.native.insideRemote)

    # -- writes -------------------------------------------------------------------------------------------------
    @write("pressure_1", unit="mbar", description="Pressure goal of channel 1",
           limit=Limit.operator_required(PRESSURE_RANGE_OPERATOR))
    def set_pressure_1(self, value):
        self.native.setPressure(1, value)

    @write("pressure_2", unit="mbar", description="Pressure goal of channel 2",
           limit=Limit.operator_required(PRESSURE_RANGE_OPERATOR))
    def set_pressure_2(self, value):
        self.native.setPressure(2, value)

    @write("pressure_3", unit="mbar", description="Pressure goal of channel 3",
           limit=Limit.operator_required(PRESSURE_RANGE_OPERATOR))
    def set_pressure_3(self, value):
        self.native.setPressure(3, value)

    @write("pressure_4", unit="mbar", description="Pressure goal of channel 4",
           limit=Limit.operator_required(PRESSURE_RANGE_OPERATOR))
    def set_pressure_4(self, value):
        self.native.setPressure(4, value)

    # -- read capabilities --------------------------------------------------------------------------------------
    @action(name="x-cap.wetenschaap.read_pressure.v1", verb="read",
            description="Read the pressure of one OB1 channel and return it in mbar",
            input={"channel": Field("integer", unit="1", description="Pressure channel, 1 to 4",
                                    limit=Limit(min=1, max=4, source="upstream_code",
                                                ref="pycrofluidics/elveob.py:468-469"))},
            output={"channel": Field("integer", unit="1", description="Pressure channel that was read"),
                    "pressure": Field("number", unit="mbar", description="Pressure measured in the channel")})
    def read_pressure(self, channel):
        channel = int(channel)
        return {"channel": channel, "pressure": self.native.getPressureUniversal(channel)}

    @action(name="x-cap.wetenschaap.read_flow.v1", verb="read",
            description="Read the flow sensor of one OB1 channel and return it in uL/min",
            input={"channel": Field("integer", unit="1", description="Flow-sensor channel, 1 to 4",
                                    limit=Limit(min=1, max=4, source="upstream_code",
                                                ref="pycrofluidics/elveob.py:468-469"))},
            output={"channel": Field("integer", unit="1", description="Flow-sensor channel that was read"),
                    "flow_rate": Field("number", unit="uL/min", description="Flow-sensor reading in the channel")})
    def read_flow(self, channel):
        channel = int(channel)
        return {"channel": channel, "flow_rate": self.native.getFlowUniversal(channel)}

    # -- remote control actions ---------------------------------------------------------------------------------
    @action(name="x-cap.wetenschaap.start_remote.v1",
            description="Start the upstream remote control loop, which reads all sensors and regulators",
            output={"running": Field("boolean", description="True once the remote control loop is running")})
    def start_remote(self):
        self.native.startRemote()
        return {"running": bool(self.native.insideRemote)}

    @action(name="x-cap.wetenschaap.stop_remote.v1", safe_state=True,
            description="Stop the remote control loop and command all four pressure channels to 0 mbar (safe state)",
            output={"stopped": Field("boolean",
                                     description="True once the remote loop is stopped and the channels are zeroed")})
    def stop_remote(self):
        if self.native.insideRemote:
            self.native.stopRemote()
        for channel in CHANNELS:
            self.native.setPressure(channel, 0.0)
        return {"stopped": True}

    # -- safety -------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """Stop the remote loop and command every pressure channel to 0 mbar."""
        if self.native.insideRemote:
            self.native.stopRemote()
        for channel in CHANNELS:
            self.native.setPressure(channel, 0.0)

    def teardown(self):
        self.native.close()
