"""OpenMHS driver for gh.isaac-sim/omniisaacgymenvs: the Cartpole vectorised environment (Gymnasium family driver).

OmniIsaacGymEnvs is a reinforcement-learning example suite that runs on Isaac Sim: the simulator is an external
installation (README.md:31-33) and ``VecEnvRLGames`` extends ``VecEnvBase`` from ``omni.isaac.gym``
(omniisaacgymenvs/envs/vec_env_rlgames.py:34-38).  The Hydra task map selects a task by name
(omniisaacgymenvs/utils/task_util.py:97-99); this package serves the ``Cartpole`` task
(omniisaacgymenvs/utils/task_util.py:61).

The Gymnasium family bridge derives the whole ``cap.world.*`` contract from the environment's spaces: for Cartpole a
``Box`` of one action in [-1, 1] (the ``RLTask`` default, rl_task.py:127-131) and a ``Box`` of four observations
(cartpole.py:46-47).  ``cap.world.step.v1`` takes ``{ticks, action: {values: [...]}}``, ``cap.world.reset.v1`` takes
``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated R0: no hardware backend and no
operator-required limit.  The e-stop is the runtime's software latch (no native stop exists), so the safe state is
"the fake stops advancing".

Isaac Sim 4.0.0 and PhysX are not installed where the gate runs and package code never imports the clone, so the
``fake`` backend is the package's own single-environment analytic stand-in (fake.py), never compared with a simulator
run.  No ``sim`` backend is offered: the upstream environment cannot be built by ``gymnasium.make`` and the real
simulator is not part of the clone.  The fidelity contract therefore describes the deployed analytic model as F0, with
gaps naming what is not modelled; it does not claim the upstream PhysX fidelity.

Every Fact cites the clone at commit f8f91bcf73cfd8ede2eab70e19dd70162abf9775.  This package is model-authored and
unreviewed; it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

VEC_ENV = "omniisaacgymenvs/envs/vec_env_rlgames.py"
RL_TASK = "omniisaacgymenvs/tasks/base/rl_task.py"
CARTPOLE = "omniisaacgymenvs/tasks/cartpole.py"
CARTPOLE_CFG = "omniisaacgymenvs/cfg/task/Cartpole.yaml"
TASK_UTIL = "omniisaacgymenvs/utils/task_util.py"


class OmniIsaacGymEnvsCartpole(GymnasiumDriver):
    device_id = "omniisaacgymenvs-cartpole"
    # The Hydra task name (config.yaml:3, task_util.py:61), not a gymnasium-registered id; the fake is passed to the
    # bridge directly, so gymnasium.make is never called.
    env_id = "Cartpole"
    native = "omniisaacgymenvs.envs.vec_env_rlgames:VecEnvRLGames"
    backends = {"fake": ".fake:FakeVecEnvRLGames"}
    action_space_ref = f"{RL_TASK}:129-131"
    # VecEnvRLGames resets the environments that report a reset on the next pre_physics_step (vec_env_rlgames.py:79,
    # cartpole.py:112-114), so the bridge may continue after a terminal state (the upstream's automatic reset).
    autoreset = True
    display_name = "OmniIsaacGymEnvs Cartpole (Isaac Sim 4.0 vectorised RL environment)"
    vendor, model = "NVIDIA", "OmniIsaacGymEnvs 4.0.0 Cartpole"
    tags = ["isaac-sim", "omniisaacgymenvs", "cartpole", "reinforcement-learning", "simulation", "vectorized"]
    facts = [
        Fact("The repository contains reinforcement-learning examples that run with Isaac Sim and are built on "
             "omni.isaac.core and omni.isaac.gym", source="vendor_doc", ref="README.md:9"),
        Fact("The examples rely on the latest Isaac Sim release and pin it to 4.0.0, installed separately",
             source="vendor_doc", ref="README.md:31-33"),
        Fact("VecEnvRLGames extends VecEnvBase, imported from omni.isaac.gym.vec_env, so its simulator and base "
             "interface come from outside the clone", source="upstream_code", ref=f"{VEC_ENV}:34-38"),
        Fact("VecEnvRLGames.step takes an actions tensor and returns four values: an observation dict, rewards, "
             "resets and extras", source="upstream_code", ref=f"{VEC_ENV}:52-104"),
        Fact("VecEnvRLGames.reset takes seed and options, resets the task, applies one zero action and returns the "
             "observation dict; its body does not read seed or options", source="upstream_code",
             ref=f"{VEC_ENV}:106-115"),
        Fact("The observation dict carries the observations under obs and the task states under states",
             source="upstream_code", ref=f"{VEC_ENV}:102"),
        Fact("The observations are clamped to +-clipObservations in the wrapper", source="upstream_code",
             ref=f"{VEC_ENV}:39-40"),
        Fact("The actions are clamped to +-clipActions before the task sees them", source="upstream_code",
             ref=f"{VEC_ENV}:77"),
        Fact("Cartpole sets clipActions to 1.0, clipObservations to 5.0, resetDist to 3.0 and maxEffort to 400.0",
             source="upstream_code", ref=f"{CARTPOLE_CFG}:10-14"),
        Fact("RLTask initializes a task's action space to a Box of -1 to 1 per action dimension and its observation "
             "space to a Box of -inf to inf per observation dimension unless the task sets its own",
             source="upstream_code", ref=f"{RL_TASK}:127-136"),
        Fact("CartpoleTask declares four observations and one action", source="upstream_code",
             ref=f"{CARTPOLE}:46-47"),
        Fact("The Cartpole observation is [cart position, cart velocity, pole position, pole velocity]",
             source="upstream_code", ref=f"{CARTPOLE}:91-103"),
        Fact("The Cartpole action is a force on the cart: maxEffort times the first action component",
             source="upstream_code", ref=f"{CARTPOLE}:118-119"),
        Fact("A Cartpole reset samples the cart position in [-1, 1], the pole position in [-0.125 pi, 0.125 pi], "
             "the cart velocity in [-0.5, 0.5] and the pole velocity in [-0.25 pi, 0.25 pi]",
             source="upstream_code", ref=f"{CARTPOLE}:127-135"),
        Fact("The Cartpole reward is 1 - pole_pos^2 - 0.01*|cart_vel| - 0.005*|pole_vel|, replaced by -2 when "
             "|cart_pos| > resetDist or |pole_pos| > pi/2", source="upstream_code", ref=f"{CARTPOLE}:153-156"),
        Fact("Cartpole flags a reset when |cart_pos| > resetDist, |pole_pos| > pi/2, or the progress reaches the "
             "episode length", source="upstream_code", ref=f"{CARTPOLE}:160-163"),
        Fact("The Cartpole episode length is 500 steps", source="upstream_code", ref=f"{CARTPOLE}:44"),
        Fact("Cartpole sets controlFrequencyInv to 2 (about 60 Hz) and the physics dt to 0.0083 s (1/120 s)",
             source="upstream_code", ref=f"{CARTPOLE_CFG}:15-18"),
        Fact("Cartpole defaults to 512 environments", source="upstream_code", ref=f"{CARTPOLE_CFG}:8"),
        Fact("The Hydra task map maps the name Cartpole to CartpoleTask", source="upstream_code",
             ref=f"{TASK_UTIL}:55-61"),
        Fact("initialize_task instantiates task_map[cfg['task_name']]", source="upstream_code",
             ref=f"{TASK_UTIL}:97-99"),
        Fact("The training script constructs VecEnvRLGames with headless, sim_device, livestream, viewport and "
             "experience arguments", source="upstream_code",
             ref="omniisaacgymenvs/scripts/rlgames_train.py:105-111"),
        Fact("The install_requires list is numpy, protobuf, omegaconf, hydra-core, urllib3, rl-games, moviepy and "
             "gymnasium 0.28.1", source="upstream_code", ref="setup.py:41-50"),
    ]
    safe_state = ("the fake stops advancing: the runtime's e-stop latch refuses every step, reset and seed until "
                  "mhs.safety.reset, and the last observation, tick and episode stay readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity FID-002).  It describes the analytic fake,
    #: not Isaac Sim's PhysX: level F0 says no dynamics are claimed, and every gap names what is missing.
    fidelity = {
        "engine": "analytic:omniisaacgymenvs Cartpole stand-in (Isaac Sim 4.0 target)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake reseeds Python's random.Random from reset(seed) or cap.world.seed.v1 and its step is "
                     "deterministic, so one seed repeats a trajectory; the upstream reset accepts but ignores seed "
                     "(vec_env_rlgames.py:106-115) and draws resets with torch's generator, so a seed does not repeat "
                     "an upstream run",
        },
        "timestep_ms": 16.6,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "analytic stand-in with no rigid-body dynamics, contacts, friction, actuator, sensor or noise model: the "
            "action sets two placeholder velocities, so this is F0 and its trajectories are not Isaac Sim's",
            "Isaac Sim 4.0.0 and PhysX are external (README.md:31-33) and were never opened here; no sim backend is "
            "offered, only the package fake",
            "the upstream is vectorised over num_envs (512 by default, Cartpole.yaml:8) and returns per-environment "
            "reward and reset tensors plus an obs/states dict (vec_env_rlgames.py:102-104); this package serves one "
            "environment, so reward and done are scalars and the observation is a four-vector",
            "reset differs: VecEnvRLGames applies one zero action after task.reset and ignores seed/options "
            "(vec_env_rlgames.py:106-115); the fake seeds its own random generator and returns the initial state "
            "without that extra step",
            "no rendering, viewport recording, cameras, domain randomisation or task states are modelled; snapshots "
            "are not offered because the environment exposes no get_state/set_state",
            "the fake was never compared with an Isaac Sim run and no hardware or real-simulator evidence exists",
        ],
    }
