"""OpenMHS driver for gh.veerwang/octoaxes: a 7-axis microscope stage over a framed serial protocol.

A direct Driver over hardware.serial_thread:SerialThread (the host-side transport of the upstream
software).  The card named the SerialDriver family, but the upstream does not put ASCII command words on
the wire directly: the host builds an 8-byte payload from a command id and an integer (for example
MOVETO_X 6 with a signed int32 microstep target), then SerialThread prefixes 0x02 and appends a
CRC-8-CCITT byte (software/common/gui/main_window.py:1220-1235, serial_thread.py:375-383).  A command
table cannot reproduce those bytes, so this package is a direct driver with a native.py hardware
factory and a package fake.

What this driver exposes:

* reads: the X and Y position in micrometres and the raw Z microstep count from the 24-byte position
  broadcast, plus the firmware's moving flag;
* an extension action to move X and Y to absolute positions (MOVETO_X 6 and MOVETO_Y 7);
* the catalogued illumination action to set one of the five ports D1-D5 to a percentage of full scale
  (SET_PORT_ILLUMINATION 37);
* an extension safe-state action and the e-stop: every axis is de-energised with SET_AXIS_DISABLE_ENABLE
  32 and every illumination port is switched off with TURN_OFF_ALL_PORTS 39.

The Z screw pitch depends on the Z_AXIS_VARIANT switch of the upstream software
(software/octoaxes/constants.py:16), so the driver reports Z as raw microsteps and does not convert it
to a length.  Z, W and Turret motion, homing, autofocus and hardware triggering are not covered.

Every Limit and Fact cites a line of the clone at the pinned commit
77cb47e0fdf83bde33c85d24be4d4b3723e74e15.  This package is model-authored and unreviewed; it is checked
on the fake backend only and no hardware run is claimed.
"""

import struct

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read

#: Command ids from software/common/define.py:75-77, 115, 122 and 124.
MOVETO_X = 6
MOVETO_Y = 7
MOVETO_Z = 8
SET_AXIS_DISABLE_ENABLE = 32
SET_PORT_ILLUMINATION = 37
TURN_OFF_ALL_PORTS = 39

#: Axis values of the binary protocol (software/common/define.py:37-43).
AXIS_X = 0
AXIS_Y = 1
AXIS_Z = 2
AXIS_W = 5
AXIS_TURRET = 7

#: FULLSTEPS_PER_REV is 200 and mm_per_step is pitch / (200 * microstepping); X and Y use a 2.54 mm
#: pitch and 256 microstepping (software/octoaxes/constants.py:63-64, 80-81, 168-173).
FULLSTEPS_PER_REV = 200
MICROSTEPS = 256
MM_PER_STEP = {
    "X": 2.54 / (FULLSTEPS_PER_REV * MICROSTEPS),
    "Y": 2.54 / (FULLSTEPS_PER_REV * MICROSTEPS),
}

#: The five illumination ports of the octoaxes profile, port index 0 to 4
#: (software/octoaxes/constants.py:199-205).
LIGHT_PORTS = ("D1", "D2", "D3", "D4", "D5")

X_LIMIT = Limit(min=-10, max=115000, unit="um", source="upstream_code",
                ref="software/octoaxes/constants.py:55",
                reason="X soft travel of the octoaxes profile, in micrometres")
Y_LIMIT = Limit(min=-10, max=76000, unit="um", source="upstream_code",
                ref="software/octoaxes/constants.py:72",
                reason="Y soft travel of the octoaxes profile, in micrometres")
INTENSITY_LIMIT = Limit(min=0, max=100, unit="%", source="upstream_code",
                        ref="software/common/gui/widgets.py:891",
                        reason="the host illumination slider runs from 0 to 100 percent")


