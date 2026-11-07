"""OpenMHS driver for gh.zihanwang0422/muarm: the panda_pick_place MuJoCo scene (a MuJoCo family driver).

A MujocoDriver is configuration only: ``model_path`` names the MJCF scene (the card's ``models[0]``,
``learning/assets/panda_pick_place.xml``) and the bridge derives the whole contract from the model it loads.  The step
action is ``data.ctrl``, bounded per actuator by the model's ``actuator_ctrlrange`` (eight general actuators: seven
arm joints and one gripper tendon), the world state is the integration state of the model (``time``, ``qpos``,
``qvel``, ``ctrl``) plus the tick count, and ``cap.world.reset.v1`` restores the model defaults.

The device is simulated (R0): there is no hardware backend and no operator-required limit.  The gate cannot install
MuJoCo where it runs, so the ``fake`` backend is this package's stand-in ``mujoco`` module (fake.py).  It reads the
same model file for the model shape (joint dimensions, actuator count, per-actuator control ranges, time step) but
its integration is a placeholder, not MuJoCo's physics; the fidelity ``gaps`` say so.  A backend name that
``backends`` does not list (``sim``) imports the real ``mujoco`` module and loads the same file; that path was not run
here.

The model file is read from the read-only upstream clone at the pinned commit (it is never copied into this package
and never imported).  Every Fact cites a line of the clone at commit 9d328f16df05b5a6199ebd0c59048d58c6cd6326.  The
card's entry symbols are Gymnasium environment classes; this package serves the card's first MJCF model directly, so
the driver declares no ``native`` class.  It is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL = "learning/assets/panda_pick_place.xml"
MODEL_PATH = "../../../../robots/zihanwang0422/muarm/" + MODEL
PANDA = "models/franka_emika_panda/panda.xml"
SCENE = "models/franka_emika_panda/scene.xml"


class MuArmPandaPickPlace(MujocoDriver):
    device_id = "muarm-panda-pick-place"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "muarm Franka Panda pick-and-place (MuJoCo)"
    vendor, model = "zihanwang0422", "muarm panda_pick_place"
    tags = ["arm", "franka", "manipulation", "mujoco", "panda", "robot", "simulation"]
    facts = [
        Fact("The package's model is the MJCF scene panda_pick_place, whose root element is "
             "'<mujoco model=\"panda_pick_place\">'", source="upstream_code", ref=f"{MODEL}:1"),
        Fact("The pick_place scene includes ../../models/franka_emika_panda/scene.xml", source="upstream_code",
             ref=f"{MODEL}:2"),
        Fact("The pick_place scene adds a target site and a pick_obj body with a freejoint and a box geom",
             source="upstream_code", ref=f"{MODEL}:4-8"),
        Fact("The included scene.xml includes panda.xml", source="upstream_code", ref=f"{SCENE}:2"),
        Fact("panda.xml declares the radian angle unit, autolimits and the assets mesh directory",
             source="upstream_code", ref=f"{PANDA}:2"),
        Fact("panda.xml sets the implicitfast integrator in its option element and states no timestep",
             source="upstream_code", ref=f"{PANDA}:4"),
        Fact("The panda default class sets joint armature 0.1, damping 1, axis 0 0 1 and range -2.8973 to 2.8973",
             source="upstream_code", ref=f"{PANDA}:9"),
        Fact("The panda default general actuator sets ctrlrange -2.8973 to 2.8973 and forcerange -87 to 87",
             source="upstream_code", ref=f"{PANDA}:10"),
        Fact("The finger default class makes its joints slide with range 0 to 0.04", source="upstream_code",
             ref=f"{PANDA}:11-12"),
        Fact("joint2 overrides the default joint range to -1.7628 to 1.7628", source="upstream_code",
             ref=f"{PANDA}:144"),
        Fact("joint4 overrides the default joint range to -3.0718 to -0.0698", source="upstream_code",
             ref=f"{PANDA}:159"),
        Fact("joint6 overrides the default joint range to -0.0175 to 3.7525", source="upstream_code",
             ref=f"{PANDA}:178"),
        Fact("The model has eight general actuators: actuator1 to actuator7 act on joint1 to joint7, and actuator8 "
             "acts on the split tendon of the two finger joints", source="upstream_code", ref=f"{PANDA}:264-278"),
        Fact("actuator2, actuator4 and actuator6 override the default ctrlrange with -1.7628 to 1.7628, -3.0718 to "
             "-0.0698 and -0.0175 to 3.7525", source="upstream_code", ref=f"{PANDA}:266-273"),
        Fact("actuator8 has ctrlrange 0 to 255 on the split tendon and forcerange -100 to 100", source="upstream_code",
             ref=f"{PANDA}:275-277"),
        Fact("The two finger joints are coupled by an equality constraint", source="upstream_code",
             ref=f"{PANDA}:260-261"),
        Fact("The model has a home keyframe with qpos '0 0 0 -1.57079 0 1.57079 -0.7853 0.04 0.04' and ctrl "
             "'0 0 0 -1.57079 0 1.57079 -0.7853 255'", source="upstream_code", ref=f"{PANDA}:280-281"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the time step and the lockstep clock; the values below are this package's.
    fidelity = {
        "engine": "mujoco:panda_pick_place",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "MuJoCo integrates one model deterministically from one initial state; the bridge takes no "
                     "seed input and cap.world.reset.v1 zeroes the model data, so a run repeats exactly on the same "
                     "engine but no seed selects a different state",
        },
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it reads the model file for the "
            "joint dimensions, actuator count, per-actuator control ranges and time step but integrates a "
            "placeholder first-order motion of each actuated joint toward its control target, so trajectories, "
            "contacts and actuator dynamics are not MuJoCo's",
            "no mesh or texture of the asset directory is loaded and no contact, equality or tendon constraint is "
            "resolved by the stand-in; the finger equality and the split-tendon gripper of the model are not "
            "applied",
            "the model sets no <option timestep> (panda.xml:4); the fake uses the MuJoCo library default as a "
            "placeholder, not a bound stated by the clone",
            "the bridge reset zeroes the model data; the upstream learning environment resets to the home keyframe "
            "(panda.xml:280-281) through MuJocoRobotEnv.reset, which this package does not serve",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared "
            "with the real engine",
            "no rendering is offered and no physical Franka Panda robot is modelled; nothing was validated against "
            "hardware",
        ],
    }
