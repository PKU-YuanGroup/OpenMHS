"""OpenMHS driver for gh.emb-ai/robobenchmart: the MoveFromBoardToBoardVanishContEnv ManiSkill environment.

A GymnasiumDriver is configuration: ``env_id`` names the registered environment and the Gymnasium bridge derives
``cap.world.step.v1`` (``{ticks, action}``), ``cap.world.reset.v1`` (``{seed, options}``) and ``cap.world.seed.v1``
(``{seed}``) from the environment.  The device is simulated (R0): it has no hardware backend, no e-stop path to a
machine and no operator-required limit.

The card's ``mock_strategy.preferred`` is ``upstream-sim``: on a machine with ManiSkill, SAPIEN, Vulkan and the
generated scene data (README.md:15 and :45-55), a backend name that ``backends`` does not list (``sim``) is served
by ``gymnasium.make(env_id, **env_kwargs)``.  That path was not run here.  The gate uses the package's own analytic
fake (fake.py), which needs neither ManiSkill nor the scene data and never imports the clone.  This package is
model-authored and unreviewed: it was checked on the fake backend only.

``_WorldBridge`` removes one unnecessary read of the upstream object: the real observation is a ManiSkill dictionary
with three camera images (scripts/eval_policy_client.py:32-44), and the clone cannot name an ``observation_space``
(the attribute belongs to ManiSkill's external BaseEnv), so the package does not derive an observation schema.  The
catalogue classes publish ``observation`` as an open object; only the action schema and its limits need the space.
"""

from mhs.bridge.gymnasium import GymnasiumBridge
from mhs.driver import Fact, GymnasiumDriver

# Paths in the clone at commit 33ca547ffeb4e4aac9af53bd685b17c05b971fc8.
ENV = "dsynth/envs/move_from_board_to_board.py"
BASE = "dsynth/envs/darkstore_cell_base.py"
EVAL = "scripts/eval_policy_client.py"
README = "README.md"


class _WorldBridge(GymnasiumBridge):
    """The Gymnasium bridge without observation-space derivation (the fake returns its JSON observation already).

    ``cap.world.step.v1`` already declares ``observation`` as an open object.  Reading ``env.observation_space``
    would only be useful to normalise a native array; the upstream class inherits that attribute from ManiSkill's
    BaseEnv, which is not in the clone, and this package does not publish an observation schema it cannot source.
    """

    @property
    def observation_space(self):
        return None