class Octoaxes(Driver):
    device_id = "octoaxes"
    device_kind = "instrument.microscope"
    mode = "hardware"
    risk = "R1"
    native = "hardware.serial_thread:SerialThread"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeSerialThread"}
    vendor, model = "veerwang", "Octoaxes"
    display_name = "Octoaxes 7-axis microscope stage"
    tags = ["microscope", "stage", "motion", "illumination", "serial", "teensy"]
    facts = [
        Fact("The host application reaches the controller over USB serial at 115200 baud",
             source="vendor_doc", ref="README.md:18"),
        Fact("SerialThread opens the port with pyserial, a 0.1 s read timeout and a 0.5 s write timeout",
             source="upstream_code", ref="software/common/hardware/serial_thread.py:123-125"),
        Fact("A string command is framed as 0x55, 0xAA, the UTF-8 command text and a newline",
             source="upstream_code", ref="software/common/hardware/serial_thread.py:335"),
        Fact("A binary command is prefixed with 0x02 and its last byte is a CRC-8-CCITT of the preceding "
             "bytes", source="upstream_code",
             ref="software/common/hardware/serial_thread.py:382-383"),
        Fact("The 24-byte status packet starts with cmd_id and status and carries X, Y, Z and W as "
             "big-endian int32 positions in bytes 2 to 17", source="upstream_code",
             ref="firmware/octoaxes/serial.cpp:139-164"),
        Fact("The host parses the 24-byte packet as X/Y/Z/W big-endian int32 and treats status 1 as moving",
             source="upstream_code", ref="software/common/gui/main_window.py:1018-1027"),
        Fact("MOVETO_X, MOVETO_Y and MOVETO_Z are command ids 6, 7 and 8, and SET_AXIS_DISABLE_ENABLE is 32",
             source="upstream_code", ref="software/common/define.py:75-115"),
        Fact("SET_PORT_ILLUMINATION is command id 37 and TURN_OFF_ALL_PORTS is command id 39",
             source="upstream_code", ref="software/common/define.py:122-124"),
        Fact("An absolute move carries a signed int32 microstep target in payload bytes 2 to 5, converted "
             "from micrometres as position / 1000 / mm_per_step", source="upstream_code",
             ref="software/common/gui/main_window.py:1220-1235"),
        Fact("The X travel is -10 to 115000 micrometres and the Y travel is -10 to 76000 micrometres",
             source="upstream_code", ref="software/octoaxes/constants.py:55-72"),
        Fact("The five illumination ports D1 to D5 have port indexes 0 to 4",
             source="upstream_code", ref="software/octoaxes/constants.py:199-205"),
        Fact("The illumination control is a 0 to 100 percent slider and the host scales a percentage to a "
             "0 to 65535 DAC value", source="upstream_code",
             ref="software/common/gui/widgets.py:891-1167"),
        Fact("SET_PORT_ILLUMINATION writes the port, a 16-bit intensity and the on/off byte",
             source="upstream_code", ref="firmware/octoaxes/commandprocessor.cpp:261-265"),
        Fact("SET_AXIS_DISABLE_ENABLE with byte 3 equal to 0 de-energises the addressed axis",
             source="upstream_code", ref="firmware/octoaxes/commandprocessor.cpp:517-524"),
        Fact("TURN_OFF_ALL_PORTS switches every illumination port off",
             source="upstream_code", ref="firmware/octoaxes/commandprocessor.cpp:278-280"),
    ]
    safe_state = "all stage axes de-energised and every illumination port off"

    # -- reads --------------------------------------------------------------------------------------------
    @read("x_position_um", unit="um", description="X stage position from the firmware position broadcast")
    def x_position_um(self):
        return float(self._status()["x_um"])

    @read("y_position_um", unit="um", description="Y stage position from the firmware position broadcast")
    def y_position_um(self):
        return float(self._status()["y_um"])

    @read("z_steps", type="integer",
          description="Raw Z microstep count; the Z screw pitch depends on the configured Z variant")
    def z_steps(self):
        return int(self._status()["z_steps"])

    @read("moving", type="boolean", description="True while the firmware reports a motion in progress")
    def moving(self):
        return bool(self._status()["moving"])

    @read("illumination_port", type="string",
          description="Last illumination port commanded through this driver")
    def illumination_port(self):
        return str(self._status()["illumination_port"])

    @read("illumination_percent", unit="%",
          description="Last illumination percentage commanded through this driver")
    def illumination_percent(self):
        return float(self._status()["illumination_percent"])

    # -- actions ------------------------------------------------------------------------------------------
    @action(name="x-cap.veerwang.move_xy.v1",
            description="Move the X and Y stage axes to absolute positions in micrometres",
            input={
                "x_um": Field("number", unit="um", description="Absolute X target position",
                              limit=X_LIMIT),
                "y_um": Field("number", unit="um", description="Absolute Y target position",
                              limit=Y_LIMIT),
            },
            output={
                "x_um": Field("number", unit="um", description="Commanded X position"),
                "y_um": Field("number", unit="um", description="Commanded Y position"),
                "commanded": Field("boolean", description="True once both MOVETO commands were accepted"),
            })
    def move_xy(self, x_um, y_um):
        """Send MOVETO_X and MOVETO_Y with the converted microstep targets."""
        for axis, target, command_id in (("X", x_um, MOVETO_X), ("Y", y_um, MOVETO_Y)):
            microsteps = int(target / 1000.0 / MM_PER_STEP[axis])
            self._send(self._binary_command(command_id, struct.pack(">i", microsteps)))
        return {"x_um": float(x_um), "y_um": float(y_um), "commanded": True}

    @action(cap="cap.imaging.illumination.v1",
            description="Set one illumination port D1 to D5 to a percentage of full scale",
            input={
                "channel": Field("string", description="Illumination port D1 to D5", enum=LIGHT_PORTS),
                "intensity": Field("number", unit="%", description="Port intensity percentage",
                                   limit=INTENSITY_LIMIT),
            })
    def set_illumination(self, channel, intensity):
        """Send SET_PORT_ILLUMINATION for the named port and intensity."""
        if channel not in LIGHT_PORTS:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               f"unknown illumination port {channel!r}; use one of {list(LIGHT_PORTS)}")
        raw = int(round(float(intensity) / 100.0 * 65535))
        command = bytearray(8)
        command[1] = SET_PORT_ILLUMINATION
        command[2] = LIGHT_PORTS.index(channel)
        command[3] = (raw >> 8) & 0xFF
        command[4] = raw & 0xFF
        command[5] = 1 if intensity > 0 else 0
        self._send(command)
        return {"applied": True, "channel": channel, "intensity": float(intensity)}

    @action(name="x-cap.veerwang.safe_state.v1", safe_state=True,
            description="De-energise every stage axis and switch all illumination ports off",
            output={"safe": Field("boolean", description="True once the safe-state commands were accepted")})
    def deenergise(self):
        """The same stop path as the e-stop; it takes no input."""
        if not self.native.stop():
            raise DriverFailed("MHS.DEVICE.FAULTED", "the safe-state stop was not accepted")
        return {"safe": True}

    @estop
    def stop(self):
        """The native stop: de-energise the axes and turn every illumination port off."""
        if not self.native.stop():
            raise DriverFailed("MHS.SAFETY.SAFE_STATE_UNREACHED",
                               "the native stop was not accepted")

    # -- native helpers -----------------------------------------------------------------------------------
    def _status(self):
        status = self.native.get_status()
        if not isinstance(status, dict):
            raise DriverFailed("MHS.DEVICE.FAULTED", "get_status returned no status object")
        for key in ("x_um", "y_um", "z_steps", "moving", "illumination_port", "illumination_percent"):
            if key not in status:
                raise DriverFailed("MHS.DEVICE.FAULTED", f"the status has no {key!r}")
        return status

    def _send(self, command):
        if not self.native.is_connected():
            raise DriverFailed("MHS.DEVICE.NOT_READY", "the serial port is not open")
        if not self.native.send_binary_command(command):
            raise DriverFailed("MHS.DEVICE.FAULTED", "the binary command was not accepted")

    @staticmethod
    def _binary_command(command_id, payload=b""):
        """The 8-byte payload the upstream GUI hands to SerialThread (prefix and CRC are added there)."""
        command = bytearray(8)
        command[1] = command_id
        command[2:2 + len(payload)] = payload
        return command
