"""OpenMHS driver for gh.kletternaut/scopemcp: an Owon/Abestop DS1102 oscilloscope over USB.

A direct Driver over the upstream pyusb class ``ds1102_mcp:ScopeController``.  The card names the PythonObjectDriver
helper, but the upstream builds every command from parts (a 4-byte little-endian length header, a colon-prefixed SCPI
line and a line feed), so a command table cannot reproduce the frame the device receives; this package is a direct
Driver over the upstream class with a ``native.py`` factory (DEVIATION FROM THE CARD, recorded in RESULT.json).
The driver calls only the upstream methods ``get_device``, ``send_cmd``, ``read_resp`` and ``get_metadata_cached``.

* reads: the model, the firmware run status, and the frequency, scale, coupling and raw offset of channels 1 and 2
  from the JSON metadata that ``get_metadata_cached`` returns;
* writes: the channel-1 vertical scale, coupling and offset, the horizontal scale, and the trigger mode, slope,
  source and level.  The clone gives the examples ``1V``/``500mV`` and ``1ms``/``500us`` but no complete allowed set,
  and it states no numeric range for the offset or the trigger level, so those four fields are
  ``Limit.operator_required`` and the site overlay fills them (``site-limits.example.json`` shows the overlay);
* actions: autoset, run and a safe-state stop;
* the native stop (``:stop``) is the e-stop and the safe-state action.  The instrument only observes and configures
  its observation, so the package is R0; its settings do not create a physical effect.

NOT COVERED: the waveform array.  ``capture_waveform`` and ``capture_dual_waveform`` transfer 1520 signed 16-bit
samples per channel (3040 bytes plus a 4-byte header) and convert them with ``ds1102_logic``; the standard has no
trace-array transport, so this package serves the scalar metadata and the settings instead.  Channel-2 settings and
the screenshot/frame buffer are not covered either.

Every Fact cites a line of the clone at the pinned commit a932b777694d7bfc48c821c3afef7e3eb2da3f0e.  This package is
model-authored and unreviewed; it is checked on the fake backend only and never ran on hardware.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write

CODE = "ds1102_mcp.py"
LOGIC = "ds1102_logic.py"
PROTOCOL = "doc/ds1102_protocol.md"
INSTALL = "doc/INSTALL.md"
README = "README.md"

#: Coupling, trigger mode, slope and source spellings the clone validates (ds1102_mcp.py:382, 409, 423, 437).
COUPLINGS = ["AC", "DC", "GND"]
TRIGGER_MODES = ["AUTO", "NORMAL", "SINGLE"]
TRIGGER_SLOPES = ["RISE", "FALL"]
TRIGGER_SOURCES = ["CH1", "CH2"]


class Ds1102(Driver):
    device_id = "ds1102"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R0"
    native = "ds1102_mcp:ScopeController"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeScopemcp"}
    vendor = "Owon/Abestop"
    model = "DS1102 oscilloscope"
    display_name = "Owon/Abestop DS1102 oscilloscope (ds1102_mcp.ScopeController)"
    tags = ["oscilloscope", "ds1102", "usb", "pyusb", "scpi"]
    facts = [
        Fact("The DS1102 connects over USB in PC mode with VID 0x5345 and PID 0x1234; USBTMC mode (PID 1235) is "
             "not supported", source="vendor_doc", ref=f"{INSTALL}:7-10"),
        Fact("The physical layer is USB bulk transfer with OUT endpoint 0x01 and IN endpoint 0x81",
             source="vendor_doc", ref=f"{PROTOCOL}:11-14"),
        Fact("Every command is prefixed with a 4-byte little-endian length header and ends with a line feed",
             source="upstream_code", ref=f"{CODE}:84-91"),
        Fact("Replies are read from the IN endpoint with dev.read", source="upstream_code", ref=f"{CODE}:117-121"),
        Fact("Metadata is fetched with :DATA:WAVE:SCREEN:HEAD? and parsed as the JSON between the first '{' and the "
             "last '}'", source="upstream_code", ref=f"{CODE}:144-148"),
        Fact("get_measurements reads FREQUENCE, SCALE, COUPLING, DISPLAY and OFFSET from each CHANNEL entry",
             source="upstream_code", ref=f"{CODE}:212-227"),
        Fact("The firmware OFFSET is an integer raw value from the metadata JSON, not volts",
             source="upstream_code", ref=f"{LOGIC}:21-22"),
        Fact("The device transfers 1520 samples per channel (3040 bytes plus a 4-byte header) in SCREEN mode",
             source="vendor_doc", ref=f"{README}:103"),
        Fact("The vertical scale command is :CH<channel>:SCALe <scale>", source="upstream_code",
             ref=f"{CODE}:365"),
        Fact("The horizontal scale command is :HORizontal:SCALe <scale>", source="upstream_code",
             ref=f"{CODE}:376"),
        Fact("The coupling command is :CH<channel>:COUPling <coupling> and the tool accepts AC, DC and GND",
             source="upstream_code", ref=f"{CODE}:381-390"),
        Fact("The offset command is :CH<channel>:OFFSet <offset> written with three decimals",
             source="upstream_code", ref=f"{CODE}:402"),
        Fact("The trigger mode is written with :TRIGger:SWEep and accepts AUTO, NORMAL and SINGLE",
             source="upstream_code", ref=f"{CODE}:407-417"),
        Fact("The trigger slope is written with :TRIGger:EDGE:SLOpe and accepts RISE and FALL",
             source="upstream_code", ref=f"{CODE}:421-431"),
        Fact("The trigger source is written with :TRIGger:EDGE:SOURce and accepts CH1 and CH2",
             source="upstream_code", ref=f"{CODE}:435-445"),
        Fact("The trigger level is written with :TRIGger:EDGE:LEVel in mV with one decimal",
             source="upstream_code", ref=f"{CODE}:449-456"),
        Fact("Autoset sends :AUToset on", source="upstream_code", ref=f"{CODE}:335-342"),
        Fact("The run state is written with :run or :stop", source="upstream_code", ref=f"{CODE}:346-353"),
        Fact("The firmware always reports TRIG in the status field, even when stopped", source="vendor_doc",
             ref=f"{README}:95"),
        Fact("The command throttle is 0.05 s", source="upstream_code", ref=f"{CODE}:35"),
        Fact("send_cmd sleeps 0.1 s after SCAL, HOR, TRIG or OFFS and 1.0 s after AUT", source="upstream_code",
             ref=f"{CODE}:110-115"),
    ]
    safe_state = "acquisition stopped (:stop); the scope captures nothing until an operator starts it again"

    # -- metadata -------------------------------------------------------------------------------------------------
    def _metadata(self):
        """The JSON metadata of the upstream ``get_metadata_cached``, refreshed (``max_age=0``)."""
        device = self.native.get_device()
        metadata = self.native.get_metadata_cached(device, 0)
        return metadata if isinstance(metadata, dict) else {}

    def _channel(self, index):
        """One CHANNEL entry of the metadata JSON (a missing entry is an empty dict)."""
        channels = self._metadata().get("CHANNEL") or []
        if isinstance(channels, list) and 1 <= index <= len(channels) and isinstance(channels[index - 1], dict):
            return channels[index - 1]
        return {}

    def _send(self, command):
        """Write one command through the upstream ``send_cmd`` (it adds the 4-byte header and the line feed)."""
        device = self.native.get_device()
        self.native.send_cmd(device, command)

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("instrument_model", type="string", description="Model name from the metadata JSON")
    def instrument_model(self):
        return str(self._metadata().get("MODEL") or "")

    @read("run_status", type="string", description="Firmware RUNSTATUS field of the metadata JSON")
    def run_status(self):
        return str(self._metadata().get("RUNSTATUS") or "")

    @read("channel1_frequency_hz", unit="Hz", description="Frequency of channel 1 from the metadata JSON")
    def channel1_frequency_hz(self):
        return float(self._channel(1).get("FREQUENCE") or 0.0)

    @read("channel1_scale", type="string", description="Vertical scale of channel 1 as the device spells it")
    def channel1_scale(self):
        return str(self._channel(1).get("SCALE") or "")

    @read("channel1_coupling", type="string", description="Coupling of channel 1")
    def channel1_coupling(self):
        return str(self._channel(1).get("COUPLING") or "")

    @read("channel1_offset_raw", type="integer", unit="1",
          description="Raw integer OFFSET of channel 1 in the metadata JSON (not volts)")
    def channel1_offset_raw(self):
        return int(self._channel(1).get("OFFSET") or 0)

    @read("channel2_frequency_hz", unit="Hz", description="Frequency of channel 2 from the metadata JSON")
    def channel2_frequency_hz(self):
        return float(self._channel(2).get("FREQUENCE") or 0.0)

    @read("channel2_scale", type="string", description="Vertical scale of channel 2 as the device spells it")
    def channel2_scale(self):
        return str(self._channel(2).get("SCALE") or "")

    @read("channel2_coupling", type="string", description="Coupling of channel 2")
    def channel2_coupling(self):
        return str(self._channel(2).get("COUPLING") or "")

    @read("channel2_offset_raw", type="integer", unit="1",
          description="Raw integer OFFSET of channel 2 in the metadata JSON (not volts)")
    def channel2_offset_raw(self):
        return int(self._channel(2).get("OFFSET") or 0)

    # -- writes ---------------------------------------------------------------------------------------------------
    @write("channel1_scale", type="string", description="Channel 1 vertical scale, for example 1V or 500mV",
           limit=Limit.operator_required(
               "the clone gives the examples '1V' and '500mV' (README.md:30) but no complete allowed set; the site "
               "supplies the scale spellings its probe and scope accept"))
    def set_channel1_scale(self, value):
        self._send(":CH1:SCALe " + str(value))
        return str(self._channel(1).get("SCALE") or "")

    @write("channel1_coupling", type="string", description="Channel 1 coupling: AC, DC or GND",
           limit=Limit(allowed=COUPLINGS, source="upstream_code", ref=f"{CODE}:382"))
    def set_channel1_coupling(self, value):
        self._send(":CH1:COUPling " + str(value).upper())
        return str(self._channel(1).get("COUPLING") or "")

    @write("channel1_offset_v", unit="V", description="Channel 1 vertical offset in volts",
           limit=Limit.operator_required(
               "no text file of the clone states a vertical offset range; it depends on the scale and the probe, so "
               "the site supplies the window of its unit"))
    def set_channel1_offset_v(self, value):
        self._send(":CH1:OFFSet {:.3f}".format(float(value)))
        return float("{:.3f}".format(float(value)))

    @write("horizontal_scale", type="string", description="Timebase scale, for example 1ms or 500us",
           limit=Limit.operator_required(
               "the clone gives the examples '1ms' and '500us' (README.md:33) but no complete allowed set; the site "
               "supplies the timebase spellings its unit accepts"))
    def set_horizontal_scale(self, value):
        self._send(":HORizontal:SCALe " + str(value))
        return str(value)

    @write("trigger_mode", type="string", description="Trigger sweep mode: AUTO, NORMAL or SINGLE",
           limit=Limit(allowed=TRIGGER_MODES, source="upstream_code", ref=f"{CODE}:409"))
    def set_trigger_mode(self, value):
        self._send(":TRIGger:SWEep " + str(value).upper())
        return str(value).upper()

    @write("trigger_slope", type="string", description="Trigger edge slope: RISE or FALL",
           limit=Limit(allowed=TRIGGER_SLOPES, source="upstream_code", ref=f"{CODE}:423"))
    def set_trigger_slope(self, value):
        self._send(":TRIGger:EDGE:SLOpe " + str(value).upper())
        return str(value).upper()

    @write("trigger_source", type="string", description="Trigger source: CH1 or CH2",
           limit=Limit(allowed=TRIGGER_SOURCES, source="upstream_code", ref=f"{CODE}:437"))
    def set_trigger_source(self, value):
        self._send(":TRIGger:EDGE:SOURce " + str(value).upper())
        return str(value).upper()

    @write("trigger_level_mv", unit="mV", description="Trigger level in millivolts",
           limit=Limit.operator_required(
               "no text file of the clone states a trigger level range; it depends on the trigger source and the "
               "scale, so the site supplies the window of its unit"))
    def set_trigger_level_mv(self, value):
        self._send(":TRIGger:EDGE:LEVel {:.1f}mV".format(float(value)))
        return float("{:.1f}".format(float(value)))

    # -- actions --------------------------------------------------------------------------------------------------
    @action(name="x-cap.kletternaut.autoset.v1",
            description="Run the scope's automatic setup (:AUToset on)",
            output={"channel1_scale": Field("string", description="Channel 1 vertical scale after autoset"),
                    "channel1_coupling": Field("string", description="Channel 1 coupling after autoset")})
    def autoset(self):
        self._send(":AUToset on")
        channel = self._channel(1)
        return {"channel1_scale": str(channel.get("SCALE") or ""),
                "channel1_coupling": str(channel.get("COUPLING") or "")}

    @action(name="x-cap.kletternaut.run.v1", description="Start continuous acquisition (:run)",
            output={"run_status": Field("string", description="Firmware RUNSTATUS after :run")})
    def run(self):
        self._send(":run")
        return {"run_status": str(self._metadata().get("RUNSTATUS") or "")}

    @action(name="x-cap.kletternaut.stop_acquisition.v1", safe_state=True,
            description="Stop the acquisition (:stop, the safe state); it takes no input",
            output={"stopped": Field("boolean", description="True once the :stop command was sent")})
    def stop_acquisition(self):
        self._send(":stop")
        return {"stopped": True}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: the runtime latches first, then sends :stop."""
        self._send(":stop")
