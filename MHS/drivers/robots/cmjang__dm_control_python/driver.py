"""OpenMHS driver for gh.cmjang/dm_control_python: one DaMiao CAN motor driven through ``DM_CAN:MotorControl``.

The clone is one module, ``DM_CAN.py``: ``MotorControl`` is the serial-to-CAN master and a ``Motor`` object holds the
last feedback frame of one motor.  This is a direct Driver over ``MotorControl``:

* reads: the measured joint angle, velocity and torque, and the control mode the driver selected;
* write: ``enabled`` switches the motor drive on (0xFC) or off (0xFD);
* ``cap.motion.joint_position.v1``: commands a target angle in position-velocity mode and waits, bounded, for the
  measured angle to arrive;
* ``cap.motion.joint_velocity.v1``: commands a joint velocity for ``duration_s`` seconds and then commands 0 rad/s,
  so the motor is stopped again even when the action is cancelled;
* the e-stop calls the upstream ``disable()``, which switches the drive off.

The driver switches the motor to the control mode a motion needs (README.md:198-209) and refuses the motion when the
motor does not confirm it.  The angle and velocity envelopes are ``Limit.operator_required``: the clone states no
mechanical travel of the joint and no site speed, so ``site-limits.json`` supplies them before the first motion.

The motor identity (slave id, master id, motor type) is a backend option; the defaults of this module are the motor
of the README example (README.md:55) and exist for the fake backend and the gate, which pass no options, while
``native.py`` refuses to open a serial line without explicit values.  Package code may not import the clone, so the
driver creates the motor object it passes to ``MotorControl`` with the attribute protocol of the upstream ``Motor``
class (DM_CAN.py:8-63): ``SlaveID``, ``MasterID``, ``MotorType``, ``temp_param_dict``, ``state_q``/``state_dq``/
``state_tau`` and ``recv_data(q, dq, tau)``.  This package is model-authored and unreviewed; nothing here ran on a
motor.
"""

from time import monotonic, sleep

from mhs.driver import Cancelled, Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

DM_CAN = "DM_CAN.py"
README = "README.md"

#: Control_Type values of the clone (DM_CAN.py:620-624): the value written to the CTRL_MODE register.
CONTROL_MIT = 1
CONTROL_POS_VEL = 2
CONTROL_VEL = 3

#: The identity of the README example motor (README.md:55); the hardware backend requires explicit options.
DEFAULT_SLAVE_ID = 0x01
DEFAULT_MASTER_ID = 0x11
DEFAULT_MOTOR_TYPE = 0

#: How long a position move waits for the measured angle; the catalogue class allows 120 s for one move.
MOVE_WAIT_S = 10.0
#: Arrival tolerance of a position move, reported in ``tolerance_rad``; a driver setting, not a device bound.
ARRIVAL_TOLERANCE_RAD = 0.02
#: Poll interval of the position wait and of the velocity hold.
POLL_S = 0.01


