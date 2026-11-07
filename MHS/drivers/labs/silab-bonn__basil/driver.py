"""OpenMHS driver for gh.silab-bonn/basil: an ISEG high-voltage power supply over RS-232 (a direct driver).

The clone's hardware layer ``basil.HL.iseg_hv:IsegHV`` speaks the ISEG ASCII protocol: one command letter, the
channel number and, for a setting, ``=<value>`` (``U1``, ``D1=100``, ``V1=5``, ``W=1``); the device echoes the
command and sends the answer after it.  The upstream assembles those lines from parts at run time
(``_get_set_property`` fills the ``{channel}`` and ``{value}`` of a CMDS template), so a command table cannot
reproduce them (gate G7).  This is therefore a direct ``Driver`` over the upstream class, with ``native.py``
opening the serial transport for the hardware backend.

* reads: the actual output voltage and output current, the target voltage, the ramp speed, the answer delay,
  the autostart flag and the selected channel;
* writes: the target voltage, the ramp speed, the answer delay, the autostart flag and the channel;
* the e-stop calls the upstream ``off()``, which sets the target voltage to 0 V.

The largest voltage and the number of channels are properties of the configured module, not constants of the
clone: the device returns ``V_MAX`` in its identifier at run time and the channel count comes from the init
configuration, so those two bounds are ``Limit.operator_required`` and ``site-limits.example.json`` shows the
operator overlay that fills them.  This package is model-authored and unreviewed; nothing here ran on hardware.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write

MODULE = "basil/HL/iseg_hv.py"


class IsegHVSupply(Driver):
    device_id = "iseg-hv"
    device_kind = "instrument.smu"
    mode = "hardware"
    #: R3, above the card's floor: a high-voltage supply is R3 (MHS/spec/04-safety.md).  The model review raised it; the hardware backend
    #: of this model-written package stays refused until a human signs reviewed_by.
    risk = "R3"
    native = "basil.HL.iseg_hv:IsegHV"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeIsegHV"}
    vendor = "iseg"
    model = "SHQ/NQH series high-voltage supply"
    display_name = "ISEG SHQ/NQH series high-voltage supply"
    tags = ["high voltage", "power supply", "iseg", "rs-232", "hv"]
    facts = [
        Fact("The class is an RS-232 interface for ISEG high-voltage power supplies of the SHQ and NQH series",
             source="upstream_code", ref=f"{MODULE}:17"),
        Fact("The CMDS table gives every command as one letter plus the channel and, for a setting, '=<value>'",
             source="upstream_code", ref=f"{MODULE}:23-46"),
        Fact("A query echoes the command first and the answer follows on the next read; a different echo raises",
             source="upstream_code", ref=f"{MODULE}:444-451"),
        Fact("The device reports '????' (syntax error), '?WCN' (wrong channel) and '?TOT' (timeout); the reader "
             "raises RuntimeError on them", source="upstream_code", ref=f"{MODULE}:57-61"),
        Fact("get_voltage and get_current return the actual output voltage in V and current in A of the channel",
             source="upstream_code", ref=f"{MODULE}:118-138"),
        Fact("get_source_voltage returns the target voltage in V and set_voltage sends the absolute value",
             source="upstream_code", ref=f"{MODULE}:166-178"),
        Fact("set_voltage refuses a magnitude above the hardware voltage limit, which is a percentage of V_MAX",
             source="upstream_code", ref=f"{MODULE}:140-143"),
        Fact("The module identifier is 'UNIT_NUMBER;SOFTWARE_REL;V_MAX;I_MAX' and V_MAX is its third field",
             source="upstream_code", ref=f"{MODULE}:253-262"),
        Fact("V_MAX is returned by the module identifier, not held as a constant of the clone",
             source="upstream_code", ref=f"{MODULE}:486-487"),
        Fact("The ramp speed is 1 up to and including 255 V/s", source="upstream_code", ref=f"{MODULE}:267"),
        Fact("The answer delay is 1 up to and including 255 ms", source="upstream_code", ref=f"{MODULE}:284"),
        Fact("get_autostart is True when the device answers '008' and set_autostart sends 8 for True and 0 for "
             "False", source="upstream_code", ref=f"{MODULE}:298-313"),
        Fact("The channel must satisfy 1 <= channel <= n_channel, and n_channel comes from the init configuration",
             source="upstream_code", ref=f"{MODULE}:248-251"),
        Fact("off() sets the output voltage to 0 V", source="upstream_code", ref=f"{MODULE}:459-460"),
    ]
    safe_state = "the target voltage of the channel is set to 0 V (the upstream off() calls set_voltage(0))"

    @read("voltage", unit="V", description="Actual output voltage of the selected channel (U<channel>)")
    def voltage(self):
        return self.native.get_voltage()

    @read("current", unit="A", description="Actual output current of the selected channel (I<channel>)")
    def current(self):
        return self.native.get_current()

    @read("voltage_target", unit="V", description="Target voltage of the selected channel (D<channel>)")
    def voltage_target(self):
        return self.native.get_source_voltage()

    @write("voltage_target", unit="V",
           description="Set the target voltage of the selected channel (D<channel>=<value>)",
           limit=Limit.operator_required(
               "The maximum output voltage is the module's V_MAX, which the device returns in its identifier at "
               "run time (basil/HL/iseg_hv.py:486-487); no text in the clone states a fixed value for this module, "
               "so the operator supplies the site bound (site-limits.example.json shows the entry)"))
    def set_voltage_target(self, value):
        self.native.set_voltage(value)

    @read("ramp_speed", type="integer", unit="V/s",
          description="Ramp speed of the output voltage (V<channel>)")
    def ramp_speed(self):
        return self.native.get_ramp_speed()

    @write("ramp_speed", type="integer", unit="V/s",
           description="Set the ramp speed of the output voltage (V<channel>=<value>)",
           limit=Limit(min=1, max=255, source="upstream_code", ref=f"{MODULE}:277"))
    def set_ramp_speed(self, value):
        self.native.set_ramp_speed(value)

    @read("answer_delay", type="integer", unit="ms",
          description="Delay between two answer characters of the serial protocol (W)")
    def answer_delay(self):
        return self.native.get_answer_delay()

    @write("answer_delay", type="integer", unit="ms",
           description="Set the delay between two answer characters (W=<value>)",
           limit=Limit(min=1, max=255, source="upstream_code", ref=f"{MODULE}:294"))
    def set_answer_delay(self, value):
        self.native.set_answer_delay(value)

    @read("autostart", type="boolean",
          description="Whether a new target voltage starts the ramp automatically (A<channel>)")
    def autostart(self):
        return self.native.get_autostart()

    @write("autostart", type="boolean",
           description="Enable the automatic ramp after setting a target voltage (A<channel>=<value>)")
    def set_autostart(self, value):
        self.native.set_autostart(value)

    @read("channel", type="integer", unit="1",
          description="Selected output channel that every command addresses")
    def channel(self):
        return self.native.get_current_channel()

    @write("channel", type="integer", unit="1",
           description="Select the output channel that every command addresses",
           limit=Limit.operator_required(
               "The channel count is the module's n_channel init setting (basil/HL/iseg_hv.py:83) and the check at "
               "line 249 bounds the channel to 1 <= channel <= n_channel; the clone states no value for this "
               "module, so the operator supplies the bound (site-limits.example.json shows the entry)"))
    def set_channel(self, value):
        self.native.set_current_channel(value)

    @action(name="x-cap.silab-bonn.output_off.v1", safe_state=True,
            description="Set the channel's target voltage to 0 V (the upstream off()), the safe state of the supply",
            output={"voltage_target": Field("number", unit="V", description="Target voltage of the channel after the call")})
    def output_off(self):
        # The same native call as the e-stop: the R3 independent stop of a model review (an e-stop runs it too).
        self.native.off()
        return {"voltage_target": float(self.native.get_source_voltage())}

    @estop(native="off")
    def stop(self):
        self.native.off()
