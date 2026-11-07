"""OpenMHS driver for gh.trash-hold/oscilloscope_dimserver: a Tektronix TDS3054C scope.

A direct Driver (decorated methods) over the upstream device class
``zmq_server.drivers.TDS3054C:TDS3054C``.  The upstream class sends every SCPI command as an
HTTP POST to the scope's web port (``COMMAND=<command>&gpibsend=Send``) and opens and closes a
TCP socket for each command (TDS3054C.py:100-111, 415-432).  The driver exposes the settings and
the scalar readbacks the upstream class implements:

* reads: the selected (control) channel, whether that channel is displayed, and the horizontal
  time increment (``WFMPre:XINcr?``);
* writes: the selected channel, that channel's display state, the vertical scale and position,
  the horizontal scale and position, the trigger channel, the trigger level and the trigger
  slope.  Only the channel numbers and the two trigger slopes are bounded by the clone; every
  other numeric setting is ``Limit.operator_required`` because no text file of the clone states
  a range, so those writes are refused ``MHS.SAFETY.LIMITS_UNSET`` until the site supplies one;
* actions: one single-sequence acquisition and the safe-state action that stops acquisition;
* the native stop is ``@estop``: it writes ``ACQ:STATE STOP`` through the same native ``write``
  method the upstream class uses (TDS3054C.py:376).

NOT COVERED: the waveform array returned by ``get_waveform`` (``CURVE?``).  The catalogue has no
class that carries a scope trace, and the clone states no record length, so this package does not
invent one; it covers the device's scalar measurements and settings only (see RESULT.json notes).

Every Fact cites a line of the clone at the pinned commit
6a34db58756fc0ac7ef8d4021bc290973d5cb65f.  This package is model-authored and unreviewed: it is
checked on the fake backend only, and no hardware run was performed.
"""

import re

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

_SELECTED = re.compile(r"CONTROL\s+CH(\d+)", re.IGNORECASE)
_CHANNEL_STATE = re.compile(r"CH(\d+)\s+([01])", re.IGNORECASE)