class DMMotor(Driver):
    device_id = "dm-motor"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R1"
    native = "DM_CAN:MotorControl"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeMotorControl"}
    vendor = "DaMiao"
    model = "DM series CAN motor"
    display_name = "DaMiao DM series CAN motor (DM_CAN.MotorControl)"
    tags = ["motor", "can", "damiao", "joint", "position control", "velocity control"]
    facts = [
        Fact("The README builds a Motor from the motor type, its Slave ID (the CAN id) and a Master ID that must be "
             "unique and not 0x00", source="vendor_doc", ref=f"{README}:55-62"),
        Fact("The README opens the serial adapter with 921600 baud and a 0.5 s timeout and gives the port object to "
             "MotorControl", source="vendor_doc", ref=f"{README}:64-73"),
        Fact("The README adds a motor to the MotorControl, enables it and documents disable as the way to switch the "
             "drive off", source="vendor_doc", ref=f"{README}:81-119"),
        Fact("A Motor object holds the last feedback in state_q, state_dq and state_tau", source="upstream_code",
             ref=f"{DM_CAN}:16-20"),
        Fact("recv_data(q, dq, tau) stores one feedback frame in the motor object", source="upstream_code",
             ref=f"{DM_CAN}:28-31"),
        Fact("getPosition, getVelocity and getTorque return the stored feedback", source="upstream_code",
             ref=f"{DM_CAN}:33-52"),
        Fact("A new Motor object starts in MIT control mode (NowControlMode = Control_Type.MIT)", source="upstream_code",
             ref=f"{DM_CAN}:25"),
        Fact("A control method finds its motor by SlaveID in motors_map and returns without a command when the motor "
             "was not added", source="upstream_code", ref=f"{DM_CAN}:147-149"),
        Fact("addMotor stores the motor under its SlaveID and, when that is not 0, under its MasterID too",
             source="upstream_code", ref=f"{DM_CAN}:317-325"),
        Fact("control_Pos_Vel sends the desired position and velocity as float32 bytes on CAN id 0x100 + SlaveID",
             source="upstream_code", ref=f"{DM_CAN}:150-156"),
        Fact("control_Vel sends the desired velocity as float32 bytes on CAN id 0x200 + SlaveID",
             source="upstream_code", ref=f"{DM_CAN}:169-173"),
        Fact("enable, disable and set_zero_position send 0xFC, 0xFD and 0xFE as the last byte of an eight byte data "
             "frame", source="upstream_code", ref=f"{DM_CAN}:327-329"),
        Fact("refresh_motor_status sends the status query and reads the answer back with recv()", source="upstream_code",
             ref=f"{DM_CAN}:408-416"),
        Fact("switchControlMode writes the CTRL_MODE register and returns True when the motor reports the new value",
             source="upstream_code", ref=f"{DM_CAN}:361-380"),
        Fact("The CTRL_MODE register is one of the integer registers (7 to 10, 13 to 16, 35 to 36), read and written "
             "as uint32", source="upstream_code", ref=f"{DM_CAN}:520-528"),
        Fact("The CTRL_MODE register takes the integer range [1,4]", source="vendor_doc", ref=f"{README}:266"),
        Fact("Control_Type maps MIT to 1, POS_VEL to 2, VEL to 3 and Torque_Pos to 4", source="upstream_code",
             ref=f"{DM_CAN}:620-624"),
        Fact("A control mode change is temporary: the motor resets it after a power cycle", source="vendor_doc",
             ref=f"{README}:209"),
    ]
    safe_state = "motor drive switched off with disable() (0xFD); the motor is free and the last command no longer acts"
    #: The control mode the driver selected; a new Motor object starts in MIT mode (DM_CAN.py:25).
    _control_mode = CONTROL_MIT

    # -- reads -----------------------------------------------------------------------------------------------------
    @read("joint_position", unit="rad", description="Measured angle of the joint")
    def joint_position(self):
        self.native.refresh_motor_status(self._motor)
        return float(self._motor.getPosition())

    @read("joint_velocity", unit="rad/s", description="Measured velocity of the joint")
    def joint_velocity(self):
        self.native.refresh_motor_status(self._motor)
        return float(self._motor.getVelocity())

    @read("joint_torque", unit="N.m", description="Measured torque of the joint")
    def joint_torque(self):
        self.native.refresh_motor_status(self._motor)
        return float(self._motor.getTorque())

    @read("control_mode", type="integer", unit="1",
          description="Control mode the driver selected last: 1 MIT, 2 POS_VEL, 3 VEL (the clone's Control_Type)")
    def control_mode(self):
        return int(self._control_mode)

    # -- configuration ---------------------------------------------------------------------------------------------
    @write("enabled", type="boolean",
           description="Enable (0xFC) or disable (0xFD) the motor drive; a motion needs an enabled drive")
    def set_enabled(self, value):
        if value:
            self.native.enable(self._motor)
        else:
            self.native.disable(self._motor)

    # -- motion ----------------------------------------------------------------------------------------------------
    @action(cap="cap.motion.joint_position.v1", long_running=True, cancellable=True,
            description="Command the joint to a target angle in position-velocity mode and wait, bounded, until the "
                        "measured angle arrives",
            input={"joint_positions": Field(
                unit="rad", length=1, description="Target angle of the joint, one value in rad",
                limit=Limit.operator_required(
                    "the clone states no mechanical travel of the joint (the 12.5 rad of Limit_Param, "
                    "DM_CAN.py:71-75, is the encoder range of a motor type, not a mechanism limit); the site sets "
                    "the joint envelope"))})
    def move_joint(self, joint_positions):
        target = float(joint_positions[0])
        self._select_mode(CONTROL_POS_VEL)
        self.native.control_Pos_Vel(self._motor, target, 0.0)
        reached = self._wait_for_position(target)
        return {"reached": reached, "joint_positions": [float(self._motor.getPosition())],
                "tolerance_rad": ARRIVAL_TOLERANCE_RAD}

    @action(cap="cap.motion.joint_velocity.v1", long_running=True, cancellable=True,
            description="Command a joint velocity for duration_s seconds, then command 0 rad/s so the motor stops "
                        "again; a cancellation stops it at once too",
            input={
                "joint_velocities": Field(
                    unit="rad/s", length=1, description="Commanded velocity of the joint, one value in rad/s",
                    limit=Limit.operator_required(
                        "the clone states no velocity envelope of the joint; the motor's MAX_SPD register is a "
                        "firmware setting, not a site limit, so the site sets the jog envelope")),
                "duration_s": Field(
                    unit="s", description="How long the velocity is commanded; the driver sends 0 rad/s afterwards",
                    limit=Limit.operator_required(
                        "the clone states no safe duration of a velocity command; the site sets it, within the 60 s "
                        "of the catalogue class")),
            })
    def jog_joint(self, joint_velocities, duration_s):
        speed = float(joint_velocities[0])
        self._select_mode(CONTROL_VEL)
        try:
            self.native.control_Vel(self._motor, speed)
            self._hold(float(duration_s))
        finally:
            # the motor keeps the last velocity command: send 0 rad/s on the way out, also after a cancellation
            self.native.control_Vel(self._motor, 0.0)
        return {"applied": True, "joint_velocities": [speed]}

    # -- safety ----------------------------------------------------------------------------------------------------
    @estop(native="disable")
    def stop(self):
        """The native stop: the runtime latches first, then the drive is switched off (0xFD)."""
        self.native.disable(self._motor)

    # -- lifecycle ---------------------------------------------------------------------------------------------------
    def setup(self):
        """Register the motor on the bus: MotorControl commands it only after addMotor (DM_CAN.py:317-325)."""
        self._motor = _MotorRef(
            slave_id=int(self.options.get("slave_id", DEFAULT_SLAVE_ID)),
            master_id=int(self.options.get("master_id", DEFAULT_MASTER_ID)),
            motor_type=int(self.options.get("motor_type", DEFAULT_MOTOR_TYPE)),
        )
        self._control_mode = CONTROL_MIT
        self.native.addMotor(self._motor)

    # -- helpers -----------------------------------------------------------------------------------------------------
    def _select_mode(self, mode):
        """Ask the motor for the control mode a motion needs, and refuse the motion when it does not confirm it.

        The modes are those of the control-type section of the README (README.md:198-209); the register is
        CTRL_MODE (DM_CAN.py:583).
        """
        if int(self._control_mode) == mode:
            return
        if not self.native.switchControlMode(self._motor, mode):
            raise DriverFailed("MHS.DEVICE.FAULTED",
                              f"the motor did not confirm control mode {mode}; nothing was commanded")
        self._control_mode = mode

    def _wait_for_position(self, target):
        """True when the measured angle is within ARRIVAL_TOLERANCE_RAD of target before MOVE_WAIT_S is over."""
        deadline = monotonic() + MOVE_WAIT_S
        while True:
            self.native.refresh_motor_status(self._motor)
            if abs(float(self._motor.getPosition()) - target) <= ARRIVAL_TOLERANCE_RAD:
                return True
            if monotonic() >= deadline:
                return False
            if self.cancelled():
                raise Cancelled("the position move was cancelled before the joint arrived")
            sleep(POLL_S)

    def _hold(self, duration_s):
        """Keep the velocity command in force for duration_s, noticing a cancellation within POLL_S."""
        deadline = monotonic() + duration_s
        while True:
            remaining = deadline - monotonic()
            if remaining <= 0:
                return
            if self.cancelled():
                raise Cancelled("the velocity command was cancelled; the drive is commanded 0 rad/s")
            sleep(min(POLL_S, remaining))


class _MotorRef:
    """The motor object MotorControl drives, with the attribute protocol of the upstream ``Motor`` class.

    Package code may not import the clone, so this is a copy of the plain data holder the upstream class expects:
    ``SlaveID``, ``MasterID``, ``MotorType``, ``temp_param_dict`` and the feedback ``state_q``/``state_dq``/
    ``state_tau`` that ``recv_data()`` stores (DM_CAN.py:8-31), plus the three getters (DM_CAN.py:33-52).
    """

    def __init__(self, slave_id, master_id, motor_type):
        self.Pd = 0.0
        self.Vd = 0.0
        self.state_q = 0.0
        self.state_dq = 0.0
        self.state_tau = 0.0
        self.SlaveID = slave_id
        self.MasterID = master_id
        self.MotorType = motor_type
        self.isEnable = False
        self.NowControlMode = CONTROL_MIT
        self.temp_param_dict = {}

    def recv_data(self, q, dq, tau):
        self.state_q = q
        self.state_dq = dq
        self.state_tau = tau

    def getPosition(self):
        return self.state_q

    def getVelocity(self):
        return self.state_dq

    def getTorque(self):
        return self.state_tau

    def getParam(self, RID):
        return self.temp_param_dict.get(RID)
