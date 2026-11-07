"""OpenMHS driver for gh.unine-chyn/thorpy: a Thorlabs APT single-channel stage port.

The upstream package speaks the Thorlabs APT framed binary protocol over a serial port (``thorpy.comm.port:Port``).
That protocol is not a text command language, so this is a direct driver over the upstream object rather than a
``SerialDriver`` command table: the card's ``family:serial`` helper cannot express a frame built from a message id,
a channel and a stop mode.  The driver talks only to the objects the upstream port returns:

* ``Port.get_stages()`` returns the ``GenericStage`` of channel 1;
* ``GenericStage.position`` reads the encoder position and its setter starts an absolute move;
* ``GenericStage.max_velocity`` and ``GenericStage.acceleration`` are the velocity parameters;
* ``GenericStage.status_homed`` reports the APT status bit 0x00000400;
* ``GenericStage.home_non_blocking()`` starts a home move;
* ``Port.send_message()`` carries the six-byte ``MGMSG_MOT_MOVE_STOP`` frame used by the e-stop.

The driver serves linear translation stages only (the clone reports ``mm`` for a stage configured with Units = 1);
a rotational stage reports degrees and is outside this binding.  This package is model-authored and unreviewed, and
nothing here was run on hardware.  Every Fact cites a line of the clone at the pinned commit
(e8f000bd8a5bcc5a11b52f59742024d929751827).
"""

import time

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write

PORT = "thorpy/comm/port.py"
STAGES = "thorpy/stages/__init__.py"
MESSAGES = "thorpy/message/_base.py"
MOTOR = "thorpy/message/motorcontrol.py"

#: ``MGMSG_MOT_MOVE_STOP`` (message id 0x465): little-endian id, channel 0x01, stop mode 0x01 (immediately), the
#: controller destination 0x50 and the host source 0x01.  The fields and their order are the upstream message class
#: (motorcontrol.py:691-704) and the short-frame layout (message/_base.py:98-108).
STOP_FRAME = b"\x65\x04\x01\x01\x50\x01"

#: Seconds between two status polls of the home loop, the same interval the upstream home() uses
#: (stages/__init__.py:449).  The loop checks self.cancelled() before every poll, so an e-stop interrupts it.
HOME_POLL_S = 1.0


