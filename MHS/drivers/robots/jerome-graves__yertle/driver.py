"""OpenMHS driver for gh.jerome-graves/yertle: the Yertle quadruped locomotion environment (Gymnasium family).

``learning.yertle_env:YertleEnv`` is a standard ``gymnasium.Env`` that loads the repository's
``simulation/yertle.urdf`` in PyBullet.  A ``GymnasiumDriver`` is configuration only: the bridge derives the whole
contract from the environment's spaces, so ``cap.world.step.v1`` takes ``{ticks, action}`` with
``action.values`` as the 12 joint residuals bounded by the environment's ``Box(-1, 1, (12,))``,
``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` takes ``{seed}``.  The device is
simulated (R0): there is no hardware backend, no e-stop path to a machine and no operator-required limit.

The environment is not registered with ``gymnasium.make`` anywhere in the clone (the Isaac Lab registrations in
``isaac_lab/__init__.py`` name an external entry point), so this package does not offer a ``sim`` backend: opening the
real environment would require importing the read-only clone, which package code must not do.  The ``fake`` backend is
a pure Python stand-in for the environment interface; it is checked by the gate.  It was never compared with a
PyBullet run, and the fidelity ``gaps`` say what it does not model.

Every Fact cites a line of the clone at the pinned commit 9d04e2d2c1da07d5845807bd36b242b1d0eff843.  This package is
model-authored and unreviewed; it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "learning/yertle_env.py"


class Yertle(GymnasiumDriver):
    device_id = "yertle"
    env_id = None  # no gymnasium id is registered for this environment in the clone
    native = "learning.yertle_env:YertleEnv"
    backends = {"fake": ".fake:FakeYertleEnv"}
    action_space_ref = f"{ENV}:151"
    display_name = "Yertle quadruped locomotion environment (PyBullet)"
    vendor, model = "Jerome Graves", "Yertle"
    tags = ["quadruped", "locomotion", "reinforcement-learning", "simulation", "gymnasium", "pybullet"]
    facts = [
        Fact("YertleEnv is a Gymnasium environment for the Yertle quadruped that loads simulation/yertle.urdf in "
             "PyBullet and exposes the standard Gymnasium API", source="upstream_code", ref=f"{ENV}:1-4"),
        Fact("YertleEnv subclasses gym.Env", source="upstream_code", ref=f"{ENV}:126"),
        Fact("The robot has 12 actuated joints: the four leg prefixes lf, rf, lb and rb times the three segments "
             "shoulder, thigh and shin", source="upstream_code", ref=f"{ENV}:47-51"),
        Fact("The action space is one residual per actuated joint: a Box with low -1.0 and high 1.0",
             source="upstream_code", ref=f"{ENV}:150-151"),
        Fact("The default action_scale is 0.4 rad", source="upstream_code", ref=f"{ENV}:83-84"),
        Fact("A step adds the scaled action residual to DEFAULT_STANCE and clips each target to the joint soft "
             "limits", source="upstream_code", ref=f"{ENV}:278-281"),
        Fact("The standing pose is shoulder 0.0, thigh -0.6 and shin 0.9 rad, repeated for the four legs",
             source="upstream_code", ref=f"{ENV}:65-71"),
        Fact("The per-joint soft limits are shoulder -45 to 45 degrees, thigh -90 to 20 degrees and shin 13 to 90 "
             "degrees", source="upstream_code", ref=f"{ENV}:56-63"),
        Fact("The observation space is a 48-dimensional Box of unbounded floats", source="upstream_code",
             ref=f"{ENV}:153-156"),
        Fact("The observation concatenates base linear velocity, base angular velocity, projected gravity, the "
             "velocity command, joint positions relative to the stance, joint velocities times 0.1 and the previous "
             "action", source="upstream_code", ref=f"{ENV}:332-343"),
        Fact("The default command ranges are vx 0.15 to 0.35 m/s, vy -0.1 to 0.1 m/s and yaw -0.4 to 0.4 rad/s",
             source="upstream_code", ref=f"{ENV}:91-95"),
        Fact("The simulation steps at 1/240 s and the control loop runs four physics steps per environment step "
             "(60 Hz), and an episode is 12 s", source="upstream_code", ref=f"{ENV}:78-81"),
        Fact("The maximum number of environment steps is int(episode_seconds / (sim_timestep * "
             "control_decimation))", source="upstream_code", ref=f"{ENV}:140"),
        Fact("A step sets truncated when the step count reaches the maximum", source="upstream_code",
             ref=f"{ENV}:297-299"),
        Fact("The termination thresholds are 0.08 m base height and 0.7 rad tilt (about 40 degrees)",
             source="upstream_code", ref=f"{ENV}:97-99"),
        Fact("A step reports terminated when the base height is below min_base_height or the tilt exceeds max_tilt",
             source="upstream_code", ref=f"{ENV}:378-381"),
        Fact("The reward uses exponential kernels for linear and yaw velocity tracking, a forward-progress term "
             "clipped to +-0.5 and penalties on energy, action rate, orientation and height",
             source="upstream_code", ref=f"{ENV}:355-376"),
        Fact("A fall subtracts 5.0 from the reward", source="upstream_code", ref=f"{ENV}:380-381"),
        Fact("reset(seed) replaces the numpy generator, samples a new velocity command, resets the joints to "
             "DEFAULT_STANCE and returns (observation, {})", source="upstream_code", ref=f"{ENV}:247-268"),
        Fact("Domain randomisation is on by default: base-mass scale 0.85 to 1.15, foot friction 0.6 to 1.2, "
             "observation noise 0.02 and random pushes every 150 steps of 0.25 m/s", source="upstream_code",
             ref=f"{ENV}:114-120"),
        Fact("The environment connects a PyBullet GUI client only when render_mode is human and a DIRECT (headless) "
             "client otherwise", source="upstream_code", ref=f"{ENV}:166-171"),
        Fact("render() returns a 640 by 480 RGB array when render_mode is rgb_array", source="upstream_code",
             ref=f"{ENV}:385-394"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity FID-002).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "gymnasium:learning.yertle_env:YertleEnv",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) reseeds the environment's generator before the command, mass, friction and "
                     "observation noise are drawn; the packaged fake is deterministic for the same seed and "
                     "actions, but it uses Python's random.Random while upstream uses numpy's default_rng, so one "
                     "seed does not give the same values on the two implementations",
        },
        "timestep_ms": 1000.0 / 60.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "rigid-body PyBullet dynamics including ground contact, foot friction, the position servo and the URDF "
            "inertia override: the fake models none of them",
            "the fake's base velocity is a first-order stand-in for the sampled command, its joint motion is a "
            "first-order approach to the clipped targets and the robot never falls, so terminated is always false "
            "and only the default episode length truncates",
            "the observation composition and the reward formula follow yertle_env.py, but the values come from the "
            "fake and were never compared with a PyBullet run",
            "upstream draws the command, mass/friction and observation noise from numpy's default_rng; the fake uses "
            "Python's random.Random, so a seed gives different values on the two",
            "no rendering: render() and the 640x480 rgb_array frame are not modelled, and the bridge does not bind "
            "cap.world.render.v1",
            "the upstream package needs pybullet>=3.2, gymnasium>=0.29 and numpy; the package imports none of them, "
            "and no sim backend is declared because no gymnasium id is registered for YertleEnv",
            "no physical Yertle is modelled and no hardware run was made",
        ],
    }
