"""OpenMHS driver for gh.zzzjie-robot/go2arm_lab: the Isaac Lab Go2Arm manager environment.

The upstream environment is a concrete ``gymnasium`` environment registered as ``Isaac-Go2Arm-Flat``
and ``Isaac-Go2Arm-Flat-Play`` (source/Go2Arm_Lab/Go2Arm_Lab/tasks/manager_based/go2arm_lab/config/__init__.py:14-31).
Its entry point is ``Go2Arm_Lab.env.manager_env:ManagerRLEnv`` (manager_env.py:4).  The environment drives an
Isaac Sim physics scene: ``step`` processes the action and loops ``cfg.decimation`` physics steps
(manager_env.py:17-34), and it returns six values, adding a second (arm) reward channel between the locomotion
reward and the terminal flags (manager_env.py:88).

A ``GymnasiumDriver`` is configuration only.  The ``fake`` backend is the package's own analytic stand-in; the
``sim`` backend is the production factory below, which constructs the same Isaac Lab environment with a single
world, applies the ``cfg`` the cards register, and normalizes the manager environment's six-value step to the five
values the bridge expects.  The production factory and the fake share the conversion helpers in this module, so a
reward/terminal conversion is never only inside ``fake.py``.  The factory was not run here: it needs Isaac Lab
v2.2.0, Isaac Sim, a GPU and a scene (README.md:28-30); the gate runs the fake backend only.

The ``fake`` is analytic (fidelity F0): it models the registered action shape (12 leg joints plus 6 arm joints,
env_cfg.py:263-289), the 727-value policy observation (env_cfg.py:300-323) and the configured 20 s time-out
(env_cfg.py:550-553), not Isaac Sim dynamics.  Its action bounds are a documented placeholder deployment envelope,
not a sourced device bound.  The package is model-authored and unreviewed and was checked on the fake backend only.
"""

from collections.abc import Mapping

from mhs.driver import Fact, GymnasiumDriver

REGISTRATION = ("source/Go2Arm_Lab/Go2Arm_Lab/tasks/manager_based/go2arm_lab/config/__init__.py")
ENV = "source/Go2Arm_Lab/Go2Arm_Lab/env/manager_env.py"
CONFIG = "source/Go2Arm_Lab/Go2Arm_Lab/tasks/manager_based/go2arm_lab/go2arm_lab_env_cfg.py"


def _scalar(value):
    """One Python number from a scalar, a one-element tensor or a one-element list."""
    if hasattr(value, "detach"):
        value = value.detach().cpu()
    if hasattr(value, "tolist"):
        value = value.tolist()
    while isinstance(value, (list, tuple)):
        if len(value) != 1:
            raise ValueError(f"expected a scalar, got a sequence of length {len(value)}")
        value = value[0]
    return float(value)


def _flatten(value):
    """A flat list of floats from a tensor, an array or nested lists/tuples."""
    if hasattr(value, "detach"):
        value = value.detach().cpu()
    if hasattr(value, "tolist"):
        value = value.tolist()
    out = []

    def walk(item):
        if isinstance(item, Mapping):
            for key in sorted(item):
                walk(item[key])
        elif isinstance(item, (list, tuple)):
            for element in item:
                walk(element)
        else:
            out.append(float(item))

    walk(value)
    return out


def _flatten_observation(observation):
    """The policy observation as a flat list; the manager env returns ``{"policy": tensor}``."""
    if isinstance(observation, Mapping):
        observation = observation.get("policy", observation)
    return _flatten(observation)


def _normalize_manager_step(result):
    """Convert the manager env's six values to Gymnasium's five, keeping the arm reward in ``info``.

    ``ManagerRLEnv.step`` returns ``(obs, reward, arm_reward, terminated, truncated, extras)``
    (manager_env.py:88).  A Gymnasium bridge consumes ``(observation, reward, terminated, truncated, info)``; the
    primary control, observation and terminal flags are unchanged, and the separate arm reward is exposed as
    ``info["arm_reward"]`` instead of being silently folded into the locomotion reward.
    """
    try:
        observation, reward, arm_reward, terminated, truncated, extras = result
    except (TypeError, ValueError) as exc:
        raise ValueError("ManagerRLEnv.step must return its six documented values") from exc
    info = dict(extras) if isinstance(extras, Mapping) else {}
    info["arm_reward"] = _scalar(arm_reward)
    return _flatten_observation(observation), _scalar(reward), bool(_scalar(terminated)), bool(_scalar(truncated)), info


def _normalize_manager_reset(result):
    """Convert the manager env's reset result to ``(observation, info)`` with a flat policy observation."""
    if isinstance(result, tuple) and result:
        observation = result[0]
        info = result[1] if len(result) > 1 and isinstance(result[1], Mapping) else {}
    else:
        observation, info = result, {}
    return _flatten_observation(observation), dict(info)


