"""OpenMHS MuJoCo driver for the pinned collab_qrc VLM exploration scene.

The upstream repository is a ROS 2 Humble multi-robot exploration stack for
Unitree Go2W (wheeled-legged) and Go2 (walking) quadrupeds.  Its MuJoCo path is
the ``mujoco_ros2_control`` node, which loads one MJCF scene and exposes the
world through the ROS 2 control and sensor graph.  The card names a
``RosDriver``, but its own candidate classes are ``cap.world.reset.v1``,
``cap.world.step.v1`` and ``cap.world.seed.v1``, its ``models`` list is a set of
MJCF scenes, and its mock strategy prefers the upstream simulator.

DEVIATION FROM THE CARD: this package serves the launch-bound MJCF scene directly
through :class:`MujocoDriver` instead of declaring a ROS transport.  The
production path is the official MuJoCo engine loading the same file.  The ROS 2
graph (``mujoco_ros2_control``, the controllers, the sensor bridges, Nav2 and
SLAM) is deliberately NOT COVERED: the package exposes the environment-step
interface, not the transport topics, and no ROS node or simulator is contacted
by the fake gate.

Every fact cites the pinned clone at f9e6998d2f7b086f60810b35683791c8c6a41d87.
The model is read from the read-only clone in place; it is never copied into the
package or modified.  This package is model-authored and unreviewed, and no
MuJoCo, ROS graph, simulator or hardware run is claimed.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

#: The launch-bound VLM scene, relative to the pinned clone root.
MODEL = "src/go2w/go2_gazebo_sim/mujoco/vlm_exploration_scene.xml"
#: The same file, from the package directory.
MODEL_PATH = "../../../../robots/hanshangzhu/collab_qrc/" + MODEL

#: The VLM launch selects this scene when no override is supplied.
_VLM_LAUNCH = "src/vlm_explorer/launch/single_vlm_mujoco_far.launch.py"
#: The base launch that starts the C++ MuJoCo node with the selected scene.
_BASE_LAUNCH = "src/go2w/go2_gazebo_sim/launch/single_go2w_mujoco_cfpa2.launch.py"
#: The selected MJCF scene.
_SCENE = MODEL


class CollabQrcSim(MujocoDriver):
    device_id = "collab_qrc"
    device_kind = "world.sim"
    mode = "simulated"
    # Direct world stepping is isolated simulated state (MHS-004 SAFE-006); the
    # package exposes no physical mobile-base or actuator command.
    risk = "R0"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    tags = ["mujoco", "mjcf", "simulation", "quadruped", "go2w", "go2",
            "ros2", "multi-robot"]
    display_name = "collab_qrc MuJoCo VLM exploration scene"
    vendor = "hanshangzhu"
    model = "vlm_exploration_scene"
    facts = [
        Fact("The README describes heterogeneous multi-robot autonomy on Unitree Go2W (wheeled-legged) "
             "and Go2 (walking) quadrupeds with ROS 2 Humble, a MuJoCo simulation and a native ROS 1 Noetic "
             "deployment on the real Go2's Jetson Orin NX.",
             source="vendor_doc", ref="README.md:3"),
        Fact("The README architecture diagram starts from 'MuJoCo ops2 (500 Hz)' or a real or HIL Mid-360 "
             "LiDAR, followed by mujoco_sensor_bridge or livox_ros_driver2.",
             source="vendor_doc", ref="README.md:20-21"),
        Fact("The README lists 'mujoco_ros2_control/' as the DFKI MuJoCo ros2_control hardware interface.",
             source="vendor_doc", ref="README.md:157"),
        Fact("The VLM MuJoCo launch defaults mujoco_model_path to "
             "go2_gazebo_sim/mujoco/vlm_exploration_scene.xml when the argument is empty.",
             source="upstream_code", ref=f"{_VLM_LAUNCH}:142-146"),
        Fact("The base MuJoCo launch starts the mujoco_ros2_control node with robot_model_path set to the "
             "selected MJCF, simulation_frequency 500.0 and real_time_factor 1.0.",
             source="upstream_code", ref=f"{_BASE_LAUNCH}:281-291"),
        Fact("The scene is an MJCF model named vlm_exploration_scene that compiles angles in radians and "
             "resolves mesh files from the assets directory.",
             source="upstream_code", ref=f"{_SCENE}:1-2"),
        Fact("The scene sets option timestep 0.002 s, gravity 0 0 -9.81, the implicitfast integrator and "
             "elliptic friction cones.",
             source="upstream_code", ref=f"{_SCENE}:4-5"),
        Fact("The Go2W base body starts at pos 4.0 0 0.6 and carries a free joint named root.",
             source="upstream_code", ref=f"{_SCENE}:158-161"),
        Fact("The base body carries the free joint root and each of the four legs carries hip, thigh, calf "
             "and foot joints, 16 named leg and foot joints in total.",
             source="upstream_code", ref=f"{_SCENE}:161-349"),
        Fact("The go2 default class sets the motor ctrlrange to -23.7 23.7, the knee class overrides it to "
             "-45.43 45.43, and the abduction/front_hip/back_hip/knee classes bound the leg joint ranges.",
             source="upstream_code", ref=f"{_SCENE}:18-36"),
        Fact("The actuator block has 12 motor actuators on the leg joints and four velocity actuators on the "
             "foot joints; each velocity actuator declares ctrlrange -15 15.",
             source="upstream_code", ref=f"{_SCENE}:361-381"),
        Fact("The scene declares accelerometer, gyro, foot touch and base frame sensors.",
             source="upstream_code", ref=f"{_SCENE}:384-402"),
        Fact("The knee default class sets the joint range -2.7227 -0.83776.",
             source="upstream_code", ref=f"{_SCENE}:33-36"),
        Fact("The README's License section says: 'Research project. Contact maintainers for licensing.'",
             source="vendor_doc", ref="README.md:183-185"),
        Fact("The go2_gazebo_sim package manifest declares the MIT licence.",
             source="upstream_code", ref="src/go2w/go2_gazebo_sim/package.xml:4-8"),
    ]
    safe_state = (
        "The simulation stops advancing: after an e-stop no cap.world.step.v1 or cap.world.reset.v1 call is "
        "accepted until mhs.safety.reset clears the latch, while the integration state stays readable."
    )
    #: The real path is the official MuJoCo engine loading the same scene.  It
    #: was not installed or run here, so the deployment is described, not
    #: validated; the ROS 2 control and sensor graph is outside this package.
    fidelity = {
        "engine": "mujoco:vlm_exploration_scene",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "none",
            "notes": "The bridge does not claim seeded or exact continuation: MuJoCo determinism depends on "
                     "the engine version, model, options and any callbacks or plugins.",
        },
        "timestep_ms": 2.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the real sim backend was not run: MuJoCo is not installed here, so the scene was never compiled "
            "(its OBJ and STL meshes in the clone's assets directory were not loaded) and no trajectory was "
            "compared with the official engine",
            "mj_resetData restores qpos0: the base body at pos 4.0 0 0.6 and every leg and foot joint at 0, "
            "which lies outside the calf joints' -2.7227..-0.83776 range; the scene has no keyframe, and the "
            "twelve motors take raw torques with no controller, so nothing holds the legs unless a caller "
            "supplies torques",
            "a step without an action keeps applying the last ctrl, which stays in data.ctrl until a reset; "
            "in this lockstep bridge the world advances only inside a step call",
            "the package steps the MJCF directly; the upstream ROS 2 runtime (mujoco_ros2_control, the "
            "ros2_control controllers, the sensor bridges, Nav2 and SLAM) is not reproduced",
            "contact, friction, inertia, actuator force limits and sensor physics are those of the model "
            "file and are not validated against a physical robot",
            "the scene resolves mesh files from the clone's assets directory; the package does not copy or "
            "modify those assets",
            "the control vector mixes 12 motor torque-like entries and four wheel velocity entries; the "
            "package declares the model's ctrlrange values and does not claim physical units",
            "the scene's sensors (IMU, foot touch, base frame) are not read or published by this package",
        ],
    }
    #: The deployed fake is a package-local stand-in for the mujoco module.  It
    #: parses the same scene for model shape, actuator names and ctrlranges, but
    #: runs no MuJoCo physics.
    fidelity_by_backend = {
        "fake": {
            "engine": "analytic:MuJoCo API stand-in (no MuJoCo engine)",
            "fidelity_level": "F0",
            "determinism": {
                "kind": "none",
                "notes": "Event-driven placeholder integration with no contact, constraint or force solver; "
                         "the same control input reproduces the same placeholder state hash, but this is a "
                         "stand-in digest, not a MuJoCo trajectory or state-hash replay.",
            },
            "timestep_ms": 2.0,
            "realtime_factor": 0,
            "clock": "lockstep",
            "reset": "full",
            "snapshot_restore": True,
            "gaps": [
                "the fake is a package-local stand-in for the mujoco module: it parses the MJCF and its "
                "includes for model shape, actuator names and ctrlranges, but it loads no meshes, textures, "
                "inertias or contacts and runs no MuJoCo physics",
                "each actuator's force (gear * ctrl for the 12 motors, kv * (ctrl - qvel) for the four "
                "velocity actuators) accelerates only its own joint against a placeholder unit inertia, with a "
                "placeholder damping on the motor joints; the free base, gravity, contacts, friction, joint "
                "limits, force limits and sensor physics are not integrated (model review 2026-11-05: it used "
                "to treat every control value as a joint velocity)",
                "reset restores qpos0 from the MJCF (base pos 4.0 0 0.6, identity quaternion, joints at their "
                "ref of 0) as mj_resetData does; it used to zero every qpos entry, including the quaternion",
                "the snapshot uses the bridge's basic profile (time, qpos, qvel, act and ctrl) because the "
                "stand-in exposes no full integration-state API; warm-start and derived quantities are not "
                "preserved",
                "the upstream ROS 2 graph, mujoco_ros2_control, the controllers, the sensor bridges, Nav2, "
                "SLAM and rendering are NOT COVERED",
                "the published timestep_ms is read from the model's option element, but the fake's state "
                "advance is a placeholder and does not establish MuJoCo timing or determinism",
            ],
        },
    }
