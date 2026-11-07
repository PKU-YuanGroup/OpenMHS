"""OpenMHS driver for gh.myohub/myosuite: the Baoding challenge environment (a Gymnasium family driver).

The card's entry symbol used here is ``myosuite.envs.myo.tasks.challenge.baoding:BaodingEnv``, the class behind the
registered ``myoChallengeBaodingP1-v1`` environment.  A GymnasiumDriver is configuration only: ``env_id`` names the
environment and the bridge derives the action and observation contract from the environment's spaces.  The action
space is a normalized Box with one value per muscle actuator, so ``cap.world.step.v1`` takes ``{ticks, action}`` with
``action = {values: [...]}``; ``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.
The device is simulated (R0): there is no hardware backend, no path to a physical e-stop and no operator-required
limit.

The gate cannot import MyoSuite, MuJoCo, gymnasium or numpy (see fake.py), so the ``fake`` backend is the package's own
kinematic stand-in for ``BaodingEnv``.  A backend name that ``backends`` does not list (``sim``) is served by
``gymnasium.make("myoChallengeBaodingP1-v1")`` (GymnasiumDriver.open_native); that path needs the upstream package and
its MuJoCo assets and was not run here.

The ``fidelity`` attribute describes the model as deployed on the fake backend (spec 05-fidelity FID-002).  It is F0:
the fake is a kinematic stand-in with no dynamics, and the gaps say so.  This package is model-authored and
unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

BAODING = "myosuite/envs/myo/tasks/challenge/baoding.py"
GYM_ENV = "myosuite/envs/gymnasium_env.py"
REGISTRY = "myosuite/envs/myo/tasks/challenge/__init__.py"
MODEL = "myosuite/envs/myo/assets/hand/myohand_baoding.xml"


class Baoding(GymnasiumDriver):
    device_id = "myosuite-baoding"
    env_id = "myoChallengeBaodingP1-v1"
    native = "myosuite.envs.myo.tasks.challenge.baoding:BaodingEnv"
    backends = {"fake": ".fake:FakeBaodingEnv"}
    display_name = "MyoSuite Baoding balls (myoChallengeBaodingP1-v1)"
    vendor, model = "MyoHub", "myoChallengeBaodingP1-v1"
    tags = ["baoding", "musculoskeletal", "reinforcement-learning", "simulation", "gymnasium", "myosuite"]
    facts = [
        Fact("myoChallengeBaodingP1-v1 is registered with entry point BaodingEnv, model hand/myohand_baoding.xml "
             "and max_episode_steps=200", source="upstream_code", ref=f"{REGISTRY}:501-505"),
        Fact("The normalized action space is a symmetric Box from -ones to +ones with one value per actuator",
             source="upstream_code", ref=f"{BAODING}:202-209"),
        Fact("The default observation keys are hand_pos, object1_pos, object1_velp, object2_pos, object2_velp, "
             "target1_pos, target2_pos, target1_err and target2_err", source="upstream_code",
             ref=f"{BAODING}:66-75"),
        Fact("act (the muscle activations) is appended to the observation when the model has muscle actuators",
             source="upstream_code", ref=f"{BAODING}:197-200"),
        Fact("hand_pos is qpos[:-14], the hand coordinates before the two balls' free joints; the ball velocities are "
             "qvel[-12:-9] and qvel[-6:-3] times the control timestep", source="upstream_code",
             ref=f"{BAODING}:279-283"),
        Fact("target1_err and target2_err are the target position minus the ball position", source="upstream_code",
             ref=f"{BAODING}:288-289"),
        Fact("The observation space is an unbounded Box: the observations are physical quantities with no common "
             "bound and are not clipped", source="upstream_code", ref=f"{GYM_ENV}:466-479"),
        Fact("step returns the Gymnasium five-tuple and always passes False for truncated; the TimeLimit wrapper "
             "owns the step limit", source="upstream_code", ref=f"{GYM_ENV}:535-542"),
        Fact("reset restores qpos and qvel from the initial state and returns the observation",
             source="upstream_code", ref=f"{BAODING}:505-515"),
        Fact("The episode is done when a ball's height is below the constructor option drop_th",
             source="upstream_code", ref=f"{BAODING}:313-327"),
        Fact("The MuJoCo model timestep is 0.0025 s", source="upstream_code", ref=f"{MODEL}:14"),
        Fact("The control timestep is the model timestep times frame_skip", source="upstream_code",
             ref=f"{BAODING}:141"),
        Fact("The baoding scene adds one free joint for each of the two balls, after the hand body",
             source="upstream_code", ref=f"{MODEL}:22-31"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop the runtime latches and refuses step and reset "
                  "until mhs.safety.reset clears it; the last observation stays readable and no native stop exists "
                  "because the device is simulated")
    #: The fidelity contract of the deployed fake (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind, the lockstep clock and the step time from the environment; the override states the
    #: kinematic F0 model of this package and records what it does not model.
    fidelity = {
        "engine": "analytic:myosuite-baoding-stand-in",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the fake's initial ball offset and its later steps are "
                     "a deterministic function of the action; the fake uses Python's random.Random, not the upstream "
                     "environment's numpy generator, so a seed does not give the same trajectory on both",
        },
        "timestep_ms": 25.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "no dynamics: the fake backend is a kinematic stand-in that moves two ball coordinates by a fixed "
            "placeholder response; no MuJoCo integration, contacts, tendons, muscles or actuator forces are modelled",
            "the observation vector has the real shape (hand coordinates, two ball positions and velocities, two "
            "target positions and errors, muscle activations) but placeholder values; it is not comparable with a "
            "MyoSuite rollout",
            "the nominal control interval is 25 ms (model timestep 0.0025 s times frame_skip 10); a deployment that "
            "overrides frame_skip changes it",
            "the fake was never compared with the upstream environment; MyoSuite, MuJoCo and gymnasium were not "
            "importable where the gate ran",
            "the sim backend (gymnasium.make of the registered environment) was not run: it needs the upstream "
            "package, MuJoCo and its assets",
            "no rendering and no snapshot or restore: the bridge leaves cap.world.render.v1 unbound and the fake "
            "exposes no get_state or set_state",
        ],
    }
