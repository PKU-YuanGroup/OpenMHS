"""Fake backend of the G1 dual-arm driver: an in-memory stand-in for G1_29_ArmController.

Gate G7: every public member defined here is a method or attribute of ``G1_29_ArmController`` in the pinned clone
(unitree_lerobot/eval_robot/robot_control/robot_arm.py:69-287), with the upstream parameter names.  The fake keeps
the same division of labour as the upstream class: ``ctrl_dual_arm`` only stores the target, the getters read the
current state, and a target that is a copy of the current q is a hold.  It does not model the DDS transport, the
250 Hz publish thread, the velocity clip, or motion over time: storing a target leaves the current q unchanged.
Nothing here talks to a device.

The starting joint values, the target values and the gains are placeholders for the fake; they are not facts about a
G1 and must not be read as joint limits.  The only stop-like call the upstream class offers is a target through
``ctrl_dual_arm``, so the fake records every call and lets a test inspect it.
"""

_NUM_ARM_JOINTS = 14


class FakeG1_29_ArmController:
    def __init__(self, motion_mode=False, simulation_mode=False, **_options):
        self.motion_mode = bool(motion_mode)
        self.simulation_mode = bool(simulation_mode)
        self.q_target = [0.0] * _NUM_ARM_JOINTS        # placeholder
        self.tauff_target = [0.0] * _NUM_ARM_JOINTS    # placeholder
        self.arm_velocity_limit = 20.0                 # placeholder
        self.control_dt = 1.0 / 250.0                  # placeholder
        self.all_motor_q = [0.0] * 35                  # placeholder
        self._current_q = [0.0] * _NUM_ARM_JOINTS      # placeholder
        self._current_dq = [0.0] * _NUM_ARM_JOINTS     # placeholder
        self._calls = []

    # -- the upstream control interface ---------------------------------------------------------------
    def ctrl_dual_arm(self, q_target, tauff_target):
        self._calls.append(("ctrl_dual_arm", {
            "q_target": [float(value) for value in q_target],
            "tauff_target": [float(value) for value in tauff_target],
        }))
        self.q_target = [float(value) for value in q_target]
        self.tauff_target = [float(value) for value in tauff_target]
        # Like the upstream setter, this only stores targets; it does not update measured state.

    def get_current_dual_arm_q(self):
        return list(self._current_q)

    def get_current_dual_arm_dq(self):
        return list(self._current_dq)

    def get_current_motor_q(self):
        all_motor_q = list(self.all_motor_q)
        for index, value in enumerate(self._current_q):
            all_motor_q[15 + index] = value
        return all_motor_q

    def get_mode_machine(self):
        return 0                                       # placeholder

    def clip_arm_q_target(self, target_q, velocity_limit):
        current_q = self.get_current_dual_arm_q()
        delta = [float(target) - float(current) for target, current in zip(target_q, current_q)]
        motion_scale = max((abs(value) for value in delta), default=0.0) / (float(velocity_limit) * self.control_dt)
        return [current + value / max(motion_scale, 1.0) for current, value in zip(current_q, delta)]

    def ctrl_dual_arm_go_home(self):
        # placeholder: a home move, not a stop; the fake jumps to the zero pose
        self.q_target = [0.0] * _NUM_ARM_JOINTS
        self._current_q = list(self.q_target)
        self._current_dq = [0.0] * _NUM_ARM_JOINTS

    def speed_gradual_max(self, t=5.0):
        self._gradual_time = float(t)

    def speed_instant_max(self):
        self.arm_velocity_limit = 30.0                 # placeholder

    # -- hooks for test_driver.py (not upstream members, never used by the driver) -------------------------
    def _set_joint_positions(self, positions):
        self._current_q = [float(value) for value in positions]
        self._current_dq = [0.0] * _NUM_ARM_JOINTS
