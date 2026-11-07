"""Fake backend of the UR5 reaching driver: a pure Python stand-in for ``CoppeliaSim_UR5_gym_v3``.

Why a fake: the upstream constructor opens CoppeliaSim's legacy remote API at 127.0.0.1:19998
(Simulation/CoppeliaSim_env.py:44), loads a ``.ttt`` scene and reads a camera image, so the acceptance gate can
never start it; package code never imports the clone.  This module re-implements the public method surface and
the movement, reward and safety-box rules of ``CoppeliaSim_UR5_gym_v3`` (the class the driver names as
``native``) without the simulator.  Every constant below cites a line of the clone at the pinned commit
513acb7e235ab940fd03c3038208678e285690f3; values chosen only for this stand-in are marked ``# placeholder``.

What this is not: the upstream environment or the CoppeliaSim engine.  The tip position is a toy forward model,
not the simulator's object position; there are no rigid-body dynamics, contacts, actuator, sensor, noise or
camera rendering; the observation is a small test image and the target comes from Python's ``random.Random``
instead of numpy's global generator.  The driver's fidelity ``gaps`` list every difference.

Nothing here talks to a device.
"""

import math
import random

# Simulation/CoppeliaSim_UR5_gym_v3.py:21 (DELTA = pi/180.0)
DELTA = math.pi / 180.0
# Simulation/CoppeliaSim_UR5_gym_v3.py:22
REACH_THRESHOLD = 0.08
# Simulation/CoppeliaSim_UR5_gym_v3.py:26-27
STAY_THRESHOLD = 0.1
STAY_FLAG = 30
# Simulation/CoppeliaSim_UR5_gym_v3.py:35
MAX_STEP = 200
# Simulation/CoppeliaSim_UR5_gym_v3.py:30-32
UR5_GLOBAL_POSITION = [0.4, -0.425, 0.65]     # test data copied from the upstream base coordinate
SAFEBOX_HIGH = [0.72, 0.275, 1.8]
SAFEBOX_LOW = [-0.72, -1.025, 0.66]
# Simulation/CoppeliaSim_UR5_gym_v3.py:33 (MOVE_UNIT = 2 * DELTA)
MOVE_UNIT = 2 * DELTA
# Simulation/CoppeliaSim_UR5_gym_v3.py:38-41
JOINT_LIMITS = [(-math.pi, math.pi), (-math.pi / 2, math.pi / 2),
                (-math.pi, math.pi), (-math.pi, math.pi)]
# Simulation/CoppeliaSim_UR5_gym_v3.py:45-46
ACTION_LOW = [-5.0, -5.0, -5.0, -5.0]
ACTION_HIGH = [5.0, 5.0, 5.0, 5.0]
# Simulation/CoppeliaSim_UR5_gym_v3.py:99
INIT_JOINTS = [0.0, 0.0, 0.0, 0.0, math.pi / 2, 0.0]
# Simulation/CoppeliaSim_UR5_base.py:26-27
TARGET_LOW = [-0.343, -0.737, 0.685]
TARGET_HIGH = [0.041, -0.003, 0.685]
# placeholder: the toy image and the toy link lengths are this fake's own test data
IMAGE_SIZE = 4
IMAGE_MAX = 255
LINK_XY = 0.2
LINK_Z = 0.1
LIFT_Z = 0.1


