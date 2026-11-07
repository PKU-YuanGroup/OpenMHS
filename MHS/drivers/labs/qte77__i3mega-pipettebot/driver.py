"""OpenMHS driver for gh.qte77/i3mega-pipettebot: the i3 Mega 3-axis G-code gantry.

A direct Driver (decorated methods) over the upstream device class ``pipettebot.gantry:GcodeGantry``.  The repository
builds a pipetting robot from an Anycubic i3 Mega whose print head has been removed and whose bare carriage carries a
DLAB dPette pipette (docs/hardware.md:9-10, 186-200).  The gantry is the motion platform; the dPette is a second USB
device, and the clone delegates its 6-byte protocol to the external ``dpette-usb-driver`` package (docs/hardware.md:21-25,
src/pipettebot/bot.py:38-48).  This package therefore drives the gantry only and does not claim a fluid capability.

* reads: x, y and z, parsed from the firmware's ``M114`` reply (docs/research/gantry-firmware-alternatives.md:143);
* one move action: ``move_to`` sends ``G1`` with three decimals and ``wait_for_moves`` flushes the planner with ``M400``
  (src/pipettebot/gantry.py:201, 211), then the driver reads ``M114`` back and fails unless the reported position is the
  requested one;
* one home action: ``G28 X Y`` plus ``M400``.  The clone warns that after head removal ``G28`` succeeds for X and Y but
  can hang or crash on Z, and says to use ``G28 X Y`` until a Z-endstop strategy exists (docs/marlin-commands.md:107);
* the workspace bounds are ``Limit.operator_required``: the clone states that soft limits are not enforced and that any
  hardcoded coordinate is untrusted (docs/hardware.md:206-207), so every move is refused until the site supplies the
  envelope of its installed tool and labware (``site-limits.example.json`` shows the overlay);
* the native stop and the safe-state action send the firmware emergency stop ``M112`` (docs/marlin-commands.md:58).

Every Fact cites a line of the clone at the pinned commit 99dc2e0a8c15067f3d994e6484507fa2be2301d7.  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

import re

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read

#: The G1 formatter writes three decimals (src/pipettebot/gantry.py:201), so the firmware's M114 reply has the same
#: resolution and a reported target within this tolerance is accepted.
_TOLERANCE_MM = 0.001

#: One M114 reply line, as documented at docs/research/gantry-firmware-alternatives.md:143.
_POSITION_RE = re.compile(r"X:\s*(-?\d+(?:\.\d+)?)\s+Y:\s*(-?\d+(?:\.\d+)?)\s+Z:\s*(-?\d+(?:\.\d+)?)")


def _workspace(axis: str) -> Limit:
    """An operator-required bound for one Cartesian axis of the gantry."""
    return Limit.operator_required(
        f"the clone states that soft limits are not enforced and that any hardcoded coordinate is untrusted "
        f"(docs/hardware.md:206-207); the site supplies the safe {axis} bound of the installed tool and labware")


_POSITION_FIELD = Field(
    "object",
    description="Target position of the tool centre point in the Marlin frame",
    properties={
        "x": Field("number", unit="mm", description="Target X coordinate", limit=_workspace("X")),
        "y": Field("number", unit="mm", description="Target Y coordinate", limit=_workspace("Y")),
        "z": Field("number", unit="mm", description="Target Z coordinate", limit=_workspace("Z")),
    },
)


class I3megaPipettebot(Driver):
    device_id = "i3mega-pipettebot"
    device_kind = "robot.arm"
    mode = "hardware"
    risk = "R2"
    native = "pipettebot.gantry:GcodeGantry"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeGcodeGantry"}
    vendor, model = "Anycubic", "i3 Mega (3-axis motion platform)"
    display_name = "Anycubic i3 Mega pipettebot gantry"
    tags = ["gantry", "cartesian", "marlin", "3d-printer", "pipetting-robot"]
    facts = [
        Fact("home() sends G28, move_to() sends G1 X... Y... Z... F... with three decimals, and wait_for_moves() "
             "sends M400", source="upstream_code", ref="src/pipettebot/gantry.py:194-211"),
        Fact("send() writes the command with a trailing newline and waits for a reply line equal to 'ok' or starting "
             "with 'ok '", source="upstream_code", ref="src/pipettebot/gantry.py:120-134"),
        Fact("send() and query() default max_secs to 30.0", source="upstream_code",
             ref="src/pipettebot/gantry.py:160-172"),
        Fact("send_and_wait_for_ok raises TimeoutError when no ok arrives before max_secs", source="upstream_code",
             ref="src/pipettebot/gantry.py:135"),
        Fact("GantryConfig defaults the feedrate to 3000 mm/min", source="upstream_code",
             ref="src/pipettebot/gantry.py:144"),
        Fact("M114 reports the current XYZE position as Marlin sees it", source="vendor_doc",
             ref="docs/marlin-commands.md:49"),
        Fact("The documented M114 reply is X:0.000 Y:0.000 Z:0.000 E:0.000 followed by ok", source="vendor_doc",
             ref="docs/research/gantry-firmware-alternatives.md:143"),
        Fact("M112 is the emergency stop: Marlin halts and refuses commands until power-cycle", source="vendor_doc",
             ref="docs/marlin-commands.md:58"),
        Fact("G28 homes all axes (X, then Y, then Z)", source="vendor_doc", ref="docs/marlin-commands.md:75"),
        Fact("After head removal G28 succeeds for X and Y but can hang or crash on Z; the clone says to use G28 X Y "
             "until a Z-endstop strategy exists", source="vendor_doc", ref="docs/marlin-commands.md:107"),
        Fact("G28 X Y is the XY homing command of the safe_home path", source="upstream_code",
             ref="src/pipettebot/devices.py:314"),
        Fact("Soft limits are not enforced in software and any hardcoded coordinate is untrusted", source="vendor_doc",
             ref="docs/hardware.md:206-207"),
        Fact("The print head, hotend, fan, sensor PCB and heater wiring have been physically removed from the "
             "carriage", source="vendor_doc", ref="docs/hardware.md:188-190"),
        Fact("The i3 Mega is no longer a 3D printer; it is a 3-axis motion platform", source="vendor_doc",
             ref="docs/hardware.md:191-192"),
        Fact("The dPette is a separate USB device whose 6-byte serial protocol is delegated to the external "
             "dpette-usb-driver package", source="vendor_doc", ref="docs/hardware.md:21-25"),
        Fact("PipetteBot.aspirate_at moves, waits for the moves (M400), then calls the pipette's aspirate",
             source="upstream_code", ref="src/pipettebot/bot.py:38-42"),
        Fact("The gantry serial link is 250000 8N1 on stock Anycubic firmware", source="vendor_doc",
             ref="docs/hardware.md:36"),
    ]
    safe_state = ("motion halted by the firmware emergency stop (M112); the controller refuses commands until it is "
                  "power-cycled")

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("x", unit="mm", description="Firmware-reported X position from the M114 reply")
    def x(self):
        return self._position()[0]

    @read("y", unit="mm", description="Firmware-reported Y position from the M114 reply")
    def y(self):
        return self._position()[1]

    @read("z", unit="mm", description="Firmware-reported Z position from the M114 reply")
    def z(self):
        return self._position()[2]

    # -- actions --------------------------------------------------------------------------------------------------
    @action(cap="cap.motion.cartesian_pose.v1",
            description="Move the tool centre point to a Cartesian position with G1, wait for the motion (M400) and "
                        "read the position back (M114)",
            input={"position": _POSITION_FIELD})
    def move_to(self, position):
        x, y, z = float(position["x"]), float(position["y"]), float(position["z"])
        self.native.move_to(x, y, z)
        self.native.wait_for_moves()
        self.check_cancelled()
        actual = self._position()
        if not all(abs(got - wanted) <= _TOLERANCE_MM for got, wanted in zip(actual, (x, y, z))):
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               f"M114 reports {actual!r} after the move to {(x, y, z)!r}")
        return {"reached": True,
                "position": {"x": actual[0], "y": actual[1], "z": actual[2]},
                "tolerance_mm": _TOLERANCE_MM}

    @action(cap="cap.motion.home.v1",
            description="Home X and Y with G28 X Y and wait for the motion (M400); Z is not homed because the clone "
                        "warns that G28 on Z hangs or crashes after the print head is removed",
            input={"axes": Field("array", description="Axes to home; only x and y are accepted, and an omitted list "
                                                     "homes both",
                                 items=Field("string", description="Axis name, x or y"))})
    def home(self, axes=None):
        if axes is None:
            wanted = ["x", "y"]
        else:
            requested = {str(axis).lower() for axis in axes}
            if not requested or not requested <= {"x", "y"}:
                raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                                   f"only x and y can be homed (requested {sorted(requested)}); G28 on Z can hang "
                                   "or crash after the print head is removed")
            wanted = [axis for axis in ("x", "y") if axis in requested]
        self.native.send("G28 " + " ".join(axis.upper() for axis in wanted))
        self.native.wait_for_moves()
        return {"homed": True, "axes": wanted}

    @action(name="x-cap.qte77.emergency_stop.v1", safe_state=True,
            description="Send the firmware emergency stop M112; it takes no input and is the declared safe state",
            output={"halted": Field("boolean",
                                    description="True once the M112 emergency-stop command was acknowledged")})
    def emergency_stop(self):
        self.native.send("M112", max_secs=1.0)
        return {"halted": True}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: the runtime latches first, then the firmware emergency stop M112 is sent."""
        self.native.send("M112", max_secs=1.0)

    def teardown(self):
        self.native.close()

    # -- helpers --------------------------------------------------------------------------------------------------
    def _position(self):
        lines = self.native.query("M114")
        for line in lines:
            match = _POSITION_RE.search(line)
            if match is not None:
                return float(match.group(1)), float(match.group(2)), float(match.group(3))
        raise DriverFailed("MHS.DEVICE.FAULTED", f"M114 returned no X/Y/Z coordinate line: {lines[:3]!r}")
