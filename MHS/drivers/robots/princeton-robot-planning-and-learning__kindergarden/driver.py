"""OpenMHS driver for gh.princeton-robot-planning-and-learning/kindergarden: the RBY1A MuJoCo model.

The device is the MJCF model ``src/kinder/envs/dynamic3d/models/rby1a/rby1a_model_v1.2.xml`` (the card's models[2]),
served as a simulated world by :class:`mhs.driver.MujocoDriver`.  The model is loaded from the read-only upstream clone
in place; the package carries neither the model nor its meshes.  ``cap.world.step.v1`` writes ``action.ctrl`` to
``data.ctrl``, bounded per actuator by the model's ``actuator_ctrlrange`` (every motor inherits -3000000..3000000 from
the root default class), and steps ``mj_step``; ``cap.world.reset.v1`` restores the model defaults with ``mj_resetData``
and ``mj_forward``.  The state is the bridge's integration state: time, qpos, qvel, ctrl and the tick count.

Why the card's models[2] and not models[0]: the first scene (``kinova_gen3/scene.xml``) declares four of its seven
position actuators without a ``ctrlrange``, so a MuJoCo control there has no bound the bridge could publish.  The RBY1A
model declares a control range for every one of its 24 motors (the root default class), which makes the whole action
contract derivable and testable.  The RBY1A model is the one ``RBY1ARobotEnv`` inserts into the dynamic3d scene
(``rby1a_robot_env.py:104-108``).

The task card's entry classes are the Gymnasium task environments, not MuJoCo models; this driver serves the model
underneath the RBY1A environment, not the environment wrapper (objects, observations, rewards, goals and episode
limits are not served).  The card's mock path is ``upstream-sim``; the gate runs without MuJoCo, so ``backends["fake"]``
is this package's stand-in ``mujoco`` module (``fake.py``, a callable, which the gate treats as the upstream simulator).
It reads the model file for the shape and ranges, but its integration is a placeholder, not the engine's; the fidelity
``gaps`` say so.  A backend name that ``backends`` does not list (``sim``) imports the real ``mujoco`` module and loads
the same file; that path was not run here.

Every Fact cites a line of the clone at commit 5b2dbac482142b879b48449b3fa2af63f641aed3.  This package is model-authored
and unreviewed: it is checked on the fake backend only, and no MuJoCo engine and no hardware ran.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import fake_mujoco

MODEL = "src/kinder/envs/dynamic3d/models/rby1a/rby1a_model_v1.2.xml"
ROBOT_ENV = "src/kinder/envs/dynamic3d/robots/rby1a_robot_env.py"
ENVS = "src/kinder/envs/dynamic3d/envs.py"
MUJOCO_UTILS = "src/kinder/envs/dynamic3d/mujoco_utils.py"
#: The card's models[2], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/princeton-robot-planning-and-learning/kindergarden/" + MODEL


class RBY1AWorld(MujocoDriver):
    device_id = "rby1a"
    model_path = MODEL_PATH
    backends = {"fake": fake_mujoco}
    display_name = "KinDER RBY1A mobile manipulator (MuJoCo model)"
    vendor, model = "Princeton Robot Planning and Learning", "RBY1A mobile manipulator"
    tags = ["kinder", "mujoco", "mobile-manipulator", "rby1a", "simulation", "world"]
    facts = [
        Fact("KinDER is a physical reasoning benchmark for robot learning and planning", source="vendor_doc",
             ref="README.md:7"),
        Fact("The package declares mujoco~=3.3.0 as a dependency", source="upstream_code",
             ref="pyproject.toml:29"),
        Fact("The RBY1A model is the MJCF model rby1, compiled in radians with autolimits and eulerseq xyz",
             source="upstream_code", ref=f"{MODEL}:1-25"),
        Fact("The model sets no option timestep: its two <option> elements name only the implicitfast integrator and "
             "the elliptic cone; the only timestep text is a commented-out line", source="upstream_code",
             ref=f"{MODEL}:2-5"),
        Fact("The root default class gives every motor the control range -3000000 to 3000000 and ctrllimited true",
             source="upstream_code", ref=f"{MODEL}:10-11"),
        Fact("The model declares 24 motors: two wheel, six torso, seven left arm, seven right arm and two head "
             "motors, all without a local ctrlrange so the root default applies", source="upstream_code",
             ref=f"{MODEL}:267-296"),
        Fact("The model has one free root joint (world_j) and 28 hinge or slide joints: the two wheels, six torso "
             "joints, seven joints per arm, two fingers per gripper and two head joints", source="upstream_code",
             ref=f"{MODEL}:83-249"),
        Fact("The joint limits are stated per joint; examples are torso_0 -0.349066 to 0.349066 rad, torso_1 "
             "-1.0472 to 1.52173 rad and right_arm_4 -6.28319 to 6.28319 rad", source="upstream_code",
             ref=f"{MODEL}:100-153"),
        Fact("The two fingers of a gripper are coupled by an equality constraint", source="upstream_code",
             ref=f"{MODEL}:262-264"),
        Fact("The dynamic3d RBY1A robot environment inserts rby1a_model_v1.2.xml into the task scene XML",
             source="upstream_code", ref=f"{ROBOT_ENV}:104-108"),
        Fact("The dynamic3d env selects RBY1ARobotEnv when the task's robot type is rby1a", source="upstream_code",
             ref=f"{ENVS}:149-153"),
        Fact("The base MuJoCo environment defines SIMULATION_TIMESTEP as 0.0005 s", source="upstream_code",
             ref=f"{MUJOCO_UTILS}:27"),
        Fact("The base MuJoCo environment writes its SIMULATION_TIMESTEP into the XML option element before "
             "loading the model", source="upstream_code", ref=f"{MUJOCO_UTILS}:774-781"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed on the fake backend.  The bridge derives the engine, the
    #: determinism kind, the step and the lockstep clock; the gaps state what is not modelled and what the fake is.
    fidelity = {
        "engine": "mujoco",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "exact",
            "seed_control": "none",
            "notes": "MuJoCo integrates one model deterministically from one state; the bridge records a seed but a "
                     "reset restores the model defaults and no seed selects a different initial state.  The package's "
                     "fake is deterministic too, but its placeholder dynamics are not the model's.",
        },
        "timestep_ms": 2.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not the MuJoCo engine: it parses the model file "
            "for the joint and actuator counts and the control ranges, then advances a placeholder first-order "
            "motion; it computes no equations of motion, inertias, contacts, equality constraints or actuator "
            "dynamics, so its trajectories are not valid simulation results",
            "the model file states no <option timestep>; timestep_ms 2.0 is the fake's placeholder for MuJoCo's "
            "library default, while the upstream dynamic3d environment sets 0.0005 s when it composes a scene "
            "(mujoco_utils.py:27,774-781), so the real step of a served model is not verified here",
            "the driver serves the RBY1A model file, not the Gymnasium task environment: the task config, objects, "
            "observations, rewards, goals and episode limits of the dynamic3d envs are not modelled",
            "the mesh assets referenced through the model's include files are read from the clone by a real MuJoCo "
            "load but are not resolved by the fake; no rendering and no sensor, camera or contact model is served",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by the model step only",
            "the model was never loaded by the MuJoCo engine where the gate ran and was never compared with a real "
            "RBY1A robot; nothing ran on hardware",
        ],
    }