class _Box:
    """Duck-typed ``gym.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high, shape=None, dtype="float32"):
        self.low = low
        self.high = high
        self.shape = shape or (len(low),)
        self.dtype = dtype


class FakeUR5Env:
    """``CoppeliaSim_UR5_gym_v3`` without CoppeliaSim: ``reset``, ``step`` and the helpers of the clone."""

    def __init__(self, reset_to_pre_if_not_reach=True, random_action="Gussian", scene_path=None, scene_side=None):
        # The upstream stores these options (Simulation/CoppeliaSim_UR5_gym_v3.py:64-65) but the fake never sleeps.
        self.reset_mode = reset_to_pre_if_not_reach
        self.random_action = random_action
        self.scene_path = scene_path
        self.scene_side = scene_side
        self.action_space = _Box(list(ACTION_LOW), list(ACTION_HIGH))          # v3:93-97
        self.observation_space = _Box(0.0, 255.0, shape=(128, 128, 3))         # v3:78-89, real size
        self._rng = random.Random()
        self._target = list(TARGET_LOW)
        self.current_joint_pos = list(INIT_JOINTS)
        self.tip_pos = self._tip_position()
        self.target_pos = list(self._target)
        self.current_dis = self.goal_distance()
        self.last_dis = self.current_dis
        self.num_step = 0
        self.tra_num_step = -1
        self.tra_total_reward = 0.0
        self.stay_loc = []
        self.sf = 0
        self.stuck_flag = False
        self.seed()                                                             # v3:66

    # -- gym environment interface -------------------------------------------------
    def seed(self, seed=None):
        if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int) or seed < 0):
            raise ValueError("seed must be a non-negative integer or None")
        self._rng = random.Random(seed)
        return [seed]

    def reset(self):
        self.stuck_flag = False
        self._set_target()
        self.current_joint_pos = list(INIT_JOINTS)
        self.tip_pos = self._tip_position()
        self.target_pos = list(self._target)
        self.current_dis = self.goal_distance()
        self.num_step = 0                                                       # v3:118
        self.tra_num_step = -1                                                  # v3:119
        self.last_dis = self.current_dis
        self.tra_total_reward = 0.0
        self.stay_loc = []
        self.sf = 0
        return self.get_state()                                                 # v3:124

    def reset_pos(self):
        self._set_target()                                                      # v3:131-135
        self.current_joint_pos = list(INIT_JOINTS)
        self.tip_pos = self._tip_position()
        self.target_pos = list(self._target)
        self.current_dis = self.goal_distance()
        self.last_dis = self.current_dis
        self.tra_num_step = -1
        self.stay_loc = []
        self.tra_total_reward = 0.0
        self.sf = 0
        return self.get_state()

    def get_state(self):
        return self._image()                                                    # v3:158-162

    def step(self, action):
        self.apply_action(action)                                               # v3:165
        if not self.stuck_flag:
            done, step_end_status = self.check_done()
            if step_end_status == 2:
                reward = -150                                                   # v3:171-174
                next_state = self.get_state()
                self.reset_pos()
            elif step_end_status == 3:
                self.current_dis = self.goal_distance()
                reward = (self.last_dis - self.current_dis) * 100                 # v3:176-181
                next_state = self.get_state()
                self.last_dis = self.current_dis
                self.reset_pos()
            else:
                self.current_dis = self.goal_distance()
                next_state = self.get_state()
                reward = (self.last_dis - self.current_dis) * 100                 # v3:183-196
                self.last_dis = self.current_dis
                self.tra_total_reward += reward
                if step_end_status == 1 and self.tra_num_step != 0:
                    reward += 2000 / self.tra_num_step
                    self.reset_pos()
        else:
            next_state = self.get_state()
            done = False
            step_end_status = 2
            reward = -50                                                        # v3:198-205
            self.stuck_flag = False
            self.reset_pos()
        return next_state, reward, done, {"step_end_status": step_end_status}  # v3:207

    # -- helpers of the clone ------------------------------------------------------
    def apply_action(self, action):
        for index in range(4):                                                  # v3:210-218
            self.current_joint_pos[index] += float(action[index]) * MOVE_UNIT
        self.tip_pos = self._tip_position()
        self.stay_loc.append(list(self.tip_pos))
        self.tra_num_step += 1                                                  # v3:231

    def goal_distance(self, goal_a=None, goal_b=None):
        here = self.tip_pos if goal_a is None else goal_a
        there = self.target_pos if goal_b is None else goal_b
        return math.sqrt(sum((here[i] - there[i]) ** 2 for i in range(3)))

    def check_done(self):
        ax, ay, az = self.tip_pos
        if self.current_dis <= REACH_THRESHOLD:                                 # v3:237-239
            return False, 1
        if self.num_step >= MAX_STEP:                                           # v3:241-243
            return True, 2
        if ax <= SAFEBOX_LOW[0] or ax >= SAFEBOX_HIGH[0]:                       # v3:247-253
            return False, 2
        if ay <= SAFEBOX_LOW[1] or ay >= SAFEBOX_HIGH[1]:                       # v3:254-259
            return False, 2
        if az <= SAFEBOX_LOW[2] or az >= SAFEBOX_HIGH[2]:                       # v3:260-265
            return False, 2
        for index, (low, high) in enumerate(JOINT_LIMITS):                      # v3:269-297
            if self.current_joint_pos[index] <= low or self.current_joint_pos[index] >= high:
                return False, 2
        if self.tra_num_step >= STAY_FLAG:                                      # v3:299-300
            return self.check_stay()
        return False, 0                                                         # v3:303

    def check_stay(self):
        sf = 0
        for index in range(30):                                                # v3:323
            here = self.stay_loc[self.tra_num_step]
            there = self.stay_loc[self.tra_num_step - index]
            if math.sqrt(sum((here[i] - there[i]) ** 2 for i in range(3))) <= STAY_THRESHOLD:
                sf += 1
        if sf >= 25:                                                            # v3:327-329

            return False, 3
        return False, 0

    def _set_target(self):
        self._target = [self._rng.uniform(TARGET_LOW[i], TARGET_HIGH[i]) for i in range(3)]   # base:111-113

    def _tip_position(self):
        q0, q1 = self.current_joint_pos[0], self.current_joint_pos[1]
        # placeholder: a toy forward model, not the simulator's object position
        return [UR5_GLOBAL_POSITION[0] + LINK_XY * math.cos(q0) * math.cos(q1),
                UR5_GLOBAL_POSITION[1] + LINK_XY * math.sin(q0) * math.cos(q1),
                UR5_GLOBAL_POSITION[2] + LIFT_Z + LINK_Z * math.sin(q1)]

    def _image(self):
        # placeholder: a small deterministic test image; the upstream camera returns 128x128x3
        q0, q1 = self.current_joint_pos[0], self.current_joint_pos[1]
        tx, ty, tz = self.target_pos
        image = []
        for row in range(IMAGE_SIZE):
            row_values = []
            for column in range(IMAGE_SIZE):
                row_values.append([
                    int((math.sin(q0 + tx + row) + 1) * (IMAGE_MAX / 2)) % IMAGE_MAX,
                    int((math.sin(q1 + ty + column) + 1) * (IMAGE_MAX / 2)) % IMAGE_MAX,
                    int((math.sin(tz + row + column) + 1) * (IMAGE_MAX / 2)) % IMAGE_MAX,
                ])
            image.append(row_values)
        return image
