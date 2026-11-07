"""Fake backend of the OT-2 twin driver: a pure Python kinematic stand-in for ``src.ot2.ot2_gym_wrapper:OT2Env``.

Why a fake: the gate never imports the upstream clone, and the upstream environment imports gymnasium, numpy and
pybullet (requirements.txt:1-17); gymnasium and pybullet are not installed where the gate runs.  This module therefore
re-implements the interface of ``OT2Env`` (the class the driver names as ``native``) without those packages.  The
public members are the ones ``OT2Env`` has (``reset``, ``step``, ``render``, ``close``; gate G7) and the one space
class duck-types ``gymnasium.spaces.Box``.

What this is not: the upstream environment.  The upstream ``step`` runs one PyBullet simulation step through
``Simulation.run`` (sim_class.py:225-232); this fake applies a direct kinematic position update with a fixed
placeholder length and has no physics, contacts, droplets, rendering or simulated clock.  The differences are all
listed in the fidelity ``gaps`` of the driver.  The goal draw and the reward/termination/truncation rules follow
``src/ot2/ot2_gym_wrapper.py`` at commit a0a621e5a79c32e70c8c97864d256693d3b3eac0.

Nothing here talks to a device.
"""

import math
import random

# src/ot2/ot2_gym_wrapper.py:16-17: the bounds of the uniform goal draw (the working envelope of the pipette)
LOW = [-0.1875, -0.1705, 0.1196]
HIGH = [0.2535, 0.2195, 0.2895]
# src/ot2/sim_class.py:66 (pipette offset), :109 (robot base z 0.03) and :173-186 (base + offset with joints at 0):
# the first agent's pipette position on a fresh simulation
START = [0.073, 0.0895, 0.1195]  # placeholder: the fake's initial pipette position
# no upstream text states a kinematic step size; the fake moves by this much per transition
STEP = 0.01  # placeholder: fake travel per step, not a property of the upstream twin


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeOT2Env:
    """Kinematic stand-in for ``OT2Env``: the same reset/step tuple contract, without PyBullet."""

    def __init__(self, render=False, max_steps=1000):
        self._render = render
        self.max_steps = max_steps  # src/ot2/ot2_gym_wrapper.py:19-22
        # src/ot2/ot2_gym_wrapper.py:26-33: the action and observation spaces of the wrapper
        self.action_space = Box([-1.0, -1.0, -1.0], [1.0, 1.0, 1.0])
        self.observation_space = Box([-math.inf] * 6, [math.inf] * 6)
        self.goal_position = None
        self.steps = 0
        self._position = list(START)
        self._rng = random.Random()

    def reset(self, seed=None):
        """Reset the position and draw a goal, like ``OT2Env.reset`` (src/ot2/ot2_gym_wrapper.py:38-53)."""
        if seed is not None:
            self._rng = random.Random(seed)  # upstream seeds numpy's global generator (:39-40)
        self._position = list(START)
        self.goal_position = [self._rng.uniform(low, high) for low, high in zip(LOW, HIGH)]  # placeholder draw
        self.steps = 0
        return list(self._position) + list(self.goal_position), {}

    def step(self, action):
        """Apply one velocity action, like ``OT2Env.step`` (src/ot2/ot2_gym_wrapper.py:55-81)."""
        velocity = [float(value) for value in action]
        if len(velocity) != 3:
            raise ValueError(f"the action space is a 3-vector, got {len(velocity)} values")
        self._position = [position + value * STEP for position, value in zip(self._position, velocity)]
        self.steps += 1
        observation = list(self._position) + list(self.goal_position)
        distance = math.dist(self._position, self.goal_position)
        reward = -distance
        terminated = False
        if distance < 0.01:  # src/ot2/ot2_gym_wrapper.py:69-71
            terminated = True
            reward += 10.0
        truncated = self.steps >= self.max_steps  # src/ot2/ot2_gym_wrapper.py:73-74
        info = {  # src/ot2/ot2_gym_wrapper.py:76-80
            "current_position": list(self._position),
            "target_position": list(self.goal_position),
            "distance_to_goal": distance,
        }
        return observation, reward, terminated, truncated, info

    def render(self, mode="human"):
        """Rendering is the PyBullet GUI flag upstream (src/ot2/ot2_gym_wrapper.py:83-84); the fake has none."""
        return None

    def close(self):
        """The upstream close disconnects PyBullet (src/ot2/ot2_gym_wrapper.py:86-87); the fake has no client."""
        self._position = list(START)
