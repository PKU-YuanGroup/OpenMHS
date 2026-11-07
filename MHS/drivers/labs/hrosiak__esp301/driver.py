"""OpenMHS driver for gh.hrosiak/esp301: the Newport ESP 301 stepper motion controller.

A direct Driver over the upstream serial class ``esp:esp``.  The card proposes a SerialDriver (family serial,
decision family-config), but the upstream builds every line from an axis number and a command letter at run time:
``<axis>OR;<axis>WS0`` for reset and ``<axis>PA<position>;<axis>WS1;<axis>TP`` for a move (esp.py:22-23, 36-42).
A fixed command table cannot reproduce the lines the controller receives, so this package is a direct Driver over
the upstream class with a ``native.py`` hardware factory (DEVIATION FROM THE CARD, recorded in RESULT.json).

* reads: the position of the served axis (``TP``) and the controller error number (``TE?``);
* one write: the absolute target position of the served axis (``PA``).  The clone states no travel range, so the
  limit is ``Limit.operator_required``: every write is refused ``MHS.SAFETY.LIMITS_UNSET`` until the site supplies
  the axis envelope (``site-limits.example.json`` is an example only, not a bound of any stage);
* one extension action, ``x-cap.hrosiak.reset_axis.v1``: the upstream reset of the served axis (``OR``, ``WS0``);
* the e-stop sends the same upstream reset.  The clone defines no stop, abort or halt method (esp.py:22-49), so this
  package does not claim to stop a move that is already in progress; the operator's independent hardware stop, if
  one is needed, is outside this text (facts.md and RESULT.json say so).

Every Fact and Limit cites a line of the clone at the pinned commit b0d1921faf37a8afcceee73d2e9a38f2639adc79.
This package is model-authored and unreviewed: it is checked on the fake backend only and never ran on hardware.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

#: The upstream module's path in the clone.
SOURCE = "esp.py"

#: Why the position write has no sourced upper or lower bound.
_POSITION_REASON = (
    "no text file of the clone states the travel range of the axis: the constructor only defaults initpos to 0.0 "
    "(esp.py:4), the README's 20.0 is a usage example (README.md:13), and setpos hands any float to the controller "
    "(esp.py:36-42); the attached stage is configuration data, so the site supplies the envelope"
)


class Esp301(Driver):
    device_id = "esp301"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R1"
    native = "esp:esp"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeEsp301"}
    vendor, model = "Newport", "ESP 301"
    display_name = "Newport ESP 301 stepper motion controller (esp.esp)"
    tags = ["motion", "stepper", "controller", "esp301", "serial", "newport"]
    facts = [
        Fact("The clone is a simple Python module to control a Newport ESP 301 stepper motion controller",
             source="vendor_doc", ref="README.md:2"),
        Fact("The clone requires a USB or serial connection to the ESP301 and the PySerial module",
             source="vendor_doc", ref="README.md:5-6"),
        Fact("The constructor takes dev, b, axis, reset, initpos and useaxis and opens serial.Serial(dev, b)",
             source="upstream_code", ref=f"{SOURCE}:4-5"),
        Fact("The served axes are useaxis, or axis alone when useaxis is empty; axis is kept as defaxis",
             source="upstream_code", ref=f"{SOURCE}:6-9"),
        Fact("When reset is true the constructor resets each axis in use and calls check_errors, and for a nonzero "
             "initpos it calls setpos", source="upstream_code", ref=f"{SOURCE}:10-20"),
        Fact("reset(axis) writes '<axis>OR;<axis>WS0' followed by a carriage return", source="upstream_code",
             ref=f"{SOURCE}:22-23"),
        Fact("check_errors writes 'TE?' followed by a carriage return and returns the reply as a float",
             source="upstream_code", ref=f"{SOURCE}:25-27"),
        Fact("getpos(axis) writes '<axis>TP' followed by a carriage return and returns the reply as a float",
             source="upstream_code", ref=f"{SOURCE}:29-34"),
        Fact("setpos(pos, axis) writes '<axis>PA<pos with four decimals>;<axis>WS1;<axis>TP' followed by a "
             "carriage return and returns the reply as a float", source="upstream_code", ref=f"{SOURCE}:36-42"),
        Fact("position(pos) with a numeric pos calls setpos, getpos and setpos again, and finally returns getpos",
             source="upstream_code", ref=f"{SOURCE}:44-49"),
        Fact("The clone defines no stop, abort or halt method: its methods are reset, check_errors, getpos, setpos "
             "and position", source="upstream_code", ref=f"{SOURCE}:22-49"),
        Fact("The clone reads and writes positions as bare floats and names no physical unit", source="upstream_code",
             ref=f"{SOURCE}:29-42"),
        Fact("The README usage example opens a device at 19200 baud with default axis 1 and calls setpos(20.0, 1); "
             "neither number is a travel range", source="vendor_doc", ref="README.md:12-14"),
    ]
    safe_state = ("the served axis is re-initialized with the upstream reset ('<axis>OR;<axis>WS0') and the driver "
                  "sends no new motion command; the clone has no separate motion-stop command")

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("position", unit="1",
          description="Position of the served axis as the controller reports it (TP), in the controller's own "
                      "position units")
    def position(self):
        return self.native.getpos(self.native.defaxis)

    @read("last_error", unit="1",
          description="Controller error number returned by TE? (0 means no error, as the constructor's check does)")
    def last_error(self):
        return self.native.check_errors()

    # -- write ----------------------------------------------------------------------------------------------------
    @write("target_position", unit="1",
           description="Absolute target position for the served axis (PA), in the controller's own position units",
           limit=Limit.operator_required(_POSITION_REASON))
    def set_target_position(self, value):
        # The upstream setpos returns the position read back by its TP command, which is the value applied.
        return self.native.setpos(value, self.native.defaxis)

    # -- action ---------------------------------------------------------------------------------------------------
    @action(name="x-cap.hrosiak.reset_axis.v1", verb="invoke", exclusive=True,
            description="Reset the served axis with the upstream reset (OR, WS0) and report whether the controller "
                        "returns no error afterwards",
            output={"reset": Field("boolean", description="True once the reset was sent and TE? returned 0")})
    def reset_axis(self):
        self.native.reset(self.native.defaxis)
        code = self.native.check_errors()
        if code != 0:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"the controller reported error {code:g} after reset",
                               native_code=code)
        return {"reset": True}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop(native="reset")
    def stop(self):
        """Send the upstream reset; the clone exposes no dedicated motion-stop command."""
        self.native.reset(self.native.defaxis)
