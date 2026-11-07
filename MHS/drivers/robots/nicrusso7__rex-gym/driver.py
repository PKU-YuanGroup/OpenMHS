"""OpenMHS driver for gh.nicrusso7/rex-gym: the RexWalk-v0 environment (a Gymnasium family driver).

A ``GymnasiumDriver`` is configuration only: ``env_id`` names the environment and the bridge derives the whole
contract from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action derived from
``Box(-0.4, 0.4)`` of two elements (the default ``ik`` signal mode), ``cap.world.reset.v1`` takes ``{seed, options}``
and ``cap.world.seed.v1`` takes ``{seed}``.  The device is simulated (R0): there is no hardware backend, no e-stop
path to a machine and no operator-required limit.

The gate cannot import rex-gym (the clone targets Python 3.7 and pins numpy 1.17.3, pybullet 2.8.3, gym 0.17.1 and
TensorFlow 1.15.5; requirements.txt:1-7), so the ``fake`` backend is the package's own pure Python stand-in (fake.py).  A backend
name that ``backends`` does not list (``sim``) is served by ``gymnasium.make(env_id)`` after the environment has been
registered by ``rex_gym.playground`` (GymnasiumDriver.open_native); that path was not run here.

The ``fidelity`` attribute is the contract of the model as deployed (spec 05-fidelity FID-002): the pybullet rigid-body
simulation behind the clone, with the fake's limitations in ``gaps``.  This package is model-authored and unreviewed:
it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

WALK = "rex_gym/envs/gym/walk_env.py"
BASE = "rex_gym/envs/rex_gym_env.py"
REGISTER = "rex_gym/playground/__init__.py"


class RexWalk(GymnasiumDriver):
    device_id = "rex-walk"
    env_id = "RexWalk-v0"
    #: The bridge's configured seed of the first episode; placeholder configuration, not a device parameter.
    seed = 0
    native = "rex_gym.envs.gym.walk_env:RexWalkEnv"
    backends = {"fake": ".fake:FakeRexWalkEnv"}
    display_name = "Rex-gym RexWalk-v0 (quadruped walk simulation)"
    vendor, model = "Nicola Russo", "rex-gym 0.2.7 RexWalk-v0"
    tags = ["rex-gym", "quadruped", "locomotion", "pybullet", "reinforcement-learning", "simulation", "gym"]
    facts = [
        Fact("RexWalk-v0 is registered with entry point rex_gym.envs.gym.walk_env:RexWalkEnv and "
             "max_episode_steps=2500", source="upstream_code", ref=f"{REGISTER}:24-29"),
        Fact("RexWalkEnv is the alternating-leg locomotion environment for the quadruped Rex",
             source="upstream_code", ref=f"{WALK}:17-24"),
        Fact("With the default signal_type 'ik' the action space is a Box of two elements bounded by -0.4 and 0.4; "
             "the 'ol' signal mode has eight elements bounded by -0.01 and 0.01", source="upstream_code",
             ref=f"{WALK}:104-114"),
        Fact("An observation is [roll, pitch, roll_rate, pitch_rate] of the robot base", source="upstream_code",
             ref=f"{WALK}:356-362"),
        Fact("The observation upper bound is 2*pi for roll and pitch and 2*pi/time_step for the two rates, and the "
             "lower bound is its negation", source="upstream_code", ref=f"{WALK}:364-378"),
        Fact("The default control_time_step is 0.005 s and the default action_repeat is 5", source="upstream_code",
             ref=f"{WALK}:34-35"),
        Fact("The base environment computes its simulation step as control_time_step/action_repeat, which is "
             "0.001 s with the RexWalk defaults", source="upstream_code", ref=f"{BASE}:170-173"),
        Fact("The base reset sets the pybullet time step to that simulation step", source="upstream_code",
             ref=f"{BASE}:308"),
        Fact("The base constructor builds the observation space as a Box from the lower bound minus OBSERVATION_EPS "
             "to the upper bound plus OBSERVATION_EPS", source="upstream_code", ref=f"{BASE}:277-282"),
        Fact("RexWalkEnv.reset resets its flags, draws the backwards flag and the target position from Python's "
             "global random module and returns _get_observation()", source="upstream_code", ref=f"{WALK}:125-154"),
        Fact("RexWalkEnv.reset passes the stand initial pose and a 0.5 s reset duration to the base reset",
             source="upstream_code", ref=f"{WALK}:125-129"),
        Fact("seed(seed) replaces the environment's numpy generator with gym.utils.seeding.np_random and returns "
             "[seed]", source="upstream_code", ref=f"{BASE}:359-361"),
        Fact("step applies the action through rex.Step, computes the reward and termination, increments the step "
             "counter and returns (observation, reward, done, info)", source="upstream_code", ref=f"{BASE}:403-414"),
        Fact("The walk environment considers Rex fallen when the dot product of the world up vector and the base up "
             "vector is below 0.85", source="upstream_code", ref=f"{WALK}:326-338"),
        Fact("The base termination is is_fallen() or env_goal_reached or _out_of_trajectory()",
             source="upstream_code", ref=f"{BASE}:490-499"),
        Fact("RexWalkEnv sets goal_reached and is_terminating when the base x is within 0.15 of the target "
             "position", source="upstream_code", ref=f"{WALK}:207-215"),
        Fact("The reward weights default to distance 1.0, energy 0.0005, drift 2.0 and shake 0.005",
             source="upstream_code", ref=f"{BASE}:56-59"),
        Fact("The base reward is the sum of the weighted forward, energy, drift and shake terms",
             source="upstream_code", ref=f"{BASE}:538-542"),
        Fact("RexWalkEnv declares the render modes human and rgb_array at 66 frames per second",
             source="upstream_code", ref=f"{WALK}:27"),
        Fact("The clone pins numpy 1.17.3, pybullet 2.8.3, gym 0.17.1, tensorflow 1.15.5 and "
             "tensorflow-probability 0.8 in requirements.txt", source="upstream_code", ref="requirements.txt:1-7"),
        Fact("The README instructs users to create a Python 3.7 environment", source="vendor_doc",
             ref="README.md:22-26"),
        Fact("The README documents Rex as a 12-joint robot with 3 motors for each leg and imports the model into "
             "pyBullet", source="vendor_doc", ref="README.md:87-89"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop the runtime refuses every step and reset until "
                  "mhs.safety.reset clears the latch, and the last world state stays readable; the simulator has no "
                  "native stop")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "pybullet:RexWalk-v0",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "statistical",
            "seed_control": "parameter",
            "notes": "seed(seed) replaces the environment's numpy generator (rex_gym_env.py:359-361), but reset() "
                     "draws the backwards flag and the target position from Python's global random module "
                     "(walk_env.py:133-146), so a seed does not fix a whole trajectory; pybullet's solver also "
                     "gives no run-to-run equality claim.  The package fake draws both values from its own "
                     "random.Random(seed), so the fake alone repeats a trajectory for one seed.",
        },
        "timestep_ms": 1.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "F1 is the pybullet rigid-body model of the clone; the package fake is an analytic stand-in with no "
            "contacts, friction, actuator, sensor or noise model and makes no physics claim",
            "the fake does not model the URDF, the 12-joint motor model, the gait planner, inverse kinematics, the "
            "fall test or the reward: it advances a four-value placeholder observation and returns reward 0.0",
            "the fake applies the registered 2500-step limit as gymnasium truncation; the upstream class alone "
            "never truncates (its step returns the legacy 4-tuple) and gym.make wraps it in a TimeLimit "
            "(rex_gym/playground/__init__.py:24-29)",
            "the upstream reset draws the backwards flag and target position from Python's global random module "
            "(walk_env.py:133-146), so the bridge seed does not repeat an upstream trajectory; the fake draws "
            "them from random.Random(seed) and was never compared with the pybullet environment",
            "the sim backend was not run: the clone targets Python 3.7 and pins numpy 1.17.3, pybullet 2.8.3, "
            "gym 0.17.1 and TensorFlow 1.15.5 (requirements.txt:1-7, README.md:22-26), none of them installed where "
            "the gate ran; "
            "a backend outside backends goes through gymnasium.make and needs rex_gym.playground imported",
            "no rendering: the metadata declares human and rgb_array at 66 frames per second (walk_env.py:27) but "
            "the fake draws no frames and cap.world.render.v1 is unbound",
            "no wall-clock pacing: realtime_factor 0; one environment step applies action_repeat=5 physics steps "
            "of 1 ms, a 5 ms control period (walk_env.py:34-35, rex_gym_env.py:170-173), while timestep_ms names "
            "the 1 ms physics step, as FID-015 requires when the two are separated",
            "snapshot and restore are not offered: RexWalkEnv defines no get_state or set_state",
            "the legacy reset() signature takes no options (walk_env.py:125); the bridge falls back to reset() "
            "after seed(seed), so a non-empty options object is ignored",
        ],
    }
