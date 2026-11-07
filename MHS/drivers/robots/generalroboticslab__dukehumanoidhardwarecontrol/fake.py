"""Fake backend of the Duke Humanoid driver: an in-memory stand-in for ``biped_controller:BipedController``.

Gate G7: the public method defined here is a method of BipedController (``step``, biped_controller.py:249).  Its
state attributes are the names BipedController assigns: ``sensor_data`` :164, ``commands`` :156, ``dof_pos_target``
:180 and ``action`` :118.  The nested ``motor`` object carries the three MotorController properties the driver reads
(``dof_pos``, ``dof_vel``, ``dof_current``, motor_controller.py:96-120), ``num_dof`` (:35) and the two Motor setters
the driver's stop calls (``set_max_torque`` and ``set_should_terminate``, src/ethercat_motor.h:361, 498).

Every number below is test data for the fake, not a fact of the device; each is marked ``# placeholder``.  The fake
does not model the learned policy, the EtherCAT transport or the Teensy firmware: one ``step`` moves every joint a
small fixed amount, refreshes the sample and writes a fixed action, and the two setters record the torque limit and
the terminate flag, as the C++ object stores them.  A cancelled or failed call comes from the runtime, never from
here.  Nothing in this file touches hardware.
"""

# All values below are test data, not device facts.
_START_JOINT_POSITIONS = [0.0] * 10                    # placeholder
_START_JOINT_VELOCITIES = [0.0] * 10                   # placeholder
_START_JOINT_CURRENTS = [0.0] * 10                     # placeholder
_START_COMMANDS = [0.0, 0.0, 0.0]                      # placeholder
_START_ACTION = [0.0] * 10                             # placeholder
_STEP_DISPLACEMENT = 0.01                              # placeholder
_STEP_VELOCITY = 0.5                                   # placeholder
_STEP_CURRENT = 1.0                                    # placeholder
_STEP_ACTION_VALUE = 0.1                               # placeholder
_SAMPLE_RATE = 500.0                                   # placeholder
_START_FORCE = [900, 1100, 1000, 800]                  # placeholder
_START_CONTACT = [True, False]                         # placeholder


class _FakeMotor:
    """The MotorController properties the driver reads and the two setters of its stop, as plain test data."""

    def __init__(self):
        self.dof_pos = list(_START_JOINT_POSITIONS)        # placeholder
        self.dof_vel = list(_START_JOINT_VELOCITIES)       # placeholder
        self.dof_current = list(_START_JOINT_CURRENTS)     # placeholder
        self.num_dof = 10                                  # placeholder (the upstream's joint count)
        self.max_torque = [1000.0] * 10                    # placeholder
        self.should_terminate = False

    def set_max_torque(self, max_torque):
        self.max_torque = [float(value) for value in max_torque]

    def set_should_terminate(self, value):
        self.should_terminate = bool(value)


class FakeBipedController:
    """In-memory BipedController: the upstream step and the state attributes the driver reads."""

    def __init__(self, **_options):
        self.commands = list(_START_COMMANDS)              # placeholder
        self.dof_pos_target = list(_START_JOINT_POSITIONS)  # placeholder
        self.action = list(_START_ACTION)                  # placeholder
        self.motor = _FakeMotor()
        self.sensor_data = {
            "force_measurement": list(_START_FORCE),       # placeholder
            "lin_acc": [0.0, 0.0, 0.0],                    # placeholder (not read by the driver)
            "contact": list(_START_CONTACT),               # placeholder
            "ang_vel": [0.0, 0.0, 0.0],                    # placeholder
            "base_quat": [0.0, 0.0, 0.0, 1.0],             # placeholder
            "gravity_vec": [0.0, 0.0, -1.0],               # placeholder
            "sps": _SAMPLE_RATE,                           # placeholder
        }
        self._steps = 0                                    # placeholder

    def step(self):
        """One control step: move every joint, refresh the sample and store the fixed action."""
        self._steps += 1                                       # placeholder
        target = [round(value + _STEP_DISPLACEMENT * (index + 1), 6)  # placeholder
                  for index, value in enumerate(self.motor.dof_pos)]
        self.dof_pos_target = target
        self.motor.dof_pos = list(target)
        self.motor.dof_vel = [_STEP_VELOCITY] * 10             # placeholder
        self.motor.dof_current = [_STEP_CURRENT] * 10          # placeholder
        self.action = [_STEP_ACTION_VALUE] * 10                # placeholder
        self.sensor_data["sps"] = _SAMPLE_RATE                 # placeholder
        self.sensor_data["force_measurement"] = list(_START_FORCE)  # placeholder
        self.sensor_data["contact"] = list(_START_CONTACT)     # placeholder
