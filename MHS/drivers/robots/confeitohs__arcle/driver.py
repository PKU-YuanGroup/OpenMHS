"""OpenMHS driver for gh.confeitohs/arcle: the ARCLE RawARCEnv-v0 environment (a Gymnasium family driver).

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives the
whole contract from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with an action shaped
by the environment's Dict action space -- a ``selection`` Box of 0/1 over the grid and an ``operation`` Discrete --
``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0):
there is no hardware backend, no native stop and no operator-required limit.

The gate cannot install or import the upstream package (it needs gymnasium, numpy and pygame, ``pyproject.toml``),
so the ``fake`` backend is the package's own pure Python RawARCEnv (fake.py).  A backend name that ``backends`` does
not list (``sim``) is served by ``gymnasium.make(env_id)`` (GymnasiumDriver.open_native); that path was not run here
and needs the upstream package installed.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002).
Every fact cites a line of the clone at the pinned commit (311be9db018ed5f17fff2f7891251f965ea7aa2e).  This package
is model-authored and unreviewed: it is checked on the fake backend only, and no hardware was attached.
"""

from mhs.driver import Fact, GymnasiumDriver

ARCENV = "arcle/envs/arcenv.py"
BASE = "arcle/envs/base.py"


class RawARC(GymnasiumDriver):
    device_id = "arcle-raw"
    env_id = "ARCLE/RawARCEnv-v0"
    native = "arcle.envs.arcenv:RawARCEnv"
    backends = {"fake": ".fake:FakeRawARCEnv"}
    display_name = "ARCLE RawARCEnv-v0 (ARC grid environment)"
    vendor, model = "confeitohs", "ARCLE/RawARCEnv-v0"
    tags = ["arc", "arc-agi", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("RawARCEnv's constructor defaults are max_grid_size (30, 30), colors 10 and max_trial -1",
             source="upstream_code", ref=f"{ARCENV}:17"),
        Fact("The observation space is a Dict of trials_remain, terminated, input, input_dim, grid and grid_dim",
             source="upstream_code", ref=f"{BASE}:121-131"),
        Fact("The state document carries trials_remain (max_trial), terminated 0, the zero-padded input and grid, "
             "input_dim and grid_dim", source="upstream_code", ref=f"{BASE}:155-166"),
        Fact("The action space is a Dict of a selection Box with 0 or 1 on every grid cell and an operation "
             "Discrete over the operation count", source="upstream_code", ref=f"{BASE}:134-138"),
        Fact("RawARCEnv's operations are ten color operations (0-9), resize_to_answer (10) and submit (11)",
             source="upstream_code", ref=f"{ARCENV}:26-41"),
        Fact("The reward is 1 only when the last operation is submit and the visible grid equals the answer; "
             "otherwise it is 0", source="upstream_code", ref=f"{ARCENV}:51-58"),
        Fact("step applies the operation, increments action_steps, updates info steps and returns the state, "
             "reward, terminated, truncated and info", source="upstream_code", ref=f"{ARCENV}:60-76"),
        Fact("A submit decrements trials_remain, terminates when the grid equals the answer, and terminates when "
             "trials_remain reaches 0", source="upstream_code", ref=f"{BASE}:172-183"),
        Fact("reset passes seed and options to gym.Env.reset, accepts prob_index, subprob_index, adaptation and "
             "reset_on_submit, and draws the problem from the data loader", source="upstream_code",
             ref=f"{BASE}:69-108"),
        Fact("The reset info carries the zero-padded input and answer with their dimensions", source="upstream_code",
             ref=f"{BASE}:145-153"),
        Fact("ARCLE/RawARCEnv-v0 is registered with entry point arcle.envs.arcenv:RawARCEnv and without "
             "max_episode_steps", source="upstream_code", ref="arcle/envs/__init__.py:7-10"),
        Fact("RawARCEnv.step returns self.truncated", source="upstream_code", ref=f"{ARCENV}:76"),
        Fact("reset sets self.truncated to False", source="upstream_code", ref=f"{BASE}:73"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine
    #: and the seeded determinism; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "gymnasium:ARCLE/RawARCEnv-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the synthetic problem of the next reset and the "
                     "transition model is deterministic, so the same seed and action sequence repeat a trajectory; "
                     "the fake draws with Python's random.Random while upstream draws with numpy's np_random, so a "
                     "seed selects an index but not necessarily the same problem as upstream",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "discrete ARC grid transitions only: no physics, dynamics or continuous time, so timestep_ms is 0 "
            "(the event-driven analytic value) and each tick is one operation",
            "no wall-clock pacing: realtime_factor 0 and ticks never sleep",
            "the fake uses a small synthetic problem table in place of the ARCLoader datasets; the loader, the "
            "pygame/ANSI rendering and the dataset split are not modelled",
            "the fake uses Python lists and random.Random where upstream uses numpy int8 arrays and np_random",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
            "no physical device is modelled and the model was never validated against one",
        ],
    }
