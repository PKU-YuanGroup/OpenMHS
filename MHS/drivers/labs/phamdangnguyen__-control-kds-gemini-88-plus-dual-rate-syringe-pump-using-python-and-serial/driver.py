"""OpenMHS driver for gh.phamdangnguyen/control-kds-gemini-88-plus-dual-rate-syringe-pump-using-python-and-serial.

The KDS Gemini 88 dual-rate syringe pump is controlled with line-oriented serial commands.  The upstream clone is
not a device SDK: it writes a user-supplied text line plus CRLF through ``realSerial.writeSerial`` and optionally
reads the reply through ``realSerial.readSerial`` (``realSerial.py:26-45``).  This package uses a direct Driver
over the upstream ``writeSerial`` object and a ``native.py`` hardware factory, because a pump run normally combines
several lines (``irate``, ``tvolume``, ``run``); a SerialDriver command table would bind one line per capability.

* reads: the raw text the pump returns to ``status`` and the driver's last run/stop command state;
* writes: the syringe volume, syringe diameter, target time, target volume and infusion rate, each sent for both
  channels (``ab``) in the independent condition;
* actions: select a syringe (``syr``), run the pump (``run``) and stop it (``stop ab``).  The stop action is the
  safe-state action and the native stop; the pump dispenses liquid, so the driver is R2 even though the card's
  floor is R0;
* the pump direction is set on the pump itself (``README.md:5`` describes infusing with one syringe and withdrawing
  with the other), so no direction command is exposed.

No text file of the clone states a numeric range for the syringe volume, diameter, target time, target volume,
infusion rate or syringe index.  Those bounds are ``Limit.operator_required``: the operator supplies them in the
site overlay, and without one every write or invoke that sets them is refused ``MHS.SAFETY.LIMITS_UNSET``.

Every Fact cites a line of the clone at the pinned commit (ab6a02be981ea541d11f8788567030073ad2a378).  This package
is model-authored and unreviewed: it is checked on the fake backend only, and no hardware was attached.
"""

import threading
import time

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

#: The commands are text lines from the clone's tutorial; these tokens are checked against the clone by the gate.
TUTORIAL = "tutorial_command_basic.txt"


