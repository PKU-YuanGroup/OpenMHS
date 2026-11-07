"""OpenMHS driver for gh.joshnegreanu/robo-lab: the TRLC DK1 blocks scene as a MuJoCo world.

A ``MujocoDriver`` is configuration only: ``model_path`` names the card's primary model
(``assets/trlc_dk1/scene_blocks.xml``) and the bridge derives the whole contract from the model it loads.
``cap.world.step.v1`` takes ``{ticks, action: {ctrl: [...]}}``; every ``ctrl`` element is checked against the
model's ``actuator_ctrlrange`` (16 position actuators: six per arm plus two gripper channels per arm) before it
is written to ``data.ctrl``, then ``mj_step`` runs ``ticks`` times.  ``cap.world.reset.v1`` restores the data
with ``mj_resetData`` + ``mj_forward``.  The world state is the bridge's integration state (``time_ms``,
``qpos``, ``qvel``, ``ctrl``, ``tick``, ``timestep_ms``, ``seed``).  The device is simulated (R0): there is no
hardware backend, no e-stop path to a machine and no operator-required limit; the control envelope is the
model's own.

The repository is teleoperated data collection and imitation learning for a TRLC DK1 bimanual arm pair, with a
MuJoCo simulator (README.md:3).  Each environment's scene is generated and committed as
``assets/trlc_dk1/scene_<env>.xml`` (README.md:327); this package serves the card's first model, the blocks
scene, and notes below that the dishes scene is the other environment.  The model file is read from the
read-only clone in place and is never copied into the package or imported.

MuJoCo is not installed where the gate runs and cannot be installed (no network, no pip), so
``backends['fake']`` is this package's stand-in ``mujoco`` module (fake.py).  It parses the same MJCF file for
the actuator control ranges, the joint dimensions and the option timestep, but its integration is a placeholder,
not MuJoCo's physics; the fidelity ``gaps`` list every difference.  A backend name that ``backends`` does not
list (``sim``) imports the real ``mujoco`` module and loads the same file; that path was not run here.  This
package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

MODEL = "assets/trlc_dk1/scene_blocks.xml"
DISHES = "assets/trlc_dk1/scene_dishes.xml"
#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/joshnegreanu/robo-lab/" + MODEL


class RoboLab(MujocoDriver):
    device_id = "robo-lab"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "TRLC DK1 bimanual blocks scene (robo-lab)"
    vendor, model = "joshnegreanu", "robo-lab"
    tags = ["trlc-dk1", "bimanual", "robot-arm", "manipulation", "mujoco", "simulation", "robo-lab"]
    facts = [
        Fact("The repository is teleoperated data collection and imitation learning for a TRLC DK1 bimanual "
             "arm pair, with a MuJoCo simulator and WebXR control from a Meta Quest", source="vendor_doc",
             ref="README.md:3"),
        Fact("The two environments are blocks (default), two 4.5 cm cubes and a bowl with the instruction 'put "
             "both blocks in the bowl', and dishes, plate, bowl, cup, fork, knife, spoon and a static dish rack "
             "with the instruction 'put all the dishes and silverware in the dish rack'", source="vendor_doc",
             ref="README.md:110-113"),
        Fact("The gripper jaws open to 82 mm; the plate is 277 mm across, the bowl 144 mm and the cup 83 mm",
             source="vendor_doc", ref="README.md:131"),
        Fact("Each environment's scene is generated and committed as assets/trlc_dk1/scene_<env>.xml, one per "
             "environment", source="vendor_doc", ref="README.md:325-327"),
        Fact("The blocks scene is an MJCF model whose root element is '<mujoco model=\"MuJoCo Model\">'",
             source="upstream_code", ref=f"{MODEL}:1"),
        Fact("The scene compiles angles in radians and resolves mesh files from the model's own directory",
             source="upstream_code", ref=f"{MODEL}:2"),
        Fact("The scene selects the implicitfast integrator and sets no timestep: its option element carries only "
             "integrator", source="upstream_code", ref=f"{MODEL}:4"),
        Fact("The left arm has six hinge joints named left_joint1 to left_joint6 with ranges +-2.0944, -0.0872665 "
             "to 3.14159, -0.0872665 to 4.71239, -1.95 to 1.5708, +-1.5708 and +-2.0944, and two slide joints "
             "left_gripper_left and left_gripper_right with range -0.045 to 0.001", source="upstream_code",
             ref=f"{MODEL}:82-112"),
        Fact("The right arm has six hinge joints named right_joint1 to right_joint6 with ranges +-2.0944, "
             "-0.0872665 to 3.14159, -0.0872665 to 4.71239, -1.95 to 1.5708, +-1.5708 and +-2.0944, and two slide "
             "joints right_gripper_left and right_gripper_right with range -0.045 to 0.001", source="upstream_code",
             ref=f"{MODEL}:133-163"),
        Fact("The two target bodies left_target and right_target are declared mocap bodies (mocap='true')",
             source="upstream_code", ref=f"{MODEL}:181-186"),
        Fact("The blocks scene places two free-jointed cubes, red_cube and blue_cube, with 0.045 kg box geoms of "
             "half-size 0.0225 m, and a free-jointed dish_bowl body", source="upstream_code", ref=f"{MODEL}:187-196"),
        Fact("The actuator block has 16 general actuators, eight per arm: one position actuator per hinge joint "
             "and per gripper slide joint", source="upstream_code", ref=f"{MODEL}:299-315"),
        Fact("The joint actuator control ranges are +-2.0944, -0.0872665 to 3.14159, -0.0872665 to 4.71239, "
             "-1.95 to 1.5708, +-1.5708 and +-2.0944 on both arms, and the four gripper actuators have ctrlrange "
             "-0.045 to 0.001", source="upstream_code", ref=f"{MODEL}:300-315"),
        Fact("The left gripper actuators are force-limited to -20 to 20 and carry a gain of 300", source="upstream_code",
             ref=f"{MODEL}:306-307"),
        Fact("The right gripper actuators are force-limited to -20 to 20 and carry a gain of 300",
             source="upstream_code", ref=f"{MODEL}:314-315"),
        Fact("The dishes scene, the card's second model, has a static dish_rack body with no joint and six "
             "free-jointed pieces: dish_plate, dish_bowl, dish_cup, utensil_fork, utensil_knife and utensil_spoon",
             source="upstream_code", ref=f"{DISHES}:330-516"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind, the time step and the lockstep clock; the gaps below are this package's.
    fidelity = {
        "engine": "mujoco:scene_blocks",
        "fidelity_level": "F1",
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses the committed MJCF for "
            "the actuator control ranges, the joint types and dimensions and the option timestep, but integrates a "
            "placeholder first-order motion of each actuated joint toward its control value, so trajectories, "
            "contacts, friction and actuator dynamics are not MuJoCo's",
            "the model states no timestep (the option element carries only the integrator), so the published "
            "timestep_ms comes from the stand-in's placeholder library default",
            "no mesh, texture, material, inertia or contact exclusion of the scene is loaded and no contact, "
            "equality, tendon or actuator constraint is resolved; the dish_bowl collision hulls and the finger "
            "contact tuning are not simulated",
            "the real model resets free joints to their model qpos0; the stand-in resets every qpos to zero, so "
            "the initial state after a reset differs",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared "
            "with the real engine; the real sim path (the official mujoco module loading the same scene) was not "
            "run",
            "no viewer, rendering or camera stream is exposed: the package serves only the cap.world.* integration "
            "state and control vector, not the scene cameras or the HDRI backdrop",
            "only the card's first model, the blocks scene, is served; the dishes scene and the upstream teleop, "
            "capture, WebXR and training stacks are other components and are not part of this driver",
            "no physical TRLC DK1 arm is modelled and nothing was validated against hardware",
        ],
    }
