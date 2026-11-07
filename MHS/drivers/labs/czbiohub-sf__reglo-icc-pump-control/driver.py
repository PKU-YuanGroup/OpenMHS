"""OpenMHS driver for gh.czbiohub-sf/reglo-icc-pump-control: an Ismatec Reglo ICC peristaltic pump over serial.

A direct Driver (decorated methods) over the upstream class reglo_icc_pump._driver:RegloIccPump.  The card's
family-config helper (SerialDriver) cannot express this device: the upstream assembles every command at run time
from the channel number, a command letter and the pump address (for example ``f"{ch_no}vv{self.pump_addr}``,
reglo_icc_pump/_driver.py:393-396), so this package uses a native factory instead (driver-authoring.md,
"Choosing the shape").  DEVIATION FROM THE CARD: a direct Driver with native.py; recorded in RESULT.json.

* the package drives one channel, selected with the backend option ``channel`` (default 1); the pump reports its
  channel count when it connects;
* reads: the maximum flow rate for the installed tubing, the running state, the tubing inner diameter, the channel
  count, the pump address and the identity the pump reports at initialization;
* one write: the tubing inner diameter in mm, which the pump reports back and the driver also reads;
* one pump action: move a commanded volume at a commanded flow rate; ``forward`` is the channel's configured
  dispense direction and ``reverse`` is the opposite direction;
* the native stop is the e-stop and the safe-state action.

Every Fact cites a line of the clone at the pinned commit (af0f8648a56512cad67af26068830e65754ead5e).  This package
is model-authored and unreviewed: it runs on the fake backend only (driver.lock.json).
"""

import time

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

CLONE = "reglo_icc_pump/_driver.py"


def _source(ref: str) -> str:
    return f"{CLONE}:{ref}"


