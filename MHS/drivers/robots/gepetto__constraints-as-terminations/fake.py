"""Fake backend of the CaT Solo12 driver: a pure Python kinematic stand-in for ``CaTEnv``.

Why a fake: the upstream environment is an Isaac Lab 2.1.0/Isaac Sim simulation with a GPU, and package code never
imports the clone (``README.md:15`` and ``:40-45``).  This module mirrors the *interface* of
``cat_envs.tasks.utils.cat.cat_env:CaTEnv`` (the class the driver names as ``native``): ``step(action)`` returns
``(observation, reward, constraint_probability, time_out, info)``, ``reset()`` returns ``(observation, extras)``, and
the termination manager flags are published as ``reset_terminated`` and ``reset_time_outs`` after a step
(``cat_env.py:94-97`` and ``:146-147``).  The action has one value per Solo12 joint-position actuator and the policy
observation is the concatenation of the six terms of ``cat_flat_env_cfg.py:145-176``.

What this is not: the upstream environment.  The fake is kinematic (F0): it moves a placeholder joint position by a
placeholder fraction of the action, models no physics, contacts, actuators, sensors, noise or constraints, and was
never compared with the upstream simulator.  Every value below that is not cited from the clone is test data and is
marked ``placeholder``.  Nothing here talks to a device.
"""

#: The twelve joint-position actions of cat_flat_env_cfg.py:114-133.
ACTION_DIM = 12
#: The policy vector size of the six concatenated terms (3 + 3 + 3 + 12 + 12 + 12); the fake's values are test data.
OBSERVATION_DIM = 45
#: 10.0 s / (decimation 4 * sim.dt 0.005 s), cat_flat_env_cfg.py:479-484.
EPISODE_STEPS = 500
#: Placeholder kinematic gain: the joint position moves by this fraction of the action value.
STEP_DELTA = 0.01
#: Placeholder reward scale and penalty.
REWARD_BASE = 1.0
REWARD_COST = 0.01


class FakeCaTEnv:
    """A stand-in for ``CaTEnv`` with one environment, plain lists and the same five-value step result."""

    def __init__(self, **options):
        # placeholder: the fake starts every joint at zero.
        self._position = [0.0] * ACTION_DIM
        self._velocity = [0.0] * ACTION_DIM
        self._last_action = [0.0] * ACTION_DIM
        self._steps = 0
        self.reset_terminated = False
        self.reset_time_outs = False

    def _observation(self) -> list:
        """The policy vector: six placeholder terms in the order of cat_flat_env_cfg.py:145-176."""
        base_ang_vel = [0.0, 0.0, 0.0]          # placeholder
        velocity_commands = [0.5, 0.0, 0.0]     # placeholder
        projected_gravity = [0.0, 0.0, -1.0]    # placeholder
        return (base_ang_vel + velocity_commands + projected_gravity
                + list(self._position) + list(self._velocity) + list(self._last_action))

    def reset(self, seed=None, options=None):
        """``CaTEnv.reset`` returns ``(observation, extras)``; the play script reads ``[0]["policy"]``."""
        # placeholder: every reset returns the same start state, so the fake has no seed control.
        self._position = [0.0] * ACTION_DIM
        self._velocity = [0.0] * ACTION_DIM
        self._last_action = [0.0] * ACTION_DIM
        self._steps = 0
        self.reset_terminated = False
        self.reset_time_outs = False
        return {"policy": self._observation()}, {"log": {}}

    def step(self, action):
        """One kinematic CaTEnv step: ``(observation, reward, constraint_probability, time_out, info)``."""
        values = [float(value) for value in action]
        if len(values) != ACTION_DIM:
            raise ValueError(f"the Solo12 action needs {ACTION_DIM} values, got {len(values)}")
        # placeholder: a first-order joint-position update, not the upstream action manager or PhysX.
        for index, value in enumerate(values):
            self._velocity[index] = STEP_DELTA * value
            self._position[index] += self._velocity[index]
        self._last_action = values
        self._steps += 1
        # The upstream sets reset_terminated and reset_time_outs from its termination manager (cat_env.py:94-97).
        self.reset_terminated = False
        self.reset_time_outs = self._steps >= EPISODE_STEPS
        # placeholder: reward and constraint probability are test data, not the upstream reward or constraint manager.
        reward = REWARD_BASE - REWARD_COST * sum(abs(value) for value in values)
        constraint_probability = 0.0
        info = {"log": {}}
        return {"policy": self._observation()}, reward, constraint_probability, self.reset_time_outs, info
