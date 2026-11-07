"""OpenMHS driver for gh.linden713/humanoid_amp: the Humanoid AMP Isaac Lab environment (a Gymnasium family driver).

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives the
``cap.world.step.v1``, ``cap.world.reset.v1`` and ``cap.world.seed.v1`` contract from the environment's spaces.
The upstream environment is an Isaac Lab ``DirectRLEnv`` that simulates a Unitree humanoid with the PhysX rigid-body
engine (humanoid_amp_env.py:22, :52-75; humanoid_amp_env_cfg.py:52-59).  It needs Isaac Sim 5.0 and Isaac Lab 2.2
(README.md:6-7), a GPU and the motion/USD assets, so the ``fake`` backend is this package's pure Python kinematic
stand-in (fake.py).  The card's preferred ``upstream-sim`` path is therefore not available here: a backend name that
``backends`` does not list (``sim``) would be served by ``gymnasium.make(env_id)`` (GymnasiumDriver.open_native), and
that path was not run.

The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no operator-required
limit.  The ``fidelity`` attribute is the contract of the modelled environment (spec 05-fidelity FID-002); its
``gaps`` disclose what the checked fake does not model.  Every fact cites a line of the clone at the pinned commit
99efa6d60e351ec3def0dc6e983baf143fd31328.  This package is model-authored and unreviewed: it is checked on the fake
backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "humanoid_amp_env.py"
CFG = "humanoid_amp_env_cfg.py"


class HumanoidAmp(GymnasiumDriver):
    device_id = "humanoid-amp"
    env_id = "Isaac-Humanoid-AMP-Dance-Direct-v0"
    native = "humanoid_amp.humanoid_amp_env:HumanoidAmpEnv"
    backends = {"fake": ".fake:FakeHumanoidAmpEnv"}
    display_name = "Humanoid AMP (Isaac Lab DirectRLEnv, dance task)"
    vendor, model = "linden713", "Humanoid AMP"
    tags = ["humanoid", "amp", "unitree", "isaac-lab", "isaac-sim", "physx", "reinforcement-learning",
            "simulation", "gymnasium"]
    facts = [
        Fact("The package registers Isaac-Humanoid-AMP-Dance-Direct-v0, Isaac-Humanoid-AMP-Run-Direct-v0 and "
             "Isaac-Humanoid-AMP-Walk-Direct-v0 with entry point humanoid_amp_env:HumanoidAmpEnv",
             source="upstream_code", ref="__init__.py:18-44"),
        Fact("HumanoidAmpEnv is an Isaac Lab DirectRLEnv", source="upstream_code", ref=f"{ENV}:22"),
        Fact("The scene spawns the robot with Articulation and the ground with spawn_ground_plane",
             source="upstream_code", ref=f"{ENV}:52-57"),
        Fact("The configured observation space is 81 values, the action space 28 values and the state space 0",
             source="upstream_code", ref=f"{CFG}:32-34"),
        Fact("The config keeps two AMP observations of 81 values each", source="upstream_code", ref=f"{CFG}:35-36"),
        Fact("The action offset is the midpoint of the robot's soft joint-position limits and the action scale is "
             "their span", source="upstream_code", ref=f"{ENV}:28-32"),
        Fact("Each applied action becomes the joint-position target action_offset + action_scale * action",
             source="upstream_code", ref=f"{ENV}:80-82"),
        Fact("The episode is configured to last 10.0 s and each environment step decimates 2 physics steps",
             source="upstream_code", ref=f"{CFG}:28-29"),
        Fact("The physics step is 1/60 s and the simulation configures PhysX", source="upstream_code",
             ref=f"{CFG}:52-58"),
        Fact("Early termination is enabled with a termination height of 0.5", source="upstream_code",
             ref=f"{CFG}:38-39"),
        Fact("The reference body of the generic humanoid environment is the torso", source="upstream_code",
             ref=f"{CFG}:42"),
        Fact("The default reset strategy is random: it samples motion times unless the strategy is random-start or "
             "default", source="upstream_code", ref=f"{CFG}:43-49"),
        Fact("The scene config sets num_envs 4096 and env_spacing 10.0", source="upstream_code",
             ref=f"{CFG}:62"),
        Fact("The observation concatenates joint positions, joint velocities, the root height, tangent and normal "
             "vectors, root linear and angular velocities and the key-body positions relative to the root",
             source="upstream_code", ref=f"{ENV}:221-240"),
        Fact("The generic humanoid reward is one for every environment at every step", source="upstream_code",
             ref=f"{ENV}:105-106"),
        Fact("The episode truncates when the episode-length buffer reaches max_episode_length - 1 and terminates "
             "early when the reference body is below termination_height", source="upstream_code",
             ref=f"{ENV}:108-114"),
        Fact("A random reset samples motion times, writes the sampled root pose and velocity plus joint positions "
             "and velocities, and updates the AMP observation buffer", source="upstream_code",
             ref=f"{ENV}:143-175"),
        Fact("The AMP observation buffer holds num_amp_observations times amp_observation_space values per "
             "environment", source="upstream_code", ref=f"{ENV}:45-50"),
    ]
    safe_state = ("the simulation stops advancing: no step, reset or seed is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the modelled environment (spec 05-fidelity section 2).  The bridge derives the
    #: engine, the determinism kind and the lockstep clock; they are written out so the whole contract reads in one
    #: place.  The gaps disclose what the checked fake does not model.
    fidelity = {
        "engine": "isaaclab:Isaac-Humanoid-AMP-Dance-Direct-v0 (Isaac Sim/PhysX)",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) re-seeds the environment's random generator; this package checked repeatability "
                     "only on the fake, whose initial joint draws are seeded. The upstream motion sampling with "
                     "numpy and the GPU physics were not run here and are not claimed bit-exact",
        },
        "timestep_ms": 1000.0 / 60.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is kinematic: it integrates the action as a small joint-position increment and "
            "models no rigid-body dynamics, contacts, friction, actuators, gravity, sensors or noise",
            "the fake presents one unbatched environment with flat (28,) and (81,) spaces, while the upstream "
            "scene config batches 4096 environments by default and returns a {'policy': ...} observation",
            "the fake never terminates on the 0.5 m reference-body height because it has no balance model; it only "
            "truncates at the 10.0 s episode length",
            "the fake's initial joint values are Python random.Random draws, not samples of the upstream motion "
            "clips; the upstream reset samples the .npz motions with numpy",
            "no wall-clock pacing: realtime_factor 0, and ticks advance simulated time only; the 16.67 ms timestep "
            "is the physics step, while the control period is two such steps (about 33.33 ms)",
            "snapshot and restore are not offered: neither the upstream DirectRLEnv nor the fake exposes "
            "get_state()/set_state()",
            "no physical device is modelled and the Isaac Sim/PhysX environment was never run or validated here",
        ],
    }