class Gemini88(Driver):
    device_id = "kds-gemini-88"
    device_kind = "fluid.pump"
    mode = "hardware"
    #: A pump that dispenses liquid is R2 (MHS/spec/04-safety.md, section 2.1), above the card's R0 floor.
    risk = "R2"
    native = "realSerial:writeSerial"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeGemini88"}
    vendor, model = "KD Scientific", "Gemini 88 Plus dual-rate syringe pump"
    display_name = "KDS Gemini 88 Plus dual-rate syringe pump"
    tags = ["syringe pump", "kds", "gemini 88", "serial", "infuse", "withdraw", "dual rate"]
    facts = [
        Fact("The repository controls a KDS Gemini 88 dual-rate syringe pump from Python over a serial COM port",
             source="vendor_doc", ref="README.md:1-5"),
        Fact("The pump can infuse with one syringe and withdraw with the other, at different rates",
             source="vendor_doc", ref="README.md:5"),
        Fact("The upstream's example command is 'condition Independent'", source="upstream_code",
             ref="InfuseCode.py:5"),
        Fact("In the independent condition the commands take channel a, b or ab", source="vendor_doc",
             ref=f"{TUTORIAL}:4"),
        Fact("The tutorial lists the command forms for syringe selection, syringe volume, diameter, target time, "
             "target volume, infusion rate, run, status and stop", source="vendor_doc", ref=f"{TUTORIAL}:4-27"),
        Fact("The example syringe selection is 'syr ab sst 1'", source="vendor_doc", ref=f"{TUTORIAL}:4"),
        Fact("'status' reports the state of the pumps", source="vendor_doc", ref=f"{TUTORIAL}:25"),
        Fact("A command is written as its bytes plus a carriage return and a line feed", source="upstream_code",
             ref="realSerial.py:31"),
        Fact("The serial port defaults to 9600 baud, a 10 s timeout, odd parity, two stop bits and seven data bits",
             source="upstream_code", ref="realSerial.py:6"),
        Fact("The upstream reads the reply bytes waiting on the port", source="upstream_code",
             ref="realSerial.py:39-45"),
        Fact("The example sends the command through realSerial.writeSerial and optionally reads the reply through "
             "realSerial.readSerial", source="upstream_code", ref="InfuseCode.py:9-11"),
        Fact("The README says the pump stops when it reaches the volume specified in the code", source="vendor_doc",
             ref="README.md:30"),
        Fact("The README says the pump's display need not change when software controls it", source="vendor_doc",
             ref="README.md:28"),
        Fact("The README names pyserial 3.5 as the serial dependency", source="vendor_doc", ref="README.md:21"),
    ]
    safe_state = "both pump channels stopped by the 'stop ab' command; no infusion or withdrawal continues until a run"

    #: A bounded wait for the status reply; the upstream Write sleeps 1 s before the example reads (realSerial.py:32).
    read_timeout_s = 2.0

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._wire_lock = threading.Lock()
        self._running = None

    # -- wire -----------------------------------------------------------------------------------------------------
    def _send(self, line: str) -> None:
        """Write one command line through the upstream writeSerial object (line + CRLF, realSerial.py:31)."""
        if not line or "\r" in line or "\n" in line:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "a pump command must be one non-empty line")
        payload = line.encode("ascii")
        with self._wire_lock:
            self.native.input = payload
            self.native.Write()

    def _read_reply(self) -> str:
        """Read the reply bytes with a bounded wait, as readSerial.Read does while bytes are waiting."""
        port = self.native.ser
        deadline = time.monotonic() + float(self.options.get("read_timeout_s", type(self).read_timeout_s))
        chunks = []
        while time.monotonic() < deadline:
            chunk = port.readline()
            if chunk:
                chunks.append(chunk)
                if chunk.endswith(b"\n"):
                    break
            else:
                time.sleep(0.01)
        return b"".join(chunks).decode("ascii", "replace").strip()

    def setup(self):
        """Put the pump in the independent condition that the channel commands require (InfuseCode.py:5)."""
        self._send("condition Independent")

    def teardown(self):
        """Close the serial port the hardware factory opened (the fake's port has the same close method)."""
        port = self.native.ser
        close = getattr(port, "close", None)
        if callable(close):
            close()

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("status", type="string", description="Raw text the pump returns to the status command")
    def status(self):
        self._send("status")
        return self._read_reply()

    @read("running", type="boolean", description="True after a run command until this driver sends stop")
    def running(self):
        return self._running is not None

    # -- writes ---------------------------------------------------------------------------------------------------
    @write("syringe_volume", unit="uL",
           description="Syringe volume set for both channels with 'svolume ab {value} ul'",
           limit=Limit.operator_required(
               "no text file of the clone states a syringe volume range; the installed syringe sets it. The site "
               "supplies the accepted range in the operator overlay."))
    def set_syringe_volume(self, value):
        self._send(f"svolume ab {float(value):g} ul")

    @write("diameter", unit="mm",
           description="Syringe diameter set for both channels with 'diameter ab {value}' (the tutorial's unit is mm)",
           limit=Limit.operator_required(
               "no text file of the clone states a syringe diameter range; the installed syringe sets it. The site "
               "supplies the accepted range in the operator overlay."))
    def set_diameter(self, value):
        self._send(f"diameter ab {float(value):g}")

    @write("target_time", unit="s",
           description="Target time set for both channels with 'ttime ab {value} sec'",
           limit=Limit.operator_required(
               "no text file of the clone states a target-time range; the process sets it. The site supplies the "
               "accepted range in the operator overlay."))
    def set_target_time(self, value):
        self._send(f"ttime ab {float(value):g} sec")

    @write("target_volume", unit="uL",
           description="Target volume set for both channels with 'tvolume ab {value} ul'",
           limit=Limit.operator_required(
               "no text file of the clone states a target-volume range; the installed syringe and the process set "
               "it. The site supplies the accepted range in the operator overlay."))
    def set_target_volume(self, value):
        self._send(f"tvolume ab {float(value):g} ul")

    @write("flow_rate", unit="mL/min",
           description="Infusion rate set for both channels with 'irate ab {value} ml/min'",
           limit=Limit.operator_required(
               "no text file of the clone states an infusion-rate range; the installed syringe, motor and tubing "
               "set it. The site supplies the accepted range in the operator overlay."))
    def set_flow_rate(self, value):
        self._send(f"irate ab {float(value):g} ml/min")

    # -- actions --------------------------------------------------------------------------------------------------
    @action(name="x-cap.phamdangnguyen.syringe.v1",
            description="Select the syringe for both channels with 'syr {channel} {code} {index}'",
            input={"channel": Field("string", description="Channel(s) the syringe list applies to",
                                    enum=["a", "b", "ab"]),
                   "code": Field("string", description="Manufacturer code of the syringe in the pump's list",
                                 max_length=32, pattern=r"^[A-Za-z0-9_.-]+$"),
                   "index": Field("integer", unit="1", description="Index in the manufacturer's syringe list",
                                  limit=Limit.operator_required(
                                      "no text file of the clone states a syringe index range; the pump's list "
                                      "sets it. The site supplies the accepted range in the operator overlay."))},
            output={"channel": Field("string", description="Channel(s) selected"),
                    "code": Field("string", description="Manufacturer code sent"),
                    "index": Field("integer", unit="1", description="Index sent")})
    def syringe(self, channel, code, index):
        if channel not in ("a", "b", "ab"):
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", f"unknown channel {channel!r}")
        if not code:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "the syringe code must not be empty")
        self._send(f"syr {channel} {code} {int(index):d}")
        return {"channel": channel, "code": code, "index": int(index)}

    @action(name="x-cap.phamdangnguyen.run.v1",
            description="Run the configured pump program on the selected channel(s) with 'run {channel}'",
            input={"channel": Field("string", description="Channel(s) to run", enum=["a", "b", "ab"])},
            output={"channel": Field("string", description="Channel(s) started"),
                    "running": Field("boolean", description="True once the run command was sent")})
    def run(self, channel):
        if channel not in ("a", "b", "ab"):
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", f"unknown channel {channel!r}")
        self._send(f"run {channel}")
        self._running = channel
        return {"channel": channel, "running": True}

    @action(name="x-cap.phamdangnguyen.stop.v1", safe_state=True,
            description="Stop both pump channels with 'stop ab' (the native stop and the safe state); takes no input",
            output={"stopped": Field("boolean", description="True once the stop command was sent")})
    def stop_pump(self):
        self._send("stop ab")
        self._running = None
        return {"stopped": True}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop(native="Write")
    def stop(self):
        """The native stop: the upstream writeSerial.Write sends 'stop ab' to both channels."""
        self._send("stop ab")
        self._running = None
