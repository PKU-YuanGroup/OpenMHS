"""OpenMHS driver for gh.chuanyune/maniskill-vitac2025: Track 1 peg insertion (a Gymnasium family driver).

The card's ``family-config`` decision fits the upstream interface: Track 1 registers the Gymnasium environment
``PegInsertionRandomizedMarkerEnv-v1`` with entry point ``envs.peg_insertion:PegInsertionSimMarkerFLowEnv``, which is
a ``gymnasium.Env``.  A ``GymnasiumDriver`` is configuration only: the bridge derives ``cap.world.step.v1`` (input
``{ticks, action}`` with the action shaped by the environment's ``Box`` space), ``cap.world.reset.v1`` and
``cap.world.seed.v1`` from the spaces and serves the ``world`` resource.  The bridge is configured with
``autoreset = True``: a step after a terminal or truncated state starts a new full episode, whereas the upstream
environment leaves that to the caller.

The device is simulated (R0): it moves no hardware, so there is no hardware backend, no e-stop path to a machine and
no operator-required limit.  The gate cannot import the upstream environment (it builds a SAPIEN scene and an IPC
tactile sensor and expects CUDA), so the ``fake`` backend is the package's own pure Python kinematic stand-in
(fake.py, gate G7 checks it against the upstream class).  A backend name that ``backends`` does not list (``sim``)
would fall through to ``gymnasium.make(env_id)`` (GymnasiumDriver.open_native); that path needs the upstream
dependencies and was not run here.

The ``fidelity`` attribute states what the package's model is and is not.  It is F0: the fake advances the commanded
offsets and a fixed insertion depth directly, with no rigid-body contact, no IPC/FEM tactile deformation and no
marker-flow or rendering model.  One tick is one insertion step and no simulated time is advanced.
"""

from mhs.driver import Fact, GymnasiumDriver

PEG = "Track_1/envs/peg_insertion.py"
REGISTRATION = "Track_1/envs/__init__.py"


