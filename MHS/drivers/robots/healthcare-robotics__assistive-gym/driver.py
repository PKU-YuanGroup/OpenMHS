"""OpenMHS driver for gh.healthcare-robotics/assistive-gym: the HumanTesting-v1 environment.

Assistive Gym is a PyBullet physics simulation for physical human-robot interaction and robotic assistance
(README.md:7), integrated into the OpenAI Gym interface (README.md:9).  The card's first entry symbol,
``assistive_gym.envs:HumanTestingEnv``, is a robot-free testing environment that builds a controllable human and
advances the PyBullet world; its observation is the empty list and its reward is always 0 (human_testing.py:15-20).

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives the whole
contract from the environment's spaces.  ``HumanTestingEnv`` passes the 20 arm joints of a controllable human to
``AssistiveEnv``, which builds a Box action space of one element per controllable joint, every element bounded -1 to 1
(human_testing.py:10-13, env.py:40-42).  The observation space has length 0 because the environment passes
``obs_robot_len=0`` and ``obs_human_len=0`` and ``_get_obs`` returns ``[]`` (human_testing.py:13-20, env.py:43-45).
``cap.world.step.v1`` therefore takes ``{ticks, action: {values: [20 numbers]}}``, ``cap.world.reset.v1`` takes
``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0): there is no hardware backend,
no e-stop path to a machine and no operator-required limit.

The upstream package needs PyBullet, Keras/TensorFlow, SMPL-X and bundled asset files (setup.py:21, env.py:37-39);
none of that is installed or importable where the gate runs, and package code never imports the clone.  The ``fake``
backend is therefore the package's own pure Python stand-in for the environment (fake.py), written from the class the
driver names as ``native``.  A backend name that ``backends`` does not list (``sim``) would be served by
``GymnasiumDriver.open_native`` -> ``gym.make(env_id)`` after importing assistive_gym; that path was not run here.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002):
PyBullet rigid-body dynamics with contacts (F1), a fixed environment step of ``frame_skip`` physics steps, seeded
randomisation, lockstep time, a full reset and no snapshot.  The ``gaps`` say what is not modelled.  Every constant
and rule cites a line of the clone at the pinned commit (fb799c377e1f144ff96044fb9096725f7f9cfc61).  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "assistive_gym/envs/human_testing.py"
BASE = "assistive_gym/envs/env.py"
HUMAN = "assistive_gym/envs/agents/human.py"


class HumanTesting(GymnasiumDriver):
    device_id = "assistive-human-testing"
    env_id = "HumanTesting-v1"
    native = "assistive_gym.envs:HumanTestingEnv"
    backends = {"fake": ".fake:FakeHumanTestingEnv"}
    action_space_ref = f"{BASE}:42"
    display_name = "Assistive Gym HumanTesting-v1 (PyBullet human arm test)"
    vendor, model = "Healthcare Robotics", "HumanTesting-v1"
    tags = ["assistive-gym", "pybullet", "human-robot-interaction", "simulation", "gym", "testing"]
    facts = [
        Fact("Assistive Gym is a physics-based simulation framework for physical human-robot interaction and "
             "robotic assistance", source="vendor_doc", ref="README.md:7"),
        Fact("Assistive Gym is integrated into the OpenAI Gym interface", source="vendor_doc", ref="README.md:9"),
        Fact("HumanTestingEnv subclasses AssistiveEnv and builds a robot-free world with a controllable human",
             source="upstream_code", ref=f"{ENV}:11-13"),
        Fact("The controllable human joints are human.right_arm_joints + human.left_arm_joints",
             source="upstream_code", ref=f"{ENV}:10"),
        Fact("right_arm_joints are 0 through 9 and left_arm_joints are 10 through 19",
             source="upstream_code", ref=f"{HUMAN}:5-6"),
        Fact("AssistiveEnv builds the action space as a Box with one element per controllable robot and human joint, "
             "with every element bounded -1 to 1", source="upstream_code", ref=f"{BASE}:40-42"),
        Fact("HumanTestingEnv passes obs_robot_len=0 and obs_human_len=0 and _get_obs returns an empty list",
             source="upstream_code", ref=f"{ENV}:13-20"),
        Fact("HumanTestingEnv.step calls take_step with gains 0.05 and forces 1.0 and returns an empty observation, "
             "reward 0, done False and an empty info dict", source="upstream_code", ref=f"{ENV}:15-17"),
        Fact("AssistiveEnv defaults time_step to 0.02 s and frame_skip to 5", source="upstream_code",
             ref=f"{BASE}:21"),
        Fact("AssistiveEnv.reset calls p.resetSimulation, disconnects the client and reconnects a DIRECT physics "
             "client", source="upstream_code", ref=f"{BASE}:91-97"),
        Fact("AssistiveEnv.reset sets the PyBullet time step to time_step, disables real-time simulation and sets "
             "gravity", source="upstream_code", ref=f"{BASE}:104-107"),
        Fact("AssistiveEnv.take_step clips the action to the action space bounds", source="upstream_code",
             ref=f"{BASE}:187"),
        Fact("AssistiveEnv.take_step calls p.stepSimulation frame_skip times per environment step",
             source="upstream_code", ref=f"{BASE}:224-226"),
        Fact("AssistiveEnv.seed uses gym's seeding.np_random and returns the seed", source="upstream_code",
             ref=f"{BASE}:78-80"),
        Fact("HumanTestingEnv.reset sets gravity to 0, 0, 0", source="upstream_code", ref=f"{ENV}:35"),
        Fact("AssistiveEnv loads realistic_arm_limits_model.h5 from the bundled assets directory",
             source="upstream_code", ref=f"{BASE}:37-39"),
        Fact("HumanTesting-v1 is registered with max_episode_steps=200", source="upstream_code",
             ref="assistive_gym/__init__.py:22-26"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    #: One environment step runs frame_skip=5 physics steps of time_step=0.02 s (env.py:21, :104, :224-226).
    fidelity = {
        "engine": "pybullet:assistive_gym:HumanTesting-v1",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the reset seed drives gym's numpy generator (env.py:78-80), which picks the human's randomised "
                     "properties; the exposed observation is the empty list and the reward is always 0, so no value "
                     "derived from the seed is visible through this interface and every seed gives the same receipts",
        },
        "timestep_ms": 100.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "PyBullet rigid-body contacts and position-controlled human joints: the motor gains and forces are the "
            "constants take_step receives (human_testing.py:16); there is no sensor model, latency model or noise "
            "model, so the contract is F1, not F2",
            "the observation is the empty list and the reward is always 0 (human_testing.py:15-20): this is a "
            "testing scaffold for the human model, not an assistive task with a task signal",
            "one environment step advances frame_skip=5 physics steps of time_step=0.02 s (env.py:21, :104, "
            ":224-226), so the declared 100 ms tick is the environment step, not one PyBullet integration step",
            "the 200-step TimeLimit comes from the Gym registration (assistive_gym/__init__.py:22-26); "
            "HumanTestingEnv.step itself always returns done False (human_testing.py:17)",
            "the fake backend does not run PyBullet: it keeps the step counter, the action-space lengths and the "
            "200-step truncation only, and was not compared with the upstream environment",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
            "the simulator needs PyBullet, Keras/TensorFlow, SMPL-X and the bundled asset files (setup.py:21, "
            "env.py:37-39), which the gate does not install; no upstream run was performed",
        ],
    }
