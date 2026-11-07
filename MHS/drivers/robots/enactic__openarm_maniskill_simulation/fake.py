"""Fake backend of the OpenArm PickCube-v1 driver: a pure Python stand-in for the environment object.

Why a fake: the upstream files are an overlay that is copied into a ManiSkill v3.0.0b21 checkout (README.md:41-56),
and ManiSkill, SAPIEN, torch and numpy are not installed where the gate runs; package code never imports or runs the
clone.  This module therefore stands in for ``mani_skill.envs.tasks.tabletop.pick_cube:PickCubeEnv`` (the class named
by ``native``) with the cube, goal, tool-centre-point (TCP), gripper and reward rules of the clone.

What is modelled (each value cites the line it comes from, and is test data, not a device Fact):

* the cube and goal placement of ``_initialize_episode`` (pick_cube.py:120-140) with the openarm configuration
  (pick_cube_cfgs.py:70-80);
* the success predicate of ``evaluate`` (pick_cube.py:163-175), with the fake's ``is_robot_static`` always true
  because the fake has no joint velocities;
* the dense reward of ``compute_dense_reward`` (pick_cube.py:177-202), with a zero joint velocity;
* the 50-step episode limit of ``@register_env("PickCube-v1", max_episode_steps=50)`` (pick_cube.py:34);
* the gripper opening range and end-effector delta range of the OpenArm controller configs (openarm.py:100-109 and
  :183-190).

What is not modelled: SAPIEN rigid-body physics, contacts, the seven arm joints and their controller, the robot URDF,
the camera observations and the full state observation ManiSkill adds.  The TCP and cube move with placeholder
kinematics, the grasp test is a distance test rather than the contact-force test of ``OpenArm.is_grasping``
(openarm.py:255-286), and no trajectory was compared with the upstream simulator.  Every number below is test data
and is marked ``# placeholder``.

The public methods are names that occur on ``PickCubeEnv`` in the clone (``evaluate`` and ``compute_dense_reward``
are defined there) or occur elsewhere in the clone's text (``reset``, ``step``, ``close``); the driver calls nothing
else.
"""

import math
import random

# pick_cube_cfgs.py:70-80 (the openarm entry of PICK_CUBE_CONFIGS)
CUBE_HALF_SIZE = 0.02                          # placeholder: cube half-size in metres
GOAL_THRESH = 0.025                            # placeholder: success distance in metres
SPAWN_HALF_SIZE = 0.05                         # placeholder: cube and goal xy half-range in metres
SPAWN_CENTER = (0.0, 0.0)                      # placeholder: cube and goal xy centre in metres
MAX_GOAL_HEIGHT = 0.3                          # placeholder: goal z draw height in metres
# pick_cube.py:34: max_episode_steps=50
MAX_EPISODE_STEPS = 50                         # placeholder: steps per episode
# openarm.py:183-190: the gripper joint position range [0, 0.0451]
GRIPPER_OPEN = 0.0451                          # placeholder: open gripper position in metres
# openarm.py:100-109: the end-effector delta position range [-0.1, 0.1]
MAX_TCP_DELTA = 0.1                            # placeholder: per-axis TCP delta bound in metres
# below are the fake's kinematic test parameters, not upstream values
TCP_START_HEIGHT = 0.1                         # placeholder: TCP start height above the cube in metres
GRASP_GRIPPER = 0.01                           # placeholder: gripper position that counts as closed, in metres
GRASP_DISTANCE = 0.01                          # placeholder: TCP-to-cube distance that counts as a grasp, in metres
TOUCH_DISTANCE = 0.005                         # placeholder: extra reach for the placeholder grasp test
IDENTITY_QUAT = (0.0, 0.0, 0.0, 1.0)          # placeholder: TCP and cube orientation used by the fake


def _distance(first, second):
    """Euclidean distance of two 3-vectors."""
    return math.sqrt(sum((float(a) - float(b)) ** 2 for a, b in zip(first, second)))


