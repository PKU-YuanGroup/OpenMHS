"""OpenMHS driver for gh.rgalljamov/learn2walk: the MimicWalker3d-v0 MuJoCo walking environment (a Gymnasium
family driver).

The card calls this package a ``MujocoDriver`` family, but the entry symbol is a legacy Gym environment
(``MimicWalker3dEnv(MimicEnv)``, ``MimicEnv(MujocoEnv, EzPickle)``), not a raw MuJoCo model.  A ``MujocoDriver``
would expose the MJCF model's joint and actuator vectors only and would drop the environment's reward, phase-driven
observation and terminal semantics.  The helper is therefore ``GymnasiumDriver`` and the package serves the
environment-step interface (``cap.world.step.v1`` / ``cap.world.reset.v1`` / ``cap.world.seed.v1``); this is a
deviation from the card's helper, not from its simulated, family-config decision.

The upstream package cannot be constructed at the pinned commit (see the fidelity gaps and RESULT.json): the
``gym_mimic_envs.mujoco`` initializer imports a missing ``mimic_walker2d`` module, the configured model
``walker3d_flat_feet_lowmass.xml`` is absent from the tree, and the reference-trajectory loader points at absolute
paths outside the clone.  The package is checked on its own pure-Python analytic stand-in (``fake``); no upstream
simulator or hardware run is claimed.  The ``native`` class and every constant are read from the pinned clone at
09d3bbd64a6b2fdd538b1d4465001bb1914243de.
"""

from mhs.driver import Fact, GymnasiumDriver

WALKER = "mujoco/gym_mimic_envs/mujoco/mimic_walker3d.py"
ENV = "mujoco/gym_mimic_envs/mimic_env.py"
REF = "scripts/mocap/ref_trajecs.py"
CFG = "scripts/config_light.py"
COMMON = "scripts/common/config.py"
XML = "mujoco/gym_mimic_envs/mujoco/assets/walker3d_flat_feet.xml"


