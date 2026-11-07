"""OpenMHS driver for gh.pcdshub/ophyd-ads: read-only TwinCAT NC axis telemetry over ADS.

DEVIATION FROM THE CARD: the card proposes the ``OphydDriver`` family helper with
``ophyd_ads.devices:NcAxis`` as the entry class.  ``NcAxis`` is a classic Ophyd
``Device``, but every one of its fields is a ``Component(AdsSignal, ...)``
(ophyd_ads/devices.py:8-18) and ``AdsSignal`` is a custom ``Signal`` subclass
(ophyd_ads/signal.py:32), not one of the classic ``EpicsSignal``,
``EpicsSignalRO`` or plain ``Signal`` declarations the Ophyd source proof accepts.
The helper therefore cannot bind this device without inventing a declaration the
clone does not have.  This package is a direct ``Driver`` over ``NcAxis``, with a
``native.py`` factory that builds the upstream Device from the deployment's ADS
address prefix.

The package is deliberately read-only: it exposes the eleven axis telemetry
channels named by the card (``act_acc`` through ``drive_output``) and one
``cap.sensing.read.v1`` action.  It does not bind the ``set_*`` Components, does
not call ``AdsSignal.put`` and does not write to the PLC.  Commanding a TwinCAT
NC axis through ``AdsSignal.put`` (ophyd_ads/signal.py:80-83) would be a physical
motion command, and neither the clone nor this package supplies a native axis
stop or a sourced position/velocity bound; a read-only integration is the only
scope this package can support without inventing that safety evidence.  The
upstream ``Plc.stop`` only stops the Python client's queue thread and closes the
ADS connection (ophyd_ads/ads.py:298-300, 324-333); it is not a claim that the
axis stopped.

Every read calls ``AdsSignal.get`` (ophyd_ads/signal.py:72-78), which reads the
symbol over ADS through ``Symbol.read`` (ophyd_ads/ads.py:206-210).  The source
states no engineering unit for any axis channel, so no field carries a unit.
The package is model-authored and unreviewed (``reviewed_by`` is null); it has
run on the fake backend only and has never connected to a PLC.
"""

from mhs.driver import Driver, Fact, Field, action, read

#: The telemetry channels of ``NcAxis`` this package serves, in the order of the driver.
CHANNELS = (
    "act_acc",
    "act_pos",
    "act_pos_modulo",
    "act_torque",
    "act_velo",
    "axis_state",
    "cmd_no",
    "control_d_word",
    "couple_state",
    "ctrl_output",
    "drive_output",
)

#: The driver method that reads each channel.
READERS = {name: "read_" + name for name in CHANNELS}