class FakePickCubeEnv:
    """PickCube-v1 for the OpenArm without SAPIEN: ``reset``, ``step``, ``evaluate`` and ``compute_dense_reward``.

    The fake keeps a cube position, a goal position, a TCP position and a gripper opening.  A step moves the TCP by
    the commanded delta; the cube follows the TCP when the gripper is closed and the TCP is at the cube.  The reward
    and success rules are those of the clone, evaluated on that placeholder state.
    """

    def __init__(self, **options):
        self.options = dict(options)                          # placeholder: the fake takes the clone's keywords
        self._seed = 0                                        # placeholder: first reset seed
        self._rng = random.Random(self._seed)
        self._cube = [0.0, 0.0, CUBE_HALF_SIZE]               # placeholder
        self._goal = [0.0, 0.0, CUBE_HALF_SIZE]               # placeholder
        self._tcp = [0.0, 0.0, CUBE_HALF_SIZE + TCP_START_HEIGHT]   # placeholder
        self._gripper = GRIPPER_OPEN                          # placeholder
        self._tick = 0
        self._episode = 0
        self._terminated = False
        self._truncated = False
        self._closed = False

    # -- state ---------------------------------------------------------------
    def _is_grasped(self):
        """A placeholder grasp test: the gripper is closed and the TCP is at the cube.

        The upstream ``OpenArm.is_grasping`` uses the pairwise contact forces and an 85 degree contact angle
        (openarm.py:255-286); the fake has no contacts, so it approximates with distance.
        """
        return (self._gripper <= GRASP_GRIPPER
                and _distance(self._tcp, self._cube) <= CUBE_HALF_SIZE + GRASP_DISTANCE + TOUCH_DISTANCE)

    def _observation(self):
        """The observation members the clone's ``_get_obs_extra`` fills in (pick_cube.py:148-161)."""
        cube_pose = list(self._cube) + list(IDENTITY_QUAT)      # placeholder
        tcp_pose = list(self._tcp) + list(IDENTITY_QUAT)        # placeholder
        return {
            "is_grasped": bool(self._is_grasped()),
            "tcp_pose": tcp_pose,
            "goal_pos": list(self._goal),
            "obj_pose": cube_pose,
            "tcp_to_obj_pos": [self._cube[i] - self._tcp[i] for i in range(3)],
            "obj_to_goal_pos": [self._goal[i] - self._cube[i] for i in range(3)],
        }

    # -- public surface ------------------------------------------------------
    def reset(self, seed=None, options=None):
        """Start a new episode, drawing the cube and goal poses like ``_initialize_episode`` (pick_cube.py:120-140).

        The draw uses Python's ``random.Random`` with the supplied seed; the upstream draws from torch's generator,
        so one seed does not produce the same positions on the two.
        """
        if seed is not None:
            self._seed = int(seed)
            self._rng = random.Random(self._seed)
        self._cube = [
            SPAWN_CENTER[0] + self._rng.uniform(-SPAWN_HALF_SIZE, SPAWN_HALF_SIZE),      # placeholder
            SPAWN_CENTER[1] + self._rng.uniform(-SPAWN_HALF_SIZE, SPAWN_HALF_SIZE),      # placeholder
            CUBE_HALF_SIZE,                                                             # placeholder
        ]
        self._goal = [
            SPAWN_CENTER[0] + self._rng.uniform(-SPAWN_HALF_SIZE, SPAWN_HALF_SIZE),      # placeholder
            SPAWN_CENTER[1] + self._rng.uniform(-SPAWN_HALF_SIZE, SPAWN_HALF_SIZE),      # placeholder
            self._rng.random() * MAX_GOAL_HEIGHT + self._cube[2],                       # placeholder
        ]
        self._tcp = [self._cube[0], self._cube[1], self._cube[2] + TCP_START_HEIGHT]    # placeholder
        self._gripper = GRIPPER_OPEN                                                     # placeholder
        self._tick = 0
        self._episode += 1
        self._terminated = False
        self._truncated = False
        return self._observation()

    def step(self, action):
        """Apply one placeholder transition and return the environment's five-tuple.

        ``action`` is ``{"tcp_delta": [dx, dy, dz], "gripper": opening}``.  The cube follows the TCP only when the
        TCP was already grasping it at the start of the step; no contact or friction is computed.
        """
        delta = [float(value) for value in action["tcp_delta"]]
        opening = float(action["gripper"])
        if len(delta) != 3:
            raise AssertionError(f"the fake takes a 3-element tcp_delta, got {len(delta)}")
        for index in range(3):
            if abs(delta[index]) > MAX_TCP_DELTA + 1e-12:
                raise AssertionError(f"the fake takes a tcp_delta of at most {MAX_TCP_DELTA} m per axis")
        was_grasped = self._is_grasped()
        for index in range(3):
            self._tcp[index] += delta[index]                       # placeholder: kinematic TCP motion
            if was_grasped:
                self._cube[index] += delta[index]                  # placeholder: the held cube follows the TCP
        self._gripper = opening
        self._tick += 1
        self._terminated = False
        self._truncated = self._tick >= MAX_EPISODE_STEPS           # pick_cube.py:34
        info = self.evaluate()
        reward = self.compute_dense_reward(None, action, info)
        return self._observation(), reward, self._terminated, self._truncated, info

    def evaluate(self):
        """The clone's success predicate (pick_cube.py:163-175) on the fake's placeholder state.

        ``is_robot_static`` is always true because the fake has no joint velocity; the real predicate reads
        ``OpenArm.is_static(0.2)`` (openarm.py:288-290).
        """
        is_obj_placed = _distance(self._goal, self._cube) <= GOAL_THRESH       # placeholder
        is_robot_static = True                                                  # placeholder: no qvel in the fake
        is_grasped = self._is_grasped()
        return {
            "success": bool(is_obj_placed and is_robot_static),
            "is_obj_placed": bool(is_obj_placed),
            "is_robot_static": bool(is_robot_static),
            "is_grasped": bool(is_grasped),
        }

    def compute_dense_reward(self, obs, action, info):
        """The clone's dense reward (pick_cube.py:177-202) with a zero joint velocity."""
        tcp_to_obj_dist = _distance(self._cube, self._tcp)                      # placeholder
        reaching_reward = 1 - math.tanh(5 * tcp_to_obj_dist)                    # placeholder: factor 5
        reward = reaching_reward
        is_grasped = float(bool(info["is_grasped"]))
        reward += is_grasped
        obj_to_goal_dist = _distance(self._goal, self._cube)                    # placeholder
        place_reward = 1 - math.tanh(5 * obj_to_goal_dist)                      # placeholder: factor 5
        reward += place_reward * is_grasped
        static_reward = 1.0                                                     # placeholder: qvel is zero
        reward += static_reward * float(bool(info["is_obj_placed"]))
        if info["success"]:
            reward = 5.0                                                        # pick_cube.py:201
        return float(reward)

    def close(self):
        """Mark the environment closed (the upstream BaseEnv.close is outside the clone)."""
        self._closed = True
