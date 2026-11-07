"""OpenMHS driver for gh.andykofman/flightmare-reinforcement-learning: the FlightEnvVec world.

The card names ``RosDriver`` and a ``family:ros`` route, but the card's own
confirmed entry symbol is
``flightrl_v2.flightrl_v2.envs.flight_env_vec:FlightEnvVec``
(flightrl_v2/flightrl_v2/envs/flight_env_vec.py:20), a Gymnasium-compatible
wrapper around the compiled ``flightgym`` vector environment.  The repository
also contains ``flightros`` nodes, but the RL environment is the primary
step/reset interface of this card, and a Gymnasium environment does not become
a ROS transport driver because the same repository has ROS nodes.  The SDK
``GymnasiumDriver`` therefore matches the runtime; the deviation from the card
is recorded in RESULT.json.

``FlightEnvVec`` is vectorized but its Python ``reset`` and ``step`` already
return the first environment's observation and scalar reward
(flight_env_vec.py:110-113 and :180-186), so the stock Gymnasium bridge serves
it without a package adapter.  The fake backend preserves that native scalar
surface before adaptation.

Scope: the ``QuadrotorEnv_v1`` binding (pybind_wrapper.cpp:16-33) with 12
observation values and 4 normalized actions.  The real backend needs a built
``flightgym`` and ``FLIGHTMARE_PATH`` (flightrl_v2/README.md:84-91); it was not
imported, built or run here.  This package is simulated R0, model-authored and
unreviewed, and is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "flightrl_v2/flightrl_v2/envs/flight_env_vec.py"
WRAPPER = "flightlib/src/wrapper/pybind_wrapper.cpp"
QUAD_ENV = "flightlib/src/envs/quadrotor_env/quadrotor_env.cpp"
QUAD_HPP = "flightlib/include/flightlib/envs/quadrotor_env/quadrotor_env.hpp"
QUAD_CFG = "flightlib/configs/quadrotor_env.yaml"
VEC_ENV = "flightlib/src/envs/vec_env.cpp"
README_V2 = "flightrl_v2/README.md"
ENV_BASE = "flightlib/include/flightlib/envs/env_base.hpp"
VEC_CFG = "flightlib/configs/vec_env.yaml"
GYM_WRAPPER = "flightrl_v2/flightrl_v2/envs/gymnasium_wrapper.py"


class FlightmareFlightEnvVec(GymnasiumDriver):
    device_id = "flightmare-vec"
    device_kind = "world.sim"
    mode, risk = "simulated", "R0"
    #: The upstream class is constructed by make_flight_env from a compiled
    #: flightgym backend; no registered Gymnasium id exists in the clone.
    env_id = None
    native = "flightrl_v2.flightrl_v2.envs.flight_env_vec:FlightEnvVec"
    backends = {"fake": ".fake:FakeFlightEnvVec"}
    action_space_ref = f"{ENV}:53-58"
    display_name = "Flightmare FlightEnvVec (QuadrotorEnv_v1 simulation)"
    vendor, model = "andykofman", "Flightmare FlightEnvVec"
    tags = ["flightmare", "flightgym", "quadrotor", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("FlightEnvVec is a Gymnasium-compatible wrapper around the C++ flightgym environments and their "
             "vectorized interface", source="upstream_code", ref=f"{ENV}:20-26"),
        Fact("FlightEnvVec reads num_envs from impl.getNumOfEnvs(), num_obs from getObsDim() and num_acts from "
             "getActDim()", source="upstream_code", ref=f"{ENV}:37-42"),
        Fact("The observation space is a Box with low=-inf, high=inf, shape=(num_obs,), dtype float32",
             source="upstream_code", ref=f"{ENV}:46-51"),
        Fact("The action space is a Box normalized to [-1, 1] with one value per action dimension, dtype float32",
             source="upstream_code", ref=f"{ENV}:53-58"),
        Fact("seed(seed) calls the base seed and, when the seed is not None, wrapper.setSeed(seed)",
             source="upstream_code", ref=f"{ENV}:77-81"),
        Fact("reset(seed, options) reseeds when a seed is given, clears the episode buffers, calls "
             "wrapper.reset(self._observation) and returns the first environment's observation and an empty info "
             "dict", source="upstream_code", ref=f"{ENV}:101-113"),
        Fact("step reshapes a one-dimensional action to (1, -1), calls wrapper.step with the observation, reward, "
             "done and extra-info buffers without checking its return value, and returns the first environment's "
             "observation, scalar reward, done[0] as terminated, a truncation flag and info",
             source="upstream_code", ref=f"{ENV}:131-186"),
        Fact("VecEnv::step logs an error and returns false without stepping when the action, observation, reward, "
             "done or extra-info dimensions do not match num_envs and the environment dimensions",
             source="upstream_code", ref=f"{VEC_ENV}:79-92"),
        Fact("The shipped vec_env.yaml sets num_envs: 100 and num_threads: 10", source="upstream_code",
             ref=f"{VEC_CFG}:4-5"),
        Fact("make_flight_env_for_sb3 calls make_flight_env with num_envs=1 and num_threads=1",
             source="upstream_code", ref=f"{GYM_WRAPPER}:174-183"),
        Fact("VecEnv::init reads render, seed, num_envs and scene_id, sets the OpenMP thread count with "
             "omp_set_num_threads and calls setUnity(render)", source="upstream_code", ref=f"{VEC_ENV}:31-48"),
        Fact("FlightEnvVecSB3 steps the whole backend with a zero action in every row other than env_index and "
             "returns that row", source="upstream_code", ref=f"{ENV}:318-337"),
        Fact("truncated is true when the first environment's episode length reaches max_episode_steps",
             source="upstream_code", ref=f"{ENV}:164"),
        Fact("close calls wrapper.close() when the wrapper exists", source="upstream_code", ref=f"{ENV}:193-196"),
        Fact("The pybind module binds VecEnv<QuadrotorEnv> as QuadrotorEnv_v1 with reset, step, setSeed, close, "
             "getNumOfEnvs, getObsDim, getActDim and getExtraInfoNames", source="upstream_code",
             ref=f"{WRAPPER}:16-33"),
        Fact("The bound QuadrotorEnv reports kNObs=12 and kNAct=4", source="upstream_code",
             ref=f"{QUAD_HPP}:36-39"),
        Fact("getObs converts the attitude with toRotationMatrix().eulerAngles(2, 1, 0) and writes position, those "
             "three angles, linear velocity and angular velocity into the observation",
             source="upstream_code", ref=f"{QUAD_ENV}:119-128"),
        Fact("step sets the four thrust commands to the normalized action times act_std plus act_mean and runs "
             "the quadrotor for sim_dt", source="upstream_code", ref=f"{QUAD_ENV}:131-137"),
        Fact("act_mean is -mass * Gz / 4 and act_std is -mass * 2 * Gz / 4 in each of the kNAct entries",
             source="upstream_code", ref=f"{QUAD_ENV}:38-40"),
        Fact("QuadrotorEnv loads sim_dt from quadrotor_env.sim_dt", source="upstream_code",
             ref=f"{QUAD_ENV}:207-210"),
        Fact("The shipped quadrotor_env.yaml sets quadrotor_env sim_dt: 0.02", source="upstream_code",
             ref=f"{QUAD_CFG}:1-3"),
        Fact("The episode terminates when the z position is at or below 0.05, with a terminal reward of -10",
             source="upstream_code", ref=f"{QUAD_ENV}:198-202"),
        Fact("The reward combines weighted position, orientation, linear-velocity and angular-velocity errors and "
             "an action penalty, adds a 0.01 survival reward, and adds 1.0 when the position is within 0.1 of "
             "the goal and the speed is below 0.1", source="upstream_code", ref=f"{QUAD_ENV}:159-195"),
        Fact("A random reset zeroes the state, sets x, y and the three velocities to uniform_dist_(random_gen_) "
             "draws, z to a draw plus 5 (mirrored when negative), the quaternion w to 1 and x, y and z to draws "
             "times 0.087, and normalizes the quaternion", source="upstream_code", ref=f"{QUAD_ENV}:83-105"),
        Fact("EnvBase::setSeed only calls std::srand(seed)", source="upstream_code", ref=f"{ENV_BASE}:39"),
        Fact("EnvBase's uniform_dist_ is uniform on [-1.0, 1.0] and random_gen_ is an std::mt19937 seeded from "
             "std::random_device", source="upstream_code", ref=f"{ENV_BASE}:60-62"),
        Fact("The vectorized per-agent step resets a terminal environment inside the same step and adds the "
             "terminal reward", source="upstream_code", ref=f"{VEC_ENV}:144-162"),
        Fact("The flightrl_v2 README requires the C++ physics engine flightgym to be built and installed",
             source="vendor_doc", ref=f"{README_V2}:84-91"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the last observation and tick stay readable")
    #: The contract of the model as deployed on the checked fake backend.  The
    #: upstream real backend is a compiled rigid-body simulator, not installed
    #: or run here; the fake is an analytic stand-in (F0).
    fidelity = {
        "engine": "analytic:Flightmare FlightEnvVec stand-in (no flightgym)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) reseeds the fake's Python random generator and repeats the same start state and "
                     "trajectory; upstream EnvBase::setSeed only calls std::srand while the reset draws from an "
                     "mt19937 seeded from std::random_device (env_base.hpp:39, 60-62), so a live backend would "
                     "not repeat a start state for a seed and no upstream determinism is claimed",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is an analytic kinematic stand-in, not Flightmare: it has no flightgym binding, no "
            "quadrotor rigid-body dynamics, motor model, integrator, contacts, sensors, Unity rendering or scene, "
            "and its gains are placeholders",
            "the upstream real path requires the flightgym C++ extension and FLIGHTMARE_PATH "
            "(flightrl_v2/README.md:84-91); neither was built, imported or run where the gate ran",
            "the fake models one environment row; FlightEnvVec reshapes a single action to one row and ignores "
            "the false return of VecEnv::step on a dimension mismatch, so a backend built with num_envs other "
            "than 1 (the shipped vec_env.yaml says 100; make_flight_env_for_sb3 forces 1) would silently never "
            "step and keep returning the last observation",
            "the native seed does not reach the reset: EnvBase::setSeed only calls std::srand, while resets draw "
            "from an mt19937 seeded from std::random_device, so cap.world.seed and reset(seed) cannot repeat a "
            "live start state; the fake's seeded repeat is fake behaviour",
            "the three angles come from Eigen's eulerAngles(2, 1, 0) (z, y, x order; Eigen returns the first "
            "angle in [0, pi], so the triple can jump near zero yaw); the fake's angle triple is a placeholder "
            "that reproduces neither the order nor the range",
            "live construction (not declared here) needs FLIGHTMARE_PATH and a built flightgym, sets the "
            "process-wide OpenMP thread count (vec_env.cpp:39) and, with render enabled, creates the Unity bridge "
            "singleton; the repository's ArduPilot deployment classes are NotImplementedError placeholders",
            "the 12-value observation layout and the reward/termination rules copy the bound QuadrotorEnv_v1 "
            "source, but the state trajectory and the seeded start sequence are stand-ins",
            "one cap.world.step.v1 tick advances the fake by one 20 ms sample; the real C++ environment can be "
            "configured with another sim_dt and is not validated here",
            "no wall-clock pacing: realtime_factor 0 and only step or reset advances the fake",
            "snapshot and restore are not offered: FlightEnvVec defines no get_state or set_state",
        ],
    }
