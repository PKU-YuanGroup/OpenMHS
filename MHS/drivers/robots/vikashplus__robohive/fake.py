"""Fake backend of the robohive driver: a pure Python kinematic stand-in for ``FrankaReachFixed-v0``.

Why a fake: the acceptance gate installs neither robohive nor MuJoCo (the card lists "MuJoCo 2.1 binaries and a C
compiler for mujoco-py" as system dependencies) and package code never imports the clone, so the package serves the
registered environment through its own fake.  The class below mirrors the public members of
``robohive.envs.arms.reach_base_v0:ReachBaseV0`` that the bridge and the driver use (``reset``, ``step``, ``get_obs``,
``get_obs_dict``, ``get_reward_dict`` and the ``dt`` property; gate G7), and defines the two spaces the bridge reads
(``action_space`` and ``observation_space``) as duck-typed ``Box`` objects.

What this is not: the upstream MuJoCo environment.  The fake moves joint positions by a fixed gain per normalized
action instead of integrating the rigid-body model, uses Python's ``random.Random`` instead of numpy's generator, and
never computes contacts, actuator forces or sensor noise.  The action bound, the reward rule and the timestep come from
the clone; the kinematics and the array dimensions are test data only (marked ``placeholder``).  The differences are
listed in the driver's ``fidelity.gaps``.

Nothing here talks to a device.
"""

import random

# robohive/envs/env_base.py:97-99: normalize_act=True builds Box(-1, 1) of sim.model.nu elements.
ACTION_LOW = -1.0
ACTION_HIGH = 1.0
# robohive/envs/env_base.py:139: Box(-10, 10) over the observation vector.
OBSERVATION_LOW = -10.0
OBSERVATION_HIGH = 10.0
# robohive/envs/arms/__init__.py:24: the registration comment "50steps*40Skip*2ms" gives a 0.002 s model timestep.
TIMESTEP_S = 0.002
# robohive/envs/arms/reach_base_v0.py:53: ReachBaseV0 defaults frame_skip to 40.
FRAME_SKIP = 40
# robohive/envs/env_base.py:521-522: dt = model timestep * frame_skip.
DT = TIMESTEP_S * FRAME_SKIP
# robohive/envs/arms/__init__.py:24: the registration's max_episode_steps (the TimeLimit wrapper gymnasium.make adds).
MAX_EPISODE_STEPS = 50
# robohive/envs/arms/reach_base_v0.py:22-26: the dense reward weights.
REACH_WEIGHT = -1.0
BONUS_WEIGHT = 4.0
PENALTY_WEIGHT = -50.0
# robohive/envs/arms/reach_base_v0.py:85-96: far_th, the two bonus distances and the solved distance.
FAR_THRESHOLD = 1.0
BONUS_DISTANCE = 0.1
BONUS_DISTANCE_NEAR = 0.05
SOLVED_DISTANCE = 0.05
# robohive/envs/env_base.py:97-99 builds the action space of sim.model.nu elements; the scene model is a submodule,
# so the exact nu is not cited here.
NQ = 9                                          # placeholder: stand-in joint count (the real model is not read)
NU = 9                                          # placeholder: stand-in actuator count
# robohive/envs/arms/reach_base_v0.py:17-19: qp_robot, qv_robot and reach_err.  The width of the first two keys is
# the stand-in joint count, not a device fact.
OBSERVATION_DIM = NQ + NQ + 3

# The remaining numbers are test data of this fake, not facts about the device.
TARGET_LOW = [0.2, 0.3, 1.2]                    # placeholder: the fixed target of the registered variant
TARGET_HIGH = [0.2, 0.3, 1.2]                   # placeholder: high == low for FrankaReachFixed-v0
END_EFFECTOR_BASE = [0.5, 0.0, 1.0]             # placeholder: the stand-in robot site position at zero joints
JOINT_GAIN = 0.1                                # placeholder: joint movement per normalized action unit per tick
INITIAL_NOISE = 0.01                            # placeholder: spread of the stand-in initial joint positions


