"""OpenMHS driver for gh.aalmuzairee/squint: the SO101LiftCube-v1 ManiSkill environment (a Gymnasium family driver).

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives the whole
``cap.world.*`` contract from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the
action ``{values}`` bounded per element to -1..1, the normalised action that ManiSkill serves for the
``pd_joint_target_delta_pos`` controller and scales to its joint deltas; ``cap.world.reset.v1`` takes
``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0): there is no hardware backend,
no e-stop path to a machine and no operator-required limit.

The gate cannot import ManiSkill/SAPIEN (see fake.py), so the ``fake`` backend is the package's own analytic stand-in
for ``envs.lift:LiftCube``.  A backend name that ``backends`` does not list (``sim``) is served by
``gymnasium.make("SO101LiftCube-v1")`` (GymnasiumDriver.open_native); that path needs the upstream package (see the
clone's ``environment.yaml``), registers the envs through ``envs/__init__.py`` and was not run here.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002).
Every constant and rule cites a line of the clone at the pinned commit (7086fd516eda7df585a5261c541e0670a6d916b4),
except the step bounds: ManiSkill, not the clone, writes the normalised space, so they have no source (fidelity gaps).
This package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

LIFT = "envs/lift.py"
SO101 = "envs/robot/so101.py"
BASE = "envs/base_random_env.py"
TRAIN = "train_squint.py"


class SO101LiftCube(GymnasiumDriver):
    device_id = "so101-lift-cube"
    env_id = "SO101LiftCube-v1"
    native = "envs.lift:LiftCube"
    backends = {"fake": ".fake:FakeSO101LiftCube"}
    display_name = "Squint SO-101 LiftCube (ManiSkill)"
    vendor, model = "Abdulaziz Almuzairee", "SO101LiftCube-v1"
    tags = ["so101", "manipulation", "lift", "reinforcement-learning", "simulation", "maniskill", "gymnasium"]
    facts = [
        Fact("SO101LiftCube-v1 is registered through mani_skill.utils.registration.register_env with "
             "max_episode_steps=50, and LiftCube fixes item_type to cube", source="upstream_code",
             ref=f"{LIFT}:407-410"),
        Fact("The Lift environment defaults to robot_uids='so101' and control_mode='pd_joint_target_delta_pos'",
             source="upstream_code", ref=f"{LIFT}:59-61"),
        Fact("The pd_joint_target_delta_pos controller is the six-joint delta controller (use_delta=True): its lower "
             "bounds are -0.1 for the five arm joints and -0.2 for the gripper, and its upper bounds are 0.1 and "
             "0.2; it does not set normalize_action, and the target variant only sets use_target=True",
             source="upstream_code", ref=f"{SO101}:97-109"),
        Fact("The default simulation config is SimConfig(sim_freq=100, control_freq=10): one control step advances "
             "0.1 s of simulated time", source="upstream_code", ref=f"{BASE}:146-148"),
        Fact("The wrist camera renders 128x128 images", source="upstream_code", ref=f"{BASE}:521-527"),
        Fact("The trainer renders at render_size 128 and downsamples the policy input to image_size 16",
             source="upstream_code", ref=f"{TRAIN}:107-110"),
        Fact("The state observation includes qvel, is_item_grasped, item_pose, tcp_pos, the item-to-tcp vector and "
             "the joint target distance to the rest pose", source="upstream_code", ref=f"{LIFT}:328-341"),
        Fact("Success requires the item to be lifted, grasped and the arm to be within 0.2 of the rest joint pose",
             source="upstream_code", ref=f"{LIFT}:354-373"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine
    #: and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "maniskill3:squint/SO101LiftCube-v1",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the initial joint and item state, and the stand-in's "
                     "step is deterministic, so one implementation repeats a trajectory for the same seed and "
                     "actions; the upstream environment draws from numpy/torch generators and simulates contacts, "
                     "so a seed does not give the same trajectory on the two",
        },
        "timestep_ms": 100.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is kinematic/analytic: the six joint targets add the scaled action deltas (a value in -1..1 "
            "times 0.1 for an arm joint and 0.2 for the gripper, envs/robot/so101.py:97-109) and are reached at "
            "once, with no rigid-body dynamics, contact, friction, actuator response, sensor noise or domain "
            "randomization",
            "the fake returns a 4x4x3 placeholder RGB frame and a 10-number state vector; the upstream wrist camera "
            "renders 128x128 (envs/base_random_env.py:521-527) and its state layout depends on obs_mode and the "
            "ManiSkill version (envs/lift.py:328-341)",
            "no camera render, segmentation, overlay or colour jitter is modelled",
            "the upstream env is truncated by the registered max_episode_steps=50; the stand-in truncates at the "
            "same step count but does not reproduce ManiSkill's time-limit wrapper",
            "the fake was not compared with the upstream ManiSkill environment (ManiSkill/SAPIEN were not installed "
            "where the gate ran)",
            "the step bounds -1..1 have no source: the controller config sets no normalize_action, and ManiSkill, "
            "which this clone does not contain, defaults it to True, serves Box(-1, 1) of the controller's shape "
            "and scales each value to the deltas (mani_skill/agents/controllers/pd_joint_pos.py:131, "
            "base_controller.py:70-72, mani_skill/utils/gym_utils.py:104-112, read in the ManiSkill clone at "
            "62ff3a58); environment.yaml:15 installs an unpinned mani_skill_nightly",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
        ],
    }
