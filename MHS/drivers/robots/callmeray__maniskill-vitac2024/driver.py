"""OpenMHS driver for gh.callmeray/maniskill-vitac2024: the ViTac peg-insertion Gymnasium environment.

The environment is a Gymnasium simulation on SAPIEN + SapienIPC (``envs/peg_insertion.py`` imports ``sapien`` and
builds an ``IPCSystem``).  A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and
the bridge derives the whole contract from its spaces.  The action space is ``Box(low=-1, high=1, shape=(3,))``
(``envs/peg_insertion.py:129``), so ``cap.world.step.v1`` takes ``{ticks, action}`` with
``action.values = [x, y, theta]`` per element in [-1, 1]; ``cap.world.reset.v1`` takes ``{seed}`` and
``cap.world.seed.v1`` takes ``{seed}``.  The device is simulated (R0): there is no hardware backend, no e-stop path to
a machine and no operator-required limit.

The gate cannot import SAPIEN or the clone, so the ``fake`` backend is the package's own pure Python kinematic
stand-in (see fake.py).  The upstream registration passes no constructor arguments and the registered subclass reads
``kwargs["params"].tac_sensor_meta_file`` (``envs/peg_insertion.py:763``), so ``gymnasium.make(env_id)`` cannot build
the upstream environment by itself; the sim backend was not run.  This package is checked on the fake backend only.

The ``fidelity`` attribute describes the model as deployed (spec 05-fidelity FID-002): the fake is an analytic,
kinematic model, so the level is F0 and the gaps say what it does not model.  Every constant and rule cites a line of
the clone at the pinned commit (114035d58c693dba00ff616fef6e67e1fe62a1f1).  This package is model-authored and
unreviewed.
"""

from mhs.driver import Fact, GymnasiumDriver

PEG = "envs/peg_insertion.py"
REGISTRATION = "envs/__init__.py"
TRAINING = "scripts/universal_training_script.py"
CONFIG = "configs/parameters/peg_insertion.yaml"


