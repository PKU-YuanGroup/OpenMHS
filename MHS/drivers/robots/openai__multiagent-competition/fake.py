"""Fake backend of the gym-compete driver: a pure Python stand-in for ``run-to-goal-ants-v0``.

Why a fake: the acceptance gate runs without the legacy ``gym`` 0.9.1 and ``mujoco-py`` 0.5.7 stack
(``requirements.txt`` of the clone), and package code never imports or runs the clone.  This module re-implements only
the *interface* of ``gym_compete.new_envs:MultiAgentEnv`` at commit
b2e081a192429913b7d21a89525901d59c85e7f3: a Tuple action space of one Box per ant, a Tuple observation space of one
Box per ant, ``reset()``, ``seed()`` and ``step()`` (gate G7 checks these names against the upstream class).

The shapes come from the clone, not from a guess:

* two agents (``gym-compete/gym_compete/__init__.py:7`` registers two ``ant`` agents);
* eight actuators per ant with ctrlrange -1.0 .. 1.0
  (``gym-compete/gym_compete/new_envs/assets/ant_body.xml:56-64``, read by
  ``gym-compete/gym_compete/new_envs/agents/agent.py:50-75``);
* one observation per ant is its 15-value qpos, 14-value qvel, 78-value external contact force (13 bodies x 6) and
  the other agent's 15-value qpos = 122 values
  (``gym-compete/gym_compete/new_envs/agents/ant.py:48-61``);
* the frame is advanced 50 ms per environment step: the ant scene XML sets the MuJoCo timestep to 0.01 s
  (``world_body.ant_body.ant_body.xml:4``) and ``MultiAgentScene`` passes frame_skip 5
  (``new_envs/multi_agent_scene.py:12``).

What this is not: the MuJoCo environment.  There is no rigid-body integration, no contact solver, no actuator model,
no rendering and no goal logic.  ``step`` moves each ant kinematically from the mean of its eight controls and the
hinge coordinates from the controls; the observation carries zero external contact forces.  ``reset`` draws a small
joint offset from Python's ``random.Random``; upstream draws from gym/MuJoCo's generator, so a seed does not give the
same trajectory on the two.  These differences are listed in the driver's fidelity ``gaps``.

The upstream ``_reset`` returns a bare observation tuple and ``_step`` returns per-agent reward and done tuples.  The
Gymnasium bridge reads a reset two-tuple as ``(observation, info)`` and a step four-tuple as
``(observation, reward, done, info)`` with scalar reward/done, so this fake returns ``(observation, {})`` and a summed
reward / any-done flag, keeping the per-agent values in ``info``.  Nothing here talks to a device.
"""

import random

#: Controls per ant (new_envs/assets/ant_body.xml:56-64).
ACTION_DIM = 8
#: qpos values per free-floating ant: 7 for the free root joint plus 8 hinge joints.
QPOS_DIM = 15
#: qvel values per free-floating ant: 6 for the free root joint plus 8 hinge joints.
QVEL_DIM = 14
#: Bodies in one ant scene before prefixing: 13 (new_envs/assets/ant_body.xml:7-54).
BODY_COUNT = 13
#: External contact force values per body (MuJoCo cfrc_ext is 6 per body).
CFRC_DIM = BODY_COUNT * 6
#: One observation per ant: qpos + qvel + cfrc_ext + the other ant's qpos.
OBS_DIM = QPOS_DIM + QVEL_DIM + CFRC_DIM + QPOS_DIM
#: One environment step is five 10 ms MuJoCo integrations (scene XML timestep 0.01, frame_skip 5).
DT = 0.05                                       # seconds per environment step
#: Placeholder start state: the real registration passes init_pos [(-1, 0, 0.75), (1, 0, 0.75)].
START_X = (-1.0, 1.0)                           # placeholder
START_Z = 0.75                                  # placeholder
RESET_NOISE = 0.01                              # placeholder
FORWARD_SCALE = 0.1                             # placeholder


class Box:
    """Duck-typed one-dimensional ``gym.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class Tuple:
    """Duck-typed ``gym.spaces.Tuple``: one sub-space per agent (``multi_agent_env.py:103-111``)."""

    def __init__(self, spaces):
        self.spaces = list(spaces)
        self.shape = (len(self.spaces),)
        self.dtype = "object"


class FakeMultiAgentEnv:
    """Two ant agents with the public interface of ``MultiAgentEnv`` (G7), not its MuJoCo dynamics."""

    def __init__(self, **_options):
        self.n_agents = 2
        action = Box([-1.0] * ACTION_DIM, [1.0] * ACTION_DIM)
        self.action_space = Tuple([action for _ in range(self.n_agents)])
        observation = Box([-float("inf")] * OBS_DIM, [float("inf")] * OBS_DIM)
        self.observation_space = Tuple([observation for _ in range(self.n_agents)])
        self._seed = 0
        self._rng = random.Random(self._seed)
        self._tick = 0
        self._qpos = []
        self._qvel = []
        self._cfrc = []
        self._reset_state()

    @property
    def dt(self):
        """The environment step in seconds (``multi_agent_env.py:176-178`` delegates to the scene)."""

        return DT

    def seed(self, seed=None):
        """Seed the next reset (the legacy ``gym.Env.seed`` path the bridge falls back to)."""

        self._seed = 0 if seed is None else int(seed)
        self._rng = random.Random(self._seed)
        return [self._seed]

    def reset(self, margins=None):
        """Reset the two worlds and return ``(observation, info)`` for the bridge (see the module docstring)."""

        self._reset_state()
        self._tick = 0
        return self._observation(), {}

    def step(self, action):
        """Apply one control per ant and return ``(observation, reward, terminated, info)``."""

        controls = [list(item) for item in action]
        if len(controls) != self.n_agents:
            raise ValueError(f"expected {self.n_agents} actions, got {len(controls)}")
        agent_rewards = []
        for index, control in enumerate(controls):
            if len(control) != ACTION_DIM:
                raise ValueError(f"expected {ACTION_DIM} controls per ant, got {len(control)}")
            values = [float(value) for value in control]
            qpos, qvel = self._qpos[index], self._qvel[index]
            forward = sum(values) / ACTION_DIM * FORWARD_SCALE       # placeholder kinematics
            qvel[0] = forward
            qpos[0] += forward * DT
            for joint, value in enumerate(values):
                qvel[6 + joint] = value
                qpos[7 + joint] += value * DT
            agent_rewards.append(0.0)
        self._tick += 1
        info = {"agent_rewards": agent_rewards, "n_agents": self.n_agents, "tick": self._tick}
        return self._observation(), sum(agent_rewards), False, info

    def _reset_state(self):
        self._qpos = []
        self._qvel = []
        self._cfrc = []
        for index in range(self.n_agents):
            qpos = [START_X[index], 0.0, START_Z, 1.0, 0.0, 0.0, 0.0]
            qpos.extend(self._rng.uniform(-RESET_NOISE, RESET_NOISE) for _ in range(ACTION_DIM))
            self._qpos.append(qpos)
            self._qvel.append([0.0] * QVEL_DIM)
            self._cfrc.append([0.0] * CFRC_DIM)

    def _observation(self):
        observations = []
        for index in range(self.n_agents):
            other = self._qpos[1 - index] if self.n_agents == 2 else []
            observations.append(self._qpos[index] + self._qvel[index] + self._cfrc[index] + list(other))
        return tuple(observations)
