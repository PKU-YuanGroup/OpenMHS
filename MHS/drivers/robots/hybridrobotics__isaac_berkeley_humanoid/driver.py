"""OpenMHS driver for gh.hybridrobotics/isaac_berkeley_humanoid: the Velocity-Rough-Berkeley-Humanoid-v0 task.

A GymnasiumDriver is configuration only: ``env_id`` names the registered task and the bridge derives the whole
contract from the environment spaces.  ``cap.world.step.v1`` takes ``{ticks, action}``, ``cap.world.reset.v1`` takes
``{seed, options}`` and ``cap.world.seed.v1`` takes ``{seed}``.  The device is simulated (R0): there is no hardware
backend, no e-stop path to a machine and no operator-required limit.

The clone is an Isaac Lab task package, not an environment implementation.  ``Velocity-Rough-Berkeley-Humanoid-v0``
is registered with the external entry point ``omni.isaac.lab.envs:ManagerBasedRLEnv`` and the in-tree configuration
class ``BerkeleyHumanoidRoughEnvCfg`` (``registration:34-42``).  The card's entry symbol used here is that class: it is
the class the fake is checked against (G7).  The Gymnasium interface (``action_space``, ``observation_space``,
``reset``, ``step``, ``close``) and the spaces are supplied by the external Isaac Lab base, which the clone does not
contain; G7 reports those five names as MAYBE_ABSENT warnings of a Gymnasium family driver.

The gate cannot import Isaac Sim or Isaac Lab (the task needs Isaac Sim 4.0.0 with Isaac Lab 1.0.0, README.md:25-27),
and package code never imports the clone.  The ``fake`` backend is therefore this package's pure Python interface
stand-in (fake.py): it reproduces the action and observation contract, not the Isaac Sim physics.  A backend name that
``backends`` does not list (``sim``) is served by ``gymnasium.make(env_id)`` (GymnasiumDriver.open_native); the upstream
training script passes ``cfg=env_cfg`` to ``gym.make`` and launches Isaac Sim first
(scripts/rsl_rl/train.py:39-40 and :89), so that path was not run here.

Every Fact cites a line or line range of the clone at the pinned commit
ffc7b2692917fdaf7cd87da53ada778e989dae35.  This package is model-authored and unreviewed: it is checked on the fake
backend only, and its evidence is ``contract_checked``, never an MHS-Device level.
"""

from mhs.driver import Fact, GymnasiumDriver

REGISTRATION = ("exts/berkeley_humanoid/berkeley_humanoid/tasks/locomotion/velocity/config/berkeley_humanoid/"
                "__init__.py")
ROUGH = ("exts/berkeley_humanoid/berkeley_humanoid/tasks/locomotion/velocity/config/berkeley_humanoid/"
         "rough_env_cfg.py")
FLAT = ("exts/berkeley_humanoid/berkeley_humanoid/tasks/locomotion/velocity/config/berkeley_humanoid/"
        "flat_env_cfg.py")
VELOCITY = "exts/berkeley_humanoid/berkeley_humanoid/tasks/locomotion/velocity/velocity_env_cfg.py"
ASSET = "exts/berkeley_humanoid/berkeley_humanoid/assets/berkeley_humanoid.py"
TRAIN = "scripts/rsl_rl/train.py"


