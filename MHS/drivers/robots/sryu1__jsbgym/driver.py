"""OpenMHS driver for gh.sryu1/jsbgym: a JSBGym fixed-wing flight-control environment (a Gymnasium family driver).

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives the
whole contract from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action
``{values: [aileron, elevator, rudder]}`` bounded per element by the environment's ``Box(-1, +1, (3,))``,
``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` takes ``{seed}``.

The environment is the FlightGear-disabled Cessna 172 HeadingControlTask variant: 11 observation values (the nine
base flight state variables plus altitude and track error), three normalised control-surface commands, a 60 s
episode at 5 agent interactions per second (12 JSBSim integration steps of 1/60 s each), and no truncation from
``step``.  The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no
operator-required bound.

The gate does not install gymnasium, jsbsim or numpy and package code never imports the clone, so the ``fake``
backend is this package's pure-Python kinematic stand-in (fake.py).  A backend name that ``backends`` does not list
(``sim``) would be served by ``gymnasium.make(env_id)`` through GymnasiumDriver.open_native; that path was not run
here.

The ``fidelity`` attribute describes the model actually deployed by this package (spec 05-fidelity FID-002): F0
kinematics of the fake backend, not the JSBSim aerodynamics of the upstream environment.  The gaps state that
difference.  Every fact cites a line of the clone at the pinned commit
(80adc75514ac2cf2d7120cc436a1cbfa49ba0bc8).  This package is model-authored and unreviewed; it is checked on the
fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENVIRONMENT = "jsbgym/environment.py"
TASKS = "jsbgym/tasks.py"
PROPERTIES = "jsbgym/properties.py"


class JsbGym(GymnasiumDriver):
    device_id = "jsbgym"
    env_id = "C172-HeadingControlTask-Shaping.STANDARD-NoFG-v0"
    native = "jsbgym.environment:NoFGJsbSimEnv"
    backends = {"fake": ".fake:FakeNoFGJsbSimEnv"}
    action_space_ref = f"{PROPERTIES}:93-101"
    display_name = "JSBGym Cessna 172 heading-control environment (FlightGear disabled)"
    vendor, model = "sryu1", "C172-HeadingControlTask-Shaping.STANDARD-NoFG-v0"
    tags = ["fixed-wing", "flight-control", "jsbsim", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("JSBGym provides reinforcement learning environments for the control of fixed-wing aircraft using "
             "the JSBSim flight dynamics model and implements the Gymnasium interface", source="vendor_doc",
             ref="README.md:8"),
        Fact("The documented use is gym.make(ENV_ID), then env.reset() and env.step(action), which returns "
             "observation, reward, terminated, truncated and info", source="vendor_doc", ref="README.md:67-73"),
        Fact("The FlightGear-disabled Cessna 172 HeadingControlTask environment is registered as "
             "C172-HeadingControlTask-Shaping.STANDARD-NoFG-v0", source="vendor_doc", ref="README.md:129"),
        Fact("The observation is an 11-tuple: altitude, pitch, roll, body velocities u, v, w, body rates p, q, r, "
             "altitude error and track error", source="vendor_doc", ref="README.md:158-172"),
        Fact("Actions are 3-tuples of floats in the range [-1, +1] describing the aileron, elevator and rudder "
             "commands", source="vendor_doc", ref="README.md:174-180"),
        Fact("The state space is a Box built from each state variable's min and max with dtype float64",
             source="upstream_code", ref=f"{TASKS}:231-234"),
        Fact("The action space is a Box built from each action variable's min and max with dtype float64",
             source="upstream_code", ref=f"{TASKS}:236-239"),
        Fact("The HeadingControlTask action variables are the aileron, elevator and rudder commands",
             source="upstream_code", ref=f"{TASKS}:279"),
        Fact("The altitude bound is -1400 to 85000 ft, the pitch bound is -pi/2 to pi/2 and the roll bound is "
             "-pi to pi", source="upstream_code", ref=f"{PROPERTIES}:19-26"),
        Fact("The body-frame velocity bounds u, v and w are -2200 to 2200 ft/s",
             source="upstream_code", ref=f"{PROPERTIES}:40-48"),
        Fact("The body-rate bounds p, q and r are -2*pi to 2*pi rad/s",
             source="upstream_code", ref=f"{PROPERTIES}:58-66"),
        Fact("The aileron, elevator and rudder command bounds are -1.0 to 1.0",
             source="upstream_code", ref=f"{PROPERTIES}:93-101"),
        Fact("The task's nine base state variables are altitude, pitch, roll, u, v, w, p, q and r",
             source="upstream_code", ref=f"{TASKS}:98-108"),
        Fact("The HeadingControlTask state adds the altitude error and the track error to the nine base variables",
             source="upstream_code", ref=f"{TASKS}:301-307"),
        Fact("The altitude error is bounded by the altitude bounds and the track error is bounded -180 to 180 deg",
             source="upstream_code", ref=f"{TASKS}:270-278"),
        Fact("The initial altitude is 5000 ft", source="upstream_code", ref=f"{TASKS}:97"),
        Fact("The initial heading is 270 deg", source="upstream_code", ref=f"{TASKS}:256"),
        Fact("The default episode time is 60 s", source="upstream_code", ref=f"{TASKS}:257"),
        Fact("The default agent interaction frequency is 5 Hz", source="upstream_code", ref=f"{ENVIRONMENT}:35"),
        Fact("The episode step budget is ceil(episode_time_s * step_frequency_hz) agent steps and steps_left is "
             "bounded 0 to that budget", source="upstream_code", ref=f"{TASKS}:295-299"),
        Fact("Each task step decrements steps_left and the task terminates when steps_left is zero or less, the "
             "last assessment reward is below MIN_STATE_QUALITY, or the altitude error exceeds "
             "MAX_ALTITUDE_DEVIATION_FT", source="upstream_code", ref=f"{TASKS}:418-431"),
        Fact("MIN_STATE_QUALITY is 0.0 and MAX_ALTITUDE_DEVIATION_FT is 1000 ft",
             source="upstream_code", ref=f"{TASKS}:262-263"),
        Fact("JSBSim integrates at 60 Hz and the environment runs JSBSIM_DT_HZ // agent_interaction_freq "
             "integration steps per agent step", source="upstream_code", ref=f"{ENVIRONMENT}:25-57"),
        Fact("The environment rejects an agent interaction frequency above JSBSIM_DT_HZ",
             source="upstream_code", ref=f"{ENVIRONMENT}:50-55"),
        Fact("The environment constructs the task with the agent interaction frequency and then takes the "
             "observation and action spaces from the task", source="upstream_code", ref=f"{ENVIRONMENT}:59-62"),
        Fact("step() calls the task for sim_steps_per_agent_step integration steps and returns observation, reward, "
             "terminated, False and info", source="upstream_code", ref=f"{ENVIRONMENT}:96-100"),
        Fact("reset(seed, options) seeds the environment, reinitialises or creates the simulation and returns the "
             "first observation and an info dict", source="upstream_code", ref=f"{ENVIRONMENT}:102-134"),
        Fact("NoFGJsbSimEnv is the training variant: it constructs the simulation with "
             "allow_flightgear_output=False", source="upstream_code", ref=f"{ENVIRONMENT}:225-246"),
        Fact("The package registers every aircraft/task/shaping setting and uses NoFGJsbSimEnv as the entry point "
             "when FlightGear is disabled", source="upstream_code", ref="jsbgym/__init__.py:18-29"),
        Fact("Environment ids are built as aircraft-task-shaping-FG or NoFG-v0", source="upstream_code",
             ref="jsbgym/utils.py:39-51"),
        Fact("The simulation constructs an in-process jsbsim.FGFDMExec and sets sim_dt to 1/sim_frequency_hz",
             source="upstream_code", ref="jsbgym/simulation.py:39-46"),
    ]
    safe_state = ("the simulation stops advancing: step, reset and seed are refused after an e-stop until "
                  "mhs.safety.reset clears the latch; the last observation stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge would derive the
    #: engine, determinism kind and lockstep clock from the backend; they are written out so the whole contract
    #: reads in one place.  F0 is claimed because the package ships a kinematic stand-in, not the JSBSim FDM.
    fidelity = {
        "engine": "jsbgym:JSBSim flight dynamics (C172-HeadingControlTask-Shaping.STANDARD-NoFG-v0)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 selects the seed the next reset records; the default "
                     "HeadingControlTask initial conditions are fixed and the fake's transition is deterministic, "
                     "so the same actions repeat the same trajectory.  The seed does not reproduce a JSBSim run: "
                     "the fake backend is a separate kinematic stand-in and was not compared with JSBSim.",
        },
        "timestep_ms": 200.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is a hand-written kinematic stand-in, not JSBSim: no aerodynamic forces, no "
            "flight-dynamics integration, no contacts and no actuator, sensor or noise model; the upstream "
            "jsbsim.FGFDMExec is never executed, so fidelity level F0 is claimed for what this package deploys",
            "the observation is an 11-number Python list from the stand-in's own equations, not the JSBSim "
            "outputs listed in facts.md, and it was never compared with a JSBSim run",
            "the reward is a placeholder function of the stand-in's altitude and track errors; the upstream "
            "assessors and potential-based shaping rewards are not reproduced",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms only; JSBSim "
            "has an optional set_simulation_time_factor (simulation.py:209-224) that the fake does not implement",
            "timestep_ms 200 is the agent interaction interval: 12 integration steps of 1/60 s each, not the "
            "16.67 ms integration step itself",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
            "the seed is accepted and recorded, but the default HeadingControlTask initial conditions are fixed, "
            "so the seed alone does not change the first observation",
            "the fake has no rendering, no FlightGear output and none of the upstream visualisers",
        ],
    }
