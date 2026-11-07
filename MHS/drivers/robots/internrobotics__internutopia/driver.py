"""OpenMHS driver for gh.internrobotics/internutopia: the single-agent Gymnasium environment over Isaac Sim.

``internutopia.core.gym_env:Env`` subclasses ``gymnasium.Env`` (gym_env.py:10) and is built from a ``Config``
(gym_env.py:17).  Its constructor imports ``SimulatorRunner`` and the runner starts ``isaacsim.SimulationApp``
(runner.py:477-486), so the upstream environment cannot be opened where the gate runs (no Isaac Sim, no GPU).  The
package therefore serves a pure-Python kinematic stand-in on the ``fake`` backend; the gate never imports the clone.

The spaces are not derived from the config: ``internutopia/core/util/space.py`` returns a hardcoded ``Dict`` action
space (``move_along_path``: Sequence of Tuple of three infinite Boxes, space.py:11-25) and a hardcoded ``Dict``
observation space (``position`` shape 3, ``orientation`` shape 4, space.py:28-34).  The bridge derives
``cap.world.step.v1`` from those spaces, so the action input is ``{"move_along_path": <sequence of [x, y, z]>}`` and
``cap.world.reset.v1`` / ``cap.world.seed.v1`` follow the family contract.

``Env.reset`` accepts ``seed`` and ``options`` but uses neither (gym_env.py:62-87), and no registration with
``gymnasium.make`` exists in the clone, so the driver deliberately declares no ``env_id`` and no ``sim`` backend: the
upstream environment is constructed from a ``Config`` object that cannot be expressed as a JSON environment id.  This
package is model-authored and unreviewed; it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

GYM_ENV = "internutopia/core/gym_env.py"
SPACE = "internutopia/core/util/space.py"
RUNNER = "internutopia/core/runner.py"
CONFIG = "internutopia/core/config/__init__.py"


class InternUtopia(GymnasiumDriver):
    device_id = "internutopia"
    mode = "simulated"
    risk = "R0"
    native = "internutopia.core.gym_env:Env"
    backends = {"fake": ".fake:FakeInternUtopiaEnv"}
    display_name = "InternUtopia Gymnasium environment (Isaac Sim)"
    vendor, model = "InternRobotics", "InternUtopia 2.2.1"
    tags = ["embodied-ai", "gymnasium", "internutopia", "isaac-sim", "simulation"]
    facts = [
        Fact("The 2.0 feature list advertises a Gym-compatible environment implementation", source="vendor_doc",
             ref="README.md:26"),
        Fact("The single-agent environment class is Env, a gymnasium.Env subclass", source="upstream_code",
             ref=f"{GYM_ENV}:10"),
        Fact("Env.__init__ requires a Config and builds a SimulatorRunner and a task config manager from it",
             source="upstream_code", ref=f"{GYM_ENV}:17-28"),
        Fact("Env accepts only env_num 1 and at most one robot per episode", source="upstream_code",
             ref=f"{GYM_ENV}:41-54"),
        Fact("The action space is a hardcoded Dict with the key move_along_path, a Sequence of Tuples of three "
             "Box(-inf, inf) entries, independent of the Config", source="upstream_code", ref=f"{SPACE}:11-25"),
        Fact("The observation space is a hardcoded Dict with position Box shape (3,) and orientation Box shape "
             "(4,), all bounds -inf to inf, independent of the Config", source="upstream_code", ref=f"{SPACE}:28-34"),
        Fact("Env.reset accepts seed and options but uses neither; it delegates to runner.reset and returns the "
             "robot observation plus info['task_config']", source="upstream_code", ref=f"{GYM_ENV}:62-87"),
        Fact("Env.step wraps the action as {robot_name: action}, calls runner.step, and returns observation, "
             "reward, terminated, False and info; truncated is always False", source="upstream_code",
             ref=f"{GYM_ENV}:100-140"),
        Fact("When the runner reports reward -1, Env.step reports 0.0; every other reward is reported unchanged",
             source="upstream_code", ref=f"{GYM_ENV}:133-134"),
        Fact("A step before the first reset returns an empty observation, 0.0, False, False and None",
             source="upstream_code", ref=f"{GYM_ENV}:121-128"),
        Fact("Env.get_dt returns the runner's dt", source="upstream_code", ref=f"{GYM_ENV}:154-160"),
        Fact("SimulatorRunner.setup_isaacsim imports isaacsim.SimulationApp and constructs it",
             source="upstream_code", ref=f"{RUNNER}:477-486"),
        Fact("The only Simulator member is ISAACSIM = 'isaac_sim'", source="upstream_code",
             ref=f"{CONFIG}:12-13"),
        Fact("SimConfig defaults physics_dt and rendering_dt to 1/60 s", source="upstream_code",
             ref=f"{CONFIG}:21-22"),
        Fact("The prerequisites list NVIDIA Omniverse Isaac Sim 4.5.0 and an NVIDIA GPU of RTX 2070 or higher",
             source="vendor_doc", ref="README.md:69-71"),
        Fact("The vectorized internutopia.core.vec_env.Env documents itself as NOT gymnasium compatible",
             source="upstream_code", ref="internutopia/core/vec_env.py:9-13"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The gate serves the package's
    #: pure-Python fake, not Isaac Sim, so the claim is kinematic (F0) and makes no determinism claim about the
    #: upstream simulator.
    fidelity = {
        "engine": "internutopia:isaac_sim",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "no determinism claim is made: Env.reset accepts a seed but never uses it (gym_env.py:62-87), "
                     "and Isaac Sim was not run or measured. The fake backend is deterministic for a fixed command "
                     "sequence but is not presented as a replay claim about the upstream simulator.",
        },
        "timestep_ms": 1000.0 / 60.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the gate's model is a pure-Python kinematic stand-in: no rigid-body dynamics, contacts, friction or "
            "physics engine",
            "the fake sets the pose from the supplied path points directly; no actuator, controller, sensor, "
            "camera or noise model is represented",
            "the fake receives the action-space object directly and interprets move_along_path itself; upstream "
            "Env.step wraps the action as {robot_name: action} and the runner dispatches it to the configured "
            "controllers (gym_env.py:130-131), and no controller or robot model is present here",
            "the fake's observation is the hardcoded observation_space shape (position, orientation), while "
            "upstream returns the robot observation mapping produced by the runner (gym_env.py:84-85 and "
            "136-137); the configured robot's observations are not represented",
            "no Isaac Sim run was made: the upstream environment needs Isaac Sim 4.5.0 and an NVIDIA GPU "
            "(README.md:69-71), and the fake was not compared with it",
            "the upstream Env.reset accepts seed and options but uses neither, so no seeded replay claim is made "
            "and Isaac Sim determinism was not measured",
            "no wall-clock pacing: realtime_factor 0; one tick advances the fake by one step only, and timestep_ms "
            "is the SimConfig physics_dt default (config/__init__.py:21), not a measured interval of the fake",
            "snapshot and restore are not offered: Env exposes no get_state/set_state",
        ],
    }
