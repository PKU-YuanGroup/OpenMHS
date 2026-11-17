"""OpenMHS driver for gh.soltanilara/av-aloha: the ``gym_guided_vision`` InsertPeg Gymnasium environment.

The card classifies the repository as a simulated Gymnasium environment (``family: gymnasium``), so this is a
configuration-only :class:`mhs.driver.GymnasiumDriver`: ``env_id`` names the registered environment
``gym_guided_vision/InsertPeg-3Arms-v0`` and the bridge derives ``cap.world.step.v1``, ``cap.world.reset.v1`` and
``cap.world.seed.v1`` from the environment's spaces and reset signature.  No Limit is declared: the bridge derives
``action.values`` from the environment's action space, and the upstream action space is the unbounded
``Box(-inf, inf, (21,), float32)`` of ``env.py:87``.

The gate cannot import the clone (and the clone needs MuJoCo and dm_control), so ``backends["fake"]`` is the
package's ``FakeInsertPegEnv`` (``fake.py``), an analytic stand-in with the upstream action layout and observation
keys, not the upstream simulator and not a recording.  A backend name that ``backends`` does not list (``sim``) is
served by ``gymnasium.make(env_id)`` (``GymnasiumDriver.open_native``); that path needs ``gym_guided_vision``,
MuJoCo and dm_control installed and was not run here.

Every Fact cites a line of the clone at the pinned commit 65da5200dda9200ced58bc3dadb5345f4703d017.  This package is
model-authored and unreviewed; it was checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "gym_guided_vision/gym_guided_vision/env.py"
CONSTANTS = "gym_guided_vision/gym_guided_vision/constants.py"
REGISTRY = "gym_guided_vision/gym_guided_vision/__init__.py"


class AVAlohaInsertPeg(GymnasiumDriver):
    """The registered 3-arm InsertPeg environment of ``gym_guided_vision``."""

    device_id = "av-aloha-insert-peg"
    env_id = "gym_guided_vision/InsertPeg-3Arms-v0"
    native = "gym_guided_vision.env:InsertPegEnv"
    backends = {"fake": ".fake:FakeInsertPegEnv"}
    action_space_ref = f"{ENV}:87"
    display_name = "AV-ALOHA gym_guided_vision InsertPeg (3 arms)"
    vendor, model = "soltanilara", "gym_guided_vision/InsertPeg-3Arms-v0"
    tags = ["av-aloha", "aloha", "gymnasium", "mujoco", "manipulation", "insert-peg", "simulation"]
    facts = [
        Fact("The ENVS entry for gym_guided_vision/InsertPeg-3Arms-v0 selects InsertPegEnv with num_arms=3, six "
             "cameras and 480x640 observations", source="upstream_code",
             ref=f"{REGISTRY}:6-12"),
        Fact("The registry loop constructs entry points as gym_guided_vision.env followed by the ENVS class name",
             source="upstream_code", ref=f"{REGISTRY}:88-91"),
        Fact("The six camera names are zed_cam_left, zed_cam_right, wrist_cam_left, wrist_cam_right, overhead_cam "
             "and worms_eye_cam", source="upstream_code", ref=f"{CONSTANTS}:8-15"),
        Fact("The observation space is a Dict of per-camera Box(480, 640, 3) uint8 pixels and an agent_pos Box of "
             "num_joints float64 values", source="upstream_code", ref=f"{ENV}:36-85"),
        Fact("The action space is Box(-inf, inf, (num_joints,), float32)", source="upstream_code",
             ref=f"{ENV}:87"),
        Fact("num_joints is 21 for three arms and 14 for two arms", source="upstream_code",
             ref=f"{ENV}:60-64"),
        Fact("The physics timestep is 0.002 s and 20 physics steps make one environment step (SIM_DT 0.04 s)",
             source="upstream_code", ref=f"{CONSTANTS}:20-23"),
        Fact("step advances the physics by SIM_PHYSICS_ENV_STEP_RATIO physics steps", source="upstream_code",
             ref=f"{ENV}:217-218"),
        Fact("step applies six left joint targets and the left gripper, six right joint targets and the right "
             "gripper, and the seven middle joint targets when num_arms is 3", source="upstream_code",
             ref=f"{ENV}:203-226"),
        Fact("The gripper normalization divides by the model's ctrlrange span and the unnormalization multiplies "
             "back", source="upstream_code", ref=f"{ENV}:156-161"),
        Fact("step documents the left and right gripper actions as values from 0 to 1", source="upstream_code",
             ref=f"{ENV}:203-207"),
        Fact("reset restores the physics, applies the fixed arm poses and open-gripper commands, calls forward and "
             "returns the observation with is_success False", source="upstream_code", ref=f"{ENV}:228-249"),
        Fact("The base step always returns terminated=False and truncated=False, and reports success only in info "
             "as reward == max_reward", source="upstream_code", ref=f"{ENV}:222-224"),
        Fact("InsertPegEnv sets max_reward to 4", source="upstream_code", ref=f"{ENV}:420"),
        Fact("InsertPegEnv.get_reward starts at 0, sets 1 for both gripper contacts, 2 for both gripper contacts "
             "without either table contact, 3 for peg-hole contact without either table contact, and finally 4 "
             "for pin contact", source="upstream_code", ref=f"{ENV}:425-472"),
        Fact("InsertPegEnv.reset draws the peg and hole placements from the global numpy RNG with "
             "np.random.uniform after the seeded super().reset", source="upstream_code", ref=f"{ENV}:474-496"),
        Fact("The environments are registered with nondeterministic=True because even seeded rendered observations "
             "differ slightly", source="upstream_code", ref=f"{REGISTRY}:88-94"),
        Fact("close closes the passive viewer when one was opened", source="upstream_code",
             ref=f"{ENV}:400-408"),
        Fact("SlotInsertionEnv loads task_slot_insertion.xml and sets max_reward to 4", source="upstream_code",
             ref=f"{ENV}:503-508"),
        Fact("SewNeedleEnv loads task_sew_needle.xml and sets max_reward to 5", source="upstream_code",
             ref=f"{ENV}:592-597"),
        Fact("TubeTransferEnv loads task_tube_transfer.xml and sets max_reward to 3", source="upstream_code",
             ref=f"{ENV}:693-698"),
        Fact("HookPackageEnv loads task_hook_package.xml and sets max_reward to 4", source="upstream_code",
             ref=f"{ENV}:782-787"),
        Fact("The separate RealEnv imports InterbotixManipulatorXS, JointSingleCommand and rospy",
             source="upstream_code", ref="data_collection_scripts/real_env.py:28-30"),
        Fact("RealEnv.reset reboots gripper motors, opens and closes grippers, then moves all three arms",
             source="upstream_code", ref="data_collection_scripts/real_env.py:176-185"),
        Fact("The simulation assets LICENSE names Trossen Robotics and has three redistribution conditions",
             source="vendor_doc", ref="gym_guided_vision/gym_guided_vision/assets/LICENSE:1-16"),
    ]
    safe_state = ("the lockstep fake stops advancing once in-flight work settles; the runtime latch refuses step, "
                  "reset and seed until mhs.safety.reset clears it; state stays readable; no stop of the separate "
                  "ROS/Interbotix RealEnv or physical arms is claimed")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2); differences of the fake are in
    #: ``gaps``.  The bridge derives the engine, the determinism kind and the lockstep clock; they are written out so
    #: the whole contract reads in one place.
    fidelity = {
        "engine": "gymnasium:gym_guided_vision/InsertPeg-3Arms-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "statistical",
            "seed_control": "none",
            "notes": "reset(seed) calls the Gymnasium Env reset and seeds np_random, but InsertPegEnv.reset draws "
                     "the peg and hole placement from the global numpy RNG (env.py:482, 489) and the registration "
                     "sets nondeterministic=True (__init__.py:92-94), so a seed does not reproduce a trajectory; "
                     "the dynamics are deterministic only for an identical starting state",
        },
        "timestep_ms": 40.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is an analytic stand-in, not the upstream MuJoCo simulator: it has no rigid-body "
            "dynamics, contacts, gravity, constraints, actuator model, peg or hole object, or contact-based "
            "reward; its joints follow the commanded targets immediately and its reward is always 0",
            "the upstream renders six cameras at 480x640x3 uint8 (env.py:66-85, __init__.py:9-11); the fake "
            "returns a 2x2x3 placeholder image per camera to keep receipts small",
            "the fake is not a recording and was not compared with the upstream environment: gym_guided_vision, "
            "MuJoCo and dm_control were not importable where the gate ran",
            "reset(seed) does not control the upstream peg and hole placement (env.py:482, 489), so even the real "
            "simulation is only statistically deterministic",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms (40 ms per "
            "environment step) only",
            "snapshot and restore are not offered: the environment exposes no get_state/set_state, so no "
            "checkpoint profile is declared",
            "the upstream simulator backend (sim) is gymnasium.make(env_id) and needs gym_guided_vision, MuJoCo "
            "and dm_control installed; that path was not run here",
            "only InsertPegEnv is served; GuidedVisionEnv is its base and SlotInsertionEnv, SewNeedleEnv, "
            "TubeTransferEnv and HookPackageEnv are separate tasks outside this package",
            "data_collection_scripts/real_env.py contains a separate ROS/Interbotix RealEnv; its reset reboots "
            "gripper motors and moves the arms (:176-185); no RealEnv factory or hardware route is served",
            "the repository licence remains NOASSERTION on the card and requires an owner publication decision; "
            "the Trossen Robotics assets LICENSE has separate three-clause redistribution conditions",
        ],
    }
    fidelity_by_backend = {
        "fake": {
            "engine": "analytic:av-aloha-insert-peg-fake",
            "determinism": {
                "kind": "exact",
                "seed_control": "none",
                "notes": "the fake has fixed placeholder arm poses and pixels, no peg/hole objects and reward 0; "
                         "its outputs repeat independently of seed, unlike the upstream task placement",
            },
        },
    }
