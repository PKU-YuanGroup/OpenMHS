"""OpenMHS driver for gh.edvardsz/ur5_gym: the ReachUR5-v0 task (a simulated UR5/RG2 reach environment).

The repository is a legacy Gym 0.21 environment for Ignition Gazebo: ``ReachUR5-v0`` is registered with the
out-of-clone entry point ``gym_ignition.runtimes.gazebo_runtime:GazeboRuntime`` and the in-clone task class
``gym_ur5.tasks.reach:Reach`` (``src/gym_ur5/__init__.py:8-18``, ``src/gym_ur5/tasks/reach.py:22``).  The card's
``entry_symbols`` are those in-clone task classes, not the environment class, so this package is a direct ``Driver``
over the task class instead of a ``GymnasiumDriver`` configuration: the fake can then implement exactly the task's
own public methods (gate G7), and the driver serves the ``cap.world.*`` contract from them.

The device is simulated (R0): no physical UR5 or RG2 is driven, there is no hardware backend and no operator-required
bound.  The fake is a kinematic stand-in: it applies the task's own action arithmetic to a point end effector and
never runs Gazebo, inverse kinematics, the joint controllers or the Fuel asset downloads.  The fidelity ``gaps`` say
so.  Every Fact and Limit cites a line of the clone at commit d059332a01d320a48617d5a46edb9856f3a4c86d.

This package is model-authored and unreviewed; it is checked on the fake backend only.
"""

import hashlib
import json
import math

from mhs.driver import Cancelled, Driver, DriverFailed, Fact, Field, Limit, action, read

INIT = "src/gym_ur5/__init__.py"
REACH = "src/gym_ur5/tasks/reach.py"
RANDOMIZER = "src/gym_ur5/randomizers/ur5_rg2_no_rand.py"
UR5_RG2 = "src/gym_ur5/models/robots/ur5_rg2.py"


