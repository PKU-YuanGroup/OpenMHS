"""OpenMHS driver for gh.oceanworldlabs/oceanscale: the ``ROVEnv`` station-keeping environment (a Gymnasium family
driver).

A GymnasiumDriver is configuration only: the bridge derives the whole contract from the environment's spaces.
``cap.world.step.v1`` takes ``{ticks, action}`` where ``action`` is an object with a six-element ``values`` array
bounded element-wise by the action space ``Box(-1.0, 1.0, (6,))``; ``cap.world.reset.v1`` takes ``{seed, options}``
and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0): there is no hardware backend, no e-stop path to
a machine and no operator-required limit.

OceanScale registers no ``gymnasium.make`` id (the clone has no ``register(`` call).  The documented usage constructs
``ROVEnv`` directly (``oceanscale/rov_env.py:10``), so ``env_id`` stays ``None``.  ``fake`` is this package's pure
Python stand-in (``fake.py``): the fake gate does not install the clone.  ``sim`` is ``_build_sim_env``.  It imports
``oceanscale.rov_env`` and constructs ``ROVEnv(n_envs=1)``.  ``n_envs`` defaults to 64 (``oceanscale/rov_env.py:86``);
the class documents one world as ``n_envs=1`` (``oceanscale/rov_env.py:78-79``), and the hover demo builds that one
world (``oceanscale/cli.py:706``).  ``step`` still returns length-1 arrays for that one world
(``oceanscale/rov_env.py:440``).  The wrapper's ``.item()`` returns each of those scalars and does not change its
value; the observation is forwarded as ``step`` returned it.  ``device`` stays at its default ``None``, so
``resolve_warp_device`` selects cuda when Warp reports a CUDA device and cpu otherwise
(``oceanscale/devices.py:37-43`` and ``:59-60``).  The import sits inside the factory, so the fake backend does not
import the clone.  The upstream simulator was not run here.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002).
Every Fact and every constant of the declared contract cites a line of the clone at the pinned commit
(84f6cc4ce3dcf7cb4a53e2e9d2e81f541b0c63f2).  This package is model-authored and unreviewed: it is checked on the
fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ROV_ENV = "oceanscale/rov_env.py"
TIER1 = "oceanscale/hydro/tier1.py"
README = "README.md"
DEVICES = "oceanscale/devices.py"


def _one_element(value):
    """The Python scalar a length-1 array holds, or ``value`` when it has no ``item`` method."""
    item = getattr(value, "item", None)
    if callable(item):
        return item()
    return value


class _OneEnvStep:
    """``ROVEnv`` with the one world's reward and done flags as Python scalars.

    ``ROVEnv.step`` returns ``observation, reward, terminated, truncated, info`` (``oceanscale/rov_env.py:440``).
    With ``n_envs=1`` each of ``reward``, ``terminated`` and ``truncated`` is a length-1 array
    (``oceanscale/rov_env.py:346-347`` and ``:414-421``).  ``.item()`` yields that element and does not change its
    value.  The observation stays the ``(n_envs, 26)`` array ``_get_flat_obs`` returned
    (``oceanscale/rov_env.py:672-674``), and ``info`` is forwarded as the environment returned it.
    """

    def __init__(self, env):
        self._env = env

    def __getattr__(self, name):
        return getattr(self._env, name)

    def reset(self, **kwargs):
        return self._env.reset(**kwargs)

    def step(self, action):
        observation, reward, terminated, truncated, info = self._env.step(action)
        return observation, _one_element(reward), _one_element(terminated), _one_element(truncated), info

    def close(self):
        return self._env.close()


def _build_sim_env(**_options):
    """Build ``ROVEnv(n_envs=1)`` for the ``sim`` backend.

    The clone has no ``register(`` call, and the usage example constructs the class directly
    (``oceanscale/rov_env.py:10``), so ``gymnasium.make`` has no id to build.  ``n_envs`` defaults to 64
    (``oceanscale/rov_env.py:86``).  One world is the shape the class documents (``oceanscale/rov_env.py:78-79``)
    and the shape the hover demo builds (``oceanscale/cli.py:706``).  ``device`` is omitted, so the constructor's
    ``None`` goes through ``resolve_warp_device`` (``oceanscale/rov_env.py:108``, ``oceanscale/devices.py:59-60``):
    cuda when Warp reports a CUDA device, otherwise cpu (``oceanscale/devices.py:37-43``).  Every other constructor
    argument keeps its default, including ``sensor_noise_std`` 0.02 (``oceanscale/rov_env.py:93``).  The import is
    inside this function: the fake backend runs where OceanScale is not installed.
    """
    from oceanscale.rov_env import ROVEnv

    return _OneEnvStep(ROVEnv(n_envs=1))


class OceanScaleROV(GymnasiumDriver):
    device_id = "oceanscale-rov"
    env_id = None
    native = "oceanscale.rov_env:ROVEnv"
    backends = {"fake": ".fake:FakeROVEnv", "sim": _build_sim_env}
    action_space_ref = f"{ROV_ENV}:164"
    display_name = "OceanScale ROVEnv (GPU-batched station keeping)"
    vendor, model = "OceanWorld Labs", "OceanScale ROVEnv"
    tags = ["oceanworldlabs", "oceanscale", "underwater-robotics", "rov", "station-keeping", "reinforcement-learning",
            "simulation", "gymnasium"]
    facts = [
        Fact("The observation is a 26-element flat vector: position error (3), orientation quaternion xyzw (4), "
             "linear velocity (3), angular velocity (3), depth error (1), roll and pitch heading error (2), the "
             "previous six-dimensional action (6) and the previous hydro wrench (4)", source="upstream_code",
             ref=f"{ROV_ENV}:62-70"),
        Fact("The observation space is an unbounded 26-element Box and the action space is a 6-element Box with "
             "element-wise bounds -1.0 and +1.0", source="upstream_code", ref=f"{ROV_ENV}:163-164"),
        Fact("The action is a six-degree-of-freedom wrench command (surge, sway, heave, roll, pitch, yaw) in "
             "[-1, +1] per DOF, mapped to the thrusters through the T_matrix pseudoinverse", source="upstream_code",
             ref=f"{ROV_ENV}:72-73"),
        Fact("The default integration step is DEFAULT_DT = 1/240 s", source="upstream_code", ref=f"{TIER1}:43"),
        Fact("ROVEnv's dt argument defaults to DEFAULT_DT", source="upstream_code", ref=f"{ROV_ENV}:89"),
        Fact("init_pos_noise_std and init_yaw_noise_std are uniform half-ranges, not standard deviations",
             source="upstream_code", ref=f"{ROV_ENV}:75-76"),
        Fact("A reset samples a position offset per axis uniformly in [-init_pos_noise_std, +init_pos_noise_std] and "
             "a yaw offset uniformly in [-init_yaw_noise_std, +init_yaw_noise_std] with the environment's np_random "
             "generator", source="upstream_code", ref=f"{ROV_ENV}:806-812"),
        Fact("reset() seeds the environment's np_random generator through gymnasium's Env.reset",
             source="upstream_code", ref=f"{ROV_ENV}:285-293"),
        Fact("The default target position is [0.0, 0.0, -1.5] m", source="upstream_code", ref=f"{ROV_ENV}:137-139"),
        Fact("A reset option target_position replaces the target position", source="upstream_code",
             ref=f"{ROV_ENV}:299-303"),
        Fact("The reward is 0.5*exp(-position_error/1.0) + 0.3*exp(-velocity_norm/0.5) + "
             "0.2*exp(-action_norm/1.0), always in (0, 1]", source="upstream_code", ref=f"{ROV_ENV}:785-789"),
        Fact("The episode truncates when the step count reaches max_episode_steps", source="upstream_code",
             ref=f"{ROV_ENV}:414-416"),
        Fact("The episode terminates when the ROV is more than 5.0 m from its target", source="upstream_code",
             ref=f"{ROV_ENV}:418-421"),
        Fact("step always returns batched shapes: observation (n_envs, 26) and reward and flags (n_envs,)",
             source="upstream_code", ref=f"{ROV_ENV}:346-347"),
        Fact("The environment adds Gaussian noise of sensor_noise_std to every observation entry, drawn from "
             "torch.randn_like rather than the seeded generator", source="upstream_code", ref=f"{ROV_ENV}:768-769"),
        Fact("Each environment models one free-body sphere (an ROV proxy) with 6-DOF hydrodynamic forces computed "
             "by the Tier-1 kernels", source="upstream_code", ref=f"{ROV_ENV}:59-60"),
        Fact("OceanScale is an alpha GPU-native underwater-robotics simulator built on Newton and Warp",
             source="vendor_doc", ref=f"{README}:7-8"),
        Fact("An NVIDIA GPU with CUDA 12.8+ is required and Linux x86_64 is the supported platform",
             source="vendor_doc", ref=f"{README}:14-20"),
        Fact("The install pulls CUDA-enabled wheels of warp-lang, newton and torch", source="upstream_code",
             ref="pyproject.toml:27-30"),
        Fact("default_warp_device returns cuda only when Warp reports a CUDA device; otherwise it aliases the names "
             "cuda and cuda:0 to the cpu device and returns cpu", source="upstream_code", ref=f"{DEVICES}:8-43"),
        Fact("resolve_warp_device with no requested device returns default_warp_device", source="upstream_code",
             ref=f"{DEVICES}:59-60"),
        Fact("ROVEnv passes its device argument through resolve_warp_device", source="upstream_code",
             ref=f"{ROV_ENV}:108"),
        Fact("The bluerov2-hover demo constructs one ROVEnv world with n_envs=1", source="upstream_code",
             ref="oceanscale/cli.py:706"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the
    #: determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "oceanscale.rov_env:ROVEnv",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "statistical",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the reset-noise generator, but the upstream observation "
                     "adds unseeded Gaussian sensor noise (rov_env.py:768-769), so repeated runs with one seed do not "
                     "produce equal state hashes; the package's fake omits the sensor noise and is deterministic "
                     "for a seed, which is a property of the fake, not a claim about the upstream simulator",
        },
        "timestep_ms": 1000.0 / 240.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "rigid-body hydrodynamics of one sphere per environment: no contact, thruster or actuator fidelity "
            "claim, and no claim that the Fossen coefficients match a physical BlueROV2",
            "the fake backend replaces Newton, Warp, Torch and Tier-1 hydrodynamics with a kinematic acceleration "
            "and linear drag (fake.py), so its trajectories are not the upstream ones",
            "the fake models one environment and returns a flat 26-vector and scalar reward; upstream's step "
            "always returns batched (n_envs, 26) arrays and the constructor default is n_envs=64",
            "upstream adds Gaussian sensor noise to every observation entry (rov_env.py:768-769); the fake omits "
            "it, so the fake is deterministic for a seed while the upstream simulator is statistical",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms only",
            "no physical device is modelled and the simulator was never validated against one",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
        ],
    }
