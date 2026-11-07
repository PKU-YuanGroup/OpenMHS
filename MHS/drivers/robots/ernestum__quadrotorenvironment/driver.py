"""OpenMHS driver for gh.ernestum/quadrotorenvironment: the QuadrotorEnvironment simulator (a Gymnasium family driver).

``quadrotor_environment.quadrotor_environment:QuadrotorEnvironment`` is a legacy Gym environment that simulates a
quadrotor with an explicit model, delays, noise, state clipping and a configurable observation/reward pipeline
(``quadrotor_environment/quadrotor_environment.py:26-40``).  A ``GymnasiumDriver`` is configuration only: the bridge
derives the contract from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action
``{values}`` bounded by ``Box(-1, 1, (4,))`` (four command values in [-1, 1]); ``cap.world.reset.v1`` takes
``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0): there is no hardware
backend, no e-stop path to a machine and no operator-required limit.

The environment is not registered with ``gymnasium.make``, so ``env_id`` stays ``None`` and no ``sim`` backend opens
the upstream package.  The gate cannot import the clone (no ``gym``, numpy or numpy-quaternion where it runs), so the
``fake`` backend is this package's pure Python ``QuadrotorModel``/``ToObservationMap``/``RewardFunction``
(``fake.py``).  That upstream path was not run here (README.md).

The ``fidelity`` attribute is the fidelity contract of the model as deployed (spec 05-fidelity FID-002).  Every
constant and rule cites a line of the clone at the pinned commit 597f8e3294c6a5d3ffc6907749f94a97dee700f3.  This
package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENVIRONMENT = "quadrotor_environment/quadrotor_environment.py"
MODEL = "quadrotor_environment/quadrotor_model.py"
PROPELLER = "quadrotor_environment/propeller_speed_mapping.py"
DELAY = "quadrotor_environment/model_delay_wrapper.py"
OBSERVATION = "quadrotor_environment/observation_mapping.py"
REWARD = "quadrotor_environment/reward_function.py"
CLIPPING = "quadrotor_environment/model_state_clipping_wrapper.py"
NOISE = "quadrotor_environment/noise_model.py"
SPR = "quadrotor_environment/simulation_parameter_randomization.py"


class Quadrotor(GymnasiumDriver):
    device_id = "quadrotor"
    #: The upstream environment is a legacy Gym class, not a registered gymnasium id: there is no gymnasium.make()
    #: path, so no ``sim`` backend is declared and env_id stays unset.
    env_id = None
    native = "quadrotor_environment.quadrotor_environment:QuadrotorEnvironment"
    backends = {"fake": ".fake:FakeQuadrotorEnvironment"}
    display_name = "QuadrotorEnvironment quadrotor simulator"
    vendor, model = "Maximilian Ernestus", "QuadrotorEnvironment"
    tags = ["quadrotor", "drone", "reinforcement-learning", "simulation", "gym"]
    facts = [
        Fact("QuadrotorEnvironment is a Gym environment that simulates a quadrotor; it is not a hardware "
             "interface", source="upstream_code", ref=f"{ENVIRONMENT}:26-28"),
        Fact("The action space is Box(-1, 1, (4,), dtype float32): four continuous command values in [-1, 1]",
             source="upstream_code", ref=f"{ENVIRONMENT}:132"),
        Fact("step() returns (observation, reward, done, {}) and done is delayed_model.time >= max_time",
             source="upstream_code", ref=f"{ENVIRONMENT}:178"),
        Fact("The max_time constructor default is 10 seconds and the controller_period default is 0.01 seconds",
             source="upstream_code", ref=f"{ENVIRONMENT}:58"),
        Fact("The default initial state parameters are box_side_length 2, velocity 1 and angular_velocity 1",
             source="upstream_code", ref=f"{ENVIRONMENT}:57"),
        Fact("random_state draws the position uniformly from [-box_side_length, box_side_length], the velocity "
             "and angular velocity uniformly from their bounds, a random rotation, and sets all four propeller "
             "speeds to the hovering speed", source="upstream_code", ref=f"{ENVIRONMENT}:187-194"),
        Fact("QuadrotorEnvironment.step computes the reward from the current state before advancing the model when "
             "reward_base is 'current_state' (the default)", source="upstream_code",
             ref=f"{ENVIRONMENT}:151-153"),
        Fact("The SPRWrappedQuadrotorEnvironment is a second Gym wrapper around the same environment that may "
             "replace a value with a ('randomize', low, high) triple on each reset", source="upstream_code",
             ref=f"{SPR}:30-38"),
        Fact("QuadrotorModel defaults: gravity 9.80665 m/s^2, mass 1.43805 kg, moments of inertia "
             "(0.01467, 0.01441, 0.02441), propeller half side length 0.16 m, thrust coefficient 1.018841e-5, "
             "propeller inertia coefficient 6.32180911740998e-09 and drag coefficient 4.82e-8",
             source="upstream_code", ref=f"{MODEL}:41-48"),
        Fact("The hovering speed is sqrt((mass * gravity / thrust coefficient) / 4)", source="upstream_code",
             ref=f"{MODEL}:74"),
        Fact("QuadrotorModel is an explicit model that does not rely on euler or RK-4 integration",
             source="upstream_code", ref=f"{MODEL}:34-37"),
        Fact("The mixer matrix M maps the squared propeller speeds to three moments and the collective thrust",
             source="upstream_code", ref=f"{MODEL}:65-68"),
        Fact("The next propeller speed follows next_prop_rate = x.propeller_speed - (ip ** h - 1) * "
             "(u - x.propeller_speed)", source="upstream_code", ref=f"{MODEL}:85-86"),
        Fact("next_state computes the next position, velocity, rotation and angular velocity for an explicit step "
             "of h seconds", source="upstream_code", ref=f"{MODEL}:76-109"),
        Fact("PropellerSpeedMapping defaults: relative_min_speed 0, relative_max_speed 3, an infinite relative "
             "propeller acceleration bound, clip acceleration constraint and direct output control",
             source="upstream_code", ref=f"{PROPELLER}:13-15"),
        Fact("In direct output mode the action element a sets the relative target speed to "
             "(a + 1) / 2 * (relative_max_speed - relative_min_speed) + relative_min_speed",
             source="upstream_code", ref=f"{PROPELLER}:49-52"),
        Fact("ModelDelayWrapper defaults: delay_scale 1, controller_period 0.01 seconds and no observation, "
             "action or controller delay or jitter", source="upstream_code", ref=f"{DELAY}:16-23"),
        Fact("ModelDelayWrapper.step advances the simulated time by the sampled controller period",
             source="upstream_code", ref=f"{DELAY}:134-135"),
        Fact("StateClippingWrapper defaults clip velocity to [-5, 5] and angular velocity to [-20, 20] and leave "
             "the position unbounded", source="upstream_code", ref=f"{CLIPPING}:13-16"),
        Fact("ToObservationMap defaults scale position by 0.5, velocity by 0.5 and angular velocity by 0.15, set "
             "the propeller speed, dt and observation-age scales to 0, and observe the rotation",
             source="upstream_code", ref=f"{OBSERVATION}:22-25"),
        Fact("The rotmat_global rotation observation mode returns the rotation matrix flattened row-major",
             source="upstream_code", ref=f"{OBSERVATION}:73-74"),
        Fact("A zero scale removes that state component from the observation", source="upstream_code",
             ref=f"{OBSERVATION}:100-120"),
        Fact("The observation concatenates the observed position, velocity, rotation and angular velocity, then "
             "the optional propeller speed, dt and observation age", source="upstream_code",
             ref=f"{OBSERVATION}:139-145"),
        Fact("NoisedStateMap defaults every noise argument to None, so the default observation has no added noise",
             source="upstream_code", ref=f"{NOISE}:24-29"),
        Fact("RewardFunction defaults: reward_scale 0.00076, position weights 9.5 horizontal and 2.2 vertical, "
             "velocity 0.9/1.5, rotation 2/2, angular velocity 2/2, propeller speed deviation 1 and propeller "
             "acceleration 1", source="upstream_code", ref=f"{REWARD}:21-39"),
        Fact("The default reward applies inverted huber scaling to the state terms, sums the propeller speed "
             "deviation and acceleration terms, and returns the negative scaled sum", source="upstream_code",
             ref=f"{REWARD}:121-129"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The fake re-implements the
    #: default model; the bridge derives the engine, determinism and clock, and they are written out so the whole
    #: contract reads in one place.
    fidelity = {
        "engine": "custom:quadrotor_environment",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "This package's fake reseeds its Python random generator from reset(seed) or "
                     "cap.world.seed.v1 and is deterministic from there; the upstream QuadrotorEnvironment.reset "
                     "has no seed argument (quadrotor_environment.py:196-197) and draws its initial state from "
                     "numpy's global generator (quadrotor_environment.py:190-193), so the seeded claim covers the "
                     "fake backend that is actually served, not an unrun upstream path",
        },
        "timestep_ms": 10.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "rigid-body quadrotor dynamics only: no contacts, no collision geometry and no aerodynamic model "
            "beyond the quadratic propeller thrust and drag coefficients of quadrotor_model.py:65-74",
            "the default configuration has no observation noise, delay or jitter (noise_model.py:24-29, "
            "model_delay_wrapper.py:16-23); the fake models the zero-noise, zero-delay defaults only",
            "the fake re-implements the dynamics, the default observation map and the default reward in pure "
            "Python floats with Python's random generator; it was never compared with the upstream environment "
            "(numpy and numpy-quaternion are not installed where the gate runs), so trajectories can differ from "
            "upstream's numpy float64 results and numpy random stream",
            "no wall-clock pacing: realtime_factor 0, one tick advances simulated time by timestep_ms (one "
            "controller period of 0.01 s) only",
            "no physical device is modelled and the model was never validated against one",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
        ],
    }
