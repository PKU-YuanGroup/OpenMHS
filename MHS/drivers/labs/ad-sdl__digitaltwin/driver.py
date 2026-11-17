"""OpenMHS driver for gh.ad-sdl/digitaltwin: the bimanual OpenArm centrifuge Mimic environment.

The upstream repository is an Isaac Lab 3.0.0 task pack.  Its registered gym id
``Isaac-Centrifuge-Bimanual-OpenArm-IK-Abs-Mimic-v0`` has the Mimic wrapper
``rpl_centrifuge.openarm.mimic_env:CentrifugeBimanualOpenArmIKAbsMimicEnv`` as
its entry point; the wrapper inherits the Gymnasium environment interface from
``ManagerBasedRLMimicEnv`` (Isaac Lab, outside the clone).  The family driver is
therefore ``GymnasiumDriver``: ``env_id`` names the registration and
``cap.world.step.v1`` carries a 16-dimensional action whose layout and gripper
range are stated in the clone.  ``cap.world.reset.v1`` and
``cap.world.seed.v1`` cover reset and seed.

The gate cannot import the upstream package: it needs Isaac Lab, Isaac Sim,
torch and a Linux GPU host, and package code never imports the clone.  The
``fake`` backend is a small analytic stand-in (``.fake:FakeCentrifugeMimicEnv``)
that preserves the 16-element action order and the Gymnasium reset/step
interface, but models no physics, contacts or termination terms.  The inherited
``gymnasium.make`` fallback is explicitly refused: this package supplies only
the fake backend. A live adapter would need an Isaac application launcher,
a resolved cfg and tensor/batch conversion; installing the task pack alone
is not that adapter.

Every fact cites a line of the clone at the pinned commit
c8dfbd5998462d6fd0c1afb197f66b5a52c2d126.  The action-space bounds are not
stated in the clone (they come from Isaac Lab's action manager, an external
package), so ``action_space_ref`` is deliberately unset and the fake's bounds
are placeholders: the reference prints them as the fake backend's.  This
package is model-authored and unreviewed; fake evidence is contract evidence,
not a simulator or hardware run.
"""

from mhs.driver import DriverDefinitionError, Fact, GymnasiumDriver

ROOT = "tasks/centrifuge/tasks/src/rpl_centrifuge"
ENV_CFG = f"{ROOT}/openarm/env_cfg.py"
IK_ABS = f"{ROOT}/openarm/ik_abs_env_cfg.py"
MIMIC = f"{ROOT}/openarm/mimic_env.py"
REGISTER = f"{ROOT}/__init__.py"
TASK_README = "tasks/centrifuge/tasks/README.md"
INSTALL_DOC = "docs/01_install_isaaclab_release-3.0.0-beta2.md"


