"""Fake backend of the NaVILA-Bench driver: a pure Python interface stand-in for the registered task.

Why a fake: ``go2_matterport_vision`` is registered with the external entry point
``omni.isaac.lab.envs:ManagerBasedRLEnv`` (``.../config/go2/__init__.py:22``).  Opening it needs Isaac Sim 4.1.0 and
Isaac Lab 1.1.0 with both extensions symlinked (README.md:55-69), a CUDA GPU (README.md:45), the R2R data and
Matterport USD assets from Hugging Face (README.md:82) and an environment configuration object
(``scripts/navila_eval.py:271``).  None of that is installed or present where the gate runs, and package code never
imports or runs the clone.  This module therefore implements the public entry points the Gymnasium bridge reads --
``action_space``, ``observation_space``, ``reset(seed, options)``, ``step(action)`` and ``close`` -- with the upstream
class and its gymnasium base outside the clone.

What this is not: the upstream environment.  It has no Isaac Sim, no rigid bodies, no Matterport scene, no robot pose,
no contacts, no actuator, sensor or noise model and no camera.  The real camera image is 512 x 512 with rgb and
distance data (``go2_matterport_base_cfg.py:301-307``); this fake returns an 8 x 8 x 3 placeholder image.  The real
observation is a dict of six groups (``go2_matterport_vision_cfg.py:133-139``); this fake returns only ``policy``
(the last-action term, ``go2_matterport_base_cfg.py:144``), ``proprio`` (a small base angular-velocity and rpy tail)
and ``camera_obs``.  The real action space is derived by the external ManagerBasedRLEnv from JointPositionActionCfg
over all robot joints (``go2_matterport_base_cfg.py:125``); the fake exposes an unbounded 12-value Box because the
joint count comes from the external USD asset (``go2_matterport_base_cfg.py:70``) and the upstream bounds are not in
the clone.  Every reduction is also listed in the driver's fidelity ``gaps`` and in RESULT.json.

Nothing here talks to a device.
"""

import math
import random

# placeholder: the joint count comes from the external go2.usd asset (go2_matterport_base_cfg.py:70); the action term
# selects every joint but does not enumerate them (go2_matterport_base_cfg.py:125).
ACTION_SIZE = 12
# placeholder: the term sizes of base_ang_vel and base_rpy come from the external Isaac Lab terms.
PROPRIO_SIZE = 6
# placeholder: a stand-in image; the real rgbd camera is 512 x 512 (go2_matterport_base_cfg.py:305-306).
IMAGE_HEIGHT = 8
IMAGE_WIDTH = 8
# the evaluation takes channel indices 0:3 of each frame (scripts/navila_eval.py:305).
IMAGE_CHANNELS = 3
IMAGE_VALUES = IMAGE_HEIGHT * IMAGE_WIDTH * IMAGE_CHANNELS
# placeholder: the pixel range of the stand-in image; not a device property.
PIXEL_MAX = 255


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high, shape, dtype="float32"):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape)
        self.dtype = dtype


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the bridge reads ``spaces`` as a mapping."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


class FakeGo2MatterportVisionEnv:
    """One go2_matterport_vision environment without Isaac Sim: the contract, not the physics."""

    def __init__(self, **options):
        # The real action bounds are built by the external ManagerBasedRLEnv and are not in the clone, so the fake
        # publishes an unbounded Box instead of inventing an envelope.
        self.action_space = Box([-math.inf] * ACTION_SIZE, [math.inf] * ACTION_SIZE, (ACTION_SIZE,))
        self.observation_space = Dict({
            "policy": Box([-math.inf] * ACTION_SIZE, [math.inf] * ACTION_SIZE, (ACTION_SIZE,)),
            "proprio": Box([-math.inf] * PROPRIO_SIZE, [math.inf] * PROPRIO_SIZE, (PROPRIO_SIZE,)),
            "camera_obs": Box([0] * IMAGE_VALUES, [PIXEL_MAX] * IMAGE_VALUES, (IMAGE_VALUES,), dtype="uint8"),
        })
        self._options = dict(options)
        self._rng = random.Random()
        self._seed = None
        self._tick = 0
        self._policy = [0.0] * ACTION_SIZE             # placeholder
        self._proprio = [0.0] * PROPRIO_SIZE           # placeholder
        self._camera = [0] * IMAGE_VALUES              # placeholder
        self._closed = False

    def _observation(self):
        return {
            "policy": list(self._policy),
            "proprio": list(self._proprio),
            "camera_obs": list(self._camera),
        }

    def reset(self, *, seed=None, options=None):
        """Start a new episode; ``options`` is accepted for the Gymnasium reset contract and has no effect."""
        if seed is not None:
            self._seed = int(seed)
            self._rng = random.Random(self._seed)
        self._tick = 0
        self._closed = False
        self._policy = [0.0] * ACTION_SIZE                                # placeholder
        self._proprio = [0.0] * PROPRIO_SIZE                              # placeholder
        # placeholder: a seeded stand-in image, not a camera or a Matterport scene.
        self._camera = [self._rng.randrange(PIXEL_MAX + 1) for _ in range(IMAGE_VALUES)]
        return self._observation(), {}

    def step(self, action):
        """Apply one 12-value joint-position action and advance the reduced state by one control step."""
        values = list(action)
        if len(values) != ACTION_SIZE:
            raise ValueError(f"the action must have {ACTION_SIZE} values, got {len(values)}")
        checked = []
        for value in values:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"the action values must be numbers, got {value!r}")
            number = float(value)
            if not math.isfinite(number):
                raise ValueError(f"the action values must be finite, got {value!r}")
            checked.append(number)
        # The policy observation's last-action term makes the applied action observable; the rest is not modelled.
        self._policy = checked
        self._tick += 1
        reward = 0.0                                                      # placeholder
        terminated = False                                                # placeholder
        truncated = False                                                 # placeholder
        return self._observation(), reward, terminated, truncated, {}

    def close(self):
        """Close the stand-in; the fake keeps no external resource."""
        self._closed = True