def make_env(**options):
    """Production factory for the ``sim`` backend: construct the registered manager environment for one world.

    Not called by the gate.  The upstream package is imported only here, never at package import time.  The
    registered entry point needs the ``cfg`` the registration names (train.py:149 passes ``cfg=env_cfg``), so this
    factory builds ``Go2ARMFlatEnvCfg`` itself, follows the training script's ``flat`` task, sets one environment
    (the MHS world is one agent), and wraps the result in :class:`_Go2ArmAdapter`.
    """
    from Go2Arm_Lab.env.manager_env import ManagerRLEnv
    from Go2Arm_Lab.tasks.manager_based.go2arm_lab.config.flat_env_cfg import Go2ARMFlatEnvCfg

    cfg = Go2ARMFlatEnvCfg()
    cfg.scene.num_envs = 1
    cfg.sim.device = str(options.get("device", "cuda:0"))
    cfg.seed = int(options.get("seed", 0))
    env = ManagerRLEnv(cfg, render_mode=None)
    return _Go2ArmAdapter(env, clip_actions=options.get("clip_actions"))


class _Go2ArmAdapter:
    """Gymnasium-shaped view of ``Go2Arm_Lab.env.manager_env:ManagerRLEnv`` for the bridge (production adapter).

    The manager environment's own API is preserved on ``self._env``: six-value step, two reward channels,
    batched observation tensors.  The adapter performs only the contract conversion the bridge needs and exposes
    the standard five-value step; the arm reward travels in ``info``.  ``action_space`` is unbounded unless the
    deployment passes ``clip_actions`` (the upstream training wrapper applies that clip, VecEnvWrapper.py:182-183);
    this package does not invent a bound for the device.
    """

    def __init__(self, env, clip_actions=None):
        import gymnasium as gym

        self._env = env
        self.dt = float(env.cfg.decimation) * float(env.cfg.sim.dt)
        action_dim = int(env.action_manager.total_action_dim)
        clipped = None
        if clip_actions is not None:
            clipped = abs(float(clip_actions))
        low = -clipped if clipped is not None else -float("inf")
        high = clipped if clipped is not None else float("inf")
        self.action_space = gym.spaces.Box(low=low, high=high, shape=(action_dim,), dtype="float32")
        observation_dim = int(env.observation_manager.group_obs_dim["policy"][0])
        self.observation_space = gym.spaces.Box(
            low=-float("inf"), high=float("inf"), shape=(observation_dim,), dtype="float32")

    def reset(self, seed=None, options=None):
        if seed is not None:
            import random

            import numpy
            import torch

            random.seed(int(seed))
            numpy.random.seed(int(seed))
            torch.manual_seed(int(seed))
        return _normalize_manager_reset(self._env.reset())

    def step(self, action):
        import torch

        tensor = torch.as_tensor(action, dtype=torch.float32, device=self._env.device).reshape(1, -1)
        return _normalize_manager_step(self._env.step(tensor))

    def close(self):
        return self._env.close()


