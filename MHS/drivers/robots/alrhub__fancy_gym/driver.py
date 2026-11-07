"""OpenMHS driver for gh.alrhub/fancy_gym: the fancy/SimpleReacher-v0 environment (a Gymnasium family driver).

A GymnasiumDriver is configuration only: ``env_id`` names the environment and the bridge derives the whole contract
from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action ``{"values": [t0,
t1]}`` bounded per link by ``+-max_torque`` (1000), ``cap.world.reset.v1`` takes ``{seed, options}`` and
``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0): there is no hardware backend, no e-stop path to a
machine and no operator-required limit.

The gate cannot import fancy_gym (the clone imports gymnasium, numpy and matplotlib at module import,
``simple_reacher.py:3-5``), so the ``fake`` backend is the package's own pure Python reacher.  A backend name that
``backends`` does not list (``sim``) is served by ``gymnasium.make(env_id)`` (GymnasiumDriver.open_native); that path
needs the upstream package and was not run here.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002):
every member of ``device.schema.json`` that applies to a simulator without a physical counterpart.  Every constant
and rule cites a line of the clone at the pinned commit (da1bced0181ced8267247779c001509a2fc94635).  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

SIMPLE = "fancy_gym/envs/classic_control/simple_reacher/simple_reacher.py"
BASE = "fancy_gym/envs/classic_control/base_reacher/base_reacher.py"
TORQUE = "fancy_gym/envs/classic_control/base_reacher/base_reacher_torque.py"
REGISTRY = "fancy_gym/envs/__init__.py"


class SimpleReacher(GymnasiumDriver):
    device_id = "simple-reacher"
    env_id = "fancy/SimpleReacher-v0"
    native = "fancy_gym.envs.classic_control.simple_reacher.simple_reacher:SimpleReacherEnv"
    backends = {"fake": ".fake:FakeSimpleReacherEnv"}
    action_space_ref = 'fancy_gym/envs/classic_control/base_reacher/base_reacher_torque.py:16-18'
    display_name = "fancy_gym SimpleReacher-v0 (classic control)"
    vendor, model = "alrhub", "fancy/SimpleReacher-v0"
    tags = ["reacher", "classic-control", "torque-control", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("fancy/SimpleReacher-v0 is registered with entry point SimpleReacherEnv and n_links=2",
             source="upstream_code", ref=f"{REGISTRY}:38-45"),
        Fact("fancy/SimpleReacher-v0 is registered with max_episode_steps=200", source="upstream_code",
             ref=f"{REGISTRY}:42"),
        Fact("The action space is a Box with one torque per link, low=-1000 and high=+1000 (max_torque 1000)",
             source="upstream_code", ref=f"{TORQUE}:16-18"),
        Fact("The simulation timestep is 0.01 s", source="upstream_code", ref=f"{BASE}:21"),
        Fact("A step adds dt times the torque to the angular velocity and then dt times the angular velocity to the "
             "joint angle", source="upstream_code", ref=f"{TORQUE}:25-26"),
        Fact("The torque step returns terminated False and truncated False: the environment class has no terminal "
             "state", source="upstream_code", ref=f"{TORQUE}:34-35"),
        Fact("Every link has length 1.0", source="upstream_code", ref=f"{BASE}:19"),
        Fact("The distance reward starts at step 199 (steps_before_reward=199)", source="upstream_code",
             ref=f"{SIMPLE}:31"),
        Fact("The reward is the distance term minus the sum of the squared torques; the distance term is zero before "
             "steps_before_reward", source="upstream_code", ref=f"{SIMPLE}:63-69"),
        Fact("The observation concatenates cos(angle), sin(angle), angular velocity, end-effector minus goal and "
             "the step count", source="upstream_code", ref=f"{SIMPLE}:75-83"),
        Fact("The observation space bounds the cos and sin components by +-pi and the velocity, target-distance and "
             "step components by infinity", source="upstream_code", ref=f"{SIMPLE}:33-40"),
        Fact("A reset with random_start samples the first joint angle uniformly between pi/4 and 3*pi/4 and sets "
             "the other joints to zero", source="upstream_code", ref=f"{BASE}:77-86"),
        Fact("SimpleReacherEnv.reset generates a goal, resets, generates the goal again and resets again so a seeded "
             "reset is deterministic", source="upstream_code", ref=f"{SIMPLE}:46-54"),
        Fact("The goal is drawn uniformly from a square of side 2*total_length until its norm is below "
             "total_length", source="upstream_code", ref=f"{SIMPLE}:89-92"),
        Fact("The joint limits are -pi and +pi", source="upstream_code", ref=f"{BASE}:38-39"),
        Fact("A joint angle outside the joint limits is reported as a self collision", source="upstream_code",
             ref=f"{BASE}:105-112"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "gymnasium:fancy/SimpleReacher-v0",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the initial joint angle and the goal, and the dynamics "
                     "are deterministic, so one implementation repeats a trajectory for the same seed and actions; "
                     "this package's fake draws with Python's random.Random and upstream with numpy's generator, so "
                     "a seed gives different trajectories on the two",
        },
        "timestep_ms": 10.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic point links integrated from torque: no link inertias, gravity, friction, contact forces or "
            "actuator dynamics; a collision only sets a flag and does not change the motion",
            "the self collision check of the fake only tests the joint limits, not the segment intersections of "
            "base_reacher.py:114-118",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms (dt 0.01 s) only",
            "no physical device is modelled and the model was never validated against one",
            "the fake backend re-implements the kinematics in pure Python floats and was not compared with the "
            "upstream environment (fancy_gym was not importable where the gate ran): trajectories can differ from "
            "upstream's float32 observations and numpy random stream",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
            "the 200-step episode limit comes from the registration and the gymnasium TimeLimit wrapper, not from "
            "SimpleReacherEnv itself",
        ],
    }