class ReachUR5(Driver):
    device_id = "ur5-gym-reach"
    device_kind = "world.sim"
    resource_id = "world"
    mode = "simulated"
    risk = "R0"
    native = "gym_ur5.tasks.reach:Reach"
    backends = {"fake": ".fake:FakeReach"}
    display_name = "UR5/RG2 Reach (Ignition Gazebo simulation)"
    vendor, model = "EdvardsZ", "ReachUR5-v0"
    tags = ["gripper", "ignition-gazebo", "reinforcement-learning", "robot", "rg2", "simulation", "ur5"]
    facts = [
        Fact("The README describes a deep reinforcement learning environment in Ignition Gazebo for a UR5 arm "
             "with an RG2 gripper", source="vendor_doc", ref="README.md:2"),
        Fact("The README tells the user to install Ignition Gazebo before installing the package", source="vendor_doc",
             ref="README.md:5"),
        Fact("setup.cfg install_requires lists gym-ignition and numpy", source="upstream_code", ref="setup.cfg:22-24"),
        Fact("requirements.txt pins gym~=0.21.0, numpy~=1.22.3 and scipy~=1.8.0", source="upstream_code",
             ref="requirements.txt:1-3"),
        Fact("The package imports register from gym.envs.registration, the legacy Gym 0.21 API", source="upstream_code",
             ref=f"{INIT}:2"),
        Fact("ReachUR5-v0 is registered with entry_point gym_ignition.runtimes.gazebo_runtime:GazeboRuntime, "
             "max_episode_steps 100, agent_rate 2.5, physics_rate 100.0 and real_time_factor max_float",
             source="upstream_code", ref=f"{INIT}:8-18"),
        Fact("ReachDictUR5-v0 and PickAndPlaceUR5-v0 are also registered with max_episode_steps 50 and different "
             "task classes; this package serves ReachUR5-v0 only", source="upstream_code", ref=f"{INIT}:20-44"),
        Fact("gym_ur5.tasks.reach defines Reach(task.Task, abc.ABC)", source="upstream_code", ref=f"{REACH}:22"),
        Fact("The workspace centre is [0.50143738, 0.15, 1.36] and the workspace volume is [0.4, 0.4, 0.4]",
             source="upstream_code", ref=f"{REACH}:31-32"),
        Fact("The action space is Box(-1.0, 1.0, shape=(3,), float32) and the observation space is Box(-inf, inf, "
             "shape=(6,), float32)", source="upstream_code", ref=f"{REACH}:37-49"),
        Fact("set_action adds action * 0.1 to the end-effector position and clamps every coordinate to the "
             "workspace centre +- half the volume", source="upstream_code", ref=f"{REACH}:50-74"),
        Fact("get_observation returns the end-effector position concatenated with the target position, six values",
             source="upstream_code", ref=f"{REACH}:76-81"),
        Fact("get_reward returns +1.0 when the distance to the target is below 0.05 and -1.0 otherwise",
             source="upstream_code", ref=f"{REACH}:83-90"),
        Fact("get_info returns is_success True when the distance to the target is at most 0.05", source="upstream_code",
             ref=f"{REACH}:92-98"),
        Fact("is_done returns the task's _is_done flag", source="upstream_code", ref=f"{REACH}:99-101"),
        Fact("reset_task clears _is_done and sets the eight joint position targets to the fixed configuration "
             "[1.47838380, -2.15699582, -0.000081469105, -2.52916159, 1.56735617, -0.0925439234, 0, 0]",
             source="upstream_code", ref=f"{REACH}:103-111"),
        Fact("get_joints returns the six arm joints and the two RG2 finger joints", source="upstream_code",
             ref=f"{REACH}:113-121"),
        Fact("get_target_position returns the base position of the RedPoint model", source="upstream_code",
             ref=f"{REACH}:163-165"),
        Fact("get_ee_position returns the world position of the model's tool0 link", source="upstream_code",
             ref=f"{REACH}:173-175"),
        Fact("The randomizer inserts the UR5RG2 model at [0.5, 0.5, 1.02] when the scene has no ur5_rg2 model",
             source="upstream_code", ref=f"{RANDOMIZER}:59"),
        Fact("The workspace random target is drawn uniformly from the workspace box with numpy's global generator",
             source="upstream_code", ref=f"{REACH}:167-171"),
        Fact("The UR5 has six arm joints with limits +-6.28319 rad and the RG2 two finger joints with limits 0 to "
             "0.52359878 rad", source="upstream_code", ref=f"{UR5_RG2}:104-113"),
    ]
    safe_state = ("the simulation stops advancing: no step, reset or seed is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch, and the world state is kept and stays readable")
    #: ReachUR5-v0 is registered with max_episode_steps=100 (src/gym_ur5/__init__.py:11); the Gym TimeLimit wrapper
    #: that gym.make adds is replicated in step().
    _max_episode_steps = 100
    #: The fidelity contract of the model as served (spec 05-fidelity FID-002).  The fake is kinematic (F0); the
    #: upstream Ignition Gazebo model would be a rigid-body (F1) model but was never run or validated here.
    fidelity = {
        "engine": "gym-ignition:ReachUR5-v0 (Ignition Gazebo; the package serves the task class with a kinematic fake)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "cap.world.seed.v1 and cap.world.reset.v1 accept a seed and the driver echoes it; the fake is "
                     "deterministic and repeats a trajectory, but its start position and target are fixed placeholder "
                     "test data, so a different seed does not change the scene.  Upstream the randomizer draws the "
                     "RedPoint target from numpy's global generator (reach.py:167-171), so a seeded run there can "
                     "differ; this package never ran the upstream environment",
        },
        "timestep_ms": 400.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a kinematic stand-in, not Ignition Gazebo: it has no rigid-body dynamics, contacts, joint "
            "controllers, inverse kinematics, gravity, friction or model assets, and it was not compared with an "
            "Ignition run; one tick applies the task's action arithmetic (reach.py:50-74) to a point end effector",
            "the start position and the RedPoint target are fixed placeholder test data in the fake, not a "
            "simulation of the upstream randomizer; a seed is accepted and echoed but does not change the fake's "
            "scene, and the seeded determinism claim is therefore not exercised by this package",
            "the upstream environment is the legacy Gym 0.21 API (requirements.txt:1) whose registered entry point "
            "is gym_ignition.runtimes.gazebo_runtime:GazeboRuntime; this driver serves the in-clone task class "
            "directly and replicates the TimeLimit at max_episode_steps=100 in step(), not the Gym wrappers "
            "(PassiveEnvChecker, OrderEnforcing, render mode)",
            "the observation is six Python floats (end-effector position followed by target position, reach.py:76-81); "
            "upstream returns a float32 numpy array of the same six values",
            "the task's set_action calls inverse kinematics and set_joint_position_targets (reach.py:67-72); the "
            "fake moves the end-effector point directly and does not model the UR5 joints, the RG2 fingers, the "
            "table, the cube or the RedPoint asset downloads",
            "no rendering, no camera or image, no Fuel asset download and no network path is served; nothing was "
            "validated against a real UR5 or RG2 gripper",
            "ReachDictUR5-v0 and PickAndPlaceUR5-v0 are NOT COVERED: their dict observations (reach_dict.py:45-57) "
            "and pick-and-place state, finger actions and cube respawn (pick_and_place.py:37-57, :59-82, :84-104, "
            ":260-282) are not served by this package",
            "snapshot and restore are not offered: the task class exposes no get_state/set_state, so "
            "snapshot_restore is false",
        ],
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._observation = {}
        self._reward = 0.0
        self._terminated = False
        self._truncated = False
        self._tick = 0
        self._episode = 0
        self._seed = 0
        self._pending_seed = None
        self._info = {}

    # -- state -----------------------------------------------------------------
    @read("observation", type=Field("object", description="Last observation: end-effector and target position"))
    def observation(self):
        return self._observation

    @read("reward", type=Field("number", description="Reward of the last transition (0.0 before the first step)"))
    def reward(self):
        return self._reward

    @read("terminated", type="boolean", description="Whether the task reported done")
    def terminated(self):
        return self._terminated

    @read("truncated", type="boolean", description="Whether the 100-step episode limit was reached")
    def truncated(self):
        return self._truncated

    @read("tick", type="integer", unit="1", description="Transitions since the last reset")
    def tick(self):
        return self._tick

    @read("episode", type="integer", unit="1", description="Resets since the driver opened")
    def episode(self):
        return self._episode

    @read("seed", type=Field("integer", unit="1", description="Seed of the last reset (0 until one is given)"))
    def seed(self):
        return self._seed

    @read("info", type="object", description="Task info: is_success")
    def info(self):
        return self._info

    # -- capabilities ----------------------------------------------------------
    @action(cap="cap.world.reset.v1", description="Reset the Reach task to its start configuration",
            input={"seed": Field("integer", unit="1", description="Seed accepted for the next episode"),
                   "options": Field("object", description="Reset options (the task accepts none)")})
    def reset_world(self, seed=None, options=None):
        if options:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                               "Reach.reset_task takes no reset options")
        if seed is None:
            seed = self._pending_seed if self._pending_seed is not None else (
                self._seed if self._seed is not None else 0)
        seed = int(seed)
        self._pending_seed = None
        self.native.reset_task()
        self._seed = seed
        self._episode += 1
        self._tick = 0
        self._terminated = False
        self._truncated = False
        self._reward = 0.0
        self._observe()
        return {"observation": self._observation, "seed": seed}

    @action(cap="cap.world.seed.v1", description="Set the seed used by the next reset",
            input={"seed": Field("integer", unit="1", description="Seed used by the next reset")})
    def seed_world(self, seed):
        self._pending_seed = int(seed)
        return {"seed": int(seed), "accepted": True}

    @action(cap="cap.world.step.v1", description="Advance the Reach task by ticks with one action",
            input={
                "action": Field("object", description="Action applied at every tick", properties={
                    "values": Field("array", unit="1", length=3, description="Normalized end-effector displacement "
                                                                             "in x, y and z",
                                    items=Field("number", unit="1"),
                                    limit=Limit(min=-1.0, max=1.0, source="upstream_code",
                                                ref=f"{REACH}:39-42"))}),
                "ticks": Field("integer", unit="1", description="Transitions to advance; the action is applied at "
                                                                 "every tick"),
            })
    def step(self, action, ticks=1):
        if self._episode == 0:
            self.reset_world()
        if self._terminated or self._truncated:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "the episode has ended (terminated or truncated); reset the task first")
        values = [float(value) for value in action["values"]]
        reward_total = 0.0
        for _ in range(int(ticks)):
            if self.cancelled():
                raise Cancelled("cancelled between world ticks")
            if self._terminated or self._truncated:
                break
            self.native.set_action(values)
            step_reward = float(self.native.get_reward())
            if not math.isfinite(step_reward):
                raise DriverFailed("MHS.DEVICE.FAULTED", "the task returned a non-finite reward")
            reward_total += step_reward
            self._reward = step_reward
            self._observe()
            self._terminated = bool(self.native.is_done())
            self._tick += 1
            if self._tick >= self._max_episode_steps:
                self._truncated = True
        return {
            "observation": self._observation,
            "reward": reward_total,
            "terminated": self._terminated,
            "truncated": self._truncated,
            "tick": self._tick,
            "state_hash": self._state_hash(),
        }

    # -- helpers ---------------------------------------------------------------
    def _observe(self):
        values = [float(value) for value in self.native.get_observation()]
        self._observation = {"values": values}
        self._info = dict(self.native.get_info())

    def _state_hash(self):
        state = {
            "observation": self._observation,
            "tick": self._tick,
            "episode": self._episode,
            "terminated": self._terminated,
            "truncated": self._truncated,
        }
        payload = json.dumps(state, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return "sha256:" + hashlib.sha256(payload).hexdigest()