class ViTacPegInsertion(GymnasiumDriver):
    device_id = "vitac-peg-insertion"
    env_id = "ContinuousInsertionRandomizedMarkerEnv-v1"
    native = "envs.peg_insertion:ContinuousInsertionSimGymRandomizedPointFLowEnv"
    backends = {"fake": ".fake:FakeContinuousInsertionEnv"}
    action_space_ref = f"{PEG}:129"
    display_name = "ManiSkill-ViTac 2024 peg insertion (Gymnasium)"
    vendor, model = "callmeray", "ManiSkill-ViTac 2024"
    tags = ["gymnasium", "sapien", "tactile", "peg-insertion", "reinforcement-learning", "simulation"]
    facts = [
        Fact("ContinuousInsertionRandomizedMarkerEnv-v1 is registered with the entry point "
             "envs.peg_insertion:ContinuousInsertionSimGymRandomizedPointFLowEnv",
             source="upstream_code", ref=f"{REGISTRATION}:3-6"),
        Fact("The environment base class ContinuousInsertionSimEnv derives from gymnasium's gym.Env",
             source="upstream_code", ref=f"{PEG}:67"),
        Fact("The action space is Box(low=-1, high=1, shape=(3,), dtype=np.float32), a three-element action",
             source="upstream_code", ref=f"{PEG}:129"),
        Fact("The constructor requires step_penalty, final_reward and max_action; max_steps defaults to 15",
             source="upstream_code", ref=f"{PEG}:70-73"),
        Fact("step increments the episode counter, multiplies the action by max_action, and returns observation, "
             "reward, terminated, truncated and info", source="upstream_code", ref=f"{PEG}:624-633"),
        Fact("The action is clipped to +-max_action; its in-plane components are rotated by the current offset "
             "angle and added to the x and y offset, and its third component is added to the theta offset",
             source="upstream_code", ref=f"{PEG}:493-501"),
        Fact("The error-too-large thresholds are 12 on the x offset, 12 on the y offset and 15 on the theta offset, "
             "compared with a 1e-5 tolerance", source="upstream_code", ref=f"{PEG}:506-509"),
        Fact("The reward is the decrease of the evaluated offset error minus step_penalty; an error-too-large step "
             "adds -2*step_penalty*(max_steps-steps)+step_penalty and a success adds final_reward",
             source="upstream_code", ref=f"{PEG}:704-715"),
        Fact("The episode truncates when the elapsed steps reach max_steps and terminates on error_too_large or "
             "is_success", source="upstream_code", ref=f"{PEG}:717-721"),
        Fact("The registered class's default observation holds gt_offset (three float32 values) and marker_flow of "
             "shape (2, 2, 128, 2) float32; render_rgb defaults to False", source="upstream_code",
             ref=f"{PEG}:740-788"),
        Fact("reset accepts offset, seed and peg_idx and returns the observation with an empty info dictionary",
             source="upstream_code", ref=f"{PEG}:467-490"),
        Fact("seed() sets numpy's global random generator with np.random.seed", source="upstream_code",
             ref=f"{PEG}:192-195"),
        Fact("The registered subclass reads kwargs['params'].tac_sensor_meta_file before the superclass constructor, "
             "so a params object is mandatory", source="upstream_code", ref=f"{PEG}:763"),
        Fact("The upstream training configuration sets step_penalty 1, final_reward 10, max_action [2.0, 2.0, 4.0] "
             "and max_steps 8 for this environment", source="upstream_code", ref=f"{CONFIG}:3-6"),
        Fact("The training script creates the environment with gym.make(env_name, device=wp_device, **env_args), so "
             "the constructor arguments come from the caller", source="upstream_code", ref=f"{TRAINING}:42"),
    ]
    safe_state = ("the simulation is latched: no step or reset is accepted after an e-stop until mhs.safety.reset "
                  "clears the latch; the world state stays readable")
    #: The bridge's reset schema: the upstream reset takes seed, offset and peg_idx, and the family bridge serves the
    #: seed.  options and scenario are not served (the upstream reset does not accept them).
    _RESET_INPUTS = {
        "seed": {"type": "integer", "minimum": 0,
                 "description": "Seed of the next reset; the fake re-seeds its generator with it"},
    }
    fidelity_level = "F0"
    #: The fidelity contract of the model as deployed (the fake backend): an analytic kinematic model, F0.
    fidelity = {
        "engine": "analytic:vitac-peg-insertion-fake",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake seeds its generator from reset(seed) or cap.world.seed.v1, so a seed repeats its "
                     "trajectory; the upstream reset accepts a seed argument but does not call seed(), so this claim "
                     "covers the fake backend only and was not established on the upstream environment",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is a kinematic/analytic stand-in: it integrates the commanded offset, rotated by the "
            "current theta, and applies the upstream error, truncation and reward rules; it does not simulate "
            "SAPIEN/IPC contacts, elastic sensor deformation, marker motion, peg/hole geometry or success detection",
            "the upstream environment is a SAPIEN + SapienIPC GPU simulation (envs/peg_insertion.py imports sapien; "
            "README.md:51 requires SapienIPC); it was neither imported nor run here, and the sim backend was not run",
            "the marker_flow observation is a zero array of the real (2, 2, 128, 2) shape: the fake computes no "
            "tactile marker flow, so that field carries no information",
            "no wall-clock pacing: realtime_factor 0 and clock lockstep",
            "timestep_ms 0: one tick is one environment step; the upstream runs a number of IPC substeps that "
            "depends on the action and params.sim_time_step, so no fixed physics interval per tick is claimed",
            "the upstream registration supplies no constructor arguments and the registered subclass requires a "
            "params object (envs/peg_insertion.py:763), so gymnasium.make(env_id) alone cannot build it",
            "the fake's initial offset draw, max_action, max_steps, step_penalty and final_reward are placeholder "
            "test data, not a bound of the upstream environment",
            "snapshot and restore are not offered: the upstream class exposes no get_state/set_state",
        ],
    }
