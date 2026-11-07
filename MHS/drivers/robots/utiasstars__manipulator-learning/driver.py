"""OpenMHS driver for gh.utiasstars/manipulator-learning: the insert-tray Panda environment (a Gymnasium family driver).

A GymnasiumDriver is configuration only: the bridge derives ``cap.world.step.v1`` (``{ticks, action}`` with
``action.values`` bounded per element by the environment's action space), ``cap.world.reset.v1`` (``{seed,
options}``) and ``cap.world.seed.v1`` (``{seed}``) from the backend's spaces and methods.  For
PandaPlayInsertTrayXYZState the action is a four-value ``Box(-1, 1, (4,))`` (three translation deltas and the
gripper) and the observation is a 59-value ``Box(-inf, +inf, (59,))``.  The device is simulated, so there is no
hardware backend, no physical e-stop and no operator-required limit.

The upstream environment is a legacy OpenAI Gym environment: ``step`` returns the four-tuple
``(observation, reward, done, info)`` and ``reset`` returns only the observation and takes no ``seed``; the bridge
falls back to the class's ``seed`` method when ``reset(seed=...)`` is refused (bridge/gymnasium.py:716-751), and it
accepts the legacy four-tuple (bridge/gymnasium.py:674-684).  It is not registered with ``gym.make``: the README
still lists that registration as an unchecked roadmap item (README.md:172), so ``env_id`` is the class name used as
the deployment identity, not a registered Gymnasium id.  A backend name outside ``backends`` (``sim``) would be
served by ``gym.make(env_id)`` and cannot open this class; only the checked ``fake`` backend is runnable here.

Why a fake: the clone imports pybullet, numpy, gym, transforms3d and liegroups at module import, and package code
never imports the clone.  ``fake.py`` is a pure Python analytic stand-in for the class named by ``native``.  The
``fidelity`` attribute is the complete contract of the model as deployed (spec 05-fidelity FID-002): the upstream
environment is a PyBullet rigid-body simulation, but the delivered fake is kinematic (F0), so the package declares
F0 and discloses the difference in the gaps.  Every fact cites a line of the clone at the pinned commit
d887bdcfc92d2238532e6b5a27491f1aeaca47b4.  This package is model-authored and unreviewed: it is checked on the fake
backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

PANDA_PLAY = "manipulator_learning/sim/envs/panda_play.py"
MANIPULATOR = "manipulator_learning/sim/envs/manipulator_env_generic.py"
PB_ENV = "manipulator_learning/sim/envs/pb_env.py"


class PandaPlayInsertTray(GymnasiumDriver):
    device_id = "panda-play-insert-tray"
    env_id = "PandaPlayInsertTrayXYZState"
    native = "manipulator_learning.sim.envs.panda_play:PandaPlayInsertTrayXYZState"
    backends = {"fake": ".fake:FakePandaPlayInsertTrayXYZState"}
    mode, risk = "simulated", "R1"
    display_name = "manipulator-learning Panda Play insert tray (PyBullet simulation)"
    vendor, model = "utiasSTARS", "PandaPlayInsertTrayXYZState"
    tags = ["pybullet", "panda", "insert", "manipulation", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("The README loads environments with getattr(manipulator_learning.sim.envs, name); its example "
             "instantiates PandaPlayInsertTrayXYZState, calls reset() and unpacks the four-value step() result",
             source="upstream_code", ref="README.md:67-74"),
        Fact("Environment generation compatible with gym.make is an unchecked roadmap item, so the class has no "
             "registered Gymnasium id", source="upstream_code", ref="README.md:172"),
        Fact("PandaPlayInsertTrayXYZState documents a 59-value observation space and a 4-value action space",
             source="upstream_code", ref=f"{PANDA_PLAY}:419"),
        Fact("The observation layout is pos 0:3, vel 3:6, grip_pos 6:8, prev_grip_pos 8:12, obj_pos 12:26, obj_vel "
             "26:38, obj_rel_pos 38:53 and force_torque 53:59", source="upstream_code",
             ref=f"{PANDA_PLAY}:420-428"),
        Fact("The class defaults are max_real_time 18 s, n_substeps 5, action_multiplier 0.002 and the insert task, "
             "with state_data pos, vel, grip_pos, prev_grip_pos, obj_pos, obj_rot, obj_vel, obj_rot_vel and "
             "force_torque", source="upstream_code", ref=f"{PANDA_PLAY}:430-433"),
        Fact("A full-magnitude action moves the desired position by 2 mm per substep over five substeps, 1 cm per "
             "environment step", source="upstream_code", ref=f"{PANDA_PLAY}:429"),
        Fact("PandaPlayGeneric passes grip_in_action=True, so the last action value is always the gripper command",
             source="upstream_code", ref=f"{PANDA_PLAY}:90-91"),
        Fact("The insert-tray class uses valid_t_dofs=(1, 1, 1) and valid_r_dofs=(0, 0, 0) with control_method "
             "'dp'", source="upstream_code", ref=f"{PANDA_PLAY}:442"),
        Fact("The insert-tray workspace bounds are x 0.85 to 1.15, y -0.35 to -0.05 and z 0.665 to 0.8 in world "
             "coordinates", source="upstream_code", ref=f"{PANDA_PLAY}:443"),
        Fact("The class defaults force_pb_direct=True", source="upstream_code", ref=f"{PANDA_PLAY}:431"),
        Fact("ManipulatorEnv derives num_actions from the translation DOFs, the rotation DOFs and grip_in_action and "
             "builds the action space as Box(-1, 1, (num_actions,))", source="upstream_code",
             ref=f"{MANIPULATOR}:141-142"),
        Fact("The observation space is a Box from -inf to +inf with num_obs elements", source="upstream_code",
             ref=f"{MANIPULATOR}:159"),
        Fact("The PBEnv default simulation time step is 0.01 s", source="upstream_code", ref=f"{PB_ENV}:69"),
        Fact("ManipulatorEnv computes real_t_per_ts as time_step * n_substeps and _max_episode_steps as "
             "round(max_real_time / real_t_per_ts)", source="upstream_code", ref=f"{MANIPULATOR}:88-89"),
        Fact("A step returns the legacy four-tuple (observation, reward, done, info) and sets done when ep_timesteps "
             "reaches _max_episode_steps", source="upstream_code", ref=f"{MANIPULATOR}:229-238"),
        Fact("reset takes mb_base_angle and reset_dict, returns only the observation and has no seed parameter",
             source="upstream_code", ref=f"{MANIPULATOR}:550-573"),
        Fact("The separate seed(seed=None) method delegates to the PBEnv seed and copies np_random",
             source="upstream_code", ref=f"{MANIPULATOR}:166-169"),
        Fact("PBEnv.seed uses gym.utils.seeding.np_random and returns [seed]", source="upstream_code",
             ref=f"{PB_ENV}:390-393"),
        Fact("PBEnv creates an in-process BulletClient in pybullet.DIRECT mode when force_pb_direct is set",
             source="upstream_code", ref=f"{PB_ENV}:221-222"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The upstream environment is a
    #: PyBullet rigid-body simulation, but the checked fake is an analytic kinematic model, so the package declares F0.
    fidelity = {
        "engine": "analytic:manipulator_learning/PandaPlayInsertTrayXYZState",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake seeds Python's random.Random from reset(seed) or cap.world.seed.v1 and its transitions "
                     "are deterministic, so one seed and action sequence repeat a fake trajectory; upstream "
                     "PBEnv.seed uses numpy's seeding.np_random and PyBullet physics, so a seed does not give the "
                     "same trajectory on the two implementations",
        },
        "timestep_ms": 50.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is an analytic F0 kinematic stand-in: it integrates the three translation values and the "
            "gripper command directly; there are no PyBullet rigid bodies, joints, IK, contacts, friction, actuator "
            "response, sensor model, cameras or rendering",
            "the upstream environment is PyBullet rigid-body dynamics (F1); this package declares F0 because the "
            "delivered fake integrates no dynamics and was never compared with the upstream environment",
            "the fake returns the full 59-value observation layout but only the pos, vel, grip_pos and "
            "prev_grip_pos slots are modelled; the object, relative-position and force-torque slots are zeros",
            "the fake reward is the placeholder 0.0 and is not the upstream insert reward; done is the upstream "
            "360-step time limit reported as the legacy terminated flag, not a Gymnasium truncation",
            "the fake draws its start jitter with Python's random.Random, while upstream PBEnv.seed uses numpy's "
            "generator and PyBullet draws its own contacts; one seed does not give the same trajectory on both",
            "reset options and mb_base_angle/reset_dict are not modelled: upstream reset takes mb_base_angle and "
            "reset_dict but no seed, so the bridge uses seed() followed by reset()",
            "env_id is the class name, not a gym.make registration (README.md:172); the sim backend would call "
            "gym.make and cannot open this class, and no pybullet environment was imported or run",
            "no wall-clock pacing: realtime_factor 0, one bridge tick advances the 50 ms control interval "
            "(5 PyBullet steps of 0.01 s) only",
            "snapshot and restore are not offered: the environment exposes no get_state/set_state pair",
        ],
    }
