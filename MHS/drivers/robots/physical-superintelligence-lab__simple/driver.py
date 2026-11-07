"""OpenMHS driver for gh.physical-superintelligence-lab/simple: the Franka tabletop grasp environment.

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives the
``cap.world.step.v1`` action schema and limits from the environment's action space.  ``simple/FrankaTabletopGraspMP-v0``
is registered with ``TabletopGraspEnv`` and the task ``franka_tabletop_grasp_mp``; the task's action space is the
Franka controller's, a ``Dict`` with one ``arm`` entry of 7 joint values bounded by -1.0 and 1.0
(``src/simple/robots/controllers/qpos.py:74``).  ``cap.world.reset.v1`` takes ``{seed, options}`` and
``cap.world.seed.v1`` takes ``{seed}``.

The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no operator-required
limit.  The upstream environment needs Python 3.10, MuJoCo 3.3.6, IsaacSim 4.5 and an RTX-class GPU (pyproject.toml,
README.md), so the gate cannot open it; the ``fake`` backend is this package's pure Python kinematic stand-in
(fake.py), checked on the fake backend only.  A backend name that ``backends`` does not list (``sim``) is served by
``gymnasium.make(env_id, **env_kwargs)`` (GymnasiumDriver.open_native); that path needs the upstream package and was
not run here.  The fake does not model the camera observations; their real sizes are named in the fidelity ``gaps``.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002):
every member of ``device.schema.json`` that applies to a simulator without a physical counterpart.  Every constant
and rule cites a line of the clone at the pinned commit (6d10628794d9c7de4596b4f2afb2c054a637c2bc).  This package is
model-authored and unreviewed.
"""

from mhs.driver import Fact, GymnasiumDriver

ENVS = "src/simple/envs/__init__.py"
BASE = "src/simple/envs/base_dual_env.py"
TABLETOP = "src/simple/envs/tabletop_grasp.py"
TASK = "src/simple/tasks/franka_tabletop_grasp_mp.py"
CORE_TASK = "src/simple/core/task.py"
FRANKA = "src/simple/robots/franka_fr3.py"
COMBO = "src/simple/robots/controllers/combo.py"
QPOS = "src/simple/robots/controllers/qpos.py"
MUJOCO = "src/simple/engines/mujoco.py"


