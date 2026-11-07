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

The device is simulated (R0): there is no hardware backend and no physical stop.  The ``fake`` backend is the
package's own pure Python stand-in (fake.py) because the gate cannot import ``mujoco``, ``numpy``, ``scipy`` or
``gymnasium``; it was not compared with the upstream simulator.  Every fact cites a line of the clone at the pinned
commit (097a8d649ae2232d3c0ed5eb83dc0e4f77483019).  This package is model-authored and unreviewed: it is checked on
the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "gym_quadruped/quadruped_env.py"
UTILS = "gym_quadruped/utils/quadruped_utils.py"
CONFIG = "gym_quadruped/robot_cfgs.py"


class GymQuadruped(GymnasiumDriver):
    device_id = "gym-quadruped"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R0"
    native = "gym_quadruped.quadruped_env:QuadrupedEnv"
    backends = {"fake": ".fake:FakeQuadrupedEnv"}
    env_kwargs = {"robot": "go2", "scene": "flat"}
    display_name = "gym-quadruped MuJoCo quadruped locomotion environment"
    vendor, model = "IIT-DLSLab", "gym-quadruped"
    tags = ["quadruped", "legged-locomotion", "mujoco", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("QuadrupedEnv is constructed from a robot name and defaults to the flat scene, the default observation "
             "names, sim_dt 0.002 s, the forward velocity command of 0.5 m/s and 0.0 rad/s, ground friction 1.0 and "
             "the leg order FL, FR, RL, RR", source="upstream_code", ref=f"{ENV}:85-99"),
        Fact("The default observations are qpos, qvel, tau_ctrl_setpoint, feet_pos:base and feet_vel:base",
             source="upstream_code", ref=f"{ENV}:80"),
        Fact("The observation space is a gymnasium Dict of Box bounds built from the model's joint ranges and "
             "actuator control ranges", source="upstream_code", ref=f"{UTILS}:250-326"),
        Fact("The action space is a gymnasium Box of shape (mjModel.nu,): one torque per actuator, with low and high "
             "taken from actuator_forcerange", source="upstream_code", ref=f"{ENV}:224-235"),
        Fact("The scene model is loaded from robot_model/scene_<scene>.xml and its terrain is generated for the "
             "robot's hip height", source="upstream_code", ref=f"{ENV}:150-155"),
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
            "the upstream environment was not imported where the gate ran (mujoco, numpy, scipy and gymnasium are "
            "not installed for the gate), so the fake was not compared with the upstream simulator and the sim "
            "backend was not run",
        ],
    }
