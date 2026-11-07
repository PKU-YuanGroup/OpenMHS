"""OpenMHS driver for gh.genesis-embodied-ai/difftactile: the box_open TactileEnv (a Gymnasium family driver).

DiffTactile is a Taichi simulator for contact-rich tactile manipulation.  Its Gymnasium environment is
``difftactile.baseline.tactile_env:TactileEnv``: ``cap.world.step.v1`` takes ``{ticks, action}``, the action is a
``Box`` of ``n_actions`` numbers bounded by -0.015 and 0.015, ``cap.world.reset.v1`` takes ``{seed, options}`` and
``cap.world.seed.v1`` takes ``{seed}``.  The device is simulated (R0): there is no hardware backend, no e-stop path
to a machine and no operator-required limit.

Upstream does not register a Gymnasium id: the baseline constructs TactileEnv directly (``make_vec_env`` in
``difftactile/baseline/training_rl.py:95-96`` with the task's ``env_kwargs``), and the clone contains no
``gymnasium.register`` call.  The bridge's ``gym.make(env_id)`` path therefore has no id to open, and this package
serves only the ``fake`` backend, a pure Python stand-in in ``fake.py``.  No upstream code is imported, installed or
run here; this package is model-authored and unreviewed, and it was checked on the fake backend only.

The ``fidelity`` attribute is the contract of the model as deployed (spec 05-fidelity FID-002).  Every constant and
rule below cites a line of the clone at the pinned commit (c4bf43d44071758aea68a5c7ae125fc8257bb8e1).
"""

from mhs.driver import Fact, GymnasiumDriver

TACTILE_ENV = "difftactile/baseline/tactile_env.py"
REGISTER_TASKS = "difftactile/baseline/register_tasks.py"
TRAINING_RL = "difftactile/baseline/training_rl.py"
BOX_OPEN = "difftactile/tasks/box_open.py"


class DiffTactileBoxOpen(GymnasiumDriver):
    device_id = "difftactile-box-open"
    #: Upstream has no Gymnasium id; the fake backend is the only backend this package lists.
    env_id = None
    native = "difftactile.baseline.tactile_env:TactileEnv"
    backends = {"fake": ".fake:FakeTactileEnv"}
    action_space_ref = f"{TACTILE_ENV}:45"
    display_name = "DiffTactile box_open tactile simulator (Gymnasium)"
    vendor, model = "Genesis Embodied AI", "DiffTactile box_open"
    tags = ["tactile", "contact-rich-manipulation", "differentiable-physics", "reinforcement-learning",
            "simulation", "gymnasium"]
    facts = [
        Fact("TactileEnv is a Gymnasium environment: the class inherits from gym.Env", source="upstream_code",
             ref=f"{TACTILE_ENV}:23"),
        Fact("The action space is Box(low=-0.015, high=0.015, shape=(n_actions,), dtype=float32)",
             source="upstream_code", ref=f"{TACTILE_ENV}:45"),
        Fact("The observation space is Box(low=-1000, high=1000, shape=(n_observations,), dtype=float32)",
             source="upstream_code", ref=f"{TACTILE_ENV}:46"),
        Fact("The environment downsamples the object to 2 * 136 * 2 = 544 particle indices, or uses every particle "
             "when the object has fewer", source="upstream_code", ref=f"{TACTILE_ENV}:55-67"),
        Fact("step increments time_step, applies the action, computes the observation and reward, calls "
             "check_termination and returns (observation, reward, terminated, truncated, info)",
             source="upstream_code", ref=f"{TACTILE_ENV}:85-102"),
        Fact("reset accepts seed and options but never reads either: it re-initialises the contact model and returns "
             "(observation, info)", source="upstream_code", ref=f"{TACTILE_ENV}:104-123"),
        Fact("For task box_open, get_observations concatenates the downsampled object particle positions with the "
             "sensor translation (3 values) and Euler angles (3 values); with obs_tactile it also appends the "
             "tactile marker positions and the predicted force", source="upstream_code",
             ref=f"{TACTILE_ENV}:130-140"),
        Fact("compute_rewards uses scale = 1.0 for task box_open and returns scale * 2000 - delta_loss",
             source="upstream_code", ref=f"{TACTILE_ENV}:211-218"),
        Fact("check_termination returns True when time_step reaches time_limit", source="upstream_code",
             ref=f"{TACTILE_ENV}:220-224"),
        Fact("TactileEnv.close is a no-op", source="upstream_code", ref=f"{TACTILE_ENV}:230-231"),
        Fact("The box_open task is registered with n_actions = 6, state_n_observations = 2 * 136 * 2 * 3 + 6, "
             "tactile_n_observations = 2 * 136 + 4 * 136 * 3 + 3 + 6, dt = 5e-5 s, total_steps = 600, "
             "sub_steps = 50 and obj = earpod-case.stl", source="upstream_code", ref=f"{REGISTER_TASKS}:70-80"),
        Fact("The baseline passes time_limit = task.total_steps to the environment", source="upstream_code",
             ref=f"{TRAINING_RL}:78"),
        Fact("Contact.apply_action for box_open reads the six action elements as a position delta and an "
             "orientation delta, adds a 0.8 offset on one position axis depending on the phase, and runs "
             "sub_steps - 1 solver updates", source="upstream_code", ref=f"{BOX_OPEN}:513-527"),
    ]
    safe_state = ("the simulated contact loop is frozen: after an e-stop no step or reset is accepted until "
                  "mhs.safety.reset clears the latch, and the last observation stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "difftactile:TactileEnv(box_open)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake seeds its placeholder particle field from reset(seed) and is deterministic for one "
                     "seed; upstream reset accepts seed and options but never reads them (tactile_env.py:104-123), "
                     "and no fake trajectory was compared with the upstream FEM/MPM simulator",
        },
        "timestep_ms": 2.45,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake replaces the FEM tactile sensor and the MPM object solver with a placeholder particle field: "
            "no contact, deformation, material, friction, force or rendering model is integrated, and every "
            "observation value is test data",
            "the fake returns the full state observation of the registered box_open task, 544 particle positions "
            "times 3 coordinates plus 6 sensor pose values = 1638 values; the tactile observation branch of the "
            "task has 1913 values (register_tasks.py:74-75) and is NOT COVERED",
            "upstream reset accepts seed and options but never reads them; the fake uses the seed for its "
            "placeholder particles, so a seed changes the fake's initial observation and not upstream's",
            "timestep_ms is the simulated time of one transition from the cited constants: box_open runs "
            "sub_steps - 1 = 49 solver updates at dt = 5e-5 s (box_open.py:526-527; register_tasks.py:76 and :78), "
            "2.45 ms; the fake does not integrate physics and advances no simulated time",
            "no wall-clock pacing: realtime_factor 0 and ticks advance the lockstep counter only",
            "no snapshot or restore: TactileEnv exposes no get_state/set_state",
            "the upstream package was not installed, imported or run, and the fake was never compared with it",
            "no rendering: the upstream render method needs Taichi GUI handles and is not served",
        ],
    }