class BerkeleyHumanoidRough(GymnasiumDriver):
    """The rough-terrain velocity-tracking task for the simulated Berkeley Humanoid."""

    device_id = "berkeley-humanoid-rough"
    env_id = "Velocity-Rough-Berkeley-Humanoid-v0"
    native = ("berkeley_humanoid.tasks.locomotion.velocity.config.berkeley_humanoid.rough_env_cfg:"
              "BerkeleyHumanoidRoughEnvCfg")
    backends = {"fake": ".fake:FakeBerkeleyHumanoidEnv"}
    mode = "simulated"
    risk = "R0"
    display_name = "Berkeley Humanoid rough-terrain velocity task (Isaac Lab)"
    vendor, model = "Hybrid Robotics", "Berkeley Humanoid"
    tags = ["berkeley-humanoid", "humanoid", "legged-locomotion", "velocity-tracking", "isaac-lab", "isaac-sim",
            "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("The repository shows the training code for Berkeley Humanoid with IsaacLab",
             source="vendor_doc", ref="README.md:10"),
        Fact("The installation guide asks for Isaac Lab v1.0.0 with Isaac Sim 4.0.0",
             source="vendor_doc", ref="README.md:25-27"),
        Fact("The extension is installed from exts/berkeley_humanoid with python -m pip install -e . after Isaac Lab "
             "is installed", source="vendor_doc", ref="README.md:29-34"),
        Fact("The documented training command runs scripts/rsl_rl/train.py with --task "
             "Velocity-Rough-Berkeley-Humanoid-v0; the play command uses Velocity-Rough-Berkeley-Humanoid-Play-v0",
             source="vendor_doc", ref="README.md:38-44"),
        Fact("Velocity-Rough-Berkeley-Humanoid-v0 is registered with entry point omni.isaac.lab.envs:"
             "ManagerBasedRLEnv and env_cfg_entry_point rough_env_cfg.BerkeleyHumanoidRoughEnvCfg",
             source="upstream_code", ref=f"{REGISTRATION}:34-42"),
        Fact("Velocity-Flat-Berkeley-Humanoid-v0 is registered with the same ManagerBasedRLEnv entry point and "
             "flat_env_cfg.BerkeleyHumanoidFlatEnvCfg as its environment configuration",
             source="upstream_code", ref=f"{REGISTRATION}:14-22"),
        Fact("Velocity-Rough-Berkeley-Humanoid-Play-v0 registers "
             "rough_env_cfg.BerkeleyHumanoidRoughEnvCfg_PLAY", source="upstream_code",
             ref=f"{REGISTRATION}:44-52"),
        Fact("BerkeleyHumanoidRoughEnvCfg subclasses LocomotionVelocityRoughEnvCfg and installs "
             "BERKELEY_HUMANOID_CFG as the scene robot", source="upstream_code", ref=f"{ROUGH}:17-22"),
        Fact("The rough configuration removes the height_scan observation term and the height scanner",
             source="upstream_code", ref=f"{ROUGH}:26-27"),
        Fact("BerkeleyHumanoidFlatEnvCfg subclasses BerkeleyHumanoidRoughEnvCfg and changes the terrain to a plane "
             "without a terrain generator", source="upstream_code", ref=f"{FLAT}:11-23"),
        Fact("LocomotionVelocityRoughEnvCfg subclasses ManagerBasedRLEnvCfg and defines the scene, observations, "
             "actions, commands, rewards, terminations, randomization and curriculum",
             source="upstream_code", ref=f"{VELOCITY}:342-356"),
        Fact("The action is a joint-position target over every joint with scale 0.5 and use_default_offset=True",
             source="upstream_code", ref=f"{VELOCITY}:115"),
        Fact("The policy observation group concatenates base_lin_vel, base_ang_vel, projected_gravity, "
             "velocity_commands, hip_pos, kfe_pos, ffe_pos, faa_pos, joint_vel and actions",
             source="upstream_code", ref=f"{VELOCITY}:126-143"),
        Fact("The policy group sets enable_corruption=True and concatenate_terms=True",
             source="upstream_code", ref=f"{VELOCITY}:152-154"),
        Fact("The hip-position term selects joints matching .*HR, .*HAA and .*HFE; the knee term .*KFE, the "
             "foot-roll term .*FFE, the foot-yaw term .*FAA, and the joint-velocity and last-action terms cover "
             "the whole joint set", source="upstream_code", ref=f"{VELOCITY}:134-143"),
        Fact("The asset init_state declares 12 joints: LL_HR, LR_HR, LL_HAA, LR_HAA, LL_HFE, LR_HFE, LL_KFE, "
             "LR_KFE, LL_FFE, LR_FFE, LL_FAA and LR_FAA", source="upstream_code", ref=f"{ASSET}:96-109"),
        Fact("The environment sets decimation 4, episode_length_s 20.0 and sim.dt 0.005 s, so one control step is "
             "4 * 0.005 = 0.02 s", source="upstream_code", ref=f"{VELOCITY}:361-364"),
        Fact("The command ranges are lin_vel_x and lin_vel_y from -1.0 to 1.0, ang_vel_z from -1.0 to 1.0 and "
             "heading from -pi to pi, resampled every 10.0 s", source="upstream_code",
             ref=f"{VELOCITY}:97-107"),
        Fact("The reset events sample the base pose x and y from -0.5 to 0.5 and yaw from -3.14 to 3.14, the base "
             "velocities from -0.5 to 0.5 and the joint-position scale from 0.5 to 1.5",
             source="upstream_code", ref=f"{VELOCITY}:223-246"),
        Fact("The termination terms are a time-out and an illegal contact of the torso with threshold 1.0",
             source="upstream_code", ref=f"{VELOCITY}:315-318"),
        Fact("The training script launches the Isaac Sim application with AppLauncher",
             source="upstream_code", ref=f"{TRAIN}:39-40"),
        Fact("The training script imports berkeley_humanoid.tasks so the gym.register calls run",
             source="upstream_code", ref=f"{TRAIN}:51-52"),
        Fact("The training script creates the environment with gym.make(task, cfg=env_cfg, render_mode=...)",
             source="upstream_code", ref=f"{TRAIN}:88-89"),
        Fact("The training script calls env.seed(agent_cfg.seed)", source="upstream_code", ref=f"{TRAIN}:115-117"),
        Fact("setup.py declares python_requires >=3.10 and an Isaac Sim 4.0.0 classifier",
             source="upstream_code", ref="exts/berkeley_humanoid/setup.py:39-44"),
        Fact("The LICENCE file states SPDX-License-Identifier: BSD-3-Clause", source="upstream_code",
             ref="LICENCE:5"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop no step or reset is accepted until "
                  "mhs.safety.reset clears the latch, and the last world state stays readable")
    #: The fidelity contract of the model this package serves on the fake backend (spec 05-fidelity).  The upstream
    #: task is an Isaac Sim rigid-body simulation, but this package ships no sim backend and the fake models no
    #: dynamics, so the level is F0 and the gaps carry every omission.  The timestep is the configured control step:
    #: decimation 4 times sim.dt 0.005 s is 20 ms (velocity_env_cfg.py:361-364).
    fidelity = {
        "engine": "mhs-fake:Velocity-Rough-Berkeley-Humanoid-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed=...) and cap.world.seed.v1 set the seed of the next reset.  The fake reseeds "
                     "Python's random.Random and draws its three placeholder base values from it, so one seed "
                     "repeats the fake's own reset and trajectory.  The upstream reset uses Isaac Lab generators "
                     "(velocity_env_cfg.py:223-246) and its seeding was not observed, so the same seed is not "
                     "claimed to reproduce an Isaac Sim trajectory.",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a kinematic interface stand-in (F0): no rigid-body dynamics, contacts, friction, "
            "actuators, sensors, terrain, noise, reward or rendering; the upstream task runs Isaac Sim 4.0.0 and "
            "Isaac Lab 1.0.0 (README.md:25-27), which this package does not install or run, and no simulator run "
            "is claimed",
            "the fake serves one environment with a 12-value action and a 15-value observation (3 placeholder base "
            "values and the 12-value last-action term), while the upstream scene defaults to 4096 environments "
            "(velocity_env_cfg.py:347) and the policy observation group concatenates ten terms "
            "(velocity_env_cfg.py:126-143); the real flattened width is built by Isaac Lab outside the clone and "
            "was not observed, so the fake returns a smaller observation and the other terms are not covered",
            "every observation value except the 12-value last-action tail is a fixed placeholder; no base "
            "velocity, projected gravity, command, joint position or joint velocity is simulated, and the reset "
            "randomizations of velocity_env_cfg.py:223-246 are not modelled",
            "the fake never terminates or truncates; the configured time-out and torso-contact termination "
            "(velocity_env_cfg.py:315-318) and the time-limit rule of the external ManagerBasedRLEnv are not "
            "modelled",
            "the upstream action space is created by the external ManagerBasedRLEnv and was not inspected; the "
            "fake exposes an unbounded 12-value Box and does not clamp, while the configured joint-position action "
            "scales by 0.5 around the default offsets (velocity_env_cfg.py:115)",
            "the sim backend through gymnasium.make was not run: the registered task needs Isaac Lab with Isaac "
            "Sim, and the training script launches Isaac Sim and passes cfg=env_cfg to gym.make "
            "(scripts/rsl_rl/train.py:39-40 and :88-89)",
            "no snapshot or restore: the clone shows no get_state/set_state for the environment, and the fake "
            "offers none",
            "no physical device is modelled and nothing was validated against the Berkeley Humanoid hardware",
        ],
    }
