"""OpenMHS driver for gh.osurobotics/kinovagrasping: the kinovagripper-v0 grasping environment.

The upstream package registers the legacy gym environment ``kinovagripper-v0`` whose entry class is
``gym_kinova_gripper.envs:KinovaGripper_Env``.  The class is a MuJoCo 1.50 / mujoco-py simulation of a Kinova
j2s7s300 arm with a three-finger gripper; its ``reset`` needs the object shape keys and the hand orientation as
positional arguments and its ``step`` returns the legacy four-tuple.  It cannot be imported where the gate runs
(README.md:7-10 names Python 3.7, MuJoCo 1.50 and mujoco-py), so the ``fake`` backend is a pure-Python analytic
stand-in for the bridge's ``reset(seed=..., options=...)`` / five-tuple contract.  The model as deployed is F0:
joint and hand positions are integrated directly, without MuJoCo, contacts or forces.

The class is a GymnasiumDriver because the card's decision is ``family-config`` (``family: gymnasium``, helper
``GymnasiumDriver``); the bridge derives ``cap.world.reset.v1``, ``cap.world.step.v1`` and ``cap.world.seed.v1``
from the fake's spaces.  ``action_space`` stays the upstream ``Box`` of four velocity commands bounded by -0.8
and 0.8 (kinova_gripper_env.py:128); ``observation_space`` is the 48-element Box declared at
kinova_gripper_env.py:211-237.  The device is simulated (R0): there is no hardware backend, no physical effect and
no operator-required limit.  This package is model-authored and unreviewed; it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "gym-kinova-gripper/gym_kinova_gripper/envs/kinova_gripper_env.py"
REGISTER = "gym-kinova-gripper/gym_kinova_gripper/__init__.py"
HAND_MODEL = ("gym-kinova-gripper/gym_kinova_gripper/envs/kinova_description/"
              "j2s7s300_end_effector_v1_mbox.xml")


class KinovaGrasping(GymnasiumDriver):
    device_id = "kinovagripper"
    env_id = "kinovagripper-v0"
    native = "gym_kinova_gripper.envs:KinovaGripper_Env"
    backends = {"fake": ".fake:FakeKinovaGripperEnv"}
    action_space_ref = f"{ENV}:128"
    display_name = "Kinova j2s7s300 grasping environment (kinovagripper-v0)"
    vendor, model = "OSU Robotics", "Kinova j2s7s300 + three-finger gripper (MuJoCo model)"
    tags = ["grasping", "kinova", "j2s7s300", "gym", "mujoco", "reinforcement-learning", "simulation"]

    facts = [
        Fact("The action space is a Box whose low is -0.8 and whose high is 0.8 on every element",
             source="upstream_code", ref=f"{ENV}:128"),
        Fact("The constructor default frame_skip is 15", source="upstream_code", ref=f"{ENV}:51"),
        Fact("The default hand model declares a timestep of 0.01 s", source="upstream_code",
             ref=f"{HAND_MODEL}:10"),
        Fact("The environment sets max_episode_steps to 30", source="upstream_code", ref=f"{ENV}:123"),
        Fact("The gym registration is kinovagripper-v0 with max_episode_steps 100", source="upstream_code",
             ref=f"{REGISTER}:3-6"),
        Fact("reset takes shape_keys and hand_orientation as positional arguments", source="upstream_code",
             ref=f"{ENV}:1310"),
        Fact("step returns the observation, reward, done flag and info as a four-tuple", source="upstream_code",
             ref=f"{ENV}:1552"),
        Fact("seed stores the numpy random generator and returns the seed in a list", source="upstream_code",
             ref=f"{ENV}:1487-1489"),
        Fact("An action whose length is 4 is padded with two zeros to 6 values", source="upstream_code",
             ref=f"{ENV}:1502-1503"),
        Fact("The local observation documentation runs from index 0 to index 81", source="upstream_code",
             ref=f"{ENV}:440-454"),
        Fact("The object-height target is 0.2", source="upstream_code", ref=f"{ENV}:634"),
        Fact("The lift reward is 50.0 and done becomes true when the object z is within 0.005 of the target or "
             "above it", source="upstream_code", ref=f"{ENV}:661-663"),
        Fact("Python 3.7 and MuJoCo 1.50 are the documented requirements", source="vendor_doc",
             ref="README.md:7-10"),
    ]

    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the world state is kept and stays readable")
    #: Fidelity contract of the model as deployed (spec 05-fidelity section 2).  The fake is kinematic (F0):
    #: one bridge tick integrates the four velocity commands for frame_skip model steps of the selected model.
    fidelity = {
        "engine": "analytic:kinovagripper-v0-fake",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) fixes the placeholders of the initial hand and object pose and the integration "
                     "is arithmetic, so one implementation repeats a trajectory; the fake draws with Python's "
                     "random.Random and was not compared with the upstream numpy stream",
        },
        "timestep_ms": 150.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is analytic (F0): it does not run MuJoCo and models no rigid-body dynamics, contacts, "
            "friction, actuator forces, sensor noise or the grasp classifier",
            "the upstream environment is legacy gym: reset(shape_keys, hand_orientation) needs two positional "
            "arguments and step returns a four-tuple (kinova_gripper_env.py:1310, :1552); the fake implements the "
            "gymnasium reset(seed, options) and five-tuple API the bridge calls, and the two required legacy "
            "arguments are accepted through reset options instead",
            "the fake returns the 48-element observation declared by observation_space "
            "(kinova_gripper_env.py:211-237); the local _get_obs() documentation describes 82 elements "
            "(kinova_gripper_env.py:440-454), which the fake does not reproduce",
            "the initial hand/object pose, object size and finger distances are placeholders, not samples from "
            "the upstream coordinate files or object XML models",
            "the 30-step class attribute and the 100-step gym registration are not enforced as a time limit; the "
            "fake only reports done from the lift-reward rule (kinova_gripper_env.py:661-663)",
            "MuJoCo 1.50, mujoco-py, a C compiler and a MuJoCo licence key are required upstream "
            "(README.md:7-10); they were not installed and the upstream simulator was never opened or compared",
        ],
    }
