"""Fake backend of the HumanoidToolBench driver: a pure Python stand-in for ``humanoidtoolbench/G1BallMove-L0-S``.

Why a fake: the acceptance gate cannot import the upstream package (it needs MuJoCo 3.11.0, torch 2.7.0, gear_sonic
and decoupled-wbc, ``pyproject.toml:8-22``), and package code never imports the clone.  This module models the
Gymnasium contract of the registered environment ``humanoidtoolbench/G1BallMove-L0-S`` without MuJoCo:

* the action space is the task controller's ``Dict`` of seven joint-position ``Box`` spaces, 43 whole-body joints in
  the order left leg, right leg, waist, left arm, right arm, left hand, right hand
  (``src/humanoidtoolbench/robots/controllers/combo.py:44-56``, ``robots/g1_sonic.py:32-94,118``);
* the leg, waist and arm groups are bounded by -1 to 1 (``controllers/qpos.py:22-23``) and the two hand groups by
  -pi to pi (``controllers/eef.py:18-22``);
* the observation is the 43-value ``joint_qpos`` stream that the environment reads from the simulator
  (``envs/sonic_loco_manip.py:44-48``); the real observation also adds four 640 by 360 by 3 camera streams
  (``tasks/g1_toolbench_tabletop.py:38-41,86-120``), which this fake omits (driver ``fidelity.gaps``);
* ``reset(seed, options)`` returns ``(observation, info)`` and ``step(action)`` returns
  ``(observation, reward, terminated, truncated, info)`` like the upstream class (``envs/sonic_loco_manip.py:57-99``);
* the registered 3000-step episode limit is applied as truncation (``envs/__init__.py:27-37``), because the fake
  stands in for ``gymnasium.make`` and the registration wraps the environment in a ``TimeLimit``.

What this is not: the MuJoCo environment.  The fake is kinematic: it copies the commanded joint values into the
observation; every dynamic, contact, object, success, reward and camera behaviour is absent, and the numeric values it
returns are test data (marked ``# placeholder`` where they are not a sourced constant).  It was never compared with the
upstream environment.  Nothing here talks to a device.
"""

import math

# The task metadata: physics_dt 0.005 s, render_hz 50 (tasks/g1_toolbench_tabletop.py:70-73).
PHYSICS_DT_S = 0.005
RENDER_HZ = 50
# The environment's decimation: int((1/physics_dt)/render_hz) = 4 (envs/sonic_loco_manip.py:70,78).
CONTROL_DECIMAL = int((1.0 / PHYSICS_DT_S) / RENDER_HZ)
# The registration's max_episode_steps=3000 (envs/__init__.py:27-37).
MAX_EPISODE_STEPS = 3000

