"""OpenMHS driver for gh.learnsyslab/crazyflow: the DroneReachPos-v0 Gymnasium vector environment.

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives the
contract from the environment's spaces.  ``DroneReachPos-v0`` is registered with ``vector_entry_point=ReachPosEnv``
(``crazyflow/envs/__init__.py:11``), so the served environment is one world of that vector environment.  The default
``attitude`` action is a four-element ``Box`` ``[roll_rad, pitch_rad, yaw_rad, thrust_N]`` bounded by +-pi/2 for the
three attitudes and by ``4*thrust_min`` .. ``4*thrust_max`` for the collective thrust
(``crazyflow/envs/drone_env.py:35-41``); the observation is a ``Dict`` of ``pos`` (3), ``quat`` (4), ``vel`` (3),
``ang_vel`` (3) and ``difference_to_goal`` (3) (``crazyflow/envs/drone_env.py:112-120``,
``crazyflow/envs/reach_pos_env.py:48-51``).  The episode terminates when the drone's z position is below zero and
truncates at ``max_episode_time`` (10 s by default) (``crazyflow/envs/drone_env.py:66,190-196``).

The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no operator-required
limit.  The gate does not install JAX, MuJoCo or the clone, and package code never imports the clone, so the ``fake``
backend is this package's own pure Python stand-in for one world (``fake.py``).  The ``sim`` backend that
``GymnasiumDriver.open_native`` would serve with ``gymnasium.make(env_id)`` is not available here: the environment is
registered as a vector entry point, and the upstream dependencies were not installed or run.  This package is
model-authored and unreviewed; it is checked on the fake backend only.

The ``fidelity`` attribute is the contract of the model as deployed.  It is F0 because the fake is a single-world
kinematic stand-in, not the batched JAX/MuJoCo simulator, and its ``gaps`` say what it does not reproduce.  Every
fact cites a line of the clone at the pinned commit 70d09e455859580c45b0e4a06ee4a92efbbc2d6f.
"""

from mhs.driver import Fact, GymnasiumDriver