class RegloIccPump(Driver):
    device_id = "reglo-icc-pump"
    device_kind = "fluid.pump"
    mode = "hardware"
    risk = "R2"
    native = "reglo_icc_pump._driver:RegloIccPump"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeRegloIccPump"}
    vendor, model = "Masterflex (Avantor)", "Ismatec Reglo ICC digital peristaltic pump"
    display_name = "Masterflex Ismatec Reglo ICC peristaltic pump"
    tags = ["peristaltic pump", "reglo icc", "ismatec", "serial", "fluid"]
    facts = [
        Fact("The package controls a Masterflex Ismatec Reglo ICC digital peristaltic pump over its USB interface; "
             "the RS-232 interface is untested", source="vendor_doc", ref="README.md:2"),
        Fact("The package needs Python >= 3.6 and pyserial >= 3.5", source="vendor_doc", ref="README.md:14-16"),
        Fact("A command is written as ASCII text followed by a carriage return", source="upstream_code",
             ref=_source("263")),
        Fact("A query response is read until CRLF (read_until(b'\\r\\n'))", source="upstream_code",
             ref=_source("290")),
        Fact("The initialization command is '{pump_addr}~1', which puts the pump in remote-control mode",
             source="upstream_code", ref=_source("95")),
        Fact("The pump reports its number of channels to '{addr}xA', its serial number to '{addr}xS' and its model, "
             "software version and head code to '{addr}#'", source="upstream_code", ref=_source("227-234")),
        Fact("get_max_flow_rate returns the maximum flow rate setting for the installed tubing in mL/minute",
             source="upstream_code", ref=_source("311-334")),
        Fact("set_tubing_id takes the tubing inner diameter in mm and sends it as hundredths of a millimetre in a "
             "four-digit field", source="upstream_code", ref=_source("353")),
        Fact("set_tubing_id stores the value the pump reports back in tubing_ids for that channel",
             source="upstream_code", ref=_source("357-359")),
        Fact("The tubing inner diameter must match one of the values listed in the pump documentation",
             source="upstream_code", ref=_source("341-342")),
        Fact("pump_vol takes the volume in mL and the rate in mL/minute; the direction is a PumpDirection (CW or CCW)",
             source="upstream_code", ref=_source("362-368")),
        Fact("dispense_vol uses the channel's configured dispense direction and aspirate_vol uses the opposite "
             "direction", source="upstream_code", ref=_source("429-451")),
        Fact("The default dispense direction is CW", source="upstream_code", ref=_source("33")),
        Fact("PumpDirection is the pump rotor rotation direction as viewed from the front: CW or CCW",
             source="upstream_code", ref="reglo_icc_pump/types.py:70-76"),
        Fact("stop(ch_no) immediately stops the specified channel, and stop(None) stops every channel",
             source="upstream_code", ref=_source("454-468")),
        Fact("is_running returns True while the channel is pumping and False when it is not", source="upstream_code",
             ref=_source("476-477")),
        Fact("The driver stops a channel and raises StallDetectionDetected when is_running reports the channel "
             "running but its odometer has not counted up for 2 seconds", source="upstream_code",
             ref=_source("486-494")),
        Fact("Volumes and rates are encoded with four significant digits in type-2 format "
             "('{mantissa}{exponent:+d}')", source="upstream_code", ref=_source("554-559")),
    ]
    safe_state = "all pump channels stopped (the native remote stop command)"

    @property
    def channel(self) -> int:
        """The one channel this package drives; the backend option ``channel`` selects it."""
        return int(self.options.get("channel", 1))

    # -- reads ------------------------------------------------------------------------------------------------
    @read("max_flow_rate", unit="mL/min",
          description="Maximum flow rate setting reported by the pump for the installed tubing")
    def max_flow_rate(self):
        return self.native.get_max_flow_rate(self.channel)

    @read("running", type="boolean", description="True while the driven channel is pumping")
    def running(self):
        return self.native.is_running(self.channel)

    @read("channel_count", type="integer", description="Number of channels the pump reported when it connected")
    def channel_count(self):
        return len(self.native.channel_nos)

    @read("pump_address", type="integer", description="Address of this pump on the serial line")
    def pump_address(self):
        return self.native.pump_addr

    @read("serial_number", type="string", description="Serial number reported by the pump")
    def serial_number(self):
        return self.native.serial_no

    @read("model_number", type="string", description="Model number reported by the pump")
    def model_number(self):
        return self.native.model_no

    @read("software_version", type="string", description="Software version reported by the pump")
    def software_version(self):
        return self.native.sw_ver

    @read("head_code", type="string", description="Pump head code reported by the pump")
    def head_code(self):
        return self.native.head_code

    @read("tubing_id", unit="mm",
          description="Inner diameter stored for the driven channel; the field is absent until tubing is configured")
    def tubing_id(self):
        return self.native.tubing_ids.get(self.channel)

    # -- the one write ----------------------------------------------------------------------------------------
    @write("tubing_id", unit="mm", description="Inner diameter of the tubing installed on the driven channel",
           limit=Limit.operator_required(
               "the tubing inner diameter must match a value listed in the pump documentation, and no text file "
               "of the clone lists those values; the site supplies the installed tubing ID"))
    def set_tubing_id(self, value):
        return self.native.set_tubing_id(self.channel, value)

    # -- the pump action --------------------------------------------------------------------------------------
    @action(
        cap="cap.actuation.pump.v1",
        description="Move a commanded volume at a commanded flow rate; forward is the configured dispense "
                    "direction and reverse is the opposite direction",
        long_running=True,
        max_duration_ms=3600000,
        cancellable=True,
        input={
            "flow_rate": Field(
                "number", unit="uL/s", description="Flow rate; the pump checks it against the installed tubing",
                limit=Limit.operator_required(
                    "the maximum flow rate is the value the pump reports for the installed tubing "
                    "(get_max_flow_rate); no text file of the clone states a static bound, so the site supplies "
                    "the flow-rate envelope")),
            "direction": Field(
                "string",
                description="forward moves in the channel's configured dispense direction; reverse moves opposite"),
            "volume": Field(
                "number", unit="uL", description="Volume to move; the pump checks it against its volume range",
                limit=Limit.operator_required(
                    "the pump checks the requested volume and reports a limit in its error reply, but no text file "
                    "of the clone states a volume range; the site supplies the volume envelope")),
        },
    )
    def pump(self, flow_rate, direction, volume=None):
        if volume is None:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "volume is required: the pump is driven by volume, not by duration")
        if direction not in ("forward", "reverse"):
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", f"unknown pump direction {direction!r}")
        rate_ml_min = float(flow_rate) * 60.0 / 1000.0       # uL/s -> mL/min
        volume_ml = float(volume) / 1000.0                   # uL -> mL
        if direction == "forward":
            self.native.dispense_vol(self.channel, volume_ml, rate_ml_min, blocking=False)
        else:
            self.native.aspirate_vol(self.channel, volume_ml, rate_ml_min, blocking=False)
        while self.native.is_running(self.channel):
            self.check_cancelled()
            time.sleep(0.05)
        return {"dispensed_volume": float(volume)}

    # -- safe state and e-stop --------------------------------------------------------------------------------
    @action(name="x-cap.czbiohub-sf.stop_pump.v1", safe_state=True,
            description="Stop every channel of the pump (the native stop, the safe state); it takes no input",
            output={"stopped": Field("boolean", description="True once the stop command completed")})
    def stop_pump(self):
        self.native.stop()
        return {"stopped": True}

    @estop
    def stop(self):
        """The native stop: the runtime latches first, then stops every channel."""
        self.native.stop()

    def teardown(self):
        self.native.ser_port.close()