class Box:
    """Duck-typed one-dimensional ``gym.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeReachBaseV0:
    """The ReachBaseV0 surface without MuJoCo: ``reset`` and ``step`` return what the registered env does."""

    def __init__(self, **options):
        self.action_space = Box([ACTION_LOW] * NU, [ACTION_HIGH] * NU)
        self.observation_space = Box([OBSERVATION_LOW] * OBSERVATION_DIM,
                                     [OBSERVATION_HIGH] * OBSERVATION_DIM)
        self.frame_skip = FRAME_SKIP
        self.np_random = random.Random()
        self._qpos = [0.0] * NQ
        self._qvel = [0.0] * NQ
        self._target = list(TARGET_LOW)
        self._tick = 0
        self._time = 0.0
        self._terminated = False
        self._truncated = False

    @property
    def dt(self):
        return DT

    def reset(self, reset_qpos=None, reset_qvel=None, **kwargs):
        """``ReachBaseV0.reset`` under gymnasium: ``(observation, {})`` (robohive/envs/env_base.py:512-513)."""
        seed = kwargs.get("seed")
        if seed is not None:
            self.np_random = random.Random(int(seed))
        if reset_qpos is None:
            self._qpos = [self.np_random.uniform(-INITIAL_NOISE, INITIAL_NOISE) for _ in range(NQ)]
        else:
            self._qpos = [float(value) for value in reset_qpos]
        self._qvel = [0.0] * NQ if reset_qvel is None else [float(value) for value in reset_qvel]
        self._target = [self.np_random.uniform(low, high)
                        for low, high in zip(TARGET_LOW, TARGET_HIGH)]
        self._tick = 0
        self._time = 0.0
        self._terminated = False
        self._truncated = False
        return self.get_obs(), {}

    def get_obs_dict(self):
        """The observation dictionary of ReachBaseV0 (robohive/envs/arms/reach_base_v0.py:74-81)."""
        end_effector = [base + joint for base, joint in zip(END_EFFECTOR_BASE, self._qpos[:3])]
        return {
            "time": [self._time],
            "qp_robot": list(self._qpos),
            "qv_robot": list(self._qvel),
            "reach_err": [target - position for target, position in zip(self._target, end_effector)],
        }

    def get_obs(self):
        """The obs_keys vector: qp_robot, qv_robot and reach_err (robohive/envs/arms/reach_base_v0.py:17-19)."""
        observation = self.get_obs_dict()
        values = []
        for key in ("qp_robot", "qv_robot", "reach_err"):
            values.extend(observation[key])
        return values

    def get_reward_dict(self, obs_dict):
        """The dense reward of ReachBaseV0 (robohive/envs/arms/reach_base_v0.py:83-96)."""
        reach_dist = sum(value * value for value in obs_dict["reach_err"]) ** 0.5
        bonus = int(reach_dist < BONUS_DISTANCE) + int(reach_dist < BONUS_DISTANCE_NEAR)
        penalty = int(reach_dist > FAR_THRESHOLD)
        reward = {
            "reach": reach_dist,
            "bonus": bonus,
            "penalty": penalty,
            "sparse": -1.0 * reach_dist,
            "solved": reach_dist < SOLVED_DISTANCE,
            "done": reach_dist > FAR_THRESHOLD,
        }
        reward["dense"] = (REACH_WEIGHT * reward["reach"] + BONUS_WEIGHT * reward["bonus"]
                           + PENALTY_WEIGHT * reward["penalty"])
        return reward

    def step(self, a, **kwargs):
        """Clip the action and advance one tick; return the gymnasium five-tuple (robohive/envs/env_base.py:254-282)."""
        action = [min(max(float(value), low), high)
                  for value, low, high in zip(a, self.action_space.low, self.action_space.high)]
        for index in range(NQ):
            # placeholder kinematics: the joint moves by a fixed gain, there is no MuJoCo integration
            self._qpos[index] += JOINT_GAIN * action[index]
            self._qvel[index] = JOINT_GAIN * action[index] / DT
        self._tick += 1
        self._time = self._tick * DT
        obs_dict = self.get_obs_dict()
        reward = self.get_reward_dict(obs_dict)
        self._terminated = bool(reward["done"])
        self._truncated = bool(self._tick >= MAX_EPISODE_STEPS)
        info = {"solved": bool(reward["solved"]), "reach_dist": float(reward["reach"])}
        return self.get_obs(), float(reward["dense"]), self._terminated, self._truncated, info
