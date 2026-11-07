"""OpenMHS driver for gh.discoverse-dev/mujoco-lidar: the Unitree G1 LiDAR scene (a MuJoCo family driver).

A MujocoDriver is configuration only: ``model_path`` names the MJCF scene and the bridge derives the whole contract
from the model it loads.  ``cap.world.step.v1`` takes ``{ticks, action: {ctrl: [nu numbers]}}``; each ``ctrl`` is
bounded per actuator by the model's ``actuator_ctrlrange`` (29 position actuators, one per joint, whose range is the
joint range through ``inheritrange="1"``) and the bridge steps ``mj_step`` that many times.  ``cap.world.reset.v1``
runs ``mj_resetData``/``mj_forward`` and returns the model defaults; the state is
``{time_ms, qpos, qvel, ctrl, tick, timestep_ms, seed}``.

The card lists five scenes.  This package serves the card's main model, ``models/scene_g1.xml`` (``models[0]``), the
scene the G1 example loads (``examples/unitree_g1.py:15``): it includes the G1 MJCF model, which carries a site named
``lidar`` (``models/unitree_g1/g1_mjx_feetonly.xml:265``), and it has 29 position actuators whose control ranges are
the joint ranges (``:13``, ``:388-422``).  The LiDAR scan itself is not part of ``cap.world.*``: the upstream wrapper
turns two ray-angle arrays into a distance array of the same shape (``docs/en/API.md:33-47``), and neither the
standard nor this family carries that array.  It is therefore NOT COVERED (see RESULT.json); the package serves the
simulated world the scan would be taken in, not the range image.

The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no operator-required
limit.  The gate cannot install MuJoCo where it runs, so the ``fake`` backend is this package's stand-in ``mujoco``
module (fake.py); it reads the same model file for the model shape but its integration is a placeholder, not
MuJoCo's physics, and the fidelity ``gaps`` say so.  A backend name that ``backends`` does not list (``sim``) imports
the real ``mujoco`` module and loads the same file; that path was not run here.  The model file is read from the
read-only clone at the pinned commit; the package copies neither the model nor its assets and never imports the
upstream package.  Every Fact cites a line of the clone at commit e6b879df4b96daaed30ef10fe02650d29048fa9b.  This
package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

SCENE = "models/scene_g1.xml"
ROBOT = "models/unitree_g1/g1_mjx_feetonly.xml"
SHARED = "models/scene.xml"
EXAMPLE = "examples/unitree_g1.py"
#: The card's main scene, relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/discoverse-dev/mujoco-lidar/" + SCENE


class LidarScene(MujocoDriver):
    device_id = "mujoco-lidar"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "MuJoCo-LiDAR Unitree G1 scene (MuJoCo model)"
    vendor, model = "DISCOVERSE", "MuJoCo-LiDAR G1 scene"
    tags = ["mujoco", "simulation", "lidar", "unitree-g1", "world", "scene"]
    facts = [
        Fact("The card's main scene includes the Unitree G1 MJCF model", source="upstream_code", ref=f"{SCENE}:2"),
        Fact("The card's main scene also includes the shared obstacle and ground scene scene.xml", source="upstream_code",
             ref=f"{SCENE}:3"),
        Fact("The G1 model integrates with the Euler scheme at a 0.002 s timestep", source="upstream_code",
             ref=f"{ROBOT}:4"),
        Fact("The G1 model carries a site named 'lidar' on the torso at position 0 0 0.405", source="upstream_code",
             ref=f"{ROBOT}:265"),
        Fact("The body tree has a freejoint named floating_base_joint and 29 named hinge joints", source="upstream_code",
             ref=f"{ROBOT}:136-358"),
        Fact("The actuator section has 29 position actuators, one per leg, waist, arm and wrist joint",
             source="upstream_code", ref=f"{ROBOT}:388-422"),
        Fact("The position actuator default sets inheritrange to 1, so an actuator's ctrlrange is its joint range: "
             "the hip pitch -2.5307 to 2.8798, the hip roll -0.5236 to 2.9671 and the knee -0.087267 to 2.8798",
             source="upstream_code", ref=f"{ROBOT}:13-27"),
        Fact("The scene's home keyframe supplies a qpos and ctrl starting pose", source="upstream_code",
             ref=f"{SCENE}:5-21"),
        Fact("The included scene.xml adds a ground plane and four wall boxes around the robot", source="upstream_code",
             ref=f"{SHARED}:19-23"),
        Fact("The G1 example loads models/scene_g1.xml", source="upstream_code", ref=f"{EXAMPLE}:15"),
        Fact("The G1 example constructs MjLidarWrapper for that model with site_name 'lidar'", source="upstream_code",
             ref=f"{EXAMPLE}:66-71"),
        Fact("MjLidarWrapper takes the MuJoCo model and the name of the LiDAR site", source="vendor_doc",
             ref="docs/en/API.md:19-23"),
        Fact("MjLidarWrapper.trace_rays traces rays and returns a distance array with the same shape as the theta and "
             "phi ray angles", source="vendor_doc", ref="docs/en/API.md:33-47"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the timestep, the determinism kind and the lockstep clock; the gaps below are this package's.
    fidelity = {
        "engine": "mujoco:g1",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "MuJoCo integrates one model deterministically from one initial state; the bridge takes no seed "
                     "input and a reset restores the model defaults, so a run repeats exactly on the same engine but "
                     "no seed selects a different one",
        },
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it reads the model file for the "
            "actuator count, the control ranges and the qpos/qvel layout but integrates a placeholder first-order "
            "motion of each actuated joint toward its control target, so trajectories, contacts and actuator "
            "dynamics are not MuJoCo's",
            "no mesh or texture of the asset directory is loaded and no contact, equality, tendon or sensor "
            "constraint is resolved by the stand-in",
            "NOT COVERED: the LiDAR range image (one distance per ray, the same shape as the theta and phi arrays) "
            "and the point cloud that MjLidarWrapper.trace_rays produces; cap.world.step.v1 and cap.world.reset.v1 "
            "carry the world state only, so the scan, the scan patterns, the cpu/taichi/jax/warp backends, the cutoff "
            "distance and the sensor pose are not exposed by this package",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared with "
            "the real engine, and no LiDAR scan was produced",
            "no physical LiDAR or robot is modelled and nothing was validated against hardware",
        ],
    }
