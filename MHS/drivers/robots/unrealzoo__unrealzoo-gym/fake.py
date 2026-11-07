"""Fake backend of the UnrealZoo driver: a pure Python stand-in for the Go1 MuJoCo environment.

Why a fake: ``UnrealCvMujocoEnv`` drives a packaged Unreal Engine process through an UnrealCV server
(gym_unrealcv/envs/base_env_mujoco.py:230-231) and imports legacy ``gym`` 0.10.9, ``unrealcv``, numpy and the rest of
the upstream dependency list (pyproject.toml:10-15).  Neither the engine binary nor those packages are installed where
the gate runs, and package code never imports or runs the clone, so this module models the part of the environment that
the ``cap.world.*`` contract needs: the two spaces, ``reset``, ``step`` and ``close``.  The public members are the ones
``UnrealCvMujocoEnv`` has (gate G7).  Every constant copied from the clone cites its line at the pinned commit
85f4b72e0ecd3c77f17fab161c3c8bdfdd86cf7c; every other number is test data marked ``# placeholder``.

What this is not: the upstream environment.  Differences, all listed in the fidelity ``gaps`` of the driver:

* the action advances a joint position kinematically (no rigid-body dynamics, contacts or actuators);
* the 48-element observation layout of the UnrealCV server is not reconstructed: 12 joint positions, 12 action values
  and 24 zero padding values are published instead;
* the reward is always 0.0 and the environment never terminates, as in ``UnrealCvMujocoEnv.step``
  (gym_unrealcv/envs/mujoco.py:388), but no task or episode logic is modelled;
* there is no Unreal Engine process, UnrealCV server, camera or rendering.

Nothing here talks to a device.
"""

import random

# gym_unrealcv/envs/mujoco.py:13-14 (ROBOT_SPECS["go1"])
OBSERVATION_DIM = 48
ACTION_DIM = 12
# gym_unrealcv/envs/mujoco.py:130-131 (spaces.Box bounds)
ACTION_LOW = -1.0
ACTION_HIGH = 1.0
# gym_unrealcv/envs/base_env_mujoco.py:17-18 (timestep 0.005, control_decimation 4) and :142-145 (the product)
CONTROL_PERIOD_S = 0.005 * 4

# Test data, not upstream facts:
_START_SPREAD = 0.05  # placeholder: half-width of the fake's initial joint draw
_DEFAULT_SEED = 0  # placeholder: the fake's generator seed before the first reset supplies one
_PADDING = OBSERVATION_DIM - 2 * ACTION_DIM  # placeholder: zero padding to the upstream observation length
_ZERO = 0.0  # placeholder: the fake's neutral joint and action value


class Box:
    """Duck-typed ``gym.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high, shape):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape)
        self.dtype = "float32"


class FakeUnrealCvMujoco:
    """Stand-in for ``UnrealCvMujocoEnv(robot="go1")``: the Go1 spaces, ``reset``, ``step`` and ``close``."""

    metadata = {"render.modes": []}

    def __init__(self, **options):
        robot = options.get("robot", "go1")
        if robot != "go1":
            raise ValueError(f"the fake models the go1 environment, not {robot!r}")
        self.action_space = Box([ACTION_LOW] * ACTION_DIM, [ACTION_HIGH] * ACTION_DIM, (ACTION_DIM,))
        self.observation_space = Box(
            [float("-inf")] * OBSERVATION_DIM, [float("inf")] * OBSERVATION_DIM, (OBSERVATION_DIM,)
        )
        self.steps = 0
        self.started = False
        self.last_action = [_ZERO] * ACTION_DIM  # placeholder
        self._joints = [_ZERO] * ACTION_DIM  # placeholder
        self._rng = random.Random(_DEFAULT_SEED)  # placeholder

    def reset(self, seed=None, options=None):
        """Return a fresh observation; the bridge passes ``seed`` (the upstream reset takes none)."""
        if options:
            raise ValueError("the fake Go1 environment has no reset options")
        if seed is not None:
            self._rng = random.Random(int(seed))
        self._joints = [self._rng.uniform(-_START_SPREAD, _START_SPREAD) for _ in range(ACTION_DIM)]  # placeholder
        self.last_action = [_ZERO] * ACTION_DIM  # placeholder
        self.steps = 0
        self.started = True
        return self._observation()

    def step(self, action):
        """Apply one normalised action and return the upstream's four-tuple shape."""
        values = [float(value) for value in action]
        if len(values) != ACTION_DIM:
            raise ValueError(f"the Go1 action has {ACTION_DIM} elements, got {len(values)}")
        for value in values:
            if not ACTION_LOW <= value <= ACTION_HIGH:
                raise ValueError(f"action element {value!r} is outside the action space")
        self._joints = [position + value * CONTROL_PERIOD_S
                        for position, value in zip(self._joints, values)]  # placeholder: kinematic integration
        self.last_action = values
        self.steps += 1
        # gym_unrealcv/envs/mujoco.py:383-388: steps counter in info, reward 0.0 and no termination
        return self._observation(), 0.0, False, {"steps": self.steps}

    def _observation(self):
        """12 joint positions, 12 applied action values and zero padding: a placeholder layout."""
        return list(self._joints) + list(self.last_action) + [_ZERO] * _PADDING  # placeholder

    def close(self):
        self.started = False