class DigitalTwinCentrifugeMimic(GymnasiumDriver):
    device_id = "digitaltwin"
    env_id = "Isaac-Centrifuge-Bimanual-OpenArm-IK-Abs-Mimic-v0"
    native = "rpl_centrifuge.openarm.mimic_env:CentrifugeBimanualOpenArmIKAbsMimicEnv"
    backends = {"fake": ".fake:FakeCentrifugeMimicEnv"}
    display_name = "AD-SDL Digital Twin centrifuge bimanual OpenArm Mimic environment"
    vendor, model = "AD-SDL", "Isaac-Centrifuge-Bimanual-OpenArm-IK-Abs-Mimic-v0"
    tags = ["centrifuge", "bimanual", "openarm", "imitation-learning", "isaac-lab", "simulation", "gymnasium"]
    facts = [
        Fact("The registered gym id Isaac-Centrifuge-Bimanual-OpenArm-IK-Abs-Mimic-v0 uses entry point "
             "rpl_centrifuge.openarm.mimic_env:CentrifugeBimanualOpenArmIKAbsMimicEnv and env cfg "
             "rpl_centrifuge.openarm.ik_abs_mimic_env_cfg:CentrifugeBimanualIkAbsMimicEnvCfg",
             source="upstream_code", ref=f"{REGISTER}:75-84"),
        Fact("The action tensor is 16-dimensional: [0:3] is the left arm position, [3:7] the left quaternion "
             "(qx, qy, qz, qw), [7:8] the left gripper, [8:11] the right arm position, [11:15] the right "
             "quaternion and [15:16] the right gripper, with positions in the robot root frame",
             source="upstream_code", ref=f"{MIMIC}:13-21"),
        Fact("Both gripper channels are scalars in [0, 1], consumed by the binary joint-position action",
             source="upstream_code", ref=f"{MIMIC}:18-21"),
        Fact("The arm actions are absolute target poses: both terms use command_type pose with "
             "use_relative_mode=False and differential IK with the dls method",
             source="upstream_code", ref=f"{IK_ABS}:260-279"),
        Fact("The binary gripper actions drive the finger joints to 0.044 for open and 0.0 for close",
             source="upstream_code", ref=f"{IK_ABS}:281-293"),
        Fact("The environment runs sim.dt=0.01 s (100 Hz) with decimation 5, so one environment step spans five "
             "physics steps", source="upstream_code", ref=f"{ENV_CFG}:398-402"),
        Fact("episode_length_s is 30.0 s", source="upstream_code", ref=f"{ENV_CFG}:400"),
        Fact("The termination terms are time_out at the episode length, tube_dropped when the tube root is below "
             "_SURFACE_Z - 0.30 m, and success once the tube has stayed inside the bucket for 3.0 s",
             source="upstream_code", ref=f"{ENV_CFG}:319-331"),
        Fact("No reward manager is configured: rewards, commands and curriculum are None",
             source="upstream_code", ref=f"{ENV_CFG}:393-396"),
        Fact("Observations are grouped into policy, an empty rgb_camera group and subtask_terms; the policy group "
             "holds joint positions and velocities, last action, left/right end-effector poses and tube/bucket poses",
             source="upstream_code", ref=f"{ENV_CFG}:243-316"),
        Fact("A reset randomizes the pickup station in x/y by (-0.03, 0.03) m and yaw by (-0.15, 0.15) rad, drops "
             "the tube into one of four rack wells from 0.15 m above the rack, and shifts the bucket in x/y by "
             "(-0.03, 0.03) m", source="upstream_code", ref=f"{ENV_CFG}:335-375"),
        Fact("The Mimic wrapper adds get_robot_eef_pose, target_eef_pose_to_action, action_to_target_eef_pose, "
             "actions_to_gripper_actions and get_subtask_term_signals to the ManagerBasedRLMimicEnv base",
             source="upstream_code", ref=f"{MIMIC}:44-192"),
        Fact("The package is an external Isaac Lab 3.0.0 task extension that bundles USD assets and registers its "
             "gym ids on import", source="vendor_doc", ref=f"{TASK_README}:3-11"),
        Fact("The prerequisites are Ubuntu 22.04+ with a recent NVIDIA driver and Isaac Sim 6.0.0 or 6.0.1",
             source="vendor_doc", ref=f"{INSTALL_DOC}:9-12"),
        Fact("The upstream README calls the scene geometry (robot mount and prop positions) and the XR anchor and "
             "retargeter offsets starting points that need in-sim tuning and cannot be validated without the GUI "
             "or a headset", source="vendor_doc", ref=f"{TASK_README}:32-34"),
        Fact("The task pack also contains SO101 physical leader-arm-over-USB variants and a GR1T2 variant",
             source="vendor_doc", ref=f"{TASK_README}:5-9"),
        Fact("The rendering script launches an Isaac application before importing rpl_centrifuge and supplies "
             "parse_env_cfg's result as cfg to gym.make",
             source="upstream_code", ref="tasks/centrifuge/tasks/scripts/render_images_from_demos.py:63-83"),
    ]
    safe_state = ("the fake world stops advancing: the latch refuses step, reset and seed until mhs.safety.reset; "
                  "the last fake state stays readable; no stop of Isaac Sim or physical equipment is claimed")
    fidelity_level = "F1"
    fidelity = {
        "engine": "isaaclab:Isaac-Centrifuge-Bimanual-OpenArm-IK-Abs-Mimic-v0",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "statistical",
            "notes": "the upstream reset randomizes the pickup station, the rack well and the bucket; the datagen "
                     "path seeds random/numpy/torch but this package ran no pair of seeded episodes, so no replay "
                     "equality is claimed for the Isaac Lab backend",
        },
        "timestep_ms": 50.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "only the fake backend is supplied; sim construction is refused because no application-launcher/cfg "
            "adapter or tensor/batch conversion is implemented; other clients and an independently running Isaac "
            "application are outside this fake's stop contract",
            "the real backend is Isaac Lab/Isaac Sim with PhysX rigid-body dynamics and contacts; it needs a Linux "
            "GPU host and was not run for this package, so contact, actuator, sensor and noise behaviour is "
            "unverified",
            "the clone does not state the arm action-space bounds: the differential-IK arm terms are configured but "
            "the Box comes from Isaac Lab's action manager, which is outside the clone; the real bounds were not "
            "observed",
            "the upstream README calls the scene geometry (robot mount and prop positions) and the XR anchor and "
            "retargeter offsets starting points that need in-sim tuning",
            "no snapshot or restore: the environment exposes no checkpoint protocol, so snapshot_restore is false",
            "the Mimic annotation methods (end-effector pose, action packing and subtask signals) are part of the "
            "native class but are not exposed through cap.world.*",
        ],
    }
    fidelity_by_backend = {
        "fake": {
            "engine": "analytic:centrifuge-mimic-placeholder",
            "fidelity_level": "F0",
            "determinism": {
                "kind": "seeded",
                "seed_control": "parameter",
                "notes": "reset(seed) fixes the fake's placeholder start offsets and the step path is deterministic; "
                         "the upstream RNG, USD scene and PhysX dynamics are not reproduced",
            },
            "timestep_ms": 50.0,
            "realtime_factor": 0,
            "clock": "lockstep",
            "reset": "full",
            "snapshot_restore": False,
            "gaps": [
                "fake-only package: the inherited live gymnasium.make fallback is refused; the SO101 physical "
                "leader-arm-over-USB variants and GR1T2 task are not served",
                "kinematic/analytic stand-in only: no physics, contacts, actuator, sensor or noise model; step echoes "
                "the action and advances a tick counter",
                "the 16-element action layout follows the upstream docstring, but the arm position and quaternion "
                "bounds are placeholders, not the upstream action space; only the two gripper channels are stated "
                "as [0, 1] upstream",
                "the observation is a 16-element echo of the last action, not the upstream Dict groups "
                "(policy, rgb_camera, subtask_terms); joint, end-effector and object dimensions are not modelled",
                "the termination terms are not modelled: the fake never reports success or tube_dropped; it truncates "
                "at the derived 600-step episode length (30.0 s divided by the 0.05 s control step)",
                "reset start offsets are placeholders drawn from a seeded Python RNG, not the upstream USD scene or "
                "its documented reset randomization ranges",
                "the Mimic helper methods are not implemented; the fake provides only reset, step, close and the "
                "Gymnasium action/observation spaces",
                "the fake was not compared with the upstream environment, which needs Isaac Lab, Isaac Sim, torch and "
                "a GPU",
            ],
        },
    }

    def open_native(self):
        if self.backend != "fake":
            raise DriverDefinitionError("this package supplies only the fake backend; no live Isaac adapter exists")
        return super().open_native()