class Go2Arm(GymnasiumDriver):
    device_id = "go2arm"
    env_id = "Isaac-Go2Arm-Flat-Play"
    native = "Go2Arm_Lab.env.manager_env:ManagerRLEnv"
    backends = {"fake": ".fake:FakeGo2ArmEnv", "sim": ".driver:make_env"}
    display_name = "Go2Arm Lab (Unitree Go2 + WidowX 250s, Isaac Lab)"
    vendor, model = "zzzjie-robot", "Go2Arm_Lab"
    tags = ["gymnasium", "isaaclab", "isaac-sim", "go2", "widowx", "legged-manipulation", "simulation"]
    seed = 0
    facts = [
        Fact("Go2Arm is a Unitree Go2 quadruped base with an Interbotix WidowX 250s manipulator; the repository "
             "trains RL policies for it", source="upstream_code", ref="README.md:22-25"),
        Fact("Isaac-Go2Arm-Flat and Isaac-Go2Arm-Flat-Play are registered with entry_point "
             "Go2Arm_Lab.env.manager_env:ManagerRLEnv and the Go2ARMFlatEnvCfg / Go2ARMFlatEnvCfg_PLAY configs",
             source="upstream_code", ref=f"{REGISTRATION}:14-31"),
        Fact("ManagerRLEnv.__init__ takes cfg and render_mode and calls the Isaac Lab base with cfg",
             source="upstream_code", ref=f"{ENV}:6-7"),
        Fact("step processes the action through the action manager and advances the Isaac Sim scene cfg.decimation "
             "times per call", source="upstream_code", ref=f"{ENV}:17-34"),
        Fact("step returns six values: observation, reward, arm reward, terminated, time-out and extras",
             source="upstream_code", ref=f"{ENV}:88"),
        Fact("The configuration sets decimation 4, episode_length_s 20.0 and sim.dt 0.005 seconds",
             source="upstream_code", ref=f"{CONFIG}:550-553"),
        Fact("The action configuration has two JointPositionAction terms: 12 leg joints with scale 0.25 and 6 "
             "arm joints with scale 0.5, both around the default joint offsets", source="upstream_code",
             ref=f"{CONFIG}:263-289"),
        Fact("The policy observation group concatenates seven history terms (base angular velocity 3, joint "
             "positions 18, joint velocities 18, last actions 18, velocity command 3, end-effector pose command 7 "
             "and projected gravity 3, each with history_length 10) and five privileged terms (base mass 1, "
             "end-effector mass 1, joint torques 18, base linear velocity 3 and foot contacts 4)", source="upstream_code",
             ref=f"{CONFIG}:300-323"),
        Fact("Termination includes a time-out and illegal contact of the base, thighs, arm links and calves at a "
             "contact threshold of 0.5", source="upstream_code", ref=f"{CONFIG}:489-508"),
        Fact("The repository targets Isaac Lab v2.2.0, an external simulator framework", source="upstream_code",
             ref="README.md:27-30"),
        Fact("The package's own install_requires lists only psutil", source="upstream_code",
             ref="source/Go2Arm_Lab/setup.py:18-22"),
    ]
    safe_state = ("the simulation stops advancing: the bridge refuses step, reset and seed after an e-stop until "
                  "mhs.safety.reset clears the latch; the last observation stays readable")
    #: The common contract is the deployed Isaac Lab simulator; the fake overrides the engine, fidelity level,
    #: determinism notes and gaps because it is analytic and was not compared with Isaac Sim.
    fidelity = {
        "engine": "isaaclab:Isaac-Go2Arm-Flat-Play",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "statistical",
            "seed_control": "parameter",
            "notes": "the upstream cfg.seed is set at construction and the training wrapper seeds the process; a "
                     "reset accepts a seed in the adapter but Isaac Sim/PhysX and the manager RNGs are not proven "
                     "reproducible from it, so replay is statistical, not exact",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "Isaac Sim rigid-body dynamics, contacts, actuator model, sensors and domain randomization are the "
            "upstream scene's; not validated against the physical Go2Arm",
            "the production adapter changes the manager environment's six-value step to Gymnasium's five and "
            "moves the separate arm reward into info['arm_reward']; the observation is flattened to the policy "
            "group and the manager env is built with one environment, not the training default",
            "the adapter's action space is unbounded unless the deployment passes clip_actions because the "
            "manager environment itself does not bound the action; apply the training wrapper's clip at deployment",
            "the factory was not run: it needs Isaac Lab v2.2.0, Isaac Sim, a GPU and a scene, and this package "
            "was checked on the fake backend only",
            "reset options are accepted for the capability contract but not forwarded, and a reset seed reseeds "
            "the process RNGs rather than reconstructing the Isaac Sim scene RNG state",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by the 20 ms control period "
            "(decimation 4 times sim.dt 0.005 s) only",
        ],
    }
    fidelity_by_backend = {
        "fake": {
            "engine": "analytic:go2arm-manager-env-fake",
            "fidelity_level": "F0",
            "determinism": {
                "kind": "seeded",
                "seed_control": "parameter",
                "notes": "the fake's reset(seed) reseeds Python's random.Random and repeats its synthetic "
                         "observation/reward trajectory; it has no Isaac Sim state to reproduce",
            },
            "gaps": [
                "analytic F0: no rigid-body dynamics, contacts, actuators, sensors or noise; the fake updates a "
                "synthetic 727-value observation from the action and a step counter",
                "only the configured 20 s time-out is modelled; the contact-based termination terms and the "
                "two reward channels' actual values require the Isaac Sim scene and are replaced by placeholders",
                "the fake's action bounds [-1, 1] are a documented placeholder deployment envelope, not a device "
                "fact: no text in the clone states an action bound, and the production adapter leaves the "
                "manager environment's action space unbounded unless clip_actions is supplied",
                "the fake was not compared with an Isaac Sim run; observations are Python floats of length 727 "
                "where the deployment returns policy-group tensors",
                "reset options are accepted and ignored: the fake has no scene options to apply",
                "no hardware is modelled; the e-stop is the SDK's software latch, not a physical stop",
            ],
        },
        "sim": {
            "fidelity_level": "F1",
        },
    }
