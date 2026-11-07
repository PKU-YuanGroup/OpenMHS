"""OpenMHS driver for gh.wil3/gymfc: the gymfc_nf-step-v1 flight-control environment (a Gymnasium family driver).

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment, ``native`` names the upstream
class the fake mirrors, and the bridge derives the contract from the fake environment's spaces.
``cap.world.step.v1`` takes ``{ticks, action}`` with the action ``{values}`` bounded element by element by the
environment's four-element Box action space ``[-1, 1]``, ``cap.world.reset.v1`` takes ``{seed, options}`` and
``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0): there is no hardware backend, no e-stop path to a
machine and no operator-required limit.

Why a fake: GymFC is a Gazebo 10.1.0 / Dart 6.7.0 simulator (README.md:97).  The upstream ``StepEnv`` connects to the
Aircraft plugin over a UDP protobuf channel, starts ``gzserver``, builds C++ plugins during ``pip install`` and needs a
digital-twin SDF (gymfc/envs/fc_env.py:168-172 and :488-493, setup.py:9-32).  The acceptance gate has no Gazebo, no
digital twin and never imports or runs the clone, so ``fake`` is this package's pure Python stand-in for the
registered ``gymfc_nf-step-v1`` environment (``examples/gymfc_nf/envs/step.py:10``).  The stand-in reproduces the
legacy gym interface (``reset()`` and a four-tuple from ``step()``), the spaces, the [-1, 1] to [0, 1] action clipping
of ``examples/gymfc_nf/envs/base.py:79``, the six-element state of
``examples/gymfc_nf/envs/states.py:19-21`` and the registered 4.608 s episode, not the Gazebo rigid-body dynamics.
The ``sim`` backend (an installed GymFC plus Gazebo) was not run here.

Every fact and constant below cites a line of the clone at the pinned commit
(08df94b06a5d7f8fb6d2cb2c155751f5336720e7).  This package is model-authored and unreviewed: it is checked on the
fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

FC_ENV = "gymfc/envs/fc_env.py"
BASE = "examples/gymfc_nf/envs/base.py"
STEP = "examples/gymfc_nf/envs/step.py"
STATES = "examples/gymfc_nf/envs/states.py"
REGISTRATION = "examples/gymfc_nf/envs/__init__.py"
REWARDS = "examples/gymfc_nf/envs/rewards.py"
WORLD = "gymfc/envs/assets/gazebo/worlds/attitude.world"


class GymFCStep(GymnasiumDriver):
    device_id = "gymfc-step"
    env_id = "gymfc_nf-step-v1"
    native = "gymfc_nf.envs.step:StepEnv"
    backends = {"fake": ".fake:FakeStepEnv"}
    action_space_ref = f"{BASE}:37"
    risk = "R0"
    display_name = "GymFC gymfc_nf-step-v1 flight-control environment"
    vendor, model = "Wil Koch", "GymFC gymfc_nf-step-v1"
    tags = ["gymfc", "flight-control", "attitude-control", "reinforcement-learning", "gazebo", "simulation"]
    facts = [
        Fact("GymFC uses Gazebo v10.1.0 with Dart v6.7.0 as the backend simulator", source="vendor_doc",
             ref="README.md:97"),
        Fact("FlightControlEnv is a generic OpenAI flight control gym environment; a subclass must set the OpenAI gym "
             "action_space and observation_space attributes", source="upstream_code", ref=f"{FC_ENV}:107-119"),
        Fact("The constructor connects an asyncio UDP datagram endpoint to the Aircraft plugin's host and port",
             source="upstream_code", ref=f"{FC_ENV}:167-174"),
        Fact("The simulator starts gzserver with the configured world file", source="upstream_code",
             ref=f"{FC_ENV}:488-493"),
        Fact("step_sim runs one asynchronous simulation step and returns the flattened observation",
             source="upstream_code", ref=f"{FC_ENV}:237-248"),
        Fact("reset sends an Action_pb2.Action.RESET message to the simulator and returns the observation",
             source="upstream_code", ref=f"{FC_ENV}:548-560"),
        Fact("The default configuration selects attitude.world", source="upstream_code", ref="gymfc/gymfc.ini:7"),
        Fact("The configured attitude.world declares the Dart physics engine and a max_step_size of 0.001 s",
             source="upstream_code", ref=f"{WORLD}:14-16"),
        Fact("FlightControlEnv.sdf_max_step_size reads the world's physics max_step_size element and returns its "
             "float value as the simulation step size", source="upstream_code", ref=f"{FC_ENV}:499-510"),
        Fact("BaseEnv declares a four-element Box action space between -np.ones(4) and np.ones(4), i.e. -1 and 1",
             source="upstream_code", ref=f"{BASE}:37"),
        Fact("BaseEnv.step maps the action with action_to_control_signal(action, 0, 1), so each element is clipped to "
             "[0, 1] before it becomes a motor control signal despite the [-1, 1] action space",
             source="upstream_code", ref=f"{BASE}:79"),
        Fact("action_to_control_signal clips the action to [action_low, action_high] and maps it linearly to "
             "[y_low, y_high]", source="upstream_code", ref=f"{BASE}:107-116"),
        Fact("The observation space is an unbounded Box (-inf to inf) with as many elements as the state function "
             "returns", source="upstream_code", ref=f"{BASE}:39-41"),
        Fact("BaseEnv.step returns (state, reward, done, {}) and sets done when sim_time reaches max_sim_time",
             source="upstream_code", ref=f"{BASE}:67-105"),
        Fact("BaseEnv.reset re-initialises the state arrays, resets the simulator and returns state_fn(self); seed() "
             "initialises the environment generator through gym.utils.seeding", source="upstream_code",
             ref=f"{BASE}:144-152"),
        Fact("StepEnv generates step setpoints: it holds a sampled target for pulse_width seconds and then returns to "
             "zero", source="upstream_code", ref=f"{STEP}:46-54"),
        Fact("StepEnv.reset samples a new target with the seeded generator as np_random.normal(0, max_rate, size=3)",
             source="upstream_code", ref=f"{STEP}:56-68"),
        Fact("The registered state function state_degrees_error_deltaerror returns the measured angular-rate error and "
             "its delta, six values in total", source="upstream_code", ref=f"{STATES}:19-21"),
        Fact("gymfc_nf-step-v1 is registered with max_rate 100, pulse_width 2.048 s, max_sim_time 4.608 s and that "
             "state function", source="upstream_code", ref=f"{REGISTRATION}:6-14"),
        Fact("RewardEnv.compute_reward combines an angular-rate error shaping term, control-output and oscillation "
             "penalties, an error-band reward and a doing-nothing penalty", source="upstream_code",
             ref=f"{REWARDS}:33-77"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "gazebo",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "StepEnv.seed() seeds the generator used to draw the next step target, and the fake repeats a "
                     "trajectory for the same seed and actions; the fake uses Python's random.Random while upstream "
                     "uses gym.utils.seeding's numpy generator, so one seed gives different trajectories on the two. "
                     "Gazebo/Dart bit-for-bit repeatability was not tested and is not claimed.",
        },
        "timestep_ms": 1.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is a reduced analytic stand-in: it models the action clipping, motor mixing and a "
            "first-order angular-rate response, not the Gazebo/Dart rigid-body, contact and aerodynamic dynamics of "
            "the upstream simulator",
            "no actuator, sensor, noise or battery model is reproduced in the fake; sample_noise is a no-op and the "
            "IMU, ESC and battery measurements of the digital twin are not simulated",
            "the fake does not model the UDP protobuf channel, packet drops or timeouts, gzserver startup, or the "
            "digital-twin SDF; it was not compared with the upstream simulator",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms only",
            "snapshot and restore are not offered: neither the environment nor the fake exposes get_state/set_state",
        ],
    }
