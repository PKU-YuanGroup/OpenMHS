"""Preserve ABC reset metadata through the synchronous Gymnasium bridge.

abc_sim/env.py:375-378 returns RandomizationState in reset info. Its source-backed JSON conversion is
abc_sim/randomization/core.py:65-72. The bridge accepts JSON data, so both factories use this adapter.
Only connect() imports the upstream package; fake checks never call it.
"""

from collections.abc import Mapping

from mhs.bridge.base import jsonable


class ResetInfoAdapter:
    """Forward the environment API and convert its one documented non-JSON info value."""

    def __init__(self, env):
        self.env = env
        self.action_space = env.action_space
        self.observation_space = env.observation_space

    def reset(self, *, seed=None, options=None, randomize=True):
        observation, info = self.env.reset(seed=seed, options=options, randomize=randomize)
        info = dict(info)
        state = info.get("randomization")
        if state is not None:
            # Never stringify, suppress or replace a failed native metadata conversion.
            info["randomization"] = dict(state) if isinstance(state, Mapping) else state.to_dict()
        return observation, jsonable(info)

    def step(self, action, *, render_obs=True):
        return self.env.step(action, render_obs=render_obs)

    def step_chunk(self, action_chunk):
        return self.env.step_chunk(action_chunk)

    def get_obs(self):
        return self.env.get_obs()

    def get_init_q(self):
        return self.env.get_init_q()

    def forget_arm_state(self):
        return self.env.forget_arm_state()

    def close(self):
        return self.env.close()


def connect(**options):
    """Construct the upstream simulator through abc_sim/__init__.py:125-140, :278-326."""
    from abc_sim import make_env

    return ResetInfoAdapter(make_env(**options))
