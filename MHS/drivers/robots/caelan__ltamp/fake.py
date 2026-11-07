"""Fake backend of the LTAMP simulated PR2: an in-memory stand-in for ``control_tools.pb_controller:PBController``.

It defines only members the upstream class has (PBController and its base Controller, control_tools/controller.py):
``execute_motor_control`` (pb_controller.py:23), ``get_joint_positions`` (47-51), ``get_arm_positions``
(controller.py:39-40), ``command_arm`` (pb_controller.py:161-162) and ``command_torso`` (72-80).  It does not import
PyBullet: joint positions are a dictionary, and a command sets them exactly, as the upstream's kinematic path does when
``execute_motor_control`` is false (pb_controller.py:145-146).  There is no physics, collision, URDF limit or gravity.
The start pose is placeholder data, not the URDF's configuration.
"""

LEFT_ARM = ["l_shoulder_pan_joint", "l_shoulder_lift_joint", "l_upper_arm_roll_joint", "l_elbow_flex_joint",
            "l_forearm_roll_joint", "l_wrist_flex_joint", "l_wrist_roll_joint"]       # controller.py:10-11
RIGHT_ARM = ["r_shoulder_pan_joint", "r_shoulder_lift_joint", "r_upper_arm_roll_joint", "r_elbow_flex_joint",
             "r_forearm_roll_joint", "r_wrist_flex_joint", "r_wrist_roll_joint"]      # controller.py:8-9
TORSO = "torso_lift_joint"                                                               # controller.py:16


class FakePBController:
    def __init__(self, **_options):
        self.execute_motor_control = False                                   # pb_controller.py:23
        self._positions = {name: 0.0 for name in LEFT_ARM + RIGHT_ARM}       # placeholder start pose
        self._positions["l_elbow_flex_joint"] = -0.5                         # placeholder (inside the soft limits)
        self._positions["r_elbow_flex_joint"] = -0.5                         # placeholder
        self._positions["l_wrist_flex_joint"] = -0.5                         # placeholder
        self._positions["r_wrist_flex_joint"] = -0.5                         # placeholder
        self._positions[TORSO] = 0.1                                         # placeholder
        self._commands = []

    @staticmethod
    def _arm_joint_names(arm):
        if arm == "l":
            return LEFT_ARM
        if arm == "r":
            return RIGHT_ARM
        raise ValueError(arm)                                                # controller.py:25-30

    def get_joint_positions(self, joint_names):
        return [self._positions[name] for name in joint_names]

    def get_arm_positions(self, arm):
        return self.get_joint_positions(self._arm_joint_names(arm))

    def command_arm(self, arm, positions, timeout, **kwargs):
        names = self._arm_joint_names(arm)
        values = [float(value) for value in positions]
        if len(values) != len(names):
            raise ValueError("one position per arm joint")
        self._commands.append(("command_arm", arm, values, timeout))
        for name, value in zip(names, values):
            self._positions[name] = value

    def command_torso(self, pose, timeout=2.0, blocking=True):
        self._commands.append(("command_torso", float(pose)))
        self._positions[TORSO] = float(pose)
