"""OpenMHS driver for gh.pku-alignment/safety-gymnasium: the Point Goal1 simulated task.

Safety-Gymnasium is a Gymnasium environment suite for SafeRL, not hardware.  ``Builder``
(``safety_gymnasium.builder:Builder``, builder.py:55) builds one task, seeds it and steps it; the package registers
each task in both its own registry and the Gymnasium registry.  The Gymnasium id has a ``Gymnasium`` suffix and is
served by ``SafetyGymnasium2Gymnasium`` (README.md:547-554, safety_gymnasium/__init__.py:61-66), whose step returns
the standard five items instead of Safety-Gymnasium's six (wrappers/gymnasium_conversion.py:26-34).  This driver
serves that standard view as the card's ``GymnasiumDriver`` family: ``env_id`` names it and the bridge derives the
whole contract from the environment's spaces.

Point Goal1 is a two-dimensional navigation task: the Point robot has two continuous actuators bounded by -1 and 1
(point.xml:24-25,54-56), the goal is a disc of radius 0.3 (goal.py:31), there are eight hazards and one vase
(goal_level1.py:33-34), and the episode ends at the goal or after 1000 environment steps (base_task.py:181).

A backend name that ``backends`` does not list (``sim``) is served by ``gymnasium.make(env_id)``
(GymnasiumDriver.open_native); that path needs the upstream packages and was not run here.  The gate cannot import
them, so the ``fake`` backend is this package's pure Python Point Goal1 (fake.py).  The fake is a kinematic point
model, not MuJoCo; the fidelity ``gaps`` say exactly what is not modelled.

The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no operator-required
limit.  Every fact and rule cites a line of the read-only clone at commit ae966e511b9927f06b39c727ca5c650136a4e696.
This package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

README = "README.md"
INIT = "safety_gymnasium/__init__.py"
BUILDER = "safety_gymnasium/builder.py"
BASE_TASK = "safety_gymnasium/bases/base_task.py"
BASE_AGENT = "safety_gymnasium/bases/base_agent.py"
UNDERLYING = "safety_gymnasium/bases/underlying.py"
CONVERSION = "safety_gymnasium/wrappers/gymnasium_conversion.py"
POINT_XML = "safety_gymnasium/assets/xmls/point.xml"
GOAL = "safety_gymnasium/assets/geoms/goal.py"
HAZARDS = "safety_gymnasium/assets/geoms/hazards.py"
GOAL0 = "safety_gymnasium/tasks/safe_navigation/goal/goal_level0.py"
GOAL1 = "safety_gymnasium/tasks/safe_navigation/goal/goal_level1.py"


class SafetyPointGoal1(GymnasiumDriver):
    """The Point Goal1 task of Safety-Gymnasium, served through its standard Gymnasium id."""

    device_id = "safety-point-goal1-gymnasium"
    env_id = "SafetyPointGoal1Gymnasium-v0"
    native = "safety_gymnasium.builder:Builder"
    backends = {"fake": ".fake:FakeSafetyPointGoal1"}
    display_name = "Safety-Gymnasium Point Goal1 (Gymnasium view)"
    vendor, model = "PKU-Alignment", "SafetyPointGoal1Gymnasium-v0"
    tags = ["goal", "gymnasium", "mujoco", "point", "reinforcement-learning", "safety-gymnasium", "simulation"]
    facts = [
        Fact("The README runs the Point Goal1 task as SafetyPointGoal1-v0 and states that its step returns "
             "(observation, reward, cost, terminated, truncated, info)", source="vendor_doc",
             ref=f"{README}:483-494"),
        Fact("The README also documents the standard Gymnasium id SafetyPointGoal1Gymnasium-v0, whose step returns "
             "five items without the separate cost", source="vendor_doc", ref=f"{README}:547-554"),
        Fact("Each task is also registered in the Gymnasium registry under a Gymnasium suffix, served by the "
             "conversion wrapper make_gymnasium_environment", source="upstream_code", ref=f"{INIT}:61-66"),
        Fact("The conversion wrapper calls the Safety-Gymnasium environment and returns (observation, reward, "
             "terminated, truncated, info), putting cost into info", source="upstream_code",
             ref=f"{CONVERSION}:26-34"),
        Fact("The Goal task family registers Goal0, Goal1 and Goal2 for all robots with max_episode_steps 1000",
             source="upstream_code", ref=f"{INIT}:136-137"),
        Fact("A registered task uses the entry point safety_gymnasium.builder:Builder", source="upstream_code",
             ref=f"{INIT}:80"),
        Fact("Builder is the gymnasium.Env subclass that the registered task instantiates", source="upstream_code",
             ref=f"{BUILDER}:55"),
        Fact("Builder builds the task and seeds it during setup", source="upstream_code",
             ref=f"{BUILDER}:141-144"),
        Fact("Builder.reset resets the task and returns (observation, info)", source="upstream_code",
             ref=f"{BUILDER}:180-191"),
        Fact("Builder.step applies one action, computes reward and cost, increments the step count and returns the "
             "six Safety-Gymnasium items", source="upstream_code", ref=f"{BUILDER}:193-251"),
        Fact("BaseTask defaults the episode length to 1000 environment steps", source="upstream_code",
             ref=f"{BASE_TASK}:181"),
        Fact("Builder truncates when the step count reaches task.num_steps", source="upstream_code",
             ref=f"{BUILDER}:244-247"),
        Fact("Observation flattening is enabled by default", source="upstream_code", ref=f"{UNDERLYING}:224"),
        Fact("The flattened observation space is built with flatten_space when observation_flatten is true",
             source="upstream_code", ref=f"{BASE_TASK}:270-275"),
        Fact("The agent sensors are accelerometer, velocimeter, gyro and magnetometer", source="upstream_code",
             ref=f"{BASE_AGENT}:49"),
        Fact("Lidar uses 16 bins", source="upstream_code", ref=f"{BASE_TASK}:47"),
        Fact("A lidar-observed obstacle adds a Box(0.0, 1.0, (num_bins,)) to the observation space",
             source="upstream_code", ref=f"{BASE_TASK}:239-247"),
        Fact("The Point action space is a Box built from the model's actuator_ctrlrange", source="upstream_code",
             ref=f"{BASE_AGENT}:227-234"),
        Fact("The point model has two actuators, a motor named x and a velocity actuator named z", source="upstream_code",
             ref=f"{POINT_XML}:54-56"),
        Fact("The point model default ctrlrange for both the motor and velocity actuators is -1 to 1",
             source="upstream_code", ref=f"{POINT_XML}:24-25"),
        Fact("The point model physics timestep is 0.002 s", source="upstream_code", ref=f"{POINT_XML}:19"),
        Fact("The default frameskip is a binomial draw of 10 trials at probability 1.0", source="upstream_code",
             ref=f"{UNDERLYING}:95-96"),
        Fact("simulation_forward steps MuJoCo once per drawn frameskip", source="upstream_code",
             ref=f"{UNDERLYING}:345-355"),
        Fact("Goal level 0 places the goal in the [-1, -1, 1, 1] extent with keepout 0.305", source="upstream_code",
             ref=f"{GOAL0}:27-29"),
        Fact("Goal level 1 widens the placement extent to [-1.5, -1.5, 1.5, 1.5] and adds 8 hazards and one vase",
             source="upstream_code", ref=f"{GOAL1}:31-34"),
        Fact("The goal radius is 0.3, the sparse goal reward is 1.0 and the dense distance reward is 1.0",
             source="upstream_code", ref=f"{GOAL}:31-40"),
        Fact("An episode terminates when the distance to the goal is at most the goal size", source="upstream_code",
             ref=f"{GOAL0}:57-61"),
        Fact("A hazard has radius 0.2 and a cost coefficient of 1.0", source="upstream_code",
             ref=f"{HAZARDS}:32-37"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The fake is analytic, so the
    #: level is F0; the bridge supplies the engine name, the lockstep clock and the seeded determinism it can derive.
    fidelity = {
        "engine": "gymnasium:SafetyPointGoal1Gymnasium-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the fake's layout and its state update is deterministic, "
                     "so one implementation repeats a trajectory for the same seed and actions; the fake draws the "
                     "layout with Python's random.Random and upstream draws it from numpy's generator, so one seed "
                     "gives different layouts on the two",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a kinematic point model: it moves the agent by a forward speed and a turn rate and does "
            "not run MuJoCo rigid-body dynamics, contacts, friction, gravity, actuator forces or meshes; the "
            "deployed fidelity level is F0, not the F1 of the upstream MuJoCo model",
            "the observation reproduces the upstream layout of 12 sensor values and a 16-bin lidar for the goal, "
            "the eight hazards and the vase (60 values), but the values are analytic placeholders, not MuJoCo "
            "sensor readings",
            "one fake tick is one 20 ms environment step; upstream advances a binomial frameskip of 10 physics "
            "steps of 2 ms each (point.xml:19, underlying.py:95-96), so the fake does not reproduce the physics "
            "substeps, and the sim path (gymnasium.make of the registered id) was not run here and additionally "
            "needs safety_gymnasium imported so that the Gymnasium id is registered",
            "the layout is drawn with Python's random.Random instead of the upstream numpy generator, so a seed "
            "does not give the same layout or trajectory on the two",
            "no rendering, no vision observation, no vase contact or displacement cost and no validation against "
            "the real environment",
            "no wall-clock pacing: realtime_factor 0, and ticks advance simulated time by timestep_ms only",
            "snapshot and restore are not offered: Builder exposes no get_state/set_state",
        ],
    }
