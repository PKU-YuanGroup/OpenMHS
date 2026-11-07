"""OpenMHS driver for gh.liorbenhorin/lerobot_so101_teleop: the Isaac Lab Rock-A-Stack Simple teleoperation task.

The clone registers ``Lerobot-So101-Teleop-Rock-A-Stack-Simple`` with Gymnasium; its entry point is
``isaaclab.envs:ManagerBasedRLEnv`` and its configuration is the local ``RockAStackSimpleEnvCfg``
(tasks/rock_a_stack/__init__.py:9-16).  The card's entry symbol is that configuration class, so ``native`` names it
while ``env_id`` names the registered task.  The family bridge derives the whole contract from the environment's
spaces: ``cap.world.step.v1`` takes ``{ticks, action}`` (a six-element joint-position Box),
``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated
(R0): there is no hardware backend and no operator-required limit.

The action is a joint-position target for the six named joints, with scale 1 and ``use_default_offset`` False
(tasks/base/base_env_cfg.py:141-146); the policy observation group is the robot's joint positions (:154-161) and the
visual group holds two 480 x 640 RGB camera terms (:163-186, :75-80, :105-110).  A policy step is 1/60 s
(decimation 2 with a 1/120 s simulation timestep, :294-305) and an episode is 5 s (:298).

Isaac Sim 5.1.0, Isaac Lab v2.3.0, Python 3.11, torch and a GPU are external dependencies (README.md:4-6, :38-47,
source/lerobot_so101_teleop/pyproject.toml:12), and the environment class lives in Isaac Lab, outside the clone.  The gate cannot install or
import any of that, so the ``fake`` backend is this package's own pure Python F0 stand-in (fake.py).  A backend name
that ``backends`` does not list (``sim``) is served by ``gymnasium.make(env_id)`` (GymnasiumDriver.open_native); that
path was not run here.  The clone's other three registered tasks (Base, Hard and Hard-Eval) are not served: one
package serves one environment, and this is the README's run example (README.md:72-75).

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002).
Every constant and rule cites a line of the clone at the pinned commit (9ea18b2c77df29e05c1c45bb1915dfd95514c470).
This package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

BASE = "source/lerobot_so101_teleop/tasks/base/base_env_cfg.py"
ROCK = "source/lerobot_so101_teleop/tasks/rock_a_stack/rock_a_stack_env_cfg.py"
REGISTER = "source/lerobot_so101_teleop/tasks/rock_a_stack/__init__.py"
ASSET = "source/lerobot_so101_teleop/assets/so101.py"
AGENT = "source/lerobot_so101_teleop/scripts/lerobot_agent.py"


class So101RockAStack(GymnasiumDriver):
    device_id = "so101-rock-a-stack"
    device_kind = "world.sim"
    mode, risk = "simulated", "R0"
    env_id = "Lerobot-So101-Teleop-Rock-A-Stack-Simple"
    native = "lerobot_so101_teleop.tasks.rock_a_stack.rock_a_stack_env_cfg:RockAStackSimpleEnvCfg"
    backends = {"fake": ".fake:FakeSo101RockAStackEnv"}
    display_name = "LeRobot SO-101 teleoperation in Isaac Lab: Rock-A-Stack Simple"
    vendor, model = "liorbenhorin", "lerobot_so101_teleop"
    tags = ["lerobot", "so-101", "robot-arm", "teleoperation", "rock-a-stack", "isaac-sim", "isaac-lab",
            "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("Lerobot-So101-Teleop-Rock-A-Stack-Simple is registered with gymnasium, with entry point "
             "isaaclab.envs:ManagerBasedRLEnv and env_cfg_entry_point "
             "rock_a_stack_env_cfg:RockAStackSimpleEnvCfg", source="upstream_code", ref=f"{REGISTER}:9-16"),
        Fact("RockAStackSimpleEnvCfg extends BaseEnvCfg", source="upstream_code", ref=f"{ROCK}:119"),
        Fact("BaseEnvCfg extends Isaac Lab's ManagerBasedRLEnvCfg", source="upstream_code", ref=f"{BASE}:280"),
        Fact("The action term is a JointPositionActionCfg over the six joints Rotation, Pitch, Elbow, Wrist_Pitch, "
             "Wrist_Roll and Jaw, with scale 1 and use_default_offset False", source="upstream_code",
             ref=f"{BASE}:141-146"),
        Fact("The policy observation group has one term, joint_pos, with corruption disabled", source="upstream_code",
             ref=f"{BASE}:154-161"),
        Fact("The visual observation group has camera_ego and camera_external RGB terms, with corruption disabled "
             "and concatenate_terms False", source="upstream_code", ref=f"{BASE}:163-186"),
        Fact("camera_ego is a 480 x 640 RGB camera", source="upstream_code", ref=f"{BASE}:75-80"),
        Fact("camera_external is a 480 x 640 RGB camera", source="upstream_code", ref=f"{BASE}:105-110"),
        Fact("The environment uses decimation 2 and a simulation timestep of 1/120 s, so one policy step is 1/60 s",
             source="upstream_code", ref=f"{BASE}:294-305"),
        Fact("The configured episode length is 5 s", source="upstream_code", ref=f"{BASE}:298"),
        Fact("The base environment declares rewards and terminations as None for teleoperation", source="upstream_code",
             ref=f"{BASE}:290-291"),
        Fact("The scene is configured with one environment (num_envs = 1)", source="upstream_code", ref=f"{BASE}:300"),
        Fact("The Rock-A-Stack Simple scene adds a rock-a-stack asset, a base plate and five rings named Ring01 to "
             "Ring05", source="upstream_code", ref=f"{ROCK}:26-59"),
        Fact("The reset event randomizes the base plate pose with the ranges written as x (0.15 - 0.2, 0.3 - 0.2), "
             "y (0.0, -0.15), z (0.04, 0.04) and yaw (-0.5, 0.5), and the five rings' offsets as x (-0.1, 0.1) and "
             "y (0.25, 0.1)", source="upstream_code", ref=f"{ROCK}:82-115"),
        Fact("The task creates a physics material with static friction 0.5, dynamic friction 0.5 and restitution 0.5",
             source="upstream_code", ref=f"{ROCK}:129-134"),
        Fact("The SO-101 robot asset spawns the USD file usd/SO-ARM101-USD.usd", source="upstream_code",
             ref=f"{ASSET}:9-11"),
        Fact("The SO-101 asset's initial joint positions are Rotation -0.2736, Pitch -0.6109, Elbow -0.0745, "
             "Wrist_Pitch 1.5148, Wrist_Roll -1.6034 and Jaw -0.1465", source="upstream_code", ref=f"{ASSET}:23-31"),
        Fact("The agent script creates the environment with gym.make(task, cfg=env_cfg)", source="upstream_code",
             ref=f"{AGENT}:77"),
        Fact("The agent script passes obs['policy'][0] and obs['visual'] to the dataset processor", source="upstream_code",
             ref=f"{AGENT}:154-158"),
        Fact("The teleop agent drives the simulation from a real leader arm on /dev/ttyACM0 with kind leader",
             source="upstream_code", ref=f"{AGENT}:100-107"),
        Fact("The README badges pin Isaac Sim 5.1.0 and Isaac Lab 2.3.0", source="vendor_doc", ref="README.md:4-5"),
        Fact("The README installs Isaac Sim 5.1.0 and Isaac Lab v2.3.0 before this repository", source="vendor_doc",
             ref="README.md:38-47"),
        Fact("The README installs this repository with uv pip install -e source/lerobot_so101_teleop",
             source="vendor_doc", ref="README.md:54"),
        Fact("The README describes a sample environment for the LeRobot SO-101 robot in Isaac Lab to collect "
             "demonstrations in simulation", source="vendor_doc", ref="README.md:17"),
        Fact("The README's run example is lerobot_agent --task Lerobot-So101-Teleop-Rock-A-Stack-Simple",
             source="vendor_doc", ref="README.md:72-75"),
        Fact("The package requires Python 3.11 or newer", source="vendor_doc",
             ref="source/lerobot_so101_teleop/pyproject.toml:12"),
    ]
    safe_state = ("the runtime latches the e-stop: no further step or reset is accepted until mhs.safety.reset "
                  "clears the latch, the simulation does not advance, and the last observation stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "isaaclab:Lerobot-So101-Teleop-Rock-A-Stack-Simple",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake reseeds Python's random.Random from reset(seed) or cap.world.seed.v1, but its "
                     "observation is a constant zero frame and the held joint positions do not depend on the seed, "
                     "so a seed changes no observable value; the upstream seed controls Isaac Lab's generators and "
                     "the Rock-A-Stack reset draws, and the two were not compared because the upstream stack was not "
                     "run",
        },
        "timestep_ms": 1000.0 * 2 / 120.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic F0 stand-in: no rigid-body dynamics, contacts, actuator, sensor, noise, renderer or domain "
            "randomisation; a step holds the commanded six joint positions and returns them, and the reward is a "
            "constant 0.0 (the clone declares rewards None, base_env_cfg.py:290)",
            "the real action space is the Box of Isaac Lab's action manager for the joint-position term; the clone "
            "states the six joints and the scale (base_env_cfg.py:141-146) but no numeric bound, so the fake "
            "publishes an unbounded six-element Box and the bridge has no action envelope to probe",
            "the real observation is a Dict of the policy group (the robot's joint positions) and the visual group "
            "(camera_ego and camera_external at 480 x 640 x 3 RGB each, base_env_cfg.py:75-80, :105-110, :163-186); "
            "the fake returns the same group names but 18 flat values per camera instead of a 480 x 640 x 3 image",
            "the upstream environment is vectorised over num_envs and returns batched tensors; the scene is "
            "configured with one environment (base_env_cfg.py:300) and the fake serves one environment with Python "
            "lists",
            "the Rock-A-Stack reset randomises the base plate, five rings, physics material and lighting "
            "(rock_a_stack_env_cfg.py:66-115); the fake's reset only reseeds its RNG and holds zero joint positions, "
            "so no randomised scene is modelled",
            "truncation: the fake ends an episode after 300 steps, derived from episode_length_s 5 s at the 1/60 s "
            "policy step (base_env_cfg.py:297-298, :305); the upstream truncation is implemented in Isaac Lab "
            "outside the clone and was not observed",
            "the sim path gymnasium.make('Lerobot-So101-Teleop-Rock-A-Stack-Simple') was not run: it needs Isaac Sim "
            "5.1.0, Isaac Lab v2.3.0, Python 3.11 and a GPU (README.md:4-5, :38-47), and the driver cannot pass a "
            "parsed cfg because building it imports the clone's modules",
            "the fake was never compared with an Isaac Sim run; Python lists are used instead of torch tensors and "
            "the cameras are constant placeholders",
        ],
    }
