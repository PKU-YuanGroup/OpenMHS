"""OpenMHS driver for gh.chauncygu/safe-multi-agent-robosuite: the Baxter arm MJCF model (a MuJoCo family driver).

A ``MujocoDriver`` is configuration only.  ``model_path`` names the card's first model,
``robosuite/models/assets/robots/baxter/robot.xml``: the fixed-base Baxter torso with two seven-joint arms and fourteen
``motor`` actuators.  The bridge loads the model with the MuJoCo engine, derives ``cap.world.step.v1``'s
``action.ctrl`` from each actuator's ``ctrlrange``, writes ``data.ctrl``, runs ``mj_step`` for ``ticks``, and serves
``cap.world.reset.v1`` with ``mj_resetData`` + ``mj_forward``.  The world state is the bridge's integration state
(``time_ms``, ``qpos``, ``qvel``, ``ctrl``, ``tick``, ``timestep_ms``, ``seed``).

The device is simulated (R0): there is no hardware backend and no physical Baxter is driven.  The model is read from
the read-only clone at the pinned commit and is neither copied into this package nor imported.  MuJoCo is not
installed where the acceptance gate runs, so ``backends["fake"]`` is this package's stand-in ``mujoco`` module
(fake.py), which reads the model shape from the same file but integrates a placeholder motion instead of the
engine's physics; the fidelity ``gaps`` below state every difference.

The card's entry_symbols are the upstream Python classes that instantiate such models (``MujocoMulti`` and the
robosuite environments); they were confirmed in the clone, but they need gym, numpy and robosuite to construct a
scene, so this package serves the MJCF model itself, which is what the card's ``models`` list and the ``MujocoDriver``
helper describe.  Every Fact cites a line of the clone at commit df9ade0fa8df984bfe6853fda7604edf10440b65.  This
package is model-authored and unreviewed: it is checked on the fake backend only, and nothing here ran the MuJoCo
engine or a physical robot.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import fake_mujoco

MODEL = "robosuite/models/assets/robots/baxter/robot.xml"
WRAPPER = "robosuite/models/robots/manipulators/baxter_robot.py"
#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/chauncygu/safe-multi-agent-robosuite/" + MODEL


class Baxter(MujocoDriver):
    device_id = "robosuite-baxter"
    model_path = MODEL_PATH
    backends = {"fake": fake_mujoco}
    display_name = "Safe Multi-Agent Robosuite Baxter bimanual arm (MuJoCo model)"
    vendor, model = "chauncygu", "Baxter"
    tags = ["baxter", "bimanual", "manipulation", "mujoco", "multi-agent", "robosuite", "robot", "simulation"]
    facts = [
        Fact("Safe Multi-Agent Robosuite is an extension of Robosuite that splits the control over a robot across "
             "multiple controllers of its joints, one or more per controller", source="vendor_doc",
             ref="README.md:10"),
        Fact("The card's first model is the MJCF document whose root element is '<mujoco model=\"baxter\">'",
             source="upstream_code", ref=f"{MODEL}:1"),
        Fact("The Baxter wrapper loads the same file through xml_path_completion(\"robots/baxter/robot.xml\")",
             source="upstream_code", ref=f"{WRAPPER}:15"),
        Fact("The Baxter wrapper describes the robot as a bimanual robot designed by Rethink Robotics",
             source="upstream_code", ref=f"{WRAPPER}:8"),
        Fact("The Baxter wrapper reports the arm type as bimanual", source="upstream_code", ref=f"{WRAPPER}:77-78"),
        Fact("The right arm is a chain of seven hinge joints named right_s0, right_s1, right_e0, right_e1, "
             "right_w0, right_w1 and right_w2 with ranges -1.70168..1.70168, -2.147..1.047, -3.05418..3.05418, "
             "-0.05..2.618, -3.059..3.059, -1.5708..2.094 and -3.059..3.059", source="upstream_code",
             ref=f"{MODEL}:71-103"),
        Fact("The left arm is the matching chain of seven hinge joints named left_s0, left_s1, left_e0, left_e1, "
             "left_w0, left_w1 and left_w2 with the same joint ranges as the right arm", source="upstream_code",
             ref=f"{MODEL}:123-155"),
        Fact("The actuator section declares fourteen motor actuators, one per joint; the control ranges are shoulder "
             "pan -50 to 50, shoulder lift -100 to 100, upper elbow -50 to 50, lower elbow -50 to 50, forearm roll "
             "-15 to 15, wrist angle -15 to 15 and wrist rotate -15 to 15, repeated for the right and left arms",
             source="upstream_code", ref=f"{MODEL}:176-190"),
        Fact("The head pan joint is inside an XML comment, so the served model has no head joint", source="upstream_code",
             ref=f"{MODEL}:59"),
        Fact("The model declares eight contact exclusions between the shoulders, elbows, head and torso",
             source="upstream_code", ref=f"{MODEL}:27-34"),
        Fact("The model declares its eleven meshes as STL files under meshes/", source="upstream_code",
             ref=f"{MODEL}:2-13"),
        Fact("The Baxter wrapper gives both arms the RethinkGripper by default; the gripper is not part of "
             "robot.xml", source="upstream_code", ref=f"{WRAPPER}:27-31"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch, and the integration state stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity FID-002).  The bridge derives the engine,
    #: the determinism kind, the timestep and the lockstep clock; the gaps below are this package's.
    fidelity = {
        "engine": "mujoco:baxter",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "exact",
            "seed_control": "none",
            "notes": "MuJoCo integrates the MJCF deterministically from the reset state and the model has no "
                     "random element, so one ctrl sequence and tick count repeat a trajectory; the package's fake "
                     "backend is deterministic too, but its placeholder motion is not the engine's physics.",
        },
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses the served robot.xml for "
            "the 14 joints, the 14 actuator ctrlranges and the time step, then moves each actuated joint toward its "
            "control value; it computes no inertia, torque, contact, equality or actuator dynamics, so no "
            "trajectory here is a MuJoCo result",
            "the stand-in loads no mesh or texture and resolves no contact: the eleven meshes of the model are not "
            "read, and the eight contact exclusions of the model are not applied",
            "the served robot.xml is the bare two-arm torso; the RethinkGripper that the robosuite wrapper attaches "
            "to each arm (baxter_robot.py:27-31) is not part of this MJCF, so no gripper joint or gripper actuator "
            "is served",
            "the model sets no option timestep; the stand-in uses a placeholder library default as the step "
            "(fake.py), and the bridge publishes that stand-in value from the stand-in",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared "
            "with the real engine",
            "no rendering, cameras or sensor publication: the robotview camera of the model is not exposed, and "
            "only the bridge's time, qpos, qvel and ctrl state is published",
            "the multiple-controller split of Safe Multi-Agent Robosuite (README.md:10) is a wrapper over a "
            "robosuite scene; it is not part of this bare robot model and is not served",
            "no physical Baxter robot is modelled and nothing was validated against the hardware",
        ],
    }
