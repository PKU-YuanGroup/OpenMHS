"""OpenMHS driver for gh.laristizabal1/pv-emulator: the EA-PS 10060-170 source of the PV emulator.

The upstream exposes a Python object, ``comm.bridge:EAPowerSupply`` (comm/bridge.py:132), whose methods issue the
SCPI commands and keep the last voltage and current setpoints in a local cache (comm/bridge.py:141-142,
comm/bridge.py:299-305).  A ScpiDriver command table would bypass that object and its cache, so this package is a
direct Driver over the upstream class with a native factory (driver-authoring.md, "Choosing the shape").
DEVIATION FROM THE CARD: the family-config ScpiDriver helper is replaced by a direct Driver; recorded in RESULT.json.

* reads: the measured voltage, current and power (MEAS queries, comm/bridge.py:214-240), the cached voltage and
  current setpoints (comm/bridge.py:299-305), the output state (OUTP:STAT?, comm/bridge.py:257-262) and the SCPI
  error code (SYST:ERR?, comm/bridge.py:267-271);
* writes: the voltage setpoint (VOLT, comm/bridge.py:280-283), the current setpoint (CURR, comm/bridge.py:285-288)
  and the output relay (OUTP ON/OFF, comm/bridge.py:276-278);
* the e-stop writes OUTP OFF through the native ``output`` call; the safe-state action is the same output-off
  command and is the independent stop required at R2.

The source is rated 0-60 V, 0-170 A and 5 kW (README.md:4).  The driver is rated R2 because the output is a high
energy source (5 kW into a DUT); the safe-state action switches the output off.

Every Fact and Limit cites a line of the clone at the pinned commit
(a2339189e88c80889a86ac67bcf98b5cc9fc4447).  This package is model-authored and unreviewed: it runs on the fake
backend only until a human sets reviewed_by in driver.lock.json.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write

BRIDGE = "comm/bridge.py"
SCPI = "comm/scpi.py"
HARDWARE = "config/hardware.py"


class PvEmulator(Driver):
    device_id = "pv-emulator"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R2"
    native = "comm.bridge:EAPowerSupply"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeEAPowerSupply"}
    vendor = "EA Elektro-Automatik"
    model = "EA-PS 10060-170"
    display_name = "EA-PS 10060-170 programmable DC source (PV emulator)"
    tags = ["dc source", "power supply", "pv emulator", "scpi", "ea-ps"]
    facts = [
        Fact("The platform uses a programmable EA-PS 10060-170 source rated 0-60 V, 0-170 A and 5 kW",
             source="vendor_doc", ref="README.md:4"),
        Fact("The source connects over USB as a virtual COM port and SCPIController sends SCPI ASCII commands",
             source="vendor_doc", ref="docs/hardware.md:5-6"),
        Fact("The electrical limits come from the EA-PS 10000 3U manual, document 06230820_EN",
             source="upstream_code", ref=f"{HARDWARE}:26-27"),
        Fact("V_MAX is 60.0 V, I_MAX 170.0 A, P_MAX 5000.0 W and DT_MIN 200 ms",
             source="upstream_code", ref=f"{HARDWARE}:28-31"),
        Fact("EAPowerSupply is the low-latency SCPI driver the upstream bridge uses for the source",
             source="upstream_code", ref=f"{BRIDGE}:132-143"),
        Fact("V and I setpoints are not queried from the source; the upstream caches them when it sends commands",
             source="upstream_code", ref=f"{BRIDGE}:141-142"),
        Fact("read_meas_fast returns measured V, I and P, using MEAS:ALL? or the separate MEAS:VOLT? and MEAS:CURR? "
             "queries", source="upstream_code", ref=f"{BRIDGE}:214-240"),
        Fact("get_output_state queries OUTP:STAT? and treats the reply '1' or 'ON' as output on",
             source="upstream_code", ref=f"{BRIDGE}:257-262"),
        Fact("get_error_code queries SYST:ERR? and reads the first field as an integer",
             source="upstream_code", ref=f"{BRIDGE}:267-271"),
        Fact("output(on) writes OUTP ON or OUTP OFF and caches the resulting state",
             source="upstream_code", ref=f"{BRIDGE}:276-278"),
        Fact("set_voltage writes VOLT after clamping the value to 0.0 through V_MAX and caches it as cached_vset",
             source="upstream_code", ref=f"{BRIDGE}:280-283"),
        Fact("set_current_limit writes CURR after clamping the value to 0.0 through I_MAX and caches it as "
             "cached_iset", source="upstream_code", ref=f"{BRIDGE}:285-288"),
        Fact("SCPIController.stop() clears the running flag and calls output_off(), which sends OUTP OFF",
             source="upstream_code", ref=f"{SCPI}:723-725"),
        Fact("STAT:OPER:COND? bit 6 (0x0040) means the output is active and bit 9 (0x0200) means remote control "
             "is active", source="upstream_code", ref=f"{SCPI}:346-355"),
    ]
    safe_state = "DC output off (OUTP OFF)"

    # -- measured state ----------------------------------------------------------------------------------------
    @read("voltage", unit="V", description="Measured output voltage at the source terminals")
    def voltage(self):
        return float(self.native.read_meas_fast()[0])

    @read("current", unit="A", description="Measured output current at the source terminals")
    def current(self):
        return float(self.native.read_meas_fast()[1])

    @read("power", unit="W", description="Measured output power at the source terminals")
    def power(self):
        return float(self.native.read_meas_fast()[2])

    @read("voltage_setpoint", unit="V",
          description="Last voltage setpoint sent by this session, from the upstream local cache")
    def voltage_setpoint(self):
        return float(self.native.cached_vset)

    @read("current_setpoint", unit="A",
          description="Last current setpoint sent by this session, from the upstream local cache")
    def current_setpoint(self):
        return float(self.native.cached_iset)

    @read("output", type="boolean", description="True when the DC output is on (OUTP:STAT?)")
    def output(self):
        return bool(self.native.get_output_state())

    @read("error_code", type="integer", description="First field of the SCPI error queue reply (SYST:ERR?)")
    def error_code(self):
        return int(self.native.get_error_code())

    # -- controllable state ------------------------------------------------------------------------------------
    @write("voltage_setpoint", unit="V", description="Output voltage setpoint sent with the VOLT command",
           limit=Limit(min=0.0, max=60.0, source="vendor_doc", ref="README.md:4",
                       reason="the source is rated 0-60 V; set_voltage also clamps to V_MAX = 60.0 "
                              "(config/hardware.py:28)"))
    def set_voltage_setpoint(self, value):
        self.native.set_voltage(value)

    @write("current_setpoint", unit="A", description="Output current setpoint sent with the CURR command",
           limit=Limit(min=0.0, max=170.0, source="vendor_doc", ref="README.md:4",
                       reason="the source is rated 0-170 A; set_current_limit also clamps to I_MAX = 170.0 "
                              "(config/hardware.py:29)"))
    def set_current_setpoint(self, value):
        self.native.set_current_limit(value)

    @write("output", type="boolean", description="Switch the DC output on or off (OUTP ON/OFF)")
    def set_output(self, value):
        self.native.output(bool(value))

    # -- safe state --------------------------------------------------------------------------------------------
    @action(name="x-cap.laristizabal1.output_off.v1", safe_state=True,
            description="Switch the DC output off (OUTP OFF); this action is the safe state and takes no input",
            output={"off": Field("boolean", description="True once the output-off command completed")})
    def output_off(self):
        self.native.output(False)
        return {"off": True}

    @estop(native="output")
    def stop(self):
        """The native stop: switch the DC output off through the upstream ``output`` call."""
        self.native.output(False)