class DroneReachPos(GymnasiumDriver):
    device_id = "crazyflow-drone-reach-pos"
    env_id = "DroneReachPos-v0"
    native = "crazyflow.envs.reach_pos_env:ReachPosEnv"
    backends = {"fake": ".fake:FakeReachPosEnv"}
    display_name = "Crazyflow DroneReachPos-v0 (JAX drone simulation)"
    vendor, model = "LearnSysLab", "Crazyflow DroneReachPos-v0"
    tags = ["crazyflow", "drone", "quadrotor", "reach-position", "reinforcement-learning", "simulation",
            "gymnasium", "jax", "mujoco"]
    facts = [
        Fact("DroneReachPos-v0 is registered with vector_entry_point=ReachPosEnv",
             source="upstream_code", ref="crazyflow/envs/__init__.py:11"),
        Fact("DroneEnv is a gymnasium.vector.VectorEnv and declares autoreset_mode NEXT_STEP",
             source="upstream_code", ref="crazyflow/envs/drone_env.py:48-60"),
        Fact("The number of worlds defaults to 1",
             source="upstream_code", ref="crazyflow/envs/reach_pos_env.py:26"),
        Fact("The action space is batched over the number of worlds",
             source="upstream_code", ref="crazyflow/envs/drone_env.py:110-111"),
        Fact("The fitted so_rpy command interface is [roll_rad, pitch_rad, yaw_rad, thrust_N]",
             source="upstream_code", ref="crazyflow/dynamics/so_rpy/dynamics.py:8"),
        Fact("With attitude control the action space is a Box whose roll, pitch and yaw bounds are +-pi/2 and whose "
             "collective thrust bounds are 4*thrust_min and 4*thrust_max",
             source="upstream_code", ref="crazyflow/envs/drone_env.py:35-41"),
        Fact("The default drone of DroneEnv is cf2x_L250",
             source="upstream_code", ref="crazyflow/envs/drone_env.py:68"),
        Fact("For cf2x_L250 the per-motor thrust bounds are 0.012817578393224994 N and 0.12 N",
             source="upstream_code", ref="crazyflow/dynamics/so_rpy/params.toml:28-29"),
        Fact("The cf2x_L250 mass is 0.0328 kg, acc_coef is 0.0 and cmd_f_coef is 1.023224599403443",
             source="upstream_code", ref="crazyflow/dynamics/so_rpy/params.toml:22-31"),
        Fact("The gravity vector is [0, 0, -9.81] m/s^2",
             source="upstream_code", ref="crazyflow/dynamics/params.toml:3"),
        Fact("The observation space is a Dict of pos (3), quat (4), vel (3) and ang_vel (3), batched by world",
             source="upstream_code", ref="crazyflow/envs/drone_env.py:112-120"),
        Fact("ReachPosEnv adds difference_to_goal (3) to the observation Dict",
             source="upstream_code", ref="crazyflow/envs/reach_pos_env.py:48-51"),
        Fact("DroneEnv.reset(seed) seeds the simulation, resets it and returns the observation and an empty info",
             source="upstream_code", ref="crazyflow/envs/drone_env.py:157-165"),
        Fact("ReachPosEnv samples the goal before resetting the simulation; the options goal_pos_min and goal_pos_max "
             "override the goal bounds",
             source="upstream_code", ref="crazyflow/envs/reach_pos_env.py:54-60"),
        Fact("The default goal box is [-1, -1, 0.5] to [1, 1, 1.5]",
             source="upstream_code", ref="crazyflow/envs/reach_pos_env.py:94-96"),
        Fact("The reset position box defaults to [-1, -1, 1] to [1, 1, 2] and the velocity box to -1 to 1 m/s",
             source="upstream_code", ref="crazyflow/envs/reach_pos_env.py:24-35"),
        Fact("The reset randomization draws positions and velocities uniformly from those boxes",
             source="upstream_code", ref="crazyflow/envs/reach_pos_env.py:108-109"),
        Fact("DroneEnv.step applies the action, advances the simulation by n_substeps, resets the worlds marked done "
             "and returns observation, reward, terminated, truncated and an empty info",
             source="upstream_code", ref="crazyflow/envs/drone_env.py:122-129"),
        Fact("The episode terminates when the drone z position is below zero",
             source="upstream_code", ref="crazyflow/envs/drone_env.py:190-191"),
        Fact("The episode truncates when the simulation time reaches max_episode_time",
             source="upstream_code", ref="crazyflow/envs/drone_env.py:195-196"),
        Fact("max_episode_time defaults to 10.0 s",
             source="upstream_code", ref="crazyflow/envs/drone_env.py:66"),
        Fact("The ReachPos reward is exp(-2 * distance) and -1 when the episode terminated",
             source="upstream_code", ref="crazyflow/envs/reach_pos_env.py:83-87"),
        Fact("The environment frequency defaults to 500 Hz",
             source="upstream_code", ref="crazyflow/envs/drone_env.py:69"),
        Fact("The simulation frequency defaults to 500 Hz",
             source="upstream_code", ref="crazyflow/sim/sim.py:87"),
        Fact("n_substeps is sim.freq // freq",
             source="upstream_code", ref="crazyflow/envs/drone_env.py:106"),
        Fact("The MuJoCo timestep is 1 / freq",
             source="upstream_code", ref="crazyflow/sim/sim.py:293"),
        Fact("The attitude action is clipped to the action space bounds before it is applied",
             source="upstream_code", ref="crazyflow/envs/drone_env.py:132-150"),
        Fact("The default simulation state has an identity quaternion [0, 0, 0, 1] and zero position, velocity and "
             "angular velocity",
             source="upstream_code", ref="crazyflow/sim/data.py:44-52"),
        Fact("seed sets the JAX rng key of the simulation",
             source="upstream_code", ref="crazyflow/sim/sim.py:276-282"),
    ]
    autoreset = True
    safe_state = ("the simulation stops advancing: no step, reset or seed is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "crazyflow:DroneReachPos-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the initial position, velocity and goal of one world, "
                     "and the fake dynamics are deterministic, so one implementation repeats a trajectory for the "
                     "same seed and actions; this package's fake draws with Python's random.Random and upstream "
                     "draws with JAX's generator, so a seed gives different trajectories on the two",
        },
        "timestep_ms": 2.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "one world of a batched vector environment: the upstream spaces carry a leading world dimension and "
            "the fake keeps that dimension but contains one world and one drone",
            "the fake follows the commanded roll, pitch and yaw directly and leaves angular velocity at zero; the "
            "fitted second-order rotational dynamics, rotor dynamics and collisions are not modelled",
            "the translational part is the ideal so_rpy thrust/gravity model with the cf2x_L250 parameters, but the "
            "fake was never compared with a JAX/MuJoCo run and no physical device is modelled",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms (2 ms) only",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
            "the sim backend (gymnasium.make on the vector_entry_point) was not run",
        ],
    }
