"""OpenMHS driver for gh.cai23sbp/go2_parkour_deploy: the Unitree GO2 MJCF scene (a MuJoCo family driver).

A ``MujocoDriver`` is configuration only.  ``model_path`` names the card's first model, ``core/go2/scene.xml``, which
includes the robot model ``core/go2/go2.xml`` and adds a floor plane (``scene.xml:2``, ``scene.xml:19-21``).  The
bridge derives the contract from the model it loads: ``cap.world.step.v1`` takes ``{ticks, action: {ctrl: [...]}}``
with one ``ctrl`` element per actuator, each checked against the model's ``actuator_ctrlrange`` before it is written
to ``data.ctrl``, and then ``mj_step`` runs ``ticks`` times; ``cap.world.reset.v1`` restores the model defaults with
``mj_resetData`` + ``mj_forward``.  The published world state is the bridge's integration state (``time_ms``, ``qpos``,
``qvel``, ``ctrl``, ``tick``, ``timestep_ms``, ``seed``).

The upstream entry class ``mujoco_deploy.mujoco_env:MujocoEnv`` was confirmed at ``mujoco_deploy/mujoco_env.py:9``:
it loads the MJCF with ``mujoco.MjModel.from_xml_path`` (``mujoco_env.py:53-54``), resets with ``mj_resetData``
(``mujoco_env.py:71-72``) and advances with ``mj_step`` (``mujoco_env.py:93``).  This package does not import or run
that demo; it serves the same model through the SDK's MuJoCo bridge.  The device is simulated (R0): there is no
hardware backend, no e-stop path to a machine and no operator-required limit; the model file is the system of record
for the control envelope.

MuJoCo is not installed and cannot be installed where the acceptance gate runs (no network, no pip), so
``backends["fake"]`` is this package's stand-in ``mujoco`` module (``fake.py``).  It parses the same MJCF text with its
include expanded and takes the actuator count, the per-actuator control ranges, the joint dimensions and the option
time step from that tree, but its integration is a placeholder, not MuJoCo's physics; the fidelity ``gaps`` state
every difference.  A backend name that ``backends`` does not list (``sim``) imports the real ``mujoco`` module and
loads the same file; that path was not run here.

The model files are read from the read-only upstream clone at the pinned commit; they are never copied into this
package and the clone is never imported.  Every Fact cites a line of that clone at
5f04c3b51dcef3629a9500aef16e247d756fcd61.  This package is model-authored and unreviewed: it is checked on the fake
backend only, and nothing here ran the MuJoCo engine or a physical GO2.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

#: The card's models[0], relative to the clone root.
MODEL = "core/go2/scene.xml"
#: The same file through the read-only clone below the repository root (never imported, never copied).
MODEL_PATH = "../../../../robots/cai23sbp/go2_parkour_deploy/" + MODEL


class Go2Parkour(MujocoDriver):
    device_id = "go2_parkour"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "Unitree GO2 parkour deployment (MuJoCo simulation)"
    vendor, model = "Unitree", "GO2"
    tags = ["unitree", "go2", "quadruped", "parkour", "mujoco", "simulation", "robot"]
    facts = [
        Fact("The repository is a Unitree GO2 deployment trained with IsaacLab", source="vendor_doc",
             ref="README.md:3"),
        Fact("The repository supports deployment in a MuJoCo simulation and in the real world", source="vendor_doc",
             ref="README.md:5"),
        Fact("Real-world deployment code is still an unchecked TODO item", source="vendor_doc", ref="README.md:43"),
        Fact("The simulation entry point uses the 'lo' network interface to build a MujocoWrapper with "
             "core/go2/scene_parkour.xml", source="upstream_code", ref="core/deployment_player.py:21-22"),
        Fact("MujocoEnv loads the MJCF with mujoco.MjModel.from_xml_path and creates the data with mujoco.MjData",
             source="upstream_code", ref="mujoco_deploy/mujoco_env.py:53-54"),
        Fact("MujocoEnv.reset restores the model with mujoco.mj_resetData", source="upstream_code",
             ref="mujoco_deploy/mujoco_env.py:71-72"),
        Fact("MujocoEnv.step writes the action to data.ctrl and advances the model with mujoco.mj_step",
             source="upstream_code", ref="mujoco_deploy/mujoco_env.py:86-93"),
        Fact("The upstream sets model.opt.timestep from the environment configuration's sim.dt", source="upstream_code",
             ref="mujoco_deploy/mujoco_env.py:67"),
        Fact("The served scene core/go2/scene.xml includes the robot model go2.xml", source="upstream_code",
             ref="core/go2/scene.xml:1-2"),
        Fact("The parkour scene core/go2/scene_parkour.xml includes go2.xml and adds a height-field terrain from "
             "../terrain.png", source="upstream_code", ref="core/go2/scene_parkour.xml:1-16"),
        Fact("The go2 model compiles angles in radians and looks for meshes in the assets directory",
             source="upstream_code", ref="core/go2/go2.xml:2"),
        Fact("The go2 model option sets an elliptic cone and impratio 100 and states no timestep", source="upstream_code",
             ref="core/go2/go2.xml:4"),
        Fact("The go2 robot body starts at pos -7.5 0 0.5 and carries a free joint", source="upstream_code",
             ref="core/go2/go2.xml:64-70"),
        Fact("The go2 default class gives every motor a control range of -23.7 to 23.7", source="upstream_code",
             ref="core/go2/go2.xml:10"),
        Fact("The knee default class narrows the motor control range to -45.43 to 45.43", source="upstream_code",
             ref="core/go2/go2.xml:24"),
        Fact("The model declares twelve motor actuators, one for each hip, thigh and calf joint of the four legs",
             source="upstream_code", ref="core/go2/go2.xml:224-237"),
        Fact("The model declares twelve named hinge joints, three on each leg", source="upstream_code",
             ref="core/go2/go2.xml:84-208"),
        Fact("The model has a home keyframe with a 19-value qpos and a 12-value ctrl", source="upstream_code",
             ref="core/go2/go2.xml:288-289"),
        Fact("The model declares joint position, joint velocity, actuator force, IMU orientation, gyro and "
             "accelerometer sensors", source="upstream_code", ref="core/go2/go2.xml:239-285"),
        Fact("The flat scene adds a ground plane and a directional light", source="upstream_code",
             ref="core/go2/scene.xml:19-21"),
        Fact("The parkour terrain is a 200 by 50 height field of size 8.0 2.0 0.3 0.001", source="upstream_code",
             ref="core/go2/scene_parkour.xml:13-16"),
    ]
    safe_state = ("the simulation is held: after an e-stop the runtime refuses every step and reset until "
                  "mhs.safety.reset clears the latch, and the model data stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the time step and the lockstep clock; the gaps below are this package's.
    fidelity = {
        "engine": "mujoco:go2_parkour",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "MuJoCo integrates the MJCF deterministically from the reset state and the served model has no "
                     "random element, so one ctrl sequence and tick count repeat a trajectory; the bridge takes no "
                     "seed input and a reset restores the model defaults, so no seed selects a different one.  The "
                     "package's fake backend is deterministic too, but its placeholder motion is not the engine's "
                     "physics and it offers no snapshot state.",
        },
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses core/go2/scene.xml with "
            "its go2.xml include, takes the twelve actuator control ranges, the joint dimensions and the option time "
            "step from the tree, then turns each ctrl into a placeholder joint velocity; it computes no inertia, "
            "torque, contact, friction, actuator, sensor or noise dynamics, so no trajectory here is a MuJoCo result",
            "the stand-in loads no mesh or texture and resolves no contact: the scene's floor and the Go2's collision "
            "geoms are not simulated physically, and the robot cannot stand or walk in the fake",
            "the model states no option timestep (core/go2/go2.xml:4); the stand-in uses a placeholder library "
            "default and the bridge publishes that stand-in value",
            "the stand-in does not apply the model's gear, gain, bias, damping, friction, armature, joint range or "
            "force limits, and it treats a motor actuator as a direct joint velocity target",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared "
            "with the real engine",
            "the served model is the card's models[0], core/go2/scene.xml; the upstream sim2sim entry point loads "
            "core/go2/scene_parkour.xml (core/deployment_player.py:21-22) with the height-field terrain, which this "
            "package does not serve",
            "the upstream policy, observation history, joystick command and camera, depth and contact sensors "
            "(mujoco_deploy/mujoco_wrapper.py:28-40, core/deployment_player.py:24-28) are not part of this driver, "
            "which exposes only the bridge's time, qpos, qvel and ctrl state",
            "snapshot and restore are not offered by the stand-in (it has no mj_getState or mj_setState); the "
            "bridge's derived fidelity field still reports the real engine's snapshot support",
            "no physical GO2 is modelled and nothing was validated against the hardware",
        ],
    }
