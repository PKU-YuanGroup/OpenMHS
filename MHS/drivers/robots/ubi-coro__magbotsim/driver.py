"""OpenMHS driver for gh.ubi-coro/magbotsim: the StateBasedPushBoxEnv-v0 Gymnasium environment.

The package serves one environment of the magbotsim family as a simulated world.  ``env_id`` names the registered
Gymnasium environment and the bridge derives the whole ``cap.world.*`` contract from its action and observation
spaces: ``cap.world.step.v1`` takes ``{ticks, action}`` with ``action.values`` bounded per element by the action
space, ``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` takes ``{seed}``.  The device is
simulated (R0): there is no hardware backend, no e-stop path to a machine and no operator-required limit.

The upstream environment needs Python 3.11 or newer, numpy, MuJoCo and shapely (pyproject.toml:9 and :22-30), and the
gate never imports the clone.  The ``fake`` backend is therefore the package's own pure Python kinematic stand-in for
``StateBasedPushBoxEnv``.  A backend name that ``backends`` does not list (``sim``) is served by
``gymnasium.make(env_id, **env_kwargs)`` (GymnasiumDriver.open_native); that path needs the upstream package and was
not run here.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002):
every member of ``device.schema.json`` that applies to a simulator without a physical counterpart.  Every constant
and rule cites a line of the clone at the pinned commit (694e8582164de71fe58c7ef36c68fd4f2b57e054).  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

GLOBAL_PUSHING = "magbotsim/rl_envs/object_manipulation/pushing/state_based_global_pushing_env.py"
SINGLE_AGENT = "magbotsim/rl_envs/basic_single_agent_env.py"
BASIC = "magbotsim/basic_magbot_env.py"


class MagBotSimPushBox(GymnasiumDriver):
    device_id = "magbotsim-push-box"
    env_id = "StateBasedPushBoxEnv-v0"
    native = ("magbotsim.rl_envs.object_manipulation.pushing.state_based_push_box_env:"
              "StateBasedPushBoxEnv")
    backends = {"fake": ".fake:FakeStateBasedPushBoxEnv"}
    display_name = "MagBotSim state-based push-box environment"
    vendor, model = "ubi-coro", "magbotsim StateBasedPushBoxEnv-v0"
    tags = ["magbotsim", "magnetic-robotics", "reinforcement-learning", "simulation", "gymnasium",
            "push-box"]
    facts = [
        Fact("StateBasedPushBoxEnv-v0 is registered with max_episode_steps=25",
             source="upstream_code", ref="magbotsim/__init__.py:58-62"),
        Fact("The observation space is a Dict with the keys observation, achieved_goal and desired_goal",
             source="upstream_code", ref=f"{GLOBAL_PUSHING}:272-286"),
        Fact("With learn_jerk and learn_mover_c_rotation false, the observation array is num_movers*4 values: "
             "the (x,y) position and (x,y) velocity of each mover",
             source="upstream_code", ref=f"{GLOBAL_PUSHING}:1157-1158"),
        Fact("When learn_pose is false, achieved_goal is the object's (x,y) position (2 values) and desired_goal "
             "the desired (x,y) position (2 values)",
             source="upstream_code", ref=f"{GLOBAL_PUSHING}:1162-1175"),
        Fact("The action space is a Box of num_movers*2 values bounded by -a_max_xy and a_max_xy",
             source="upstream_code", ref=f"{GLOBAL_PUSHING}:288-298"),
        Fact("a_max_xy defaults to 10.0", source="upstream_code", ref=f"{GLOBAL_PUSHING}:129"),
        Fact("max_position_err defaults to 0.05 m and is the position threshold for goal achievement",
             source="upstream_code", ref=f"{GLOBAL_PUSHING}:142"),
        Fact("The per-step penalty is -0.01, the collision penalty -10.0 and the at-goal reward 1.0",
             source="upstream_code", ref=f"{GLOBAL_PUSHING}:144-146"),
        Fact("compute_reward applies the per-step penalty, replaces it with the collision penalty on a collision, "
             "and with the at-goal reward when the goal is reached without a collision",
             source="upstream_code", ref=f"{GLOBAL_PUSHING}:1134-1142"),
        Fact("The episode terminates on a mover collision or a wall collision (or early termination when "
             "configured)", source="upstream_code", ref=f"{GLOBAL_PUSHING}:953"),
        Fact("The environment's compute_truncated always returns False: the time limit is the Gymnasium "
             "TimeLimit wrapper", source="upstream_code", ref=f"{GLOBAL_PUSHING}:955-974"),
        Fact("The default layout is a 4x3 grid of tiles when layout_tiles is None",
             source="upstream_code", ref=f"{GLOBAL_PUSHING}:155-157"),
        Fact("The default number of control cycles applied per step is 40",
             source="upstream_code", ref=f"{GLOBAL_PUSHING}:124"),
        Fact("The default MuJoCo option sets timestep=0.001 s",
             source="upstream_code", ref=f"{BASIC}:1340"),
        Fact("The environment takes cycle_time from model.opt.timestep",
             source="upstream_code", ref=f"{BASIC}:297"),
        Fact("reset(seed) seeds the gymnasium RNG and rng_noise, and passes options to _reset_callback",
             source="upstream_code", ref=f"{SINGLE_AGENT}:134-140"),
        Fact("The reset options mover_xy_start_pos, object_xy_start_pos and object_xy_goal_pos override the "
             "sampled positions", source="upstream_code", ref=f"{GLOBAL_PUSHING}:690-700"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "magbotsim:StateBasedPushBoxEnv-v0",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) fixes the initial positions drawn by the environment and the dynamics are "
                     "deterministic, so one implementation repeats a trajectory for the same seed and actions; "
                     "the upstream environment also draws observation noise from the seed, while this package's "
                     "fake is noise-free, so a seed gives different trajectories on the two",
        },
        "timestep_ms": 40.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "rigid-body magnetic-levitation and contact physics of MuJoCo: no contact solver, friction, "
            "impedance controller, sensor or observation-noise model; the fake uses a kinematic stand-in",
            "no rendering, no MuJoCo viewer and no 2D matplotlib view",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms "
            "(40 control cycles of 0.001 s) only",
            "no physical device is modelled and the model was never validated against one",
            "the fake backend was not compared with the upstream environment (the gate does not import the "
            "clone): trajectories can differ from upstream's numpy random stream and MuJoCo state",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
        ],
    }
