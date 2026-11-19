"""OpenMHS driver for gh.iit-dlslab/gym-quadruped: the MuJoCo quadruped locomotion environment.

The upstream entry class is ``gym_quadruped.quadruped_env:QuadrupedEnv``, a ``gymnasium.Env`` that owns a MuJoCo
``MjModel``/``MjData`` pair and steps it with ``mujoco.mj_step`` (quadruped_env.py:71, :170-183, :281).  That is an
environment object, not a bare ``mujoco`` module, so this package uses ``GymnasiumDriver`` rather than the card's
``MujocoDriver``: the card's ``family``/``helper`` was a scan guess and the bridge that can express the real entry
symbol is the Gymnasium one.  This is a deliberate deviation from the card (also recorded in RESULT.json notes).

The bridge derives ``cap.world.step.v1`` (``{ticks, action}``) from the environment's action space, a
``gymnasium.spaces.Box`` of one torque per actuator (quadruped_env.py:224-235), and the observation from the
environment's ``spaces.Dict``.  ``cap.world.reset.v1`` passes ``seed`` and ``options`` to ``QuadrupedEnv.reset``
(quadruped_env.py:319-326) and ``cap.world.seed.v1`` sets the seed of the next reset.

The upstream registers no Gymnasium id: the clone contains no ``register(...)`` call, and its README constructs
``QuadrupedEnv`` directly (README.md:15-27).  ``env_id`` and ``env_module`` therefore stay unset.  The ``fake``
backend is the package's own pure Python stand-in (fake.py), built through the ``.fake:FakeQuadrupedEnv`` factory;
the ``sim`` backend is ``_build_sim_env``, which imports the real class and constructs it with the deployed
constructor arguments (``robot='go2'``, ``scene='flat'``; quadruped_env.py:85-99).  The import is inside the
factory, so the fake backend does not need ``mujoco``, ``numpy``, ``scipy`` or ``gymnasium``.  The real class is
``gym_quadruped.quadruped_env:QuadrupedEnv`` (quadruped_env.py:71).  The constructor resolves its scene and model
files from its own package directory and writes the composed scene to
``utils/mujoco/assets/{robot}-{scene}.xml`` there (quadruped_env.py:150-170).  The returned object is that
upstream instance; nothing on it is wrapped, patched or replaced.

The device is simulated (R0): there is no hardware backend and no physical stop.  The fake was not compared with
the upstream simulator.  Every fact cites a line of the clone at the pinned commit
(097a8d649ae2232d3c0ed5eb83dc0e4f77483019).  This package is model-authored and unreviewed.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "gym_quadruped/quadruped_env.py"
UTILS = "gym_quadruped/utils/quadruped_utils.py"
CONFIG = "gym_quadruped/robot_cfgs.py"
TERRAIN = "gym_quadruped/utils/mujoco/terrain.py"

#: The constructor arguments the ``sim`` backend passes.  ``robot`` is required (quadruped_env.py:85-99) and
#: ``scene`` defaults to ``'flat'``, the scene this package deploys (quadruped_env.py:89).
_SIM_ENV_KWARGS = {"robot": "go2", "scene": "flat"}


def _build_sim_env(**_options):
    """Build the real upstream ``QuadrupedEnv`` for the ``sim`` backend.

    The import is inside the factory so the fake backend, and the gate that loads it, never needs the upstream
    stack.  ``QuadrupedEnv`` requires ``robot`` and defaults ``scene`` to ``'flat'`` (quadruped_env.py:85-99).
    The returned object is that upstream instance; nothing on it is wrapped, patched or replaced, and no
    attribute of the imported package is assigned.  The constructor arguments are the same ``env_kwargs`` the
    driver declares.  The constructor writes ``utils/mujoco/assets/{robot}-{scene}.xml`` beside its own module
    before loading it (quadruped_env.py:167-170); this factory does not redirect that write.
    """
    from gym_quadruped.quadruped_env import QuadrupedEnv

    return QuadrupedEnv(**_SIM_ENV_KWARGS)


class GymQuadruped(GymnasiumDriver):
    device_id = "gym-quadruped"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R0"
    native = "gym_quadruped.quadruped_env:QuadrupedEnv"
    # `fake` is this package's stand-in; `sim` constructs the upstream environment class (quadruped_env.py:71)
    # through `_build_sim_env`.  The sim entry is a callable, so the lock's string entry (`fake` only) still
    # describes the package's declared string backend and G2 compares a lock only when every entry is a string.
    backends = {"fake": ".fake:FakeQuadrupedEnv", "sim": _build_sim_env}
    env_kwargs = dict(_SIM_ENV_KWARGS)
    display_name = "gym-quadruped MuJoCo quadruped locomotion environment"
    vendor, model = "IIT-DLSLab", "gym-quadruped"
    tags = ["quadruped", "legged-locomotion", "mujoco", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("The upstream environment class is gym_quadruped.quadruped_env:QuadrupedEnv, a gymnasium.Env",
             source="upstream_code", ref=f"{ENV}:71"),
        Fact("QuadrupedEnv is constructed from a robot name and defaults to the flat scene, the default observation "
             "names, sim_dt 0.002 s, the forward velocity command of 0.5 m/s and 0.0 rad/s, ground friction 1.0 and "
             "the leg order FL, FR, RL, RR", source="upstream_code", ref=f"{ENV}:85-99"),
        Fact("The default observations are qpos, qvel, tau_ctrl_setpoint, feet_pos:base and feet_vel:base",
             source="upstream_code", ref=f"{ENV}:80"),
        Fact("The observation space is a gymnasium Dict of Box bounds built from the model's joint ranges and "
             "actuator control ranges", source="upstream_code", ref=f"{UTILS}:250-326"),
        Fact("The action space is a gymnasium Box of shape (mjModel.nu,): one torque per actuator, with low and high "
             "taken from actuator_forcerange", source="upstream_code", ref=f"{ENV}:224-235"),
        Fact("The constructor resolves robot_model/scene_<scene>.xml and the procedural utils/mujoco/assets from "
             "its own package directory", source="upstream_code", ref=f"{ENV}:150-155"),
        Fact("The constructor writes the composed scene to utils/mujoco/assets/<robot>-<scene>.xml beside the "
             "package and loads that file with MjModel.from_xml_path", source="upstream_code", ref=f"{ENV}:167-170"),
        Fact("When robot_model/scene_<scene>.xml is absent (flat), generate_terrain parses the procedural "
             "utils/mujoco/assets/scene_flat.xml", source="upstream_code", ref=f"{TERRAIN}:318-358"),
        Fact("The go2 robot configuration uses robot_model/go2/go2.xml and a hip height of 0.28 m",
             source="upstream_code", ref=f"{CONFIG}:43-44"),
        Fact("The simulation timestep is the sim_dt constructor argument and is assigned to mjModel.opt.timestep",
             source="upstream_code", ref=f"{ENV}:182-183"),
        Fact("A step writes the action to mjData.ctrl, advances MuJoCo with one mj_step and then steps every "
             "configured sensor", source="upstream_code", ref=f"{ENV}:279-284"),
        Fact("A step returns the observation, reward, terminated, truncated and info; info carries time, step_num and "
             "invalid_contacts", source="upstream_code", ref=f"{ENV}:287-300"),
        Fact("The reward is the constant 0", source="upstream_code", ref=f"{ENV}:1147-1150"),
        Fact("An episode terminates on an invalid contact or on leaving the terrain bounds; step never truncates",
             source="upstream_code", ref=f"{ENV}:292-296"),
        Fact("A random reset adds white noise of +-20 degrees to joint positions and +-0.5 to joint velocities "
             "around the model keyframe, with an options angle_sweep override for the position amplitude",
             source="upstream_code", ref=f"{ENV}:352-360"),
        Fact("reset(seed) seeds numpy's global random generator", source="upstream_code", ref=f"{ENV}:348-349"),
        Fact("reset returns the observation dictionary from _get_obs()", source="upstream_code", ref=f"{ENV}:416"),
        Fact("A reset randomizes the ground tangential friction coefficient from the configured "
             "ground_friction_coeff range", source="upstream_code", ref=f"{ENV}:412-414"),
        Fact("close() closes the viewer if one was opened and clears it", source="upstream_code", ref=f"{ENV}:880-885"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "mujoco:gym_quadruped.QuadrupedEnv(go2, flat)",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) seeds numpy's global generator at quadruped_env.py:348-349, so one MuJoCo build "
                     "repeats a trajectory for the same seed and actions; the package's fake draws the initial "
                     "perturbation with Python's random.Random, so a seed gives different trajectories on the two",
        },
        "timestep_ms": 2.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "rigid-body MuJoCo dynamics with contacts and a terrain generated from the scene, but no actuator, "
            "sensor or noise model beyond a direct torque command: F2 is not claimed",
            "the fake backend is a pure Python stand-in: it has no contacts, friction, actuator model, sensors or "
            "terrain, and its one scalar integration step does not reproduce MuJoCo's equations of motion",
            "the fake never terminates or truncates: the upstream invalid-contact and out-of-terrain checks are not "
            "modelled",
            "the fake's initial state is perturbed with Python's random.Random while upstream uses numpy's global "
            "generator, so the same seed does not replay the same trajectory on both",
            "no physical quadruped is modelled and the environment was never validated against one: F3 is not "
            "claimed",
            "the fake is a separate pure Python implementation of the upstream interface and was not compared with "
            "the upstream simulator where this package was authored; the sim backend builds the real environment, "
            "but its contract is derived from the environment's spaces rather than from a recorded trajectory",
        ],
    }
