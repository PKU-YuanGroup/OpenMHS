"""Fake backend of the DaMiao motor driver: an in-memory stand-in for ``DM_CAN:MotorControl``.

Gate G7: every public method defined here is a method of MotorControl (DM_CAN.py at the pinned commit).  The
signatures keep the motor argument of the upstream class, and the fake drives the same motor object the driver passes
(the attribute protocol of the upstream Motor class, DM_CAN.py:8-63).  The state is that of a motor just powered up:
at 0 rad and 0 rad/s, MIT mode, drive disabled.  The numbers are placeholder test data, not facts of a motor.

What it does not do: no CAN bus and no serial frame (nothing checks the 16-byte frame of DM_CAN.py:460-477), no
control loop (a position command "arrives" at once and a velocity command holds the reported state), no firmware
register behaviour beyond a stored mode, no enable delay and no power-on delay.  ``_commands`` keeps what the driver
called, and the underscore hook ``_refuse_mode_switch`` lets a test make a mode change fail.
"""


class FakeMotorControl:
    def __init__(self, serial_device=None, **_options):
        self.motors_map = {}
        self._commands = []          # (name, arguments) of every command the driver sent; for test_driver.py
        self._mode = 1               # placeholder: MIT (DM_CAN.py:25, Control_Type.MIT)
        self._enabled = False        # placeholder: the README enables a motor before it is controlled
        self._refuse_switch = False  # placeholder: a test may make switchControlMode fail

    def addMotor(self, Motor):
        self._commands.append(("addMotor", Motor.SlaveID))
        self.motors_map[Motor.SlaveID] = Motor
        if Motor.MasterID != 0:
            self.motors_map[Motor.MasterID] = Motor
        return True

    def enable(self, Motor):
        self._commands.append(("enable", Motor.SlaveID))
        self._enabled = True

    def disable(self, Motor):
        self._commands.append(("disable", Motor.SlaveID))
        self._enabled = False
        Motor.recv_data(Motor.getPosition(), 0.0, Motor.getTorque())

    def switchControlMode(self, Motor, ControlMode):
        self._commands.append(("switchControlMode", int(ControlMode)))
        if self._refuse_switch:
            return False
        self._mode = int(ControlMode)
        return True

    def refresh_motor_status(self, Motor):
        self._commands.append(("refresh_motor_status", Motor.SlaveID))

    def control_Pos_Vel(self, Motor, P_desired, V_desired):
        self._commands.append(("control_Pos_Vel", float(P_desired), float(V_desired)))
        if Motor.SlaveID not in self.motors_map:
            return
        # placeholder: the fake has no control loop, so the joint is at the target as soon as the command returns
        Motor.recv_data(float(P_desired), 0.0, 0.0)

    def control_Vel(self, Motor, Vel_desired):
        self._commands.append(("control_Vel", float(Vel_desired)))
        if Motor.SlaveID not in self.motors_map:
            return
        # placeholder: the fake does not integrate the velocity into an angle
        Motor.recv_data(Motor.getPosition(), float(Vel_desired), 0.0)

    def _refuse_mode_switch(self, refusal=True):
        """Make the next switchControlMode calls report failure (a test hook, not a MotorControl member)."""
        self._refuse_switch = bool(refusal)