class RoboBenchMart(GymnasiumDriver):
    device_id = "robobenchmart"
    env_id = "MoveFromBoardToBoardVanishContEnv"
    native = "dsynth.envs.move_from_board_to_board:MoveFromBoardToBoardVanishContEnv"
    backends = {"fake": ".fake:FakeMoveFromBoardToBoardVanishContEnv"}
    display_name = "RoboBenchMart MoveFromBoardToBoardVanishContEnv (fake stand-in)"
    vendor, model = "emb-ai", "RoboBenchMart MoveFromBoardToBoardVanishContEnv"
    tags = ["robobenchmart", "retail", "manipulation", "reinforcement-learning", "simulation", "gymnasium",
            "mani-skill"]
    facts = [
        Fact("The repository describes dsynth as specialized ManiSkill environments for retail setups, with scene "
             "generation, motion planning and policy evaluation", source="vendor_doc", ref=f"{README}:7"),
        Fact("The ManiSkill simulator requires the Vulkan API", source="vendor_doc", ref=f"{README}:15"),
        Fact("The README instructs downloading RoboCasa assets and the RoboBenchMart assets from separate sources",
             source="vendor_doc", ref=f"{README}:45-55"),
        Fact("MoveFromBoardToBoardVanishContEnv is registered with max_episode_steps=200000", source="upstream_code",
             ref=f"{ENV}:459-460"),
        Fact("MoveFromBoardToBoardContEnv documents the task as picking the target item and placing it one board "
             "higher, with the robot spawned near the shelf", source="upstream_code", ref=f"{ENV}:335-336"),
        Fact("DarkstoreCellBaseEnv derives from ManiSkill's BaseEnv", source="upstream_code", ref=f"{BASE}:29"),
        Fact("The environment constructor requires config_dir_path, the scene directory", source="upstream_code",
             ref=f"{BASE}:33-41"),
        Fact("reset accepts seed and options and reads reconfigure and robot_init_pose_seed from the options",
             source="upstream_code", ref=f"{BASE}:79-85"),
        Fact("The policy client builds the environment with gym.make(env_id, config_dir_path=<scene dir>, "
             "num_envs=1, control_mode=..., ...)", source="upstream_code", ref=f"{EVAL}:100-110"),
        Fact("The policy client resets the environment with a seed and an options dictionary", source="upstream_code",
             ref=f"{EVAL}:161"),
        Fact("The policy client calls env.step(action) and receives obs, reward, done, trunc and info",
             source="upstream_code", ref=f"{EVAL}:175"),
        Fact("The policy client zeroes action[8] and action[9], so its action vectors have at least ten float "
             "components", source="upstream_code", ref=f"{EVAL}:171-174"),
        Fact("The policy client reads three RGB camera images and the agent qpos from the observation",
             source="upstream_code", ref=f"{EVAL}:32-44"),
        Fact("The target size is 0.3 m on each axis", source="upstream_code", ref=f"{ENV}:26"),
        Fact("The placement tolerance is half of target_sizes on each axis", source="upstream_code",
             ref=f"{ENV}:263"),
        Fact("The robot is static when its q velocity is below 0.2", source="upstream_code", ref=f"{ENV}:285"),
        Fact("A non-target product counts as displaced when its pose leaves the initial pose by more than "
             "rtol/atol 0.1", source="upstream_code", ref=f"{ENV}:300"),
        Fact("The success condition is object placed and robot static and no non-target product displaced",
             source="upstream_code", ref=f"{ENV}:314-320"),
        Fact("The interboard height is 0.397 m", source="upstream_code", ref=f"{ENV}:368-370"),
        Fact("The task docstring says the target item must be within TARGET_POS_THRESH of the goal, other items "
             "move by no more than 0.1 m and the robot q velocity stays below 0.2", source="upstream_code",
             ref=f"{ENV}:452-455"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the world state is kept and stays readable")
    #: The model as deployed is the package's analytic fake (FID-002), not the upstream ManiSkill simulator.
    fidelity = {
        "engine": "analytic:dsynth-fake",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the initial joint state and the kinematic update is "
                     "deterministic, so one implementation repeats a trajectory for the same seed and actions; the "
                     "fake uses Python's random.Random and was never compared with ManiSkill's RNG",
        },
        "timestep_ms": 0.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is kinematic: each joint moves by a fixed placeholder gain per step; there are no "
            "rigid-body dynamics, contacts, actuators, sensors, cameras, lighting or textures",
            "the real environment runs ManiSkill/SAPIEN and needs Vulkan plus scene data and assets downloaded "
            "separately (README.md:15, README.md:45-55); the fake was never compared with it and the sim path was "
            "not run",
            "NOT COVERED: the real observation is a ManiSkill dictionary with three RGB camera streams and the "
            "agent qpos (scripts/eval_policy_client.py:32-44); the fake returns only ten joint positions and "
            "publishes no observation schema",
            "the action space is a ten-value Box in [-1, 1] (test data of the fake); the real action space comes "
            "from the ManiSkill controller and robot_uids and is not stated in the clone",
            "the scene layout, product placement and target-product geometry are not modelled; the fake always "
            "reports success false",
            "no wall-clock pacing: realtime_factor 0, and the clone states no fixed timestep, so timestep_ms is 0 "
            "and ticks are uncalibrated control steps",
            "snapshot and restore are not offered: the fake exposes no get_state/set_state",
        ],
    }

    def make_bridge(self, native):
        """Build the bridge with the class's environment configuration (the fake is already constructed)."""
        cls = type(self)
        origin = f"the {self.backend} backend {dict(cls.backends).get(self.backend)}" if native is not None else None
        return _WorldBridge(env=native, env_id=cls.env_id, seed=cls.seed, device_id=self.device_id,
                            autoreset=cls.autoreset, max_ticks=cls.max_ticks, env_origin=origin)
