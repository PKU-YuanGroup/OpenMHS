"""OpenMHS driver for gh.openai/safety-gym: the car robot model (a MuJoCo family driver).

Safety Gym is an environment builder: ``safety_gym.envs.engine:Engine`` (the card's entry symbol, engine.py:83) copies
a robot MJCF, adds the task objects to it and steps the result through ``mujoco_py``.  A ``MujocoDriver`` is
configuration only, so this package serves the default robot model of that environment, ``safety_gym/xmls/car.xml``
(``'robot_base': 'xmls/car.xml'``, engine.py:112): the bridge loads the MJCF with the ``mujoco`` library, writes the
step action to ``data.ctrl``, bounded per actuator by the model's ``actuator_ctrlrange`` (the car model gives its two
motors ``ctrlrange="-1 1"``, car.xml:7), and publishes the integration state.  That is the same control vector the
Engine builds its action space from: ``Box(-1, 1, (self.robot.nu,))`` (engine.py:306-308), where ``nu`` is the
actuator count of the robot model (world.py:383).

What is not served: the Engine's task objects, goal, hazards, lidar, cost and reward.  The card's three robot models
are complete robot scenes by the clone's own design goals ("XML should be complete and simulate-able as-is", "only the
robot in the scene", xmls/README.md:7,15-16), so the driver serves the default one as a ``world.sim`` and says in the
fidelity ``gaps`` that the task layer is absent.  A second model is served by changing ``model_path`` and the facts.

The device is simulated (R0): there is no hardware backend, no native stop and no operator-required limit.  MuJoCo is
not installed and cannot be installed where the acceptance gate runs, so ``backends["fake"]`` is this package's
stand-in ``mujoco`` module (fake.py).  It reads the same model file for the joint layout and the actuator control
ranges but integrates a placeholder motion, not MuJoCo's physics; the fidelity ``gaps`` say so.  A backend name that
``backends`` does not list (``sim``) imports the real ``mujoco`` module and loads the same file; that path was not run
here.

The model file is read from the read-only upstream clone at the pinned commit (never copied into this package, never
imported).  Every fact cites a line of the clone at commit f31042f2f9ee61b9034dd6a416955972911544f5.  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL = "safety_gym/xmls/car.xml"
MODEL_PATH = "../../../../robots/openai/safety-gym/" + MODEL
ENGINE = "safety_gym/envs/engine.py"
WORLD = "safety_gym/envs/world.py"
XMLS = "safety_gym/xmls/README.md"


class SafetyGymCar(MujocoDriver):
    """The car robot model of Safety Gym: two motorised wheels on a free-jointed body, stepped by ``data.ctrl``."""

    device_id = "safety-gym-car"
    model_path = MODEL_PATH
    native = "safety_gym.envs.engine:Engine"
    backends = {"fake": FakeMujoco}
    display_name = "Safety Gym car robot (MuJoCo)"
    vendor, model = "OpenAI", "Safety Gym car"
    tags = ["car", "mujoco", "openai", "reinforcement-learning", "robot", "safety-gym", "simulation"]
    facts = [
        Fact("The Engine default configuration uses the car model: 'robot_base': 'xmls/car.xml'",
             source="upstream_code", ref=f"{ENGINE}:112"),
        Fact("Engine builds a Robot from the configured robot XML before it derives the action space",
             source="upstream_code", ref=f"{ENGINE}:305-306"),
        Fact("The action space is Box(-1, 1, (robot.nu,)): one control between -1 and 1 per actuator of the robot "
             "model", source="upstream_code", ref=f"{ENGINE}:308"),
        Fact("Robot loads the configured XML with load_model_from_path and takes nu (the actuator count) from the "
             "loaded model", source="upstream_code", ref=f"{WORLD}:370-383"),
        Fact("car.xml sets the simulation timestep to 0.004 s", source="upstream_code", ref=f"{MODEL}:3"),
        Fact("The car model default motor has ctrlrange -1 1, ctrllimited true, forcerange -0.02 0.02 and "
             "forcelimited true", source="upstream_code", ref=f"{MODEL}:7"),
        Fact("car.xml declares a free joint named robot, two hinge joints named left and right, and a ball joint "
             "named rear", source="upstream_code", ref=f"{MODEL}:15-30"),
        Fact("car.xml has two motors, both jointinparent transmissions with gear 1, so the model has two actuators",
             source="upstream_code", ref=f"{MODEL}:53-56"),
        Fact("The car body starts at 0 0 0.1", source="upstream_code", ref=f"{MODEL}:12"),
        Fact("The xmls README states each robot XML should be complete and simulate-able as-is",
             source="vendor_doc", ref=f"{XMLS}:7"),
        Fact("The xmls README states each robot XML should include actuators which provide control",
             source="vendor_doc", ref=f"{XMLS}:10"),
        Fact("The xmls README says a robot scene should be clear of other objects, with only the robot in the scene",
             source="vendor_doc", ref=f"{XMLS}:14-16"),
        Fact("The Engine default ends an episode after 1000 environment steps",
             source="upstream_code", ref=f"{ENGINE}:98"),
        Fact("One Engine step advances the simulation by a binomial draw of up to 10 physics steps, and the default "
             "probability 1.0 makes it 10 steps", source="upstream_code", ref=f"{ENGINE}:287-291"),
        Fact("Engine.step clips the action to the model's actuator_ctrlrange before writing data.ctrl",
             source="upstream_code", ref=f"{ENGINE}:1245-1247"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the time step and the lockstep clock; determinism and the gaps below are this package's.
    fidelity = {
        "engine": "mujoco:safety_gym/xmls/car.xml",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "MuJoCo integrates one model deterministically from one initial state; the bridge takes no seed "
                     "input and cap.world.reset.v1 restores the model defaults (mj_resetData), so a run repeats on "
                     "one engine but no seed selects a different state",
        },
        "gaps": [
            "the driver steps the robot model of car.xml alone: the Engine's task objects, goal, hazards, vases, "
            "lidar and cost/reward are not modelled (xmls/README.md:14-16) and cap.world.step.v1 carries no reward",
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it reads the model file for the joint "
            "layout and the actuator control ranges but integrates a placeholder first-order motion of each actuated "
            "joint, so trajectories, contacts, friction, free-joint dynamics and sensors are not MuJoCo's",
            "the Engine advances an environment step by a binomial draw of up to 10 physics steps at p=1.0 "
            "(engine.py:287-291) and ends an episode after 1000 environment steps (engine.py:98); this driver's "
            "ticks are physics steps of the model, and it declares no episode and no truncation",
            "the Engine clips an action to actuator_ctrlrange (engine.py:1245-1247); this driver instead refuses a "
            "ctrl outside the model's actuator_ctrlrange before any call, because the runtime rejects rather than "
            "clamps",
            "the car model uses MuJoCo 2.0-era mujoco_py syntax (jointinparent transmissions at car.xml:54-55 and "
            "<size njmax=\"3000\" nconmax=\"1000\"> at car.xml:2); the modern mujoco library was not installed where "
            "the gate ran, so whether it loads this file was not verified",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared with "
            "the real engine",
            "no rendering is offered and no physical car robot is modelled; nothing was validated against a device",
        ],
    }