class TDS3054C(Driver):
    device_id = "tds3054c"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "zmq_server.drivers.TDS3054C:TDS3054C"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeTDS3054C"}
    vendor, model = "Tektronix", "TDS3054C"
    display_name = "Tektronix TDS3054C oscilloscope (oscilloscope_dimserver)"
    tags = ["oscilloscope", "scope", "tektronix", "tds3054c", "instrument"]
    facts = [
        Fact("The repository README describes a system for controlling an oscilloscope with a ready-to-use "
             "driver for the Tektronix TDS3054C", source="vendor_doc", ref="readMe.md:19-23"),
        Fact("The TDS3054C class is the repository's oscilloscope driver; it connects to the scope's HTTP "
             "server over an AF_INET TCP socket", source="upstream_code",
             ref="zmq_server/drivers/TDS3054C.py:35-39"),
        Fact("test_connection queries *IDN? and accepts the device only when the reply contains 'TDS 3054C'",
             source="upstream_code", ref="zmq_server/drivers/TDS3054C.py:121-127"),
        Fact("Every command is an HTTP POST to /Comm.html whose body is COMMAND=<command>&gpibsend=Send",
             source="upstream_code", ref="zmq_server/drivers/TDS3054C.py:419-429"),
        Fact("set_channel accepts only channels 1 to 4 and writes DATA:SOURCE CH<n>", source="upstream_code",
             ref="zmq_server/drivers/TDS3054C.py:141-145"),
        Fact("set_channel_state writes SELECT:CH<n> ON or OFF", source="upstream_code",
             ref="zmq_server/drivers/TDS3054C.py:223-227"),
        Fact("set_vertical_scale writes CH<n>:SCAle and set_vertical_position writes CH<n>:POSition",
             source="upstream_code", ref="zmq_server/drivers/TDS3054C.py:233-245"),
        Fact("set_horizontal_scale writes HORizontal:MAIn:SCAle and set_horizontal_position writes "
             "HORizontal:MAIn:POSition", source="upstream_code",
             ref="zmq_server/drivers/TDS3054C.py:251-263"),
        Fact("get_horizontal_increment queries WFMPre:XINcr? and returns the device reply",
             source="upstream_code", ref="zmq_server/drivers/TDS3054C.py:269-275"),
        Fact("The Slope enum allows only the values RISE and FALL", source="upstream_code",
             ref="zmq_server/drivers/TDS3054C.py:9-11"),
        Fact("set_trigger_slope writes TRIGger:A:EDGE:SLOpe only for the two Slope values",
             source="upstream_code", ref="zmq_server/drivers/TDS3054C.py:287-291"),
        Fact("set_trigger_level writes TRIGger:A:LEVel", source="upstream_code",
             ref="zmq_server/drivers/TDS3054C.py:279-282"),
        Fact("set_trigger_channel accepts only channels 1 to 4 and writes TRIGger:A:EDGE:SOUrce CH<n>",
             source="upstream_code", ref="zmq_server/drivers/TDS3054C.py:300-302"),
        Fact("sample stops the current acquisition, arms a single sequence, starts ACQ:STATE ON and polls "
             "BUSY? until 0", source="upstream_code", ref="zmq_server/drivers/TDS3054C.py:367-405"),
        Fact("SELECT? may return the channel states followed by CONTROL CH<n>, which names the selected "
             "waveform", source="upstream_code", ref="zmq_server/drivers/TDS3054C.py:193-198"),
    ]
    safe_state = "acquisition stopped (ACQ:STATE STOP); the scope output is not software-controlled"

    # -- SELECT? parsing -------------------------------------------------------------------------
    def _select_reply(self) -> str:
        """The raw SELECT? reply: channel states followed by CONTROL CH<n>."""
        return str(self.native.query("SELECT?"))

    def _selected_channel(self, reply: str) -> int:
        match = _SELECTED.search(reply)
        if match is None:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               f"SELECT? reply has no CONTROL CH<n>: {reply!r}")
        return int(match.group(1))

    def _selected_channel_enabled(self, reply: str) -> bool:
        selected = self._selected_channel(reply)
        for match in _CHANNEL_STATE.finditer(reply):
            if int(match.group(1)) == selected:
                return match.group(2) == "1"
        raise DriverFailed("MHS.DEVICE.FAULTED",
                           f"SELECT? reply has no state for CH{selected}: {reply!r}")

    # -- reads -----------------------------------------------------------------------------------
    @read("channel", type="integer", unit="1",
          description="Selected (control) channel of the scope (1 to 4)")
    def channel(self):
        return self._selected_channel(self._select_reply())

    @read("channel_enabled", type="boolean",
          description="True while the selected (control) channel is displayed")
    def channel_enabled(self):
        return self._selected_channel_enabled(self._select_reply())

    @read("horizontal_increment", unit="s",
          description="Horizontal time increment between waveform samples (WFMPre:XINcr?)")
    def horizontal_increment(self):
        return float(self.native.get_horizontal_increment())

    # -- writes ----------------------------------------------------------------------------------
    @write("channel", type="integer", unit="1", description="Selected channel (1 to 4)",
           limit=Limit(allowed=[1, 2, 3, 4], source="upstream_code",
                       ref="zmq_server/drivers/TDS3054C.py:141"))
    def set_channel(self, value):
        self.native.set_channel(int(value))

    @write("channel_enabled", type="boolean",
           description="Selected channel display state")
    def set_channel_enabled(self, value):
        channel = self._selected_channel(self._select_reply())
        self.native.set_channel_state(channel, bool(value))

    @write("vertical_scale", unit="V",
           description="Vertical scale (volts/div)",
           limit=Limit.operator_required(
               "the clone writes CH<n>:SCAle without validating or stating a vertical scale range; "
               "the site supplies the range of its probe and scope"))
    def set_vertical_scale(self, value):
        channel = self._selected_channel(self._select_reply())
        self.native.set_vertical_scale(channel, float(value))

    @write("vertical_position", unit="1",
           description="Vertical position (native value)",
           limit=Limit.operator_required(
               "the clone writes CH<n>:POSition without validating or stating a vertical position range; "
               "the site supplies the usable range of its scope"))
    def set_vertical_position(self, value):
        channel = self._selected_channel(self._select_reply())
        self.native.set_vertical_position(channel, float(value))

    @write("horizontal_scale", unit="s",
           description="Horizontal scale (seconds/div)",
           limit=Limit.operator_required(
               "the clone writes HORizontal:MAIn:SCAle without validating or stating a horizontal scale "
               "range; the site supplies the range of its scope"))
    def set_horizontal_scale(self, value):
        self.native.set_horizontal_scale(float(value))

    @write("horizontal_position", unit="1",
           description="Horizontal position (native value)",
           limit=Limit.operator_required(
               "the clone writes HORizontal:MAIn:POSition without validating or stating a horizontal "
               "position range; the site supplies the usable range of its scope"))
    def set_horizontal_position(self, value):
        self.native.set_horizontal_position(float(value))

    @write("trigger_channel", type="integer", unit="1", description="Trigger channel (1 to 4)",
           limit=Limit(allowed=[1, 2, 3, 4], source="upstream_code",
                       ref="zmq_server/drivers/TDS3054C.py:300"))
    def set_trigger_channel(self, value):
        self.native.set_trigger_channel(int(value))

    @write("trigger_level", unit="1",
           description="Trigger level (native value)",
           limit=Limit.operator_required(
               "the clone writes TRIGger:A:LEVel without validating or stating a trigger level range; "
               "the site supplies the range of its signal and scope"))
    def set_trigger_level(self, value):
        channel = self._selected_channel(self._select_reply())
        self.native.set_trigger_level(channel, float(value))

    @write("trigger_slope", type="string", description="Trigger slope (RISE or FALL)",
           limit=Limit(allowed=["RISE", "FALL"], source="upstream_code",
                       ref="zmq_server/drivers/TDS3054C.py:9-11"))
    def set_trigger_slope(self, value):
        self.native.set_trigger_slope(str(value))

    # -- actions ---------------------------------------------------------------------------------
    @action(name="x-cap.trash-hold.single_acquisition.v1",
            description="Run one single-sequence acquisition and wait for it to finish (the native sample)",
            output={"acquired": Field("boolean",
                                      description="True once the scope has finished the single acquisition")})
    def single_acquisition(self):
        self.native.sample()
        return {"acquired": True}

    @action(name="x-cap.trash-hold.stop_acquisition.v1", safe_state=True,
            description="Stop the acquisition (ACQ:STATE STOP); this is the safe state and takes no input",
            output={"stopped": Field("boolean",
                                     description="True after ACQ:STATE STOP has been sent")})
    def stop_acquisition(self):
        self.native.write("ACQ:STATE STOP")
        return {"stopped": True}

    # -- safety and lifecycle --------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: the runtime latches first, then writes ACQ:STATE STOP."""
        self.native.write("ACQ:STATE STOP")

    def teardown(self):
        self.native.end_connection()