class MimicWalker3d(GymnasiumDriver):
    device_id = "learn2walk-walker3d"
    env_id = "MimicWalker3d-v0"
    native = "gym_mimic_envs.mujoco.mimic_walker3d:MimicWalker3dEnv"
    backends = {"fake": ".fake:FakeMimicWalker3dEnv"}
    # No action_space_ref: the configured lowmass model is missing. The fake's finite envelope is placeholder
    # data borrowed from the other, available XML; it is not the selected environment's verified action space.
    display_name = "learn2walk MimicWalker3d-v0 (MuJoCo biped)"
    vendor, model = "rgalljamov", "learn2walk (MimicWalker3d-v0)"
    tags = ["biped", "walking", "humanoid", "mujoco", "gym", "reinforcement-learning", "simulation"]
    facts = [
        Fact("MimicWalker3dEnv is a concrete subclass of MimicEnv", source="upstream_code", ref=f"{WALKER}:31"),
        Fact("MimicEnv is a subclass of gym's MujocoEnv and EzPickle", source="upstream_code", ref=f"{ENV}:27"),
        Fact("MimicWalker3dEnv implements the base class hooks: COM indices [0, 1, 2], trunk rotation indices "
             "[3, 4, 5], the not-actuated joints [0, 1, 2, 3, 4, 5], and maximum actuator velocities "
             "[5, 1, 10, 10, 5, 1, 10, 10]", source="upstream_code", ref=f"{WALKER}:59-84"),
        Fact("The constructor reads the model file name from config_light.WALKER_MJC_XML_FILE, builds the mocap "
             "reference trajectories, joins the name below assets/, and calls MimicEnv.__init__ with the XML path "
             "and the reference object", source="upstream_code", ref=f"{WALKER}:37-47"),
        Fact("The configured model file name is walker3d_flat_feet_lowmass.xml", source="upstream_code",
             ref=f"{CFG}:28"),
        Fact("The reference trajectories are loaded from a hard-coded absolute assets path: /home/rustam/code/"
             "remote/ on remote machines and /mnt/88E4BD3EE4BD2EF6/... elsewhere; data paths are built from that "
             "root", source="upstream_code", ref=f"{REF}:26-35"),
        Fact("MimicWalker3d-v0 is registered with entry point gym_mimic_envs.mujoco:MimicWalker3dEnv",
             source="upstream_code", ref="mujoco/gym_mimic_envs/__init__.py:8-10"),
        Fact("The gym_mimic_envs.mujoco package initializer imports MimicWalker2dEnv from mimic_walker2d, so "
             "importing the package entry point executes that import first", source="upstream_code",
             ref="mujoco/gym_mimic_envs/mujoco/__init__.py:1"),
        Fact("MimicEnv builds the simulation with MujocoEnv.__init__(xml_path, frame_skip), then sets the model "
             "timestep to 1 / SIM_FREQ and control_freq = SIM_FREQ / frame_skip, syncs the reference trajectories "
             "to that control frequency and overwrites actuator_forcerange with the configured torque ranges",
             source="upstream_code", ref=f"{ENV}:53-63"),
        Fact("The simulation runs at SIM_FREQ = 1000 Hz and the control loop at CTRL_FREQ = 200 Hz",
             source="upstream_code", ref=f"{CFG}:30-32"),
        Fact("The configured peak joint torques are [50, 50, 50, 5] for hip_sag, hip_front, knee and ankle",
             source="upstream_code", ref=f"{CFG}:35-36"),
        Fact("get_torque_ranges repeats its four peak arguments for both sides into an 8 by 2 range",
             source="upstream_code", ref=f"{COMMON}:29-33"),
        Fact("frame_skip is SIM_FREQ / CTRL_FREQ and must be an integer", source="upstream_code",
             ref=f"{ENV}:184-189"),
        Fact("The MJCF model uses the RK4 integrator with timestep 0.001 s and defines the default motor ctrlrange "
             "as -300 to 300", source="upstream_code", ref=f"{XML}:8-11"),
        Fact("The actuator list has eight motors: hip sagittal, hip frontal, knee and ankle, right then left",
             source="upstream_code", ref=f"{XML}:71-80"),
        Fact("MimicEnv.step rescales the action, mirrors it in a mirroring mode, calls do_simulation(action, "
             "frame_skip), advances the reference trajectories, builds the observation, computes the imitation "
             "reward, evaluates the terminal condition and returns (observation, reward, done, {})",
             source="upstream_code", ref=f"{ENV}:66-131"),
        Fact("In torque mode rescale_actions clips every policy action to [-1, 1] and scales it by "
             "PEAK_JOINT_TORQUES * 2", source="upstream_code", ref=f"{ENV}:155-164"),
        Fact("The constant-speed mocap dataset contains 35 steps of walking at 1.5 m/s sampled at 400 Hz",
             source="vendor_doc", ref="assets/ref_trajecs/mocaps_readme.md:3"),
        Fact("The observation is [phase, desired walking speed] + qpos[1:] + qvel; the 3D layout runs from index "
             "0 (phase) and 1 (desired velocity) through 28 (left ankle velocity)", source="upstream_code",
             ref=f"{ENV}:351-388"),
        Fact("The imitation reward uses weights from config.rew_weights for a sum of pose, velocity, COM and "
             "power rewards, or sqrt(pose) * sqrt(COM) in MOD_REW_MULT, and multiplies by rew_scale",
             source="upstream_code", ref=f"{ENV}:540-559"),
        Fact("The reward weights string is '8200' outside MOD_FLY and '7300' in MOD_FLY; rew_scale is 1 and the "
             "alive bonus is 0.2 * rew_scale", source="upstream_code", ref=f"{COMMON}:128-146"),
        Fact("The episode ends when the COM height is below 0.5, the episode duration reaches cfg.ep_dur_max or "
             "the walked distance exceeds cfg.max_distance + 0.01; outside evaluation it also ends on early "
             "termination", source="upstream_code", ref=f"{ENV}:109-124"),
        Fact("The configured maximum episode length is 3000 steps and the maximum walking distance is 10",
             source="upstream_code", ref=f"{CFG}:8-10"),
        Fact("Early termination thresholds are COM height below 0.75, sagittal trunk angle above 0.3 or below "
             "-0.05, frontal deviation above 0.2, axial deviation above 0.5 and absolute lateral COM position "
             "above 0.2; MOD_FLY disables the COM-height condition",
             source="upstream_code", ref=f"{ENV}:583-610"),
        Fact("reset_model calls get_init_state, applies qpos/qvel, subtracts the lowest foot-site z from COM z, "
             "checks reward > 0.95 * rew_scale outside MOD_FLY, advances the reference trajectories and returns "
             "the observation", source="upstream_code",
             ref=f"{ENV}:440-473"),
        Fact("README.md names mimic_walker3d.py as the main environment used to train walking policies and "
             "walker3d_flat_feet.xml as the model that defines the morphology and inertial properties",
             source="vendor_doc", ref="README.md:36-40"),
    ]
    safe_state = ("the lockstep fake stops advancing once in-flight work settles: the bridge latch refuses step, "
                  "reset and seed until mhs.safety.reset clears it; state stays readable; no native stop or "
                  "construction of the broken upstream environment is claimed")
    fidelity_level = "F0"
    fidelity = {
        "engine": "analytic:learn2walk-walker3d",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake draws its initial phase with Python's random.Random(seed) and every later transition "
                     "is a deterministic analytic update, so a fresh fake world repeats a trajectory for the same "
                     "seed and actions; the upstream class was not constructed or compared, so this claim is about "
                     "the deployed fake only",
        },
        "timestep_ms": 5.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is an analytic, phase-driven stand-in, not MuJoCo: it models no rigid-body dynamics, "
            "contacts, friction, actuators, sensors or noise; one tick is the 5 ms control period "
            "(SIM_FREQ 1000 Hz / CTRL_FREQ 200 Hz) and the action only perturbs a synthetic reference gait",
            "the upstream environment cannot be constructed at the pinned commit: the gym_mimic_envs.mujoco "
            "initializer imports mimic_walker2d (mujoco/gym_mimic_envs/mujoco/__init__.py:1), that file is absent; "
            "the configured walker3d_flat_feet_lowmass.xml (scripts/config_light.py:28) is absent from the assets "
            "directory, which contains walker3d_flat_feet.xml; and the reference loader uses hard-coded absolute "
            "paths outside the clone (scripts/mocap/ref_trajecs.py:26-35)",
            "the fake's [-300, 300] action envelope is placeholder data borrowed from the available XML; the "
            "configured lowmass XML is absent, so no upstream action-space provenance is claimed; MimicEnv clips "
            "policy actions to [-1, 1] in torque mode (mujoco/gym_mimic_envs/mimic_env.py:161), as the fake does",
            "the reward is an analytic imitation-like stand-in using the configured weights and alive bonus; it is "
            "not the upstream reference-trajectory reward and no trajectory was compared with a real MuJoCo run",
            "the fake uses a constant 1.5 m/s desired speed instead of the configured ramp trajectories; its "
            "zero-reference termination deviations and terminal rewards are placeholders",
            "the fake exposes legacy reset() plus seed(seed); the bridge's keyword reset falls back to these; "
            "reset options are ignored, and the upstream inherited Gym implementation is outside the clone",
            "the observation space is unbounded and 29 values wide, matching the class layout; the fake returns "
            "Python floats and lists where the upstream returns numpy arrays",
            "no rendering, no snapshot or restore (the upstream class exposes no get_state/set_state pair) and no "
            "wall-clock pacing: realtime_factor is 0 and only commands advance the world",
            "the upstream dependency set is gym, mujoco-py and MuJoCo 2.1, none of which is installed where the "
            "gate runs; package code never imports the clone",
        ],
    }