class ThorpyStage(Driver):
    device_id = "thorpy-stage"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R1"
    native = "thorpy.comm.port:Port"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakePort"}
    vendor, model = "Thorlabs", "APT single-channel stage controller"
    display_name = "Thorlabs APT stage (Thorpy)"
    tags = ["thorlabs", "apt", "stage", "motion", "serial"]
    facts = [
        Fact("The APT serial port opens at 115200 baud, 8 data bits, no parity, one stop bit and RTS/CTS flow control",
             source="upstream_code", ref=f"{PORT}:20-24"),
        Fact("Port.create returns a SingleControllerPort unless the serial number starts with 70, 73 or 94, which "
             "selects the unimplemented CardSlotPort", source="upstream_code", ref=f"{PORT}:181-193"),
        Fact("SingleControllerPort.get_stages accepts only channel 0x01 and returns a GenericStage for it",
             source="upstream_code", ref=f"{PORT}:236-249"),
        Fact("A short APT frame is a little-endian 16-bit message id, two parameter bytes, a destination byte and a "
             "source byte", source="upstream_code", ref=f"{MESSAGES}:98-108"),
        Fact("The stage position is the encoder count divided by EncCnt", source="upstream_code",
             ref=f"{STAGES}:224-226"),
        Fact("The position setter multiplies the position by EncCnt and sends MGMSG_MOT_MOVE_ABSOLUTE_long",
             source="upstream_code", ref=f"{STAGES}:228-232"),
        Fact("The velocity conversion uses EncCnt and T, with T = 2048 / 6e6", source="upstream_code",
             ref=f"{STAGES}:235-237"),
        Fact("A stage reports mm when its configured Units value is 1 and the degree sign when it is 2",
             source="upstream_code", ref=f"{STAGES}:399-400"),
        Fact("status_homed is status bit 0x00000400 of the APT status word", source="upstream_code",
             ref=f"{STAGES}:275-277"),
        Fact("home_non_blocking sends MGMSG_MOT_MOVE_HOME and returns without waiting for the move to finish",
             source="upstream_code", ref=f"{STAGES}:455-461"),
        Fact("MGMSG_MOT_MOVE_ABSOLUTE_long is message 0x453 with a 16-bit channel and a signed 32-bit position",
             source="upstream_code", ref=f"{MOTOR}:560-572"),
        Fact("MGMSG_MOT_MOVE_HOME is message 0x443 with a channel byte", source="upstream_code",
             ref=f"{MOTOR}:625-635"),
        Fact("MGMSG_MOT_MOVE_STOP is message 0x465 with a channel byte and a stop mode (0x01 immediately, 0x02 "
             "controlled)", source="upstream_code", ref=f"{MOTOR}:691-704"),
        Fact("MGMSG_MOT_SET_VELPARAMS is message 0x415 and carries min_velocity, acceleration and max_velocity",
             source="upstream_code", ref=f"{MOTOR}:548-559"),
    ]
    safe_state = "all motion on the channel stopped with an immediate MGMSG_MOT_MOVE_STOP command"

    def _stage(self):
        """The GenericStage of channel 1, obtained through Port.get_stages (the native call G7 can see)."""
        return self.native.get_stages()[0x01]

    @read("position", unit="mm", description="Encoder position of the stage, in mm for a Units = 1 stage")
    def position(self):
        return float(self._stage().position)

    @read("max_velocity", unit="mm/s", description="Maximum velocity sent to the controller with the velocity "
          "parameters; the stage configuration sets the usable range")
    def max_velocity(self):
        return float(self._stage().max_velocity)

    @read("acceleration", unit="mm/s2", description="Acceleration sent to the controller with the velocity "
          "parameters")
    def acceleration(self):
        return float(self._stage().acceleration)

    @read("homed", type="boolean", description="True when the controller reports status bit 0x00000400 (homed)")
    def homed(self):
        return bool(self._stage().status_homed)

    @write("position", unit="mm", description="Start an absolute move to this encoder position",
           limit=Limit.operator_required(
               "The travel range depends on the installed stage and is per-stage server configuration, not a bound "
               "of the upstream code; the operator must narrow it for the bench"))
    def set_position(self, value):
        self._stage().position = float(value)

    @write("max_velocity", unit="mm/s", description="Set the maximum velocity of the velocity parameters",
           limit=Limit.operator_required(
               "The usable velocity depends on the installed stage; the upstream code only converts the value and "
               "states no bound, so the operator must narrow it for the bench"))
    def set_max_velocity(self, value):
        self._stage().max_velocity = float(value)

    @write("acceleration", unit="mm/s2", description="Set the acceleration of the velocity parameters",
           limit=Limit.operator_required(
               "The usable acceleration depends on the installed stage; the upstream code only converts the value "
               "and states no bound, so the operator must narrow it for the bench"))
    def set_acceleration(self, value):
        self._stage().acceleration = float(value)

    @action(name="x-cap.unine-chyn.stage_home.v1", risk="R1",
            description="Start a home move and wait until the controller reports homed",
            input={}, output={"homed": Field("boolean", description="True when status bit 0x00000400 is set")})
    def home(self):
        stage = self._stage()
        stage.home_non_blocking(force=True)
        while not stage.status_homed:
            self.check_cancelled()
            time.sleep(HOME_POLL_S)
        return {"homed": True}

    @action(name="x-cap.unine-chyn.stage_stop.v1", risk="R1", safe_state=True,
            description="Stop every kind of motor move on the channel immediately",
            input={}, output={"stopped": Field("boolean", description="True when the stop frame was sent")})
    def stop_motion(self):
        self._send_stop()
        return {"stopped": True}

    def _send_stop(self):
        # Port.send_message writes bytes(msg); a bytes object is passed through unchanged (message/_base.py:182-200).
        self.native.send_message(STOP_FRAME)

    @estop
    def emergency_stop(self):
        self._send_stop()
