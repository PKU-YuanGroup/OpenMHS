"""OpenMHS driver for gh.hsp-iit/pybullet-robot-envs: the iCubReach-v0 PyBullet environment.

A GymnasiumDriver is configuration only.  The card's helper fits the upstream class: the environment exposes the
OpenAI Gym ``reset()`` / ``step(action)`` / ``seed(seed)`` interface (a legacy four-tuple ``step``), and the bridge
serves it through ``cap.world.step.v1``, ``cap.world.reset.v1`` and ``cap.world.seed.v1``.  The environment is a
simulator (R0): there is no hardware backend, no e-stop path to a machine and no operator-required bound.

The gate never imports the clone or installs PyBullet/Gym, so the ``fake`` backend is this package's own pure Python
stand-in for ``pybullet_robot_envs.envs.icub_envs.icub_reach_gym_env:iCubReachGymEnv`` (fake.py).  A backend name that
``backends`` does not list (``sim``) is served by ``gym.make(env_id)`` (GymnasiumDriver.open_native); that path needs the
upstream package, Gym, PyBullet and the object model data and was not run here.

The ``fidelity`` attribute is the contract of the model as deployed (spec 05-fidelity FID-002).  Every fact cites a line
of the clone at the pinned commit 8fb3f9ba1f1a0dec4cd1e96e26556afbd89cbd59.  This package is model-authored and
unreviewed: it is checked on the fake backend only, and its evidence is ``contract_checked``.
"""

from mhs.driver import Fact, GymnasiumDriver

REACH = "pybullet_robot_envs/envs/icub_envs/icub_reach_gym_env.py"
ICUB = "pybullet_robot_envs/envs/icub_envs/icub_env.py"
WORLD = "pybullet_robot_envs/envs/world_envs/world_env.py"
UTILS = "pybullet_robot_envs/envs/utils.py"
REGISTRY = "pybullet_robot_envs/__init__.py"


class iCubReach(GymnasiumDriver):
    device_id = "icub-reach"
    env_id = "iCubReach-v0"
    native = "pybullet_robot_envs.envs:iCubReachGymEnv"
    backends = {"fake": ".fake:FakeiCubReachEnv"}
    display_name = "PyBullet iCubReach-v0 (iCub reach simulation)"
    vendor, model = "Istituto Italiano di Tecnologia (IIT)", "iCubReach-v0"
    tags = ["icub", "reach", "manipulation", "pybullet", "reinforcement-learning", "simulation", "gym"]
    facts = [
        Fact("iCubReach-v0 is registered with entry point pybullet_robot_envs.envs:iCubReachGymEnv, "
             "max_episode_steps=1000, IK position control of the left arm (use_IK=1, control_orientation=0) and "
             "rendering on by default", source="upstream_code", ref=f"{REGISTRY}:7-17"),
        Fact("The observation concatenates the robot observation, the world observation and the object pose in the "
             "hand frame as position and Euler angles", source="upstream_code", ref=f"{REACH}:151-180"),
        Fact("The robot observation is the end-effector position, Euler orientation, Cartesian linear velocity and "
             "the positions of the controlled joints", source="upstream_code", ref=f"{ICUB}:202-249"),
        Fact("The world observation is the object position and its Euler orientation, or its quaternion when "
             "control_eu_or_quat is 1", source="upstream_code", ref=f"{WORLD}:109-126"),
        Fact("The controlled joints are the three torso joints plus the seven joints of the selected arm",
             source="upstream_code", ref=f"{ICUB}:42-50"),
        Fact("With use_IK set and control_orientation 0 the action dimension is 3: position x, y and z",
             source="upstream_code", ref=f"{ICUB}:187-197"),
        Fact("The action space is a Box whose every element is bounded by -1 and 1", source="upstream_code",
             ref=f"{REACH}:103-107"),
        Fact("In IK position mode a raw action element is multiplied by 0.005 and added to the hand position, then "
             "the position is clamped to the workspace", source="upstream_code", ref=f"{REACH}:204-229"),
        Fact("The workspace limits are [0.1, 0.45] on x, [-0.3, 0.3] on y and [0.5, 1.0] on z before the table "
             "height adjusts the z minimum", source="upstream_code", ref=f"{ICUB}:62"),
        Fact("Observations and actions are rescaled between the Box bounds and -1..1 by scale_gym_data",
             source="upstream_code", ref=f"{UTILS}:78-92"),
        Fact("The physics timestep is 1/240 s", source="upstream_code", ref=f"{REACH}:37"),
        Fact("The gravity used by the simulation is -9.8 m/s^2 on z", source="upstream_code", ref=f"{REACH}:130"),
        Fact("A reset reloads the robot and the world, steps the simulation 100 times after each reload and clears "
             "the step counter", source="upstream_code", ref=f"{REACH}:121-149"),
        Fact("The reach task's target distance threshold is 0.03 m", source="upstream_code", ref=f"{REACH}:52"),
        Fact("The episode ends when the hand-to-object distance is at most the target distance, when the terminated "
             "flag is set, or when the step counter exceeds max_steps", source="upstream_code",
             ref=f"{REACH}:301-317"),
        Fact("The reward is minus the hand-to-object distance, plus 1000 and (100 - distance * 80) when the "
             "distance is at most the target distance", source="upstream_code", ref=f"{REACH}:319-330"),
        Fact("step returns the four-tuple observation, reward, done, info of the legacy Gym API", source="upstream_code",
             ref=f"{REACH}:248-259"),
        Fact("seed sets the numpy generator and the world and robot seeds and returns the seed in a list",
             source="upstream_code", ref=f"{REACH}:261-265"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "pybullet:iCubReach-v0",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the environment seeds its numpy generator and its world and robot seeds; the fake draws its "
                     "start jitter with Python's random.Random(seed), so a seed repeats this package's fake but does "
                     "not reproduce the upstream trajectory",
        },
        "timestep_ms": 1000.0 / 240.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "rigid-body dynamics of the iCub, the table and the object in PyBullet: contacts, friction and the "
            "actuator/sensor models are those of the upstream simulation and are not modelled by this package",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms only",
            "the upstream registered environment asks for rendering (renders=True); the fake does not render",
            "the fake returns a 31-element observation with the upstream shape but fills the orientation, velocity, "
            "joint, object orientation and relative orientation channels with zeros; it was never compared with the "
            "upstream environment",
            "no physical device is modelled and the model was never validated against one",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
        ],
    }
