"""OpenMHS driver for gh.ice-mao/rl_auv_tracking: the AUVTracking_v0 target-tracking Gymnasium environment.

The card names the family ``gymnasium`` and the helper ``GymnasiumDriver``.  That matches the runtime: the suite's
concrete environment is ``auv_env.envs.base:TargetTrackingBase``, a ``gym.Env`` whose ``reset`` and ``step`` the
stock Gymnasium bridge serves as ``cap.world.reset.v1`` and ``cap.world.step.v1``.  ``auv_env.make`` is the factory
the README uses, but it only imports the environment, chooses a world and wraps it in ``gym.wrappers.TimeLimit``;
the class itself is the interface.  The clone registers no Gymnasium id (every ``gym.register`` call is commented
out, ``auv_env/__init__.py:125-129``), so ``env_id`` stays unset and the bridge's ``gymnasium.make`` path is not
offered.  The ``sim`` backend would need the upstream factory, HoloOcean, the HoloOcean Ocean packages and the
scenario files copied into the HoloOcean worlds directory; none of them is installed here and package code never
imports the clone.  The gate therefore runs the package's own analytic ``fake`` backend only.

The package covers ``AUVTracking_v0`` with the shipped ``configs/envs/v0_config.yml`` defaults: the state-only
``WorldAuvV0``, the PID controller with the 2-element action Box ``[-1, 1]``, ``num_targets`` 1, the 6-element
state observation and the reward/termination rule of ``WorldAuvV0``.  The other worlds, the 3D variants and the
LQR/KEYBOARD controller configurations are not covered.

The device is a simulated world (R0): there is no hardware backend, no path to a machine and no operator-required
limit.  Every Fact cites a line of the clone at the pinned commit 8ff39512f796801aa461fa074f7972e3a4e3a81f.  The
``fidelity`` attribute describes the analytic fake actually opened by the gate (level F0); the HoloOcean model and
the upstream factory were not run and were not compared with the fake.
"""

from mhs.driver import Fact, GymnasiumDriver

INIT = "auv_env/__init__.py"
BASE = "auv_env/envs/base.py"
V0 = "auv_env/envs/world_auv_v0.py"
V0_CONFIG = "configs/envs/v0_config.yml"
README = "README.md"