class SimpleFrankaTabletopGrasp(GymnasiumDriver):
    device_id = "simple-franka-tabletop-grasp"
    env_id = "simple/FrankaTabletopGraspMP-v0"
    env_kwargs = {"sim_mode": "mujoco"}
    # The conformance suite invokes step repeatedly after a successful grasp (the task terminates then); with
    # autoreset the bridge starts the next episode instead of refusing the step with PRECONDITION_UNMET.
    autoreset = True
    native = "simple.envs.tabletop_grasp:TabletopGraspEnv"
    backends = {"fake": ".fake:FakeTabletopGraspEnv"}
    action_space_ref = f"{QPOS}:74"
    display_name = "SIMPLE Franka tabletop grasp (MuJoCo)"
    vendor, model = "physical-superintelligence-lab", "simple/FrankaTabletopGraspMP-v0"
    tags = ["simple", "franka", "tabletop-grasp", "mujoco", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("simple/FrankaTabletopGraspMP-v0 is registered with entry point "
             "simple.envs.tabletop_grasp:TabletopGraspEnv and task franka_tabletop_grasp_mp", source="upstream_code",
             ref=f"{ENVS}:12-16"),
        Fact("BaseDualSim defaults sim_mode to mujoco_isaac and always builds MuJoCo; a mode without 'isaac' sets "
             "the Isaac Sim simulator to None", source="upstream_code", ref=f"{BASE}:41-68"),
        Fact("The environment takes action_space and observation_space from the task",
             source="upstream_code", ref=f"{BASE}:71-72"),
        Fact("The task's action_space is the robot controller's action space", source="upstream_code",
             ref=f"{TASK}:241-244"),
        Fact("The controller action space is a Dict with one 'arm' entry", source="upstream_code",
             ref=f"{COMBO}:24-28"),
        Fact("The arm PD joint-position controller is configured with joint1 to joint7", source="upstream_code",
             ref=f"{FRANKA}:63-65"),
        Fact("Each arm joint action is bounded by -1.0 and 1.0", source="upstream_code", ref=f"{QPOS}:74"),
        Fact("The Franka Research 3 robot has 9 degrees of freedom", source="upstream_code", ref=f"{FRANKA}:27"),
        Fact("The parallel gripper is configured with the two finger joints finger_joint1 and finger_joint2",
             source="upstream_code", ref=f"{FRANKA}:67-70"),
        Fact("_get_obs returns agent, joint_qpos and eef_pose and merges the rendered camera frames into the "
             "observation", source="upstream_code", ref=f"{TABLETOP}:83-88"),
        Fact("The observation space bounds agent and joint_qpos to -pi..pi with robot.dof entries and eef_pose to "
             "-inf..inf with 7 entries, and adds the camera spaces of the task sensor configs", source="upstream_code",
             ref=f"{TASK}:247-262"),
        Fact("The task configures a 640x360 front stereo camera, a 480x270 wrist camera, a 480x270 second wrist "
             "camera and a 640x360 side camera", source="upstream_code", ref=f"{TASK}:53-105"),
        Fact("The task metadata defaults physics_dt to 0.002 s and render_hz to 30", source="upstream_code",
             ref=f"{TASK}:41-46"),
        Fact("MujocoSimulator reads physics_dt from the task metadata", source="upstream_code", ref=f"{MUJOCO}:40"),
        Fact("MujocoSimulator reads need_gravity from the task metadata and defaults it to False",
             source="upstream_code", ref=f"{MUJOCO}:55"),
        Fact("MujocoSimulator sets the MuJoCo model timestep to physics_dt", source="upstream_code",
             ref=f"{MUJOCO}:129-132"),
        Fact("Without need_gravity, MujocoSimulator.step advances MuJoCo from the current physics time to the end "
             "of the next render frame (render_step + 1) / render_hz using the model timestep", source="upstream_code",
             ref=f"{MUJOCO}:64-75"),
        Fact("reset calls task.reset(seed, options), updates the MuJoCo layout, steps it once, clears step_count and "
             "_success, and returns the observation and info", source="upstream_code", ref=f"{TABLETOP}:101-122"),
        Fact("step applies the action, steps MuJoCo, increments step_count, computes the reward and success, never "
             "truncates, and returns obs, reward, terminated, truncated and info", source="upstream_code",
             ref=f"{TABLETOP}:124-140"),
        Fact("The task reward is clip((target height - initial target height) / _LIFT_HEIGHT, 0, 1)",
             source="upstream_code", ref=f"{TASK}:291-297"),
        Fact("_LIFT_HEIGHT is 0.02 m", source="upstream_code", ref=f"{TASK}:32"),
        Fact("check_success returns reward >= 1.0", source="upstream_code", ref=f"{TASK}:287-289"),
        Fact("Task.reset seeds the domain randomizer with dr.reset(seed=seed) unless an option carries a state_dict",
             source="upstream_code", ref=f"{CORE_TASK}:144-149"),
        Fact("close closes the MuJoCo simulator and the Isaac Sim application if it was loaded, then calls "
             "gym.Env.close", source="upstream_code", ref=f"{BASE}:126-139"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the last observation and the fake state are kept and stay "
                  "readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the
    #: determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "mujoco:simple/FrankaTabletopGraspMP-v0",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the domain randomisation and the fake's initial jitter, "
                     "so one implementation repeats a trajectory for the same seed and actions; the fake draws "
                     "initial values with Python's random.Random while the upstream task seeds numpy-based domain "
                     "randomisers, so a seed gives different worlds on the two",
        },
        "timestep_ms": 2.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "rigid-body dynamics and contacts are those of the MuJoCo model built from the task layout; no actuator, "
            "sensor or noise model is claimed, and the fake backend is not the MuJoCo engine",
            "no wall-clock pacing: realtime_factor 0; an OpenMHS tick is one env.step and the fake advances one "
            "placeholder control step per tick",
            "control period: the physics timestep is 2 ms (the task's physics_dt, set on the MuJoCo model), while one "
            "env.step advances MuJoCo to the end of the next render frame at render_hz 30 (about 16-17 physics steps, "
            "a control period of about 33.3 ms); timestep_ms names the physics timestep per FID-015 and the package "
            "has no operating_notes field, so the control period is disclosed here",
            "no physical device is modelled and the model was never validated against one",
            "the fake is a pure Python kinematic stand-in: it implements only the scalar observation members agent, "
            "joint_qpos and eef_pose, not the camera images the upstream _get_obs returns through _render_frame; the "
            "real camera observations are 640x360 for front_stereo_left, front_stereo_right and side_left and "
            "480x270 for wrist and wrist_left",
            "the upstream package needs Python 3.10, MuJoCo 3.3.6, IsaacSim 4.5 and an RTX GPU (pyproject.toml, "
            "README.md); it was not installed or run where the gate ran, so the fake was not compared with the "
            "upstream environment",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
            "the fake's step, jitter and pose constants are placeholders, not calibrated values; only the reward "
            "shape and the success threshold follow the task code cited in the facts",
        ],
    }
