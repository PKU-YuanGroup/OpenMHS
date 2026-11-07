"""OpenMHS driver for gh.ycyao216/dexverse: the Dexverse-GraspKettle-v0 environment (a Gymnasium family driver).

DexVerse is a benchmark of tabletop dexterous-manipulation tasks built on Isaac Lab (README.md:31-32).  The card's
entry symbol is ``GraspKettleEnvFloatingDexHandRightCfg``, the concrete configuration registered as
``Dexverse-GraspKettle-v0`` (tasks/config/functional/__init__.py:17); it drives a floating right Shadow hand to grasp a
kettle and pour it over a mug (tasks/config/functional/grasp_kettle_cfg.py:65-71).

A GymnasiumDriver is configuration only: ``env_id`` names the environment and the bridge derives the whole contract
from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with a 28-value action vector,
``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0):
there is no hardware backend, no e-stop path to a machine and no operator-required limit.

The gate cannot build the upstream environment: it needs Isaac Sim 5.1.0, Isaac Lab v2.3.2, a CUDA GPU and gated USD
assets (README.md:84-101 and :144-146), and package code never imports the clone.  The ``fake`` backend is therefore
the package's own reduced pure Python environment (fake.py); a backend name that ``backends`` does not list (``sim``)
is served by ``gymnasium.make(env_id)`` (GymnasiumDriver.open_native), which was not run here.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002).
Every fact cites a line of the clone at the pinned commit (30cc673e27684b9f10186fa6bea731aed246bc9f).  This package
is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

FUNCTIONAL = "source/dexverse/dexverse/tasks/config/functional"
KETTLE = f"{FUNCTIONAL}/grasp_kettle_cfg.py"
REGISTRATION = "source/dexverse/dexverse/tasks/utils/registration.py"
BASE = "source/dexverse/dexverse/tasks/dexverse_base_env_cfg.py"
FUNCTIONAL_BASE = f"{FUNCTIONAL}/base_cfg.py"
FLOATING = "source/dexverse/dexverse/robot_agents/shadow/floating.py"
REWARDS = "source/dexverse/dexverse/tasks/mdp/rewards.py"
WRIST_ORIGIN = "source/dexverse/dexverse/devices/wrist_origin.py"


class DexVerseGraspKettle(GymnasiumDriver):
    device_id = "dexverse-grasp-kettle"
    env_id = "Dexverse-GraspKettle-v0"
    native = "dexverse.tasks.config.functional.grasp_kettle_cfg:GraspKettleEnvFloatingDexHandRightCfg"
    backends = {"fake": ".fake:FakeDexVerseGraspKettleEnv"}
    display_name = "DexVerse GraspKettle (floating right Shadow hand, Isaac Lab)"
    vendor, model = "The DexVerse Project Developers", "Dexverse-GraspKettle-v0"
    tags = ["dexverse", "isaac-lab", "dexterous-manipulation", "functional-grasping", "pouring", "simulation",
            "gymnasium"]
    facts = [
        Fact("Dexverse-GraspKettle-v0 is registered to GraspKettleEnvFloatingDexHandRightCfg", source="upstream_code",
             ref=f"{FUNCTIONAL}/__init__.py:17"),
        Fact("The registration entry point is isaaclab.envs:ManagerBasedRLEnv with disable_env_checker=True and the "
             "environment configuration passed as env_cfg_entry_point", source="upstream_code",
             ref=f"{REGISTRATION}:27-36"),
        Fact("GraspKettleEnvFloatingDexHandRightCfg is the functional kettle task: grasp the kettle by the handle, "
             "then lift it and pour over a mug", source="upstream_code", ref=f"{KETTLE}:65-71"),
        Fact("The kettle success thresholds are pour_lift_height 0.15 m, pour_angle_rad 45 degrees about the local "
             "+X axis and pour_goal_xy_threshold 0.05 m", source="upstream_code", ref=f"{KETTLE}:89-95"),
        Fact("The kettle object is configured with mass 0.5 kg, half-height 0.04 m, and static and dynamic "
             "friction 2.0", source="upstream_code", ref=f"{KETTLE}:74-80"),
        Fact("The kettle resets x in [-0.05, 0.15] m, y in [-0.3, -0.1] m and yaw in [2.84, 3.44] rad",
             source="upstream_code", ref=f"{KETTLE}:85-87"),
        Fact("The mug that is the pour goal resets x in [-0.15, 0.15] m and y in [0.05, 0.3] m", source="upstream_code",
             ref=f"{KETTLE}:123-124"),
        Fact("The table top is at height 0.6 m", source="upstream_code", ref=f"{BASE}:36"),
        Fact("The floating right Shadow hand is controlled by three joint-position action terms: 3 translation "
             "joints, 3 rotation joints in z, y, x order and the 22 Shadow finger joints, all with scale 1.0",
             source="upstream_code", ref=f"{FLOATING}:99-113"),
        Fact("The relative retargeter layout has 28 output values: wrist translation indices 0-2, wrist rotation "
             "indices 3-5 and 22 finger indices 6-27", source="upstream_code", ref=f"{FLOATING}:116-126"),
        Fact("Isaac Lab's JointPositionActionCfg defaults to use_default_offset=True, so a joint target is "
             "action * scale + default joint position", source="upstream_code", ref=f"{WRIST_ORIGIN}:15-18"),
        Fact("Control runs at 60 Hz: decimation is 2", source="upstream_code", ref=f"{BASE}:1252"),
        Fact("The simulation timestep is 1/120 s", source="upstream_code", ref=f"{BASE}:1318"),
        Fact("The episode length is 20 s", source="upstream_code", ref=f"{FUNCTIONAL_BASE}:467"),
        Fact("A time_out term with time_out=True ends an episode at the time limit", source="upstream_code",
             ref=f"{BASE}:1017"),
        Fact("The action penalties are action_l2 and action_rate_l2, each with weight -0.005", source="upstream_code",
             ref=f"{BASE}:1011-1012"),
        Fact("The action_l2_clamped and action_rate_l2_clamped terms sum squared actions and squared action changes "
             "over the action dimension and clamp each sum to [-1000, 1000]", source="upstream_code",
             ref=f"{REWARDS}:44-51"),
        Fact("The observation layout is grouped into policy (last action), proprio (joint positions), contact, state "
             "(object pose), privileged (velocities), goal, rgb, depth and pointcloud", source="upstream_code",
             ref=f"{BASE}:728-756"),
        Fact("The functional grasping observation layout adds a state group with object position and orientation "
             "and a goal group", source="upstream_code", ref=f"{FUNCTIONAL_BASE}:204-238"),
        Fact("The zero-action script samples a full action vector as 2 * rand - 1 from the action-space shape "
             "before multiplying it by zero", source="upstream_code", ref="scripts/zero_agent.py:312-313"),
        Fact("The package installs with python -m pip install -e source/dexverse", source="vendor_doc",
             ref="README.md:123"),
        Fact("The supported setup installs Isaac Sim 5.1.0 and Isaac Lab v2.3.2 with CUDA 12.8 PyTorch builds",
             source="vendor_doc", ref="README.md:84-101"),
        Fact("The robot hand and object/scene assets are not stored in the git repository; they come from the gated "
             "dexverse/DexVerse_release Hugging Face dataset and must be downloaded before any environment can run",
             source="vendor_doc", ref="README.md:144-146"),
    ]
    safe_state = ("the simulation stops advancing: the runtime latches the e-stop before any further step or reset, "
                  "and the environment state stays readable until mhs.safety.reset clears the latch")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The fake is F0: it reproduces
    #: the action and observation contract and the episode timing, not the rigid-body simulation.
    fidelity = {
        "engine": "gymnasium:Dexverse-GraspKettle-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake reset(seed) seeds Python's random.Random and draws the kettle and mug reset poses from "
                     "the ranges of grasp_kettle_cfg.py, so one seed and one action sequence repeat on this fake; "
                     "upstream Isaac Lab uses its own random generators and physics, so the two were never compared",
        },
        "timestep_ms": 1000.0 / 60.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "no rigid-body simulation: the fake has no Isaac Sim/Isaac Lab physics, no contacts, no actuators, no "
            "sensors, no cameras and no object or hand USD assets; the joint positions follow the commanded targets",
            "the upstream observation groups (policy, proprio, contact, state, privileged, goal, rgb, depth, "
            "pointcloud) are reduced to policy, proprio, state and goal arrays with fixed sizes that the clone does "
            "not state; camera, depth and point-cloud observations are absent",
            "the task success and termination terms of the upstream environment (the kettle lift, tilt and xy pour "
            "criteria, object out-of-bound and forbidden-zone contact) are not modelled; episodes only truncate at "
            "episode_length_s = 20 s = 1200 control steps",
            "the 28-value action vector is the dimension of the Shadow hand action terms, and each value is bounded "
            "to [-1, 1] following the range the zero-action script samples; the clone does not state Isaac Lab's exact "
            "action-space bounds, and the fake does not apply the articulation's scale, offset or joint limits",
            "the fake's object and goal poses are redrawn from the configured reset ranges on every reset but do not "
            "move with the action; the real task simulates the kettle, mug and hand together",
            "snapshot and restore are not offered: the fake exposes no get_state or set_state",
            "the real environment was never built or run: it needs Isaac Sim 5.1.0, Isaac Lab v2.3.2, a CUDA GPU and "
            "the gated assets (README.md:84-101 and :144-146), none of which were installed here",
        ],
    }