# The seven controller action members and their DoF counts (robots/controllers/combo.py:44-56,
# robots/g1_sonic.py:32-94,131-159).  The order is the controller Dict order and the WHOLE_BODY_JOINTS order.
JOINT_GROUPS = (
    ("left_leg", 6),
    ("right_leg", 6),
    ("waist", 3),
    ("left_arm", 7),
    ("right_arm", 7),
    ("left_eef", 7),
    ("right_eef", 7),
)
WHOLE_BODY_DOF = sum(size for _, size in JOINT_GROUPS)  # 43 (robots/g1_sonic.py:118)
# PDJointPosController._get_joint_limits is [[-1.0, 1.0]] per joint (controllers/qpos.py:22-23); the hand controllers use
# -pi to pi (controllers/eef.py:18-22).
BODY_LIMIT = 1.0
HAND_LIMIT = math.pi


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``.

    A scalar ``low``/``high`` with a shape bounds every element by the same pair; the real controller Boxes are built
    from one ``[[-1.0, 1.0]] * dof`` (or ``[[-pi, pi]] * dof``) array, so the scalar is the same bound written once.
    """

    def __init__(self, low, high, shape=None, dtype="float32"):
        self.low = low
        self.high = high
        self.shape = tuple(shape) if shape is not None else (1,)
        self.dtype = dtype


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the bridge reads ``spaces`` as a mapping."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


def _body_box(size):
    return Box(-BODY_LIMIT, BODY_LIMIT, (size,))


def _hand_box(size):
    return Box(-HAND_LIMIT, HAND_LIMIT, (size,))


class FakeSonicLocoManipEnv:
    """The G1BallMove-L0-S Gymnasium contract without MuJoCo: ``reset``, ``step``, ``render`` and ``close`` only."""

    def __init__(self, **_options):
        # The controller's Dict of seven Box spaces (robots/controllers/combo.py:44-56).  Each group is one Box of the
        # joint positions of that group; the bounds are the controllers' (qpos.py:22-23, eef.py:18-22).
        self.action_space = Dict(
            {
                "left_leg": _body_box(6),
                "right_leg": _body_box(6),
                "waist": _body_box(3),
                "left_arm": _body_box(7),
                "right_arm": _body_box(7),
                "left_eef": _hand_box(7),
                "right_eef": _hand_box(7),
            }
        )
        # The real observation space starts with joint_qpos, a Box from -pi to pi with shape wholebody_dof
        # (tasks/g1_toolbench_tabletop.py:165-174).  The four camera spaces of the real environment are not modelled.
        self.observation_space = Dict(
            {"joint_qpos": Box(-math.pi, math.pi, (WHOLE_BODY_DOF,))}
        )
        # The evaluator turns image observations off while the robot stabilizes (envs/sonic_loco_manip.py:40-42); the
        # fake never renders and keeps them off.
        self.render_obs = False
        self.control_decimal = CONTROL_DECIMAL                 # envs/sonic_loco_manip.py:70
        self.step_count = 0                                    # envs/sonic_loco_manip.py:71
        self._physics_steps = 0
        self._seed = None
        self._qpos = [0.0] * WHOLE_BODY_DOF                    # placeholder: the controller init_qpos is all zero
        self._closed = False

    # -- helpers -----------------------------------------------------------------
    def _action_values(self, action):
        """Flatten the controller Dict into the 43 joint values in the observation order."""
        if not isinstance(action, dict):
            raise TypeError(f"the action must be a Dict object, got {type(action).__name__}")
        values = []
        for name, size in JOINT_GROUPS:
            group = action.get(name)
            if not isinstance(group, (list, tuple)) or len(group) != size:
                raise ValueError(f"the action member {name!r} must be a list of {size} values")
            if any(isinstance(value, bool) for value in group):
                raise ValueError(f"the action member {name!r} must contain numbers")
            values.extend(float(value) for value in group)
        return values

    def _observation(self):
        return {"joint_qpos": list(self._qpos)}

    def _info(self):
        # The upstream info carries object poses and proprio (envs/sonic_loco_manip.py:50-55); the fake models neither.
        # The booleans are placeholders: no success or failure predicate is modelled.
        return {"success": False, "failure": False, "metrics": {}}

    # -- the public members the upstream class has (gate G7) ----------------------
    def reset(self, *, seed=None, options=None):
        """Gymnasium reset: zero the joint state and return ``(observation, info)``."""
        del options   # placeholder: no reset option is modelled
        if seed is not None:
            self._seed = int(seed)
        self._qpos = [0.0] * WHOLE_BODY_DOF    # placeholder: the controller init_qpos is all zero
        self.step_count = 0
        self._physics_steps = 0
        return self._observation(), self._info()

    def step(self, action):
        """Apply one control action and return the next observation, reward, flags and info."""
        values = self._action_values(action)
        # The upstream calls apply_action and mujoco.step control_decimal times (envs/sonic_loco_manip.py:77-80).
        # The fake simply holds the commanded joint values over those substeps; it has no dynamics.
        for _ in range(self.control_decimal):
            self._qpos = list(values)          # placeholder: kinematic copy, not a MuJoCo integration
            self._physics_steps += 1
        self.step_count += 1
        truncated = self.step_count >= MAX_EPISODE_STEPS    # envs/__init__.py:27-37
        reward = 0.0                           # placeholder: the task reward is not modelled
        ended = False                          # placeholder: the task success/failure predicates are not modelled
        return self._observation(), reward, ended, truncated, self._info()

    def render(self):
        """The real render returns camera frames (envs/sonic_loco_manip.py:101-105); the fake returns none."""
        return {}

    def close(self):
        self._closed = True
