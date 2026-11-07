"""OpenMHS driver for gh.limxdynamics/humanoid-description: the LimX HU_D03 humanoid MJCF as a MuJoCo world.

The upstream repository is a robot-description package: URDF, MuJoCo MJCF and USD files for the HU_D03 and HU_D04
humanoids (README.md:5).  It contains no controller executable, ROS node, topic, service or action: each description
package's CMakeLists installs the meshes, urdf, xml and world directories and builds nothing (CMakeLists.txt:11-41),
and the package manifest declares no message, service or action definition (package.xml:3-24).  A RosDriver would have
no pinned endpoint or type to bind, so this package follows the MJCF instead: a ``MujocoDriver`` over the card's
primary model, ``HU_D03_description/xml/HU_D03_03.xml`` (``models[0]``).  This is a deliberate deviation from the
card's static ``family:ros`` scan.

A ``MujocoDriver`` is configuration only: ``model_path`` names the MJCF and the bridge derives the contract from the
model it loads.  ``cap.world.step.v1`` takes ``{ticks, action: {ctrl: [...]}}``; each ``ctrl`` element is checked
against that actuator's ``ctrlrange`` (the model limits every motor, ``HU_D03_description/xml/HU_D03_03.xml:406-443``)
before it is written to ``data.ctrl``, then ``mj_step`` runs ``ticks`` times.  ``cap.world.reset.v1`` restores the
model defaults with ``mj_resetData`` + ``mj_forward``.  The world state is the bridge's integration state (``time_ms``,
``qpos``, ``qvel``, ``ctrl``, ``tick``, ``timestep_ms``, ``seed``).

The model file is read from the read-only clone at the pinned commit (it is never copied into this package and never
imported).  MuJoCo is not installed where the gate runs, so ``backends["fake"]`` is this package's stand-in ``mujoco``
module (fake.py); it parses the same MJCF for the joint dimensions and the actuator ctrlranges, but its integration is
a placeholder, not MuJoCo's physics.  ``fidelity`` describes the real-engine backend (F1); ``fidelity_by_backend``
publishes the stand-in's own F0 contract for the fake (model review, 2026-11-05: the fake was published with the
F1 contract before, and the stand-in treated the torque motors' control values as position targets).  This package
is model-authored and unreviewed: it is checked on the fake backend only and no hardware is attached.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL = "HU_D03_description/xml/HU_D03_03.xml"
MODEL_PATH = "../../../../robots/limxdynamics/humanoid-description/" + MODEL
XML = "HU_D03_description/xml/HU_D03_03.xml"
CMAKE = "HU_D03_description/CMakeLists.txt"
MANIFEST = "HU_D03_description/package.xml"
D03_README = "HU_D03_description/README"
D04_README = "HU_D04_description/README"
README = "README.md"


#: Gaps of the fake backend only: the stand-in module is not MuJoCo.
_FAKE_GAPS = [
    "the fake backend is a stand-in for the mujoco library, not MuJoCo: it reads the MJCF for the joint dimensions "
    "and the per-motor ctrlranges, and integrates a placeholder torque-like motion: each motor's control value "
    "accelerates its joint through a placeholder gain against a placeholder damping, with no inertia, gravity, "
    "contact, joint limit or equality constraint, so trajectories, actuator dynamics and the free-base dynamics are "
    "not MuJoCo's",
    "the stand-in moves each motor's own joint; the ankle and waist motors drive rod joints whose linkage to the "
    "ankle and waist is a set of connect equality constraints that the stand-in does not resolve",
    "the stand-in derives qpos0 from the MJCF text (the free joint at the base_link pose 0 0 1.0 with an identity "
    "quaternion, identity quaternions for the six ball joints, zero for every hinge) and restores it on reset, but "
    "it runs no mj_forward and resolves no constraint, so the reset pose is not settled by physics",
    "the fake has no mj_getState/mj_setState/mj_stateSize, so the bridge uses its basic checkpoint profile: time, "
    "qpos, qvel, ctrl and actuator activation are restored, not MuJoCo's full integration state",
]

#: Gaps of every backend.
_SHARED_GAPS = [
    "no mesh or texture is loaded by the stand-in, and no backend exposes the model's IMU site, joint-position "
    "sensors or force/torque sensors",
    "no rendering is offered; the bridge exposes qpos, qvel, ctrl and time, not the model's camera or sensor arrays",
    "the package serves the card's models[0] only; the HU_D04 model (models[1]), which the README recommends "
    "because HU_D03 is discontinued, is not served",
    "the upstream is a description repository with no controller executable, ROS node, topic, service or action; "
    "this package drives the bare MJCF plant with raw motor torques, not a deployed robot, a controller or a ROS "
    "graph, so the humanoid falls unless a caller supplies balancing torques",
    "no physical HU_D03 robot is modelled or driven; this simulated package has no hardware backend and nothing "
    "was validated against hardware",
]


class LimxHumanoidDescription(MujocoDriver):
    device_id = "limx-hu-d03"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "LimX HU_D03 humanoid description (MuJoCo)"
    vendor, model = "LimX Dynamics", "HU_D03_03"
    tags = ["limx", "hu-d03", "humanoid", "mujoco", "description", "simulation", "robot"]
    facts = [
        Fact("The repository provides URDF, MuJoCo MJCF and USD robot descriptions for the LimX HU_D03 and HU_D04 "
             "humanoids, for ROS, MuJoCo and NVIDIA Isaac Sim.", source="vendor_doc", ref=f"{README}:5"),
        Fact("The README's available-models table names HU_D03_03.xml and HU_D04_01.xml as the MuJoCo MJCF files "
             "for HU_D03 and HU_D04.", source="vendor_doc", ref=f"{README}:9-12"),
        Fact("The README marks HU_D03 as discontinued and says to use HU_D04 instead.", source="vendor_doc",
             ref=f"{README}:18"),
        Fact("The MuJoCo quick start runs python -m mujoco.viewer with HU_D04_description/xml/HU_D04_01.xml.",
             source="vendor_doc", ref=f"{README}:50-51"),
        Fact("The HU_D03 package README names HU_D03_description/xml/HU_D03_03.xml as its MJCF.",
             source="vendor_doc", ref=f"{D03_README}:5"),
        Fact("The HU_D04 package README names HU_D04_description/xml/HU_D04_01.xml as its MJCF.",
             source="vendor_doc", ref=f"{D04_README}:5"),
        Fact("The HU_D03 CMakeLists installs the meshes, urdf, xml and world directories into the ROS package share "
             "for ROS 1 and ROS 2, or into etc/ when only AMENT_PREFIX_PATH is set; it defines no executable target.",
             source="upstream_code", ref=f"{CMAKE}:11-41"),
        Fact("The HU_D03 CMakeLists header reads '© [2025] LimX Dynamics Technology Co., Ltd. All rights reserved.'",
             source="upstream_code", ref=f"{CMAKE}:1-3"),
        Fact("The HU_D03 package manifest names HU_D03_description, leaves its licence field as TODO, declares "
             "catkin/ament build types with roscpp/rclcpp dependencies, and declares no message, service or action "
             "definition.", source="upstream_code", ref=f"{MANIFEST}:3-24"),
        Fact("The README's licence section names the Apache License 2.0 and the LICENSE file.", source="vendor_doc",
             ref=f"{README}:58-60"),
        Fact("The HU_D03 MJCF root element declares the model name HU_D03_03.", source="upstream_code", ref=f"{XML}:1"),
        Fact("The HU_D03 MJCF compiler sets angle='radian' and meshdir='../meshes/HU_D03_03/'.",
             source="upstream_code", ref=f"{XML}:2"),
        Fact("The HU_D03 MJCF sets its integration timestep to 0.001 s.", source="upstream_code", ref=f"{XML}:16"),
        Fact("The HU_D03 base body base_link is placed at pos='0 0 1.0' and carries the free joint "
             "floating_base_joint.", source="upstream_code", ref=f"{XML}:90-92"),
        Fact("The left_hip_pitch_joint is a hinge joint limited to -3.1415 to 3.1415 rad with armature 0.15257125.",
             source="upstream_code", ref=f"{XML}:102"),
        Fact("The actuator section declares motors for the legs, waist, head, arms and hands, and every motor sets "
             "ctrllimited='true' with an explicit ctrlrange.", source="upstream_code", ref=f"{XML}:406-443"),
        Fact("The hip and knee motor ctrlranges are -120 to 120 and the ankle motor ctrlranges are -45 to 45.",
             source="upstream_code", ref=f"{XML}:407-419"),
        Fact("The waist motor ctrlranges are -45 to 45 and the head motor ctrlranges are -18 to 18.",
             source="upstream_code", ref=f"{XML}:421-426"),
        Fact("The left arm motor ctrlranges are -30 to 30 for the shoulder and elbow motors and -18 to 18 for the "
             "wrist and hand motors.", source="upstream_code", ref=f"{XML}:428-434"),
        Fact("The right arm motor ctrlranges are -30 to 30 for the shoulder and elbow motors and -18 to 18 for the "
             "wrist and hand motors.", source="upstream_code", ref=f"{XML}:436-442"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The real-engine contract (the bridge over the mujoco module).  The fake backend is the package's stand-in module,
    #: whose F0 contract ``fidelity_by_backend`` selects below (model review, 2026-11-05).
    fidelity = {
        "engine": "mujoco:HU_D03_03",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "none",
            "seed_control": "none",
            "notes": "The bridge reports determinism 'none': cap.world.reset.v1 restores the model defaults with "
                     "mj_resetData and takes no seed, and a native checkpoint does not establish hidden-state, "
                     "contact or RNG completeness.",
        },
        "timestep_ms": 1.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": _SHARED_GAPS + [
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared "
            "with the real engine",
        ],
    }
    #: The fake backend is the package's stand-in mujoco module, not MuJoCo and not a recording: F0, no physics.
    fidelity_by_backend = {
        "fake": {
            "engine": "analytic:stand-in mujoco module (no physics)",
            "fidelity_level": "F0",
            "determinism": {
                "kind": "none",
                "seed_control": "none",
                "notes": "The stand-in is deterministic, but its placeholder motion is not the engine's physics; "
                         "cap.world.reset.v1 restores zeros and takes no seed.",
            },
            "timestep_ms": 1.0,
            "realtime_factor": 0,
            "clock": "lockstep",
            "reset": "full",
            "snapshot_restore": True,
            "gaps": _FAKE_GAPS + _SHARED_GAPS,
        },
    }
