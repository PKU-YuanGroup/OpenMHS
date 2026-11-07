"""OpenMHS driver for gh.abizovnuralem/go2_omniverse: the Isaac Lab Unitree Go2 velocity task.

The upstream script creates a Gymnasium environment with
``gym.make("Isaac-Velocity-Rough-Unitree-Go2-v0", cfg=UnitreeGo2CustomEnvCfg())`` (omniverse_sim.py:19 and :384).
The card's entry symbol is the configuration class, so ``native`` names ``custom_rl_env:UnitreeGo2CustomEnvCfg`` and
``env_id`` names the registered task.  The bridge derives the whole contract from the environment's spaces:
``cap.world.step.v1`` takes ``{ticks, action}`` (a joint-position Box), ``cap.world.reset.v1`` takes ``{seed,
options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0): there is no hardware backend, no
e-stop path to a machine and no operator-required limit.

Isaac Sim 5.0, Isaac Lab 0.54.3, torch and a GPU are external dependencies (JAZZY.md:61-69), and the environment
class itself lives outside the clone (custom_rl_env.py:32).  The gate cannot install or import any of that, so the
``fake`` backend is this package's own pure Python kinematic stand-in (fake.py).  A backend name that ``backends``
does not list (``sim``) is served by ``gymnasium.make(env_id)`` (GymnasiumDriver.open_native); that path was not run
here, and it would use the registered task's default configuration because the driver cannot build
``UnitreeGo2CustomEnvCfg`` without importing the clone.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002).
Every constant and rule cites a line of the clone at the pinned commit
(db18970d66fa77a68bf0976b0f7c183825cd2292).  This package is model-authored and unreviewed: it is checked on the fake
backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "omniverse_sim.py"
CFG = "custom_rl_env.py"


class Go2Omniverse(GymnasiumDriver):
    device_id = "go2-omniverse"
    env_id = "Isaac-Velocity-Rough-Unitree-Go2-v0"
    native = "custom_rl_env:UnitreeGo2CustomEnvCfg"
    backends = {"fake": ".fake:FakeGo2Env"}
    display_name = "Unitree Go2 velocity task in Isaac Sim / Isaac Lab (go2_omniverse)"
    vendor, model = "abizovnuralem", "go2_omniverse"
    tags = ["unitree", "go2", "quadruped", "locomotion", "isaac-sim", "isaac-lab", "reinforcement-learning",
            "simulation", "gymnasium"]
    facts = [
        Fact("The upstream script defaults the Gymnasium task to Isaac-Velocity-Rough-Unitree-Go2-v0",
             source="upstream_code", ref=f"{ENV}:19"),
        Fact("The script creates the environment with gym.make(args_cli.task, cfg=env_cfg) after the Isaac Sim "
             "application has started", source="upstream_code", ref=f"{ENV}:384"),
        Fact("AppLauncher(args_cli) starts the Isaac Sim application before the environment is created",
             source="upstream_code", ref=f"{ENV}:50-51"),
        Fact("UnitreeGo2CustomEnvCfg extends LocomotionVelocityRoughEnvCfg", source="upstream_code",
             ref=f"{CFG}:321"),
        Fact("UnitreeGo2CustomEnvCfg replaces the scene robot with UNITREE_GO2_CFG",
             source="upstream_code", ref=f"{CFG}:326"),
        Fact("The action term is a JointPositionAction over every joint with use_default_offset=True and a scale "
             "of 0.5 in the base configuration", source="upstream_code", ref=f"{CFG}:195"),
        Fact("UnitreeGo2CustomEnvCfg reduces the joint-position action scale to 0.25", source="upstream_code",
             ref=f"{CFG}:330"),
        Fact("The physics timestep is 0.005 s and the policy action is applied every 4 physics steps",
             source="upstream_code", ref=f"{CFG}:296-300"),
        Fact("The episode length is 20.0 s", source="upstream_code", ref=f"{CFG}:298"),
        Fact("The policy observation concatenates base linear velocity, base angular velocity, projected gravity, "
             "velocity commands, joint positions, joint velocities, last actions and a height scan, in that order",
             source="upstream_code", ref=f"{CFG}:167-186"),
        Fact("The height scan is clipped to (-1.0, 1.0)", source="upstream_code", ref=f"{CFG}:181"),
        Fact("Projected gravity is corrupted with uniform noise in (-0.05, 0.05)", source="upstream_code",
             ref=f"{CFG}:172"),
        Fact("The height scanner samples a grid with 0.1 m resolution over a 1.6 m by 1.0 m extent",
             source="upstream_code", ref=f"{CFG}:118-119"),
        Fact("The velocity command ranges are all zero: lin_vel_x, lin_vel_y, ang_vel_z and heading are (0, 0)",
             source="upstream_code", ref=f"{CFG}:209-211"),
        Fact("The termination terms are a time-out and an illegal contact of the base body above a threshold of 1.0",
             source="upstream_code", ref=f"{CFG}:254-257"),
        Fact("The policy reads the observation group named policy", source="upstream_code", ref=f"{ENV}:407"),
        Fact("The main loop advances the environment with the policy actions", source="upstream_code",
             ref=f"{ENV}:454"),
        Fact("The environment base class is imported from isaaclab.envs, outside the clone", source="upstream_code",
             ref=f"{CFG}:32"),
        Fact("Isaac Sim 5.0 and Isaac Lab 0.54.3 are installed into a separate Python 3.11 virtual environment",
             source="vendor_doc", ref="JAZZY.md:61-69"),
        Fact("The twinbot mode drives the simulated Go2's joints from the physical robot's /lowstate stream; the "
             "simulation mirrors the real state rather than commanding it", source="vendor_doc",
             ref="README.md:29-37"),
    ]
    safe_state = ("on an e-stop the bridge stops stepping and refuses further step and reset calls until "
                  "mhs.safety.reset clears the latch; the last observation stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The gate checks the fake, which
    #: is a kinematic stand-in, so the contract declares F0 rather than the F1 of an Isaac Lab run.
    fidelity = {
        "engine": "gymnasium:Isaac-Velocity-Rough-Unitree-Go2-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake reseeds Python's random.Random from reset(seed), so one seed repeats its own "
                     "trajectory; Isaac Lab draws from numpy/torch generators and its seeding was not observed, so "
                     "the same seed is not claimed to reproduce an Isaac Sim trajectory",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a kinematic stand-in (F0): no rigid-body dynamics, contacts, actuator, sensor or noise "
            "model; the base motion and the height scan are placeholder kinematics and were never compared with "
            "an Isaac Sim run",
            "the action space is published as an unbounded 12-value Box because the clone configures a "
            "joint-position action over every joint (custom_rl_env.py:195) and states no numeric action bound; the "
            "12-value joint count comes from the external UNITREE_GO2_CFG (custom_rl_env.py:326), not the clone, "
            "and the real total_action_dim was not observed",
            "the policy observation is concatenated into one 235-value vector: 3 + 3 + 3 + 3 base terms, 12 joint "
            "positions, 12 joint velocities, 12 last actions and a 17 x 11 height scan (custom_rl_env.py:167-183, "
            ":118-119); the real Isaac Lab observation_space shape and bounds come from the external environment "
            "and were not observed",
            "the illegal-contact termination of custom_rl_env.py:255-257 is not modelled; only the 20 s time-out of "
            "custom_rl_env.py:298 truncates an episode",
            "the reward is a constant placeholder, not the sum of the configured reward terms, because those terms "
            "are external Isaac Lab MDP functions",
            "the fake draws its noise with Python's random.Random and returns Python floats rather than float32 "
            "arrays; a seed does not reproduce an Isaac Sim trajectory",
            "the sim backend gymnasium.make('Isaac-Velocity-Rough-Unitree-Go2-v0') was not run: it needs Isaac Sim, "
            "Isaac Lab, torch and a GPU (JAZZY.md:68-69), and the driver cannot pass cfg=UnitreeGo2CustomEnvCfg() "
            "because building that object needs the clone's imports, so a sim run would use the registered task's "
            "default configuration rather than the custom action scale and contact termination",
            "twinbot mirrors a physical Go2's state into the simulation (README.md:29-37), but this driver serves the "
            "simulation only and never commands the real robot",
        ],
    }