class NcAxisTelemetry(Driver):
    device_id = "ophyd-ads-nc-axis"
    device_kind = "sensor"
    mode = "hardware"
    risk = "R0"
    native = "ophyd_ads.devices:NcAxis"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeNcAxis"}
    vendor = "Beckhoff"
    model = "TwinCAT NC axis through ophyd-ads"
    display_name = "TwinCAT NC axis telemetry (ophyd-ads, read only)"
    tags = ["ophyd", "ads", "beckhoff", "twincat", "nc-axis", "telemetry", "read-only"]
    safe_state = ("unchanged: the package only reads axis symbols over ADS and never writes a setpoint; an e-stop "
                  "engages the endpoint's software latch and stops nothing physical")

    facts = [
        Fact("NcAxis is an ophyd Device whose fields are Component(AdsSignal, ...) declarations",
             source="upstream_code", ref="ophyd_ads/devices.py:7-18"),
        Fact("The README describes ophyd-ads as ophyd integration with Beckhoff TwinCAT 3 via pyads",
             source="vendor_doc", ref="README.rst:12"),
        Fact("act_acc, act_pos, act_pos_modulo, act_torque, act_velo, axis_state, cmd_no, control_d_word, "
             "couple_state, ctrl_output and drive_output are Component(AdsSignal, ...) declarations of NcAxis",
             source="upstream_code", ref="ophyd_ads/devices.py:8-18"),
        Fact("set_acc, set_pos, set_pos_modulo, set_torque and set_velo are also Component(AdsSignal, ...) "
             "declarations of NcAxis; this read-only package does not bind them", source="upstream_code",
             ref="ophyd_ads/devices.py:25-29"),
        Fact("AdsSignal is a Signal subclass", source="upstream_code", ref="ophyd_ads/signal.py:32"),
        Fact("AdsSignal.get reads the Symbol value over ADS and updates the Signal value and timestamp",
             source="upstream_code", ref="ophyd_ads/signal.py:72-78"),
        Fact("AdsSignal.put writes the value through the Symbol over ADS", source="upstream_code",
             ref="ophyd_ads/signal.py:80-83"),
        Fact("AdsSignal parses an ADS address from read_pv and requires an IP address", source="upstream_code",
             ref="ophyd_ads/signal.py:40-60"),
        Fact("AdsSignal obtains its Symbol from Plc.get_symbol with the _SignalSymbol class", source="upstream_code",
             ref="ophyd_ads/signal.py:62-64"),
        Fact("Symbol.read reads the symbol by name with the ADS data type", source="upstream_code",
             ref="ophyd_ads/ads.py:206-210"),
        Fact("Plc.get_symbol caches a Symbol by symbol name, poll rate and class, and opens the ADS connection "
             "when it is closed", source="upstream_code", ref="ophyd_ads/ads.py:340-348"),
        Fact("Plc.stop sets running to False and queues a no-op", source="upstream_code",
             ref="ophyd_ads/ads.py:298-300"),
        Fact("The Plc connection thread loops while running and closes the ADS connection when it exits",
             source="upstream_code", ref="ophyd_ads/ads.py:324-333"),
        Fact("Plc.stop_polling removes a registered poll call from the poll thread", source="upstream_code",
             ref="ophyd_ads/ads.py:282-287"),
    ]

    # -- the eleven telemetry channels the card names ----------------------------------------------------------
    @read("act_acc", type="number",
          description="ActAcc symbol read over ADS; the clone states no unit or meaning")
    def read_act_acc(self):
        return self.native.act_acc.get()

    @read("act_pos", type="number",
          description="ActPos symbol read over ADS; the clone states no unit or meaning")
    def read_act_pos(self):
        return self.native.act_pos.get()

    @read("act_pos_modulo", type="number",
          description="ActPosModulo symbol read over ADS; the clone states no unit or meaning")
    def read_act_pos_modulo(self):
        return self.native.act_pos_modulo.get()

    @read("act_torque", type="number",
          description="ActTorque symbol read over ADS; the clone states no unit or meaning")
    def read_act_torque(self):
        return self.native.act_torque.get()

    @read("act_velo", type="number",
          description="ActVelo symbol read over ADS; the clone states no unit or meaning")
    def read_act_velo(self):
        return self.native.act_velo.get()

    @read("axis_state", type="number",
          description="AxisState symbol read over ADS; the clone states no unit or meaning")
    def read_axis_state(self):
        return self.native.axis_state.get()

    @read("cmd_no", type="number",
          description="CmdNo symbol read over ADS; the clone states no unit or meaning")
    def read_cmd_no(self):
        return self.native.cmd_no.get()

    @read("control_d_word", type="number",
          description="ControlDWord symbol read over ADS; the clone states no unit or meaning")
    def read_control_d_word(self):
        return self.native.control_d_word.get()

    @read("couple_state", type="number",
          description="CoupleState symbol read over ADS; the clone states no unit or meaning")
    def read_couple_state(self):
        return self.native.couple_state.get()

    @read("ctrl_output", type="number",
          description="CtrlOutput symbol read over ADS; the clone states no unit or meaning")
    def read_ctrl_output(self):
        return self.native.ctrl_output.get()

    @read("drive_output", type="number",
          description="DriveOutput symbol read over ADS; the clone states no unit or meaning")
    def read_drive_output(self):
        return self.native.drive_output.get()

    # -- the capability ----------------------------------------------------------------------------------------
    @action(cap="cap.sensing.read.v1",
            description="Read the TwinCAT NC axis telemetry channels over ADS; the optional fields input selects "
                        "a subset. Every selected channel is a fresh Symbol.read, not a monitor cache. A name outside "
                        "the eleven channels contributes no value; the driver never invents a reading",
            input={"fields": Field(
                "array", items="string",
                description="Channel names to return: " + ", ".join(CHANNELS) +
                            ". Omit the input to return every channel; other names contribute no value")})
    def read_channels(self, fields=None):
        if fields is None:
            wanted = list(CHANNELS)
        else:
            wanted = [name for name in (str(value) for value in fields) if name in CHANNELS]
        values = {name: getattr(self, READERS[name])() for name in wanted}
        return {"values": values}
