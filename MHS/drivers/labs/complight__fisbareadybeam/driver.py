"""OpenMHS driver for gh.complight/fisbareadybeam: the Fisba ReadyBeam multicolor laser module.

A direct Driver over the upstream device class ``FisbaReadyBeam:FisbaReadyBeam``.  The card proposes a SerialDriver
(family ``serial``, decision ``family-config``); the wire protocol is framed, not a line of text: every command is
'#' + address + sequence + '?VR'/'VS' + parameter id + instance + parameter + CRC16-XMODEM + CR
(FisbaReadyBeam/__init__.py:160-193, 125-136), and the class builds each frame at run time and reads a frame back.
A SerialDriver command table cannot reproduce those bytes (driver-authoring.md, "Choosing the shape"), so this
package is a direct Driver (DEVIATION FROM THE CARD, recorded in RESULT.json).

* reads: the device status (parameter 104) and the device type (parameter 100, returned as the raw response frame);
* one write: the brightness of the three channels at once, the argument the upstream ``set_brightness`` takes — a
  list of three powers in percent (red, green, blue; FisbaReadyBeam/__init__.py:196-217);
* the e-stop sets all three channels to 0 percent, which switches every channel off: the class sends the channel
  switch (parameter 7006) off whenever a power is not > 0 (FisbaReadyBeam/__init__.py:209-213).

Every Limit and Fact cites a line of the clone at the pinned commit (65b73a79aa1fe3eb10c809246a40e44449780492).  This
package is model-authored and unreviewed: it is checked on the fake backend only and never ran on hardware.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write

SOURCE = "FisbaReadyBeam/__init__.py"
#: The three channel instances of the module: red 1, green 2, blue 3 (FisbaReadyBeam/__init__.py:171).
CHANNELS = 3
#: The powers the upstream set_brightness writes, in the order red, green, blue (FisbaReadyBeam/__init__.py:209-217).
CHANNEL_NAMES = ["red", "green", "blue"]


class FisbaReadyBeam(Driver):
    device_id = "fisba-readybeam"
    device_kind = "light.source"
    mode = "hardware"
    #: R2, above the card's floor: a laser module above class 1 is R2 (MHS/spec/04-safety.md), and a class 3B or 4 module is R3.  The model review raised it; the hardware backend
    #: of this model-written package stays refused until a human signs reviewed_by.
    risk = "R2"
    native = "FisbaReadyBeam:FisbaReadyBeam"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeFisbaReadyBeam"}
    vendor = "Fisba"
    model = "ReadyBeam multicolor laser module (RGB-1171)"
    display_name = "Fisba ReadyBeam multicolor laser module"
    tags = ["laser", "light source", "multicolor", "rgb", "serial", "mecom", "fisba", "readybeam"]
    facts = [
        Fact("A command is framed as '#' + address + sequence + '?VR' (query) or 'VS' (set) + parameter id + "
             "instance + parameter; the parameter is eight hex digits (an IEEE-754 float or an integer)",
             source="upstream_code", ref=f"{SOURCE}:160-193"),
        Fact("The frame carries the address, a sequence number modulo 0x10000 and a CRC16 XMODEM checksum over the "
             "text, and ends with CR", source="upstream_code", ref=f"{SOURCE}:125-136"),
        Fact("The three channel instances are red 1, green 2 and blue 3",
             source="upstream_code", ref=f"{SOURCE}:171"),
        Fact("set_brightness takes a list of powers in percent, one per channel, and sends for each channel a "
             "channel-switch command (parameter 7006) and a power command (parameter 7013)",
             source="upstream_code", ref=f"{SOURCE}:209-217"),
        Fact("A channel is switched on when its power is greater than 0 and off otherwise",
             source="upstream_code", ref=f"{SOURCE}:210-213"),
        Fact("Laser powers are set in percentage using floating numbers and the maximum percentage is 100.5",
             source="upstream_code", ref=f"{SOURCE}:203"),
        Fact("The device status is read from parameter 104 and the class lists Init, Ready, Run, Error, Bootloader "
             "and Pending Reset", source="upstream_code", ref=f"{SOURCE}:22-29"),
        Fact("The device type is read from parameter 100 and should answer 1171, which means RGB-1171",
             source="upstream_code", ref=f"{SOURCE}:248-253"),
        Fact("open() enables digital control by setting parameter 7000 to 1; close() disables it with 7000 set to 0 "
             "and closes the port", source="upstream_code", ref=f"{SOURCE}:60-87"),
        Fact("The device error codes 1 to 9 are Command not available, Device is busy, General communication error, "
             "Format error, Parameter not available, Parameter is read-only, Value is out of range, Instance is "
             "not available, and Parameter general error", source="upstream_code", ref=f"{SOURCE}:11-21"),
        Fact("The library controls Fisba ReadyBeam laser light sources and was only tested on Ubuntu 22.04",
             source="vendor_doc", ref="README.md:2-4"),
    ]
    safe_state = "all three laser channels at 0 percent (channel switch off)"

    # -- reads ------------------------------------------------------------------------------------------------
    @read("device_status", type="integer",
          description="Device status code: 0 Init, 1 Ready, 2 Run, 3 Error, 4 Bootloader, 5 Pending Reset")
    def device_status(self):
        return self.native.get_device_status()

    @read("device_type", type="string",
          description="Raw response frame of parameter 100 (device type); the module should answer 1171 (RGB-1171)")
    def device_type(self):
        return self.native.get_device_type()

    # -- the write --------------------------------------------------------------------------------------------
    @write("brightness", type="array", items="number", length=CHANNELS, unit="%",
           description="Laser power of the red, green and blue channel in percent, as one list of three numbers",
           limit=Limit(min=0, max=100.5, source="upstream_code", ref=f"{SOURCE}:203-213",
                       reason="the set_brightness docstring states a maximum percentage of 100.5 (line 203) and the "
                              "code switches a channel off when its power is not > 0 (lines 210-213), so 0 is the "
                              "lower end; the class itself does not validate the value"))
    def set_brightness(self, value):
        powers = [float(item) for item in value]
        self.native.set_brightness(powers)
        return powers

    def teardown(self):
        """Close the module the way the upstream class does: disable digital control and close the port."""
        self.native.close()

    # -- safety -----------------------------------------------------------------------------------------------
    @action(name="x-cap.complight.lasers_off.v1", safe_state=True,
            description="Switch every laser channel off (all three at 0 percent), the safe state of the module",
            output={"lasers_off": Field("boolean", description="True once the zero brightness was sent to every channel")})
    def lasers_off(self):
        # The same native call as the e-stop: the R2 independent stop of a model review (an e-stop runs it too).
        self.native.set_brightness([0.0] * CHANNELS)
        return {"lasers_off": True}

    @estop(native="set_brightness")
    def stop(self):
        """The native stop: all three channels at 0 percent, which switches every laser off."""
        self.native.set_brightness([0.0] * CHANNELS)
