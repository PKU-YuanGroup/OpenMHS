"""OpenMHS driver for gh.quantumquadrate/k10cr1: the Thorlabs K10CR1 motorized rotation stage.

A direct Driver over the upstream class ``K10CR1.k10cr1:K10CR1`` (K10CR1/k10cr1.py:6).  The card proposes a
SerialDriver (family ``serial``, decision ``family-config``); every command is a hex frame of the Thorlabs APT
protocol, and each move frame is assembled from a header, a channel word and a 4-byte encoder position
(K10CR1/k10cr1.py:154-170), so a command table cannot reproduce the bytes: this package is a direct Driver
(DEVIATION FROM THE CARD, recorded in RESULT.json).

* reads: the stage angle in degrees (``getpos``, K10CR1/k10cr1.py:184-189);
* actions: an absolute move (``moveabs``), a relative move (``moverel``), homing (``home``) and a jog (``jog``);
* the stage angle is the unit the class publishes (degrees, three decimals, K10CR1/k10cr1.py:38-39, 189); the class
  states no travel limits, so every angle input is ``Limit.operator_required``;
* BLOCKED on the stop path: the class defines no stop, abort or disable method — a review of the whole module
  (K10CR1/k10cr1.py:9-189) finds only __init__, connect, angle_to_DU, DU_to_angle, dth, btd, htb, rd, write, identify,
  home, moverel, moveabs, zerobacklash, jog and getpos — so no honest @estop can be written and the package cannot
  pass the acceptance gate at hardware R1 (DRV-012); RESULT.json records the block.

Every Fact cites a line of the clone at the pinned commit (2ffdc284da575e525f96ef27b99e5e260bbe415d).  This package
is model-authored and unreviewed: it is checked on the fake backend only and never ran on hardware.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, read

SOURCE = "K10CR1/k10cr1.py"
#: Encoder counts per 180 degrees (K10CR1/k10cr1.py:35-39): the class converts degrees and its own position unit.
DU_PER_180_DEG = 24576000


class K10CR1(Driver):
    device_id = "k10cr1"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R1"
    native = "K10CR1.k10cr1:K10CR1"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeK10CR1"}
    vendor = "Thorlabs"
    model = "K10CR1 motorized rotation stage"
    display_name = "Thorlabs K10CR1 rotation stage"
    tags = ["rotation stage", "motor", "thorlabs", "k10cr1", "apt", "serial", "motion"]
    facts = [
        Fact("The class is the Thorlabs K10CR1 rotation stage driver",
             source="upstream_code", ref=f"{SOURCE}:6-7"),
        Fact("The constructor takes the serial number, searches the serial ports for that device, and zeroes the "
             "backlash when the connection succeeded", source="upstream_code", ref=f"{SOURCE}:9-18"),
        Fact("connect() scans every serial port and matches the device by the serial number inside the port "
             "description, then opens the port at 115200 baud with a 0.1 s timeout",
             source="upstream_code", ref=f"{SOURCE}:20-33"),
        Fact("The FTDI chip of the controller has VID:PID 0403:faf0 according to the comment of connect()",
             source="upstream_code", ref=f"{SOURCE}:27-29"),
        Fact("The class converts an angle to its encoder unit as angle * 24576000 / 180 and back as "
             "counts * 180 / 24576000", source="upstream_code", ref=f"{SOURCE}:35-39"),
        Fact("The protocol commands are fixed byte frames written as hex text; the homing frame is '430401005001' "
             "and the jog frame is '6a0401015001'", source="upstream_code", ref=f"{SOURCE}:150-152"),
        Fact("home() writes the homing frame and reads 6 bytes of response",
             source="upstream_code", ref=f"{SOURCE}:150-152"),
        Fact("moverel() and moveabs() assemble the frame from the header, the channel word '0100' and the 4-byte "
             "encoder position; they do not read a response", source="upstream_code", ref=f"{SOURCE}:154-170"),
        Fact("jog() writes the jog frame and reads 20 bytes of response", source="upstream_code", ref=f"{SOURCE}:180-182"),
        Fact("getpos() writes the position query frame, reads 12 bytes, takes the last 4 as the position and "
             "returns degrees rounded to three decimals", source="upstream_code", ref=f"{SOURCE}:184-189"),
        Fact("identify() only writes the information frame and returns the byte count of the serial write, not an "
             "identity", source="upstream_code", ref=f"{SOURCE}:147-148"),
        Fact("zerobacklash() writes the backlash parameter with the position of 0 degrees",
             source="upstream_code", ref=f"{SOURCE}:172-177"),
        Fact("The clone README describes the repository as a Thorlabs K10CR1 rotation stage python driver",
             source="vendor_doc", ref="README.md:2"),
        Fact("The clone's own test opens the stage by serial number and makes a relative move of -10 degrees",
             source="vendor_doc", ref="test.py:3-4"),
    ]
    safe_state = ("unreachable through this library: it has no stop, abort or disable command, so a latched e-stop "
                  "cannot stop a move in flight (RESULT.json)")

    # -- read -------------------------------------------------------------------------------------------------
    @read("position", unit="deg", description="Angle of the stage in degrees, as getpos() reports it")
    def position(self):
        return self.native.getpos()

    # -- moves (extensions: no catalogue class carries an angle of a rotation stage in degrees) -----------------
    @action(name="x-cap.quantumquadrate.move_absolute.v1",
            description="Move the stage to an absolute angle with the native moveabs()",
            input={"angle": Field("number", unit="deg",
                                  description="Absolute stage angle in degrees",
                                  limit=Limit.operator_required(
                                      "no text file of the clone states the travel range of the stage: it only "
                                      "converts degrees to encoder counts (k10cr1.py:35-39), so the site states "
                                      "the allowed angle range"))},
            output={"angle": Field("number", unit="deg",
                                   description="Angle written to the stage (moveabs() reads no response)")})
    def move_absolute(self, angle):
        self.native.moveabs(angle)
        return {"angle": angle}

    @action(name="x-cap.quantumquadrate.move_relative.v1",
            description="Move the stage by a relative angle with the native moverel()",
            input={"delta": Field("number", unit="deg",
                                  description="Relative angle in degrees, positive or negative",
                                  limit=Limit.operator_required(
                                      "no text file of the clone states the travel range of the stage: it only "
                                      "converts degrees to encoder counts (k10cr1.py:35-39), so the site states "
                                      "the allowed step range"))},
            output={"delta": Field("number", unit="deg",
                                   description="Angle written to the stage (moverel() reads no response)")})
    def move_relative(self, delta):
        self.native.moverel(delta)
        return {"delta": delta}

    @action(name="x-cap.quantumquadrate.home_stage.v1",
            description="Home the stage with the native home() and report the response frame it read",
            output={"response": Field("string", description="Response frame the class read back after homing")})
    def home_stage(self):
        return {"response": _text(self.native.home())}

    @action(name="x-cap.quantumquadrate.jog_stage.v1",
            description="Start the native jog() and report the response frame it read",
            output={"response": Field("string", description="Response frame the class read back after the jog")})
    def jog_stage(self):
        return {"response": _text(self.native.jog())}


def _text(value):
    """The response the class read, as text (the upstream methods return bytes)."""
    return value.decode(errors="replace").strip() if isinstance(value, (bytes, bytearray)) else str(value)
