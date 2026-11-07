"""OpenMHS driver for gh.drkirkm/syringepump: a Harvard Apparatus OEM syringe pump over the
CR-terminated ASCII protocol of the upstream PyQt5 controller (a direct Driver).

DEVIATION FROM THE CARD: the card's family-config / SerialDriver shape was replaced by a direct Driver with a
native.py factory.  The upstream does not expose a transport object: it is a Qt main window whose button handlers
open ``COM1``, write one line and close it (``pumpcontroller.py:228-389``), and its commands are assembled from an
address, a command word and the text of a Qt line edit.  A SerialDriver command table could bind one line to one
capability, but a run is the pair "set the rate" and "RUN", and a safe state is the three lines "STP", "01STP" and
"02STP"; a direct Driver keeps that sequence and still writes exactly the bytes of the clone.

* reads: the flow rate, the syringe diameter and the running flag this driver last commanded.  The upstream never
  reads a reply from the pump (``pumpcontroller.py:232-235``), so these are commanded state, not measurements.
* writes: the flow rate in mL/h (``MLH``) and the syringe diameter in mm (``MMD``), for pump address 00, 01 or 02.
* actions: run the configured pump (``RUN`` / ``01RUN`` / ``02RUN``) and stop all three addresses (``STP``,
  ``01STP``, ``02STP``).  The stop action is the declared safe state; the native e-stop stops the configured
  address.  The pump dispenses liquid, so the driver is R2 even though the card's floor is R0.

No text file of the clone states a flow-rate or diameter range.  Both numeric writes are
``Limit.operator_required``: the operator supplies the installed syringe, motor and tubing envelope in the site
overlay, and without one every write is refused ``MHS.SAFETY.LIMITS_UNSET``.

Every Fact cites a line of the clone at the pinned commit (6a39723535c339f24b0eeb7332c2dfe96e5a7afb).  This package
is model-authored and unreviewed: it is checked on the fake backend only, and no hardware was attached.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

#: The upstream button handlers and line edits for each pump address (pumpcontroller.py:228-389).  The unprefixed
#: handlers belong to the first pump group; the 01 and 02 groups have their own handlers and line edits.
_FLOW = {
    "00": ("lineEdit1", "sfrbuttonClicked"),
    "01": ("lineEdit4", "mlh2buttonClicked"),
    "02": ("lineEdit5", "mlh3buttonClicked"),
}
_DIAMETER = {
    "00": ("lineEdit2", "diambuttonClicked"),
    "01": ("lineEdit3", "diam2buttonClicked"),
    "02": ("lineEdit6", "diam3buttonClicked"),
}
_RUN = {"00": "runbuttonClicked", "01": "run2buttonClicked", "02": "run3buttonClicked"}
_STOP = {"00": "stopbuttonClicked", "01": "stop2buttonClicked", "02": "stop3buttonClicked"}


class SyringePump(Driver):
    device_id = "harvard-oem-syringe-pump"
    device_kind = "fluid.pump"
    mode = "hardware"
    #: A pump that dispenses liquid is R2 (MHS/spec/04-safety.md, section 2.1), above the card's R0 floor.
    risk = "R2"
    native = "pumpcontroller:Pumps"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakePumps"}
    vendor, model = "Harvard Apparatus", "OEM syringe pump"
    display_name = "Harvard Apparatus OEM syringe pump"
    tags = ["syringe pump", "harvard apparatus", "serial", "infuse", "dispense"]
    #: The pump address this driver instance controls: 00 (unprefixed commands), 01 or 02.
    address = "00"
    facts = [
        Fact("The repository controls and operates Harvard Apparatus OEM model syringe pumps from a desktop program",
             source="vendor_doc", ref="README.md:4"),
        Fact("The program is set up to control up to 3 pumps, each with its own address 00, 01 or 02",
             source="vendor_doc", ref="README.md:8"),
        Fact("The program uses pyserial 3.5 and PyQt5 5.9.7, and its serial port defaults to COM1",
             source="vendor_doc", ref="README.md:5-6"),
        Fact("Pumps is a QMainWindow desktop GUI class, not a device transport",
             source="upstream_code", ref="pumpcontroller.py:15"),
        Fact("The module's only runtime entry creates a QApplication, instantiates Pumps and enters the Qt event loop",
             source="upstream_code", ref="pumpcontroller.py:412-416"),
        Fact("Every command opens the serial line at 9600 baud, 8 data bits, no parity and a 0.5 s timeout",
             source="upstream_code", ref="pumpcontroller.py:229"),
        Fact("A diameter command is the bytes 'MMD ', the entered text and a carriage return",
             source="upstream_code", ref="pumpcontroller.py:231"),
        Fact("Flow-rate commands are 'MLH ', 'ULH ' or 'ULM ' followed by the entered text and a carriage return",
             source="upstream_code", ref="pumpcontroller.py:240-258"),
        Fact("The first pump group sends the unprefixed RUN and STP commands",
             source="upstream_code", ref="pumpcontroller.py:264-278"),
        Fact("The second pump group prefixes the same commands with 01: 01MLH, 01MMD, 01RUN and 01STP",
             source="upstream_code", ref="pumpcontroller.py:270-301"),
        Fact("The third pump group prefixes the same commands with 02: 02MLH, 02MMD, 02RUN and 02STP",
             source="upstream_code", ref="pumpcontroller.py:325-367"),
        Fact("The stop-all handler writes STP, 01STP and 02STP",
             source="upstream_code", ref="pumpcontroller.py:373-377"),
        Fact("The close handler writes STP, 01STP and 02STP to stop all pumps before exit",
             source="upstream_code", ref="pumpcontroller.py:404-407"),
        Fact("The diameter handler writes the command and closes the port without reading a reply",
             source="upstream_code", ref="pumpcontroller.py:232-235"),
        Fact("The GUI lists the diameters 4.78, 8.66, 12.06, 14.5, 19.13 and 21.7 mm for 1, 3, 5, 10, 20 and 30 mL "
             "syringes", source="upstream_code", ref="pumpcontroller.py:139"),
        Fact("The third pump's uL/min handler writes 02ULH instead of 02ULM",
             source="upstream_code", ref="pumpcontroller.py:355-358"),
    ]
    safe_state = ("all pump addresses stopped by STP, 01STP and 02STP; no pump runs until a RUN command is sent")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # The state below is the last value this driver wrote, not a device reading: the upstream never reads a
        # reply.  The zeros are the state before the first command, not a fact about the pump.
        self._flow_rate = 0.0
        self._diameter = 0.0
        self._pumping = False

    # -- helpers ---------------------------------------------------------------------------------------------------
    def _address(self) -> str:
        """The configured pump address, normalised to the two digits of the clone's prefixes."""
        address = str(self.options.get("address", type(self).address)).strip()
        if address in ("0", "1", "2"):
            address = address.zfill(2)
        if address not in _FLOW:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               f"pump address {address!r} is not one of 00, 01 or 02")
        return address

    # -- reads -----------------------------------------------------------------------------------------------------
    @read("flow_rate", unit="mL/h",
          description="Flow rate last commanded by this driver; the pump reply is never read")
    def flow_rate(self):
        return self._flow_rate

    @read("diameter", unit="mm",
          description="Syringe diameter last commanded by this driver; the pump reply is never read")
    def diameter(self):
        return self._diameter

    @read("pumping", type="boolean",
          description="True after this driver sent a RUN command and until it sends a stop command")
    def pumping(self):
        return self._pumping

    # -- writes ----------------------------------------------------------------------------------------------------
    @write("flow_rate", unit="mL/h",
           description="Flow rate set with MLH for the configured address (lineEdit text plus CR)",
           limit=Limit.operator_required(
               "no text file of the clone states a flow-rate range; the installed syringe, motor and tubing set it. "
               "The site supplies the accepted range in the operator overlay."))
    def set_flow_rate(self, value):
        line_edit, handler = _FLOW[self._address()]
        getattr(self.native, line_edit).setText(f"{float(value):.10g}")
        getattr(self.native, handler)()
        self._flow_rate = float(value)

    @write("diameter", unit="mm",
           description="Syringe diameter set with MMD for the configured address (lineEdit text plus CR)",
           limit=Limit.operator_required(
               "no text file of the clone states a diameter range; the installed syringe sets it. The site supplies "
               "the accepted range in the operator overlay."))
    def set_diameter(self, value):
        line_edit, handler = _DIAMETER[self._address()]
        getattr(self.native, line_edit).setText(f"{float(value):.10g}")
        getattr(self.native, handler)()
        self._diameter = float(value)

    # -- actions ---------------------------------------------------------------------------------------------------
    @action(name="x-cap.drkirkm.run.v1",
            description="Start the configured pump address at the flow rate it was configured with",
            output={"running": Field("boolean", description="True once the RUN command was sent")})
    def run_pump(self):
        getattr(self.native, _RUN[self._address()])()
        self._pumping = True
        return {"running": True}

    @action(name="x-cap.drkirkm.stop.v1", safe_state=True,
            description="Stop all three pump addresses with the STP, 01STP and 02STP commands",
            output={"stopped": Field("boolean", description="True once the stop commands were sent")})
    def stop_all(self):
        self.native.stopallbuttonClicked()
        self._pumping = False
        return {"stopped": True}

    # -- safety ----------------------------------------------------------------------------------------------------
    @estop(native="stopbuttonClicked / stop2buttonClicked / stop3buttonClicked")
    def stop(self):
        """Stop the configured pump address through the upstream stop handler."""
        getattr(self.native, _STOP[self._address()])()
        self._pumping = False
