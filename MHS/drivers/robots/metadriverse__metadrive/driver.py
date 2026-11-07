"""OpenMHS driver for gh.metadriverse/metadrive: the MetaDrive driving simulator (a Gymnasium family driver).

MetaDrive is a simulated driving world: ``MetaDriveEnv`` subclasses ``BaseEnv``, which subclasses
``gymnasium.Env`` (metadrive/envs/base_env.py:279).  A ``GymnasiumDriver`` is configuration only, and the gymnasium
bridge derives the whole ``cap.world.*`` contract from the environment's spaces: the default continuous action is
``Box(-1.0, 1.0, shape=(2,))`` (metadrive/policy/env_input_policy.py:61-62), so ``cap.world.step.v1`` takes
``{ticks, action: {values: [steering, throttle]}}`` and refuses values outside -1.0..1.0 before the environment is
stepped.  ``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` takes ``{seed}``.

The device is simulated (R0): there is no hardware backend, no path to a machine and no operator-required limit.  The
upstream environment is never imported or run here: the ``fake`` backend is the package's own kinematic stand-in
(fake.py), and the acceptance gate checks only that backend (task.json acceptance).  The fake is not the Panda3D
simulator and was not compared with an upstream run; the fidelity ``gaps`` say what it does not model.

The ``fidelity`` attribute is the model as deployed (spec 05-fidelity FID-002).  Every constant cites a line of the
clone at the pinned commit (325d9e2f9c20e495bde66f30e0ef2b40efbce39c).  This package is model-authored and
unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

BASE_ENV = "metadrive/envs/base_env.py"
META_ENV = "metadrive/envs/metadrive_env.py"
POLICY = "metadrive/policy/env_input_policy.py"
STATE_OBS = "metadrive/obs/state_obs.py"
NAVIGATION = "metadrive/component/navigation_module/base_navigation.py"


class MetaDrive(GymnasiumDriver):
    """MetaDriveEnv as a simulated OpenMHS world; only the fake backend is served."""

    device_id = "metadrive"
    # MetaDrive has no gymnasium registration id; env_id stays None and the fake backend provides the environment.
    native = "metadrive.envs.metadrive_env:MetaDriveEnv"
    backends = {"fake": ".fake:FakeMetaDriveEnv"}
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R0"
    display_name = "MetaDrive driving simulator (Gymnasium environment)"
    vendor, model = "MetaDrive Team", "MetaDrive"
    tags = ["driving-simulator", "reinforcement-learning", "simulation", "gymnasium", "world-model"]
    facts = [
        Fact("MetaDrive is a driving simulator with synthesised road maps and traffic, sensor simulation, and "
             "point-cloud, RGB/depth/semantic, top-down map and first-person view inputs", source="vendor_doc",
             ref="README.md:35-39"),
        Fact("The documented usage imports MetaDriveEnv, calls reset() for (obs, info), calls step() for the "
             "five-value (obs, reward, terminated, truncated, info) tuple and calls close()", source="vendor_doc",
             ref="README.md:106-117"),
        Fact("BaseEnv subclasses gymnasium.Env, so MetaDriveEnv (a BaseEnv) is a Gymnasium environment",
             source="upstream_code", ref=f"{BASE_ENV}:279"),
        Fact("BaseEnv.step takes one action (or a per-agent dict), preprocesses it, steps the simulator and returns "
             "through _get_step_return", source="upstream_code", ref=f"{BASE_ENV}:435-440"),
        Fact("For a single agent, _get_step_return returns observation, reward, terminated and truncated values and "
             "an info dict", source="upstream_code", ref=f"{BASE_ENV}:638-643"),
        Fact("BaseEnv.reset(seed) resets the simulation, clears the episode counters and returns "
             "_get_reset_return(reset_info)", source="upstream_code", ref=f"{BASE_ENV}:512-547"),
        Fact("The reset seed is applied through _reset_global_seed(seed)", source="upstream_code",
             ref=f"{BASE_ENV}:523-524"),
        Fact("The seed(seed) method calls set_global_random_seed(seed)", source="upstream_code",
             ref=f"{BASE_ENV}:684-686"),
        Fact("When discrete_action is False, the input space is a Box from -1.0 to 1.0 with shape (2,)",
             source="upstream_code", ref=f"{POLICY}:61-62"),
        Fact("The continuous action is converted to a (steering, throttle) pair and clipped to -1.0..1.0",
             source="upstream_code", ref=f"{POLICY}:34-48"),
        Fact("discrete_action defaults to False", source="upstream_code", ref=f"{BASE_ENV}:60-61"),
        Fact("The state observation is a Box from -0.0 to 1.0 whose width is ego_state_obs_dim (6) plus the "
             "navigation dimension plus the line-detector dimension", source="upstream_code",
             ref=f"{STATE_OBS}:9-28"),
        Fact("The default lidar state observation adds the lidar rays (num_lasers plus 4 * num_others) to the state "
             "width and is likewise bounded by 0.0..1.0", source="upstream_code", ref=f"{STATE_OBS}:175-186"),
        Fact("The default vehicle lidar has 240 lasers, 0 others and a 50 m distance", source="upstream_code",
             ref=f"{BASE_ENV}:170"),
        Fact("The navigation constants are NUM_WAY_POINT 2 and CHECK_POINT_INFO_DIM 5", source="upstream_code",
             ref=f"{NAVIGATION}:18-19"),
        Fact("A physics step is 0.02 s and decision_repeat repeats it 5 times per env.step, so one environment step "
             "advances 0.1 s of simulated time", source="upstream_code", ref=f"{BASE_ENV}:189-191"),
        Fact("The default horizon is 1000 environment steps", source="upstream_code", ref=f"{META_ENV}:58"),
        Fact("MAX_STEP is true when episode_lengths reaches the horizon", source="upstream_code",
             ref=f"{META_ENV}:133-145"),
        Fact("truncated is derived from the MAX_STEP entry of the step info", source="upstream_code",
             ref=f"{BASE_ENV}:623-625"),
        Fact("start_seed defaults to 0 and num_scenarios to 1", source="upstream_code", ref=f"{META_ENV}:18-19"),
        Fact("The default map is 3 blocks with lane width 3.5 and 3 lanes", source="upstream_code",
             ref=f"{META_ENV}:22-30"),
        Fact("close() closes the engine when one exists", source="upstream_code", ref=f"{BASE_ENV}:645-647"),
        Fact("The generic install requirements contain no serial, VISA, USB or vendor hardware SDK",
             source="upstream_code", ref="setup.py:39-52"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the world state is kept and stays readable")
    #: The model as deployed by this package: a kinematic fake, not the upstream Panda3D/Bullet simulator.
    fidelity = {
        "engine": "analytic",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the initial lateral and heading offsets and every step "
                     "is deterministic, so this package's fake repeats a trajectory for the same seed and actions; "
                     "the upstream simulator draws from its own global random stream, so a seed need not give the "
                     "same trajectory on the two",
        },
        "timestep_ms": 100.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic/analytic model with no dynamics: positions and state transitions are integrated directly; no "
            "forces, contacts, collisions, traffic rules, map or road network are modelled",
            "no actuator, sensor or noise model: the 259-float observation is a synthetic vector in 0..1 shaped like "
            "the default LidarStateObservation (6 ego + 10 navigation + 3 line-detector + 240 lidar values), not a "
            "rendered or ray-cast measurement",
            "the fake integrates one 0.1 s step per tick; upstream MetaDriveEnv runs five 0.02 s physics steps per "
            "environment step (base_env.py:189-191), and the two were never compared",
            "no rendering, image observation or panda3d engine: the fake is pure Python and imports nothing from the "
            "clone",
            "no wall-clock pacing: realtime_factor 0 and ticks advance simulated time by timestep_ms only",
            "reset options are accepted by the bridge but upstream MetaDriveEnv.reset only accepts seed, so the "
            "bridge falls back to seed(seed) and reset() and the options are not applied",
            "snapshot and restore are not offered: MetaDriveEnv exposes no get_state/set_state pair",
            "no physical device is modelled and this package was never validated against the upstream simulator or "
            "a vehicle",
        ],
    }