class PegInsertionMarkerFlow(GymnasiumDriver):
    device_id = "vitac2025-peg-insertion"
    env_id = "PegInsertionRandomizedMarkerEnv-v1"
    autoreset = True
    native = "envs.peg_insertion:PegInsertionSimMarkerFLowEnv"
    backends = {"fake": ".fake:FakePegInsertionMarkerFlowEnv"}
    action_space_ref = f"{PEG}:294-296"
    display_name = "ManiSkill-ViTac 2025 Track 1 peg insertion (tactile-vision simulation)"
    vendor, model = "chuanyune", "ManiSkill-ViTac 2025 Track 1"
    tags = ["manipulation", "peg-insertion", "tactile", "vision", "reinforcement-learning",
            "simulation", "gymnasium", "sapien"]
    facts = [
        Fact("Track 1 registers PegInsertionRandomizedMarkerEnv-v1 with entry_point "
             "envs.peg_insertion:PegInsertionSimMarkerFLowEnv",
             source="upstream_code", ref=f"{REGISTRATION}:3-6"),
        Fact("PegInsertionSimMarkerFLowEnv extends PegInsertionSimEnv", source="upstream_code",
             ref=f"{PEG}:1138"),
        Fact("The action space is Box(low=-1, high=1, shape=(3,), dtype=float32)", source="upstream_code",
             ref=f"{PEG}:294-296"),
        Fact("A step scales the action by max_action_mm_deg and applies it with _sim_step", source="upstream_code",
             ref=f"{PEG}:796-798"),
        Fact("step returns (observation, reward, terminated, truncated, info)", source="upstream_code",
             ref=f"{PEG}:809"),
        Fact("reset accepts offset_mm_deg, seed, peg_idx and options and returns (observation, info)",
             source="upstream_code", ref=f"{PEG}:335-337"),
        Fact("The separate seed(seed) method calls numpy.random.seed", source="upstream_code",
             ref=f"{PEG}:300-303"),
        Fact("The default observation holds relative_motion of four floats and gt_offset of three floats",
             source="upstream_code", ref=f"{PEG}:328-332"),
        Fact("The marker-flow subclass replaces surface_pts with marker_flow of shape (2, 2, 128, 2) and rebuilds "
             "observation_space from that default observation", source="upstream_code", ref=f"{PEG}:1181-1198"),
        Fact("get_obs drops surface_pts and adds marker_flow from the two tactile sensors", source="upstream_code",
             ref=f"{PEG}:1289-1297"),
        Fact("When render_rgb is true the observation also carries rgb_images shaped (2, 240, 320, 3)",
             source="upstream_code", ref=f"{PEG}:1189-1196"),
        Fact("The tactile movement flag is set when the mean surface difference exceeds 1.5e-3 m",
             source="upstream_code", ref=f"{PEG}:949-951"),
        Fact("The error flag is set when the x or y offset exceeds 12 mm or the theta offset exceeds 15 degrees",
             source="upstream_code", ref=f"{PEG}:957-966"),
        Fact("Success requires no error, no step limit, no tactile movement flag, steps times z_step_size_mm above "
             "0.35, and every peg bottom point more than 0.3 mm below the hole surface", source="upstream_code",
             ref=f"{PEG}:970-978"),
        Fact("The episode truncates when too_many_steps, tactile_movement_too_large or error_too_large is set",
             source="upstream_code", ref=f"{PEG}:1083-1087"),
        Fact("The reward subtracts step_penalty, adds final_reward on success and adds a remaining-steps penalty "
             "when the episode is truncated by error or tactile movement", source="upstream_code",
             ref=f"{PEG}:1049-1063"),
    ]
    safe_state = ("the simulation stops advancing: an e-stop makes the runtime refuse step and reset until "
                  "mhs.safety.reset clears the latch; the environment state stays readable and no hardware is moved")
    #: The complete fidelity contract of the package's model (spec 05-fidelity FID-002/FID-005).  It is written out
    #: because the fake is not the upstream SAPIEN/IPC simulator and the F0 claim must be explicit.
    fidelity = {
        "engine": "gymnasium:PegInsertionRandomizedMarkerEnv-v1",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake's reset draws the initial offset with Python's random.Random(seed) and the offsets "
                     "then evolve deterministically, so one fake repeats a trajectory for the same seed and actions; "
                     "the upstream reset accepts seed but never uses it (its randomness is numpy's global stream, "
                     "seeded by the separate seed() method), so the two do not share a trajectory for a seed",
        },
        "timestep_ms": 0.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a kinematic stand-in, not the upstream SAPIEN/IPC simulator: it adds the commanded x, y "
            "and theta offsets and a fixed insertion step directly, with no rigid-body contacts, no FEM/IPC "
            "tactile deformation, no actuator, sensor or noise model and no rendering (F0: no dynamics)",
            "one tick advances one insertion step and no simulated time is advanced (timestep_ms 0); there is no "
            "wall-clock pacing",
            "the marker_flow observation is (2, 2, 128, 2) in the upstream space but the fake returns zeros; the "
            "real optical marker flow of the two tactile sensors is not modelled",
            "the fake honours reset(seed=...) for reproducibility, while upstream reset accepts seed and does not "
            "use it and upstream randomness is numpy's global generator; equal seeds therefore do not give equal "
            "trajectories between the fake and the upstream environment",
            "the optional rgb_images observation (2, 240, 320, 3) of render_rgb=True is not rendered by the fake",
            "the bridge is configured with autoreset=True: a step after a terminal or truncated state starts a new "
            "full episode, whereas the upstream Gymnasium environment requires the caller to reset it",
            "the upstream environment requires SAPIEN, sapienipc and CUDA and was never imported, run or compared "
            "with this fake; no physical device is modelled and nothing was validated",
            "snapshot and restore are not offered: the upstream class exposes no get_state/set_state",
        ],
    }