class AuvTrackingV0(GymnasiumDriver):
    device_id = "auv-tracking-v0"
    #: The clone registers no Gymnasium environment id (every gym.register call is commented out, INIT:125-129).
    env_id = None
    native = "auv_env.envs.base:TargetTrackingBase"
    backends = {"fake": ".fake:FakeAuvTrackingV0"}
    #: The fake copies the shipped v0 PID action space, so the derived limits cite the lines that write its bounds.
    action_space_ref = f"{V0_CONFIG}:79-81"
    display_name = "AUVTracking_v0 (HoloOcean AUV target tracking)"
    vendor, model = "ice-mao", "AUVTracking_v0"
    tags = ["auv", "underwater", "target-tracking", "reinforcement-learning", "holoocean", "simulation",
            "gymnasium"]
    facts = [
        Fact("TargetTrackingBase is the Gymnasium environment class and derives from gym.Env",
             source="upstream_code", ref=f"{BASE}:27"),
        Fact("TargetTrackingBase constructs the world from the world class, map and viewport flag, stores the "
             "config, and takes its action and observation spaces from the world", source="upstream_code",
             ref=f"{BASE}:32-44"),
        Fact("auv_env.make builds TargetTrackingBase(world_class, map_name, show_viewport, config, **kwargs)",
             source="upstream_code", ref=f"{INIT}:51"),
        Fact("The make factory's t_steps parameter defaults to 100", source="upstream_code", ref=f"{INIT}:11"),
        Fact("auv_env.make wraps the environment in gym.wrappers.TimeLimit(max_episode_steps=t_steps)",
             source="upstream_code", ref=f"{INIT}:53"),
        Fact("AUVTracking_v0 selects WorldAuvV0, the SimpleUnderwater-Bluerov2 map and ../configs/envs/v0_config.yml",
             source="upstream_code", ref=f"{INIT}:31"),
        Fact("The v1-state gym.register block is commented out", source="upstream_code", ref=f"{INIT}:125-129"),
        Fact("When no config is passed, make loads the cwd-relative default by config_loader.load_config",
             source="upstream_code", ref=f"{INIT}:44-46"),
        Fact("WorldAuvV0 is the state-only world", source="upstream_code", ref=f"{V0}:20-23"),
        Fact("WorldBase creates the scene with holoocean.make(self.map, show_viewport=show)",
             source="upstream_code", ref=f"{BASE}:73"),
        Fact("WorldBase derives the sampling period as 1/scenario['ticks_per_sec'] from the HoloOcean scenario",
             source="upstream_code", ref=f"{BASE}:78"),
        Fact("WorldBase computes ticks_per_rl_step from the controller frequency and the sampling period",
             source="upstream_code", ref=f"{BASE}:110-118"),
        Fact("TargetTrackingBase.reset calls np.random.seed() with no argument before delegating to world.reset",
             source="upstream_code", ref=f"{BASE}:46-51"),
        Fact("WorldAuvV0.reset clears its reward and action queues before calling WorldBase.reset",
             source="upstream_code", ref=f"{V0}:30-33"),
        Fact("get_init_pose_random calls np.random.seed() with no argument inside its outer initial-pose sampling "
             "loop", source="upstream_code", ref=f"{BASE}:461-466"),
        Fact("TargetTrackingBase.step delegates to world.step(action=action)",
             source="upstream_code", ref=f"{BASE}:53-60"),
        Fact("WorldBase.step loops over ticks_per_rl_step iterations", source="upstream_code", ref=f"{BASE}:181"),
        Fact("WorldBase.step calls self.ocean.tick()", source="upstream_code",
             ref=f"{BASE}:237"),
        Fact("WorldBase.step returns (state, reward, done, 0, info)",
             source="upstream_code", ref=f"{BASE}:271"),
        Fact("WorldBase.reset teleports auv0 and each target to the sampled poses and ticks the ocean once",
             source="upstream_code", ref=f"{BASE}:386-408"),
        Fact("WorldBase.reset returns (state, info) with info {'reset_info': 'yes'}",
             source="upstream_code", ref=f"{BASE}:432-444"),
        Fact("WorldBase.reset prints the sampled agent and target poses", source="upstream_code",
             ref=f"{BASE}:383-384"),
        Fact("TargetTrackingBase.seed calls np.random.seed(seed)", source="upstream_code", ref=f"{BASE}:62-63"),
        Fact("The shipped v0 config selects the PID controller", source="upstream_code",
             ref=f"{V0_CONFIG}:24"),
        Fact("The PID controller config has action_dim 2 and control_frequency 5",
             source="upstream_code", ref=f"{V0_CONFIG}:35-37"),
        Fact("WorldAuvV0.set_limits builds the PID action space from config action_range_low[1] and "
             "action_range_high[1]", source="upstream_code", ref=f"{V0}:43-48"),
        Fact("The shipped v0 PID action range is low [-1, -1] and high [1, 1] with scale [1.5, 0.5]",
             source="upstream_code", ref=f"{V0_CONFIG}:79-81"),
        Fact("The PID step sets CmdVel.linear.x to action[0] times action_range_scale[0] and CmdVel.angular.z to "
             "action[1] times action_range_scale[1]", source="upstream_code", ref=f"{BASE}:174-179"),
        Fact("The v0 state is [target-belief distance, target-belief bearing, log determinant of the covariance, observed flag] "
             "per target, then [nearest obstacle distance, nearest obstacle angle]",
             source="upstream_code", ref=f"{V0}:109-133"),
        Fact("The v0 observation space is Box(6) with lower [0, -pi, -50, 0, 0, -pi] and upper [600, pi, 50, 2, "
             "sensor_r, pi] for one target", source="upstream_code", ref=f"{V0}:61-67"),
        Fact("The v0 reward is c_mean * r_detcov_mean + c_std * r_detcov_std + c_smooth * r_action_smooth and, on "
             "a collision, min(0, reward) - c_penalty", source="upstream_code", ref=f"{V0}:78-95"),
        Fact("The v0 reward defaults are c_mean 0.2, c_std 0.0, c_smooth 1.0 and c_penalty 5.0",
             source="upstream_code", ref=f"{V0_CONFIG}:83-87"),
        Fact("WorldAuvV0 keeps the last 100 rewards in a deque(maxlen=100)",
             source="upstream_code", ref=f"{V0}:26"),
        Fact("The episode is done when the 100-entry reward deque is full and its mean is below -3.5",
             source="upstream_code", ref=f"{V0}:97-103"),
        Fact("The v0 config sets num_targets 1, margin 1.0 and margin2wall 1.0",
             source="upstream_code", ref=f"{V0_CONFIG}:14-16"),
        Fact("The v0 config sets sensor_r 4.0 and fov 100", source="upstream_code", ref=f"{V0_CONFIG}:46-47"),
        Fact("The README requires HoloOcean 2.0.0 and copying the configs/holoocean scenarios into the HoloOcean "
             "worlds directory", source="vendor_doc", ref=f"{README}:48-53"),
        Fact("The README documents gym.make('AUVTracking_v0') as the registration path", source="vendor_doc",
             ref=f"{README}:134"),
    ]
    safe_state = ("the fake simulation stops advancing: no step, reset or seed is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the last observation, reward and tick stay readable; the "
                  "latch calls nothing in HoloOcean and this package declares only the fake backend")
    #: The fidelity contract of the analytic fake actually opened by the gate.  The upstream HoloOcean model was not
    #: run: its sampling period comes from the scenario file and is not fixed in the clone (BASE:78), so the checked
    #: fake advances one abstract step and reports no wall-clock timestep.
    fidelity = {
        "engine": "analytic: AUVTracking_v0 target-tracking stand-in (no HoloOcean, PID, LQR or KF belief)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake seeds its own random.Random from reset(seed) and is deterministic for one seed and "
                     "action sequence; the upstream reset reseeds numpy from entropy (BASE:47, BASE:463), so a seed "
                     "passed to reset or seed does not fix a HoloOcean trajectory",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "no HoloOcean physics, water, ocean current, PID or LQR controller, KF belief, sonar, camera or "
            "obstacles: the fake moves a point with the PID action scale and a fixed placeholder interval, and the "
            "target is static",
            "the covariance determinant, the observed flag, the rewards and the initial poses are analytic "
            "stand-ins; they follow the shape of WorldAuvV0 (V0:78-107, V0:109-133) but not its numbers or its "
            "belief update",
            "the initial poses are drawn from the v0 map bounds; the upstream draws them through get_init_pose_random "
            "with obstacle, margin and insight rejection loops (BASE:454-533) that the fake does not reproduce",
            "the upstream sampling period is 1/scenario['ticks_per_sec'] of the HoloOcean scenario (BASE:78) and "
            "one RL step integrates ticks_per_rl_step of them (BASE:110-118); the fake advances one abstract step and "
            "reports timestep_ms 0",
            "the deployed env is auv_env.make, which wraps TargetTrackingBase in a TimeLimit of t_steps (INIT:53); "
            "the driver serves the class, so the fake implements only the environment's own done rule and never "
            "truncates",
            "no live backend was run: the clone registers no Gymnasium id (INIT:125-129), the constructor needs "
            "HoloOcean, the HoloOcean Ocean packages and the copied scenario files (README:48-53), and package code "
            "never imports the clone",
            "upstream reset samples initial poses in an outer loop with no attempt or time bound "
            "(auv_env/envs/base.py:454-533); it prints poses to stdout (base.py:383-384), which would need "
            "isolation from an MHS stdio server; the fake neither launches nor stops a HoloOcean process",
        ],
    }
