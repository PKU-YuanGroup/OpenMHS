"""OpenMHS driver for gh.xingyu-lin/softgym: the PourWater environment (a Gymnasium family driver).

A ``GymnasiumDriver`` is configuration only: ``env_id`` names the environment and the bridge derives the contract
from the environment's spaces.  The package serves ``PourWaterPosControlEnv`` (``softgym/envs/pour_water.py:12``)
configured for its ``key_point`` observation mode (a 13-element vector, ``pour_water.py:35`` and ``:368-370``) and
its ``rotation_bottom`` action mode (a 3-element Box of (dx, dy, dtheta), ``pour_water.py:49-54``).  The bridge then
serves ``cap.world.step.v1`` as ``{ticks, action}`` with ``action.values`` bounded by that action space,
``cap.world.reset.v1`` as ``{seed, options}`` and ``cap.world.seed.v1`` as ``{seed}``.  The device is simulated
(R0): there is no hardware backend, no e-stop path to a machine and no operator-required limit.

The registration ``PourWaterPosControl-v0`` passes ``action_mode='direct'`` (``softgym/__init__.py:21``), which the
class itself rejects (``pour_water.py:23``), so the driver overrides ``observation_mode`` and ``action_mode`` in
``env_kwargs``; it does not rely on the registered keyword values.  ``register_flex_envs()`` is defined at
``softgym/__init__.py:9`` but never called by the clone, so the ``sim`` backend needs an install that registers it
and compiles PyFlex (``README.md:22``); it was not run here.

The gate cannot import pyflex, numpy, gym or shapely (see fake.py), so the ``fake`` backend is the package's own pure
Python PourWater stand-in.  A backend name that ``backends`` does not list (``sim``) is served by ``gym.make(env_id,
**env_kwargs)`` through ``GymnasiumDriver.open_native``.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002):
every member of ``device.schema.json`` that applies to a simulator without a physical counterpart.  Every constant
and rule cites a line of the clone at the pinned commit (bb383f64cd488062587714abbae38f27ed9f2457).  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

POUR = "softgym/envs/pour_water.py"
FLEX = "softgym/envs/flex_env.py"
FLUID = "softgym/envs/fluid_env.py"
INIT = "softgym/__init__.py"
README = "README.md"


class SoftGymPourWater(GymnasiumDriver):
    device_id = "softgym-pour-water"
    env_id = "PourWaterPosControl-v0"
    #: The registered PourWaterPosControl-v0 environment rejects its own registered action_mode='direct'
    #: (softgym/__init__.py:21 against pour_water.py:23), so the served configuration overrides both modes and
    #: keeps the registered horizon of 75 (softgym/__init__.py:26).  The values are configuration, not device bounds.
    env_kwargs = {
        "observation_mode": "key_point",
        "action_mode": "rotation_bottom",
        "render_mode": "fluid",
        "deterministic": True,
        "render": False,
        "headless": True,
        "horizon": 75,
        "action_repeat": 8,
    }
    native = "softgym.envs.pour_water:PourWaterPosControlEnv"
    backends = {"fake": ".fake:FakePourWaterEnv"}
    action_space_ref = f"{POUR}:52-53"
    display_name = "SoftGym PourWaterPosControlEnv (key_point, rotation_bottom)"
    vendor, model = "Xingyu Lin", "PourWaterPosControl-v0"
    tags = ["softgym", "pour-water", "fluid", "deformable-object", "reinforcement-learning", "simulation",
            "gymnasium"]
    facts = [
        Fact("SoftGym is a set of benchmark environments for deformable object manipulation built on the Nvidia "
             "FleX simulator with a standard Gym API", source="vendor_doc", ref=f"{README}:2"),
        Fact("The README documents compiling PyFleX with CMake and Pybind11", source="vendor_doc",
             ref=f"{README}:22"),
        Fact("FlexEnv is a gym.Env, the legacy Gym API", source="upstream_code", ref=f"{FLEX}:17"),
        Fact("FlexEnv imports pyflex and raises gym.error.DependencyNotInstalled when the compiled binding is "
             "missing", source="upstream_code", ref=f"{FLEX}:12-15"),
        Fact("PourWaterPosControlEnv extends FluidEnv", source="upstream_code", ref=f"{POUR}:12"),
        Fact("FluidEnv extends FlexEnv", source="upstream_code", ref=f"{FLUID}:7"),
        Fact("PourWaterPosControlEnv accepts the observation modes cam_rgb, point_cloud and key_point and the "
             "action modes rotation_bottom and rotation_top", source="upstream_code", ref=f"{POUR}:22-23"),
        Fact("The key_point observation has 13 elements: the two cups' positions and shapes, the water height and "
             "the water fractions of the two cups", source="upstream_code", ref=f"{POUR}:32-41"),
        Fact("The key_point observation space is a Box of 13 values bounded by -inf and +inf", source="upstream_code",
             ref=f"{POUR}:42"),
        Fact("In the rotation_bottom and rotation_top action modes the action space is a 3-element Box: (dx, dy) "
             "for the floor centre and dtheta for its rotation", source="upstream_code", ref=f"{POUR}:49-54"),
        Fact("The key_point observation is built from the glass pose and shape, the poured glass pose and shape, "
             "the water height and the two water fractions", source="upstream_code", ref=f"{POUR}:368-370"),
        Fact("The reward is the fraction of water particles inside the poured glass and outside the control glass",
             source="upstream_code", ref=f"{POUR}:377-392"),
        Fact("The reward range is 0 to 1", source="upstream_code", ref=f"{POUR}:59-60"),
        Fact("FlexEnv's default action_repeat is 8", source="upstream_code", ref=f"{FLEX}:26"),
        Fact("FlexEnv.step calls _step once per action_repeat before it computes the observation and reward",
             source="upstream_code", ref=f"{FLEX}:180-185"),
        Fact("FlexEnv.step increments time_step and marks the episode done when time_step reaches the horizon",
             source="upstream_code", ref=f"{FLEX}:190-194"),
        Fact("FlexEnv.step returns the legacy four-value (observation, reward, done, info) tuple",
             source="upstream_code", ref=f"{FLEX}:197"),
        Fact("FlexEnv's default horizon is 100", source="upstream_code", ref=f"{FLEX}:22"),
        Fact("The PourWaterPosControl-v0 registration sets the horizon to 75", source="upstream_code",
             ref=f"{INIT}:26"),
        Fact("The PourWaterPosControl-v0 registration passes action_mode='direct'", source="upstream_code",
             ref=f"{INIT}:21"),
        Fact("The class itself only accepts action_mode rotation_bottom or rotation_top, so the registered value "
             "'direct' fails its assertion", source="upstream_code", ref=f"{POUR}:23"),
        Fact("PourWaterPosControl-v0 is registered with entry point "
             "softgym.envs.pour_water:PourWaterPosControlEnv", source="upstream_code", ref=f"{INIT}:16-18"),
        Fact("FluidEnv.set_scene creates the fluid scene with pyflex.set_scene",
             source="upstream_code", ref=f"{FLUID}:51-57"),
        Fact("FlexEnv.reset loads a cached configuration and state and returns only the observation",
             source="upstream_code", ref=f"{FLEX}:153-175"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "softgym:PourWaterPosControl-v0/key_point",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) seeds the fake's placeholder start state, and cap.world.seed.v1 supplies the "
                     "seed of the next reset.  The upstream environment is created with deterministic=True, which "
                     "selects cached configuration 0 (flex_env.py:158-161); its cached scene variations are "
                     "generated with numpy's global generator (pour_water.py:111-127), while the fake uses "
                     "Python's random.Random, so a seed does not give the same trajectory on the two.  There is no "
                     "wall-clock pacing.",
        },
        "timestep_ms": 0.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "F0 analytic stand-in: the fake models the pouring glass pose and two scalar water fractions "
            "directly; there is no fluid particle simulation, no contact or collision handling, no friction, no "
            "pyflex and therefore no claim about forces or fluid dynamics",
            "only the key_point observation is served: the cam_rgb image (720 x 720 x 3, pour_water.py:44-45) and "
            "the point_cloud particle array are not modelled, and cap.world.render.v1 is unbound",
            "the fake does not load the cached start-state pickle of pour_water.py:31; its start pose and glass "
            "dimensions are placeholders, not the environment's cached scene",
            "no wall-clock pacing: realtime_factor 0 and timestep_ms 0, because the clone exposes no fixed physics "
            "timestep in Python; one cap.world.step.v1 tick is one FlexEnv.step, which repeats the action "
            "action_repeat (default 8) times (flex_env.py:177-181)",
            "the legacy four-value step return (flex_env.py:197) has one done flag, not terminated/truncated: the "
            "bridge serves the horizon case (flex_env.py:192-194) as terminated=True and truncated=False",
            "snapshot and restore are not offered: FlexEnv and PourWaterPosControlEnv define get_state/set_state "
            "(pour_water.py:161-187), but the fake does not implement them, so snapshot_restore is false",
            "the sim backend was not run: it needs PyFlex compiled (README.md:22) and register_flex_envs() called "
            "(the clone defines it at softgym/__init__.py:9 but never calls it)",
            "no physical device is modelled: SoftGym is a simulator and the model was never validated against "
            "hardware",
        ],
    }
