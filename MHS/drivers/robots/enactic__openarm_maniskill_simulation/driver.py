"""OpenMHS driver for gh.enactic/openarm_maniskill_simulation: the OpenArm PickCube-v1 tabletop environment.

The clone is an overlay, not a standalone package: README.md:41-56 copies its URDF, agent package and four tabletop
task files into a ManiSkill v3.0.0b21 checkout (README.md:10).  The card names the Gymnasium helper, but the upstream
environment classes are thin subclasses of ManiSkill's ``BaseEnv``, which is not in the clone, so an AST read of
``PickCubeEnv`` cannot see ``reset``, ``step``, ``action_space`` or ``observation_space``; a Gymnasium-family fake
that supplies the two spaces would fail G7.NOT_UPSTREAM although the names exist through the external base.  This
package therefore uses a direct ``Driver`` over the environment object, the same shape as the LIBERO package, and
serves the three ``cap.world.*`` classes.

DEVIATION FROM THE CARD: the card says ``family-config``/``GymnasiumDriver``; the direct driver below serves the real
environment object instead of letting the Gymnasium bridge derive a space contract from an external base class.  The
action is the OpenArm end-effector delta and gripper opening of the agent's controller configs (openarm.py:100-109 and
:183-190); one tick is one environment step.  ``PickCube-v1`` is covered; the clone's other tasks (``PullCube-v1`` and
``PushCube-v1``, README.md:64-68) are not covered by this package.

The gate cannot import the clone (it imports SAPIEN, torch, numpy and ManiSkill, pick_cube.py:1-17), and package code
never imports or runs it, so ``backends`` names the package's own fake (fake.py), a pure Python stand-in.  The device is
simulated (R0): there is no hardware backend, no e-stop path to a machine and no operator-required limit.  Every Fact
cites a line of the clone at the pinned commit 3d3615aadabff11ce61ddc2e1608c1447cb3a59d; this package is
model-authored and unreviewed and is checked on the fake backend only.

The ``fidelity`` attribute is the contract of the model as deployed on the checked fake (spec 05-fidelity FID-002):
analytic, level F0, seeded with a parameter seed, no wall-clock time, lockstep, full reset, no snapshot.  The gaps say
what is not modelled.
"""

from collections.abc import Mapping

from mhs import canonical
from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, read

PICK = "mani_skill/envs/tasks/tabletop/pick_cube.py"
CFGS = "mani_skill/envs/tasks/tabletop/pick_cube_cfgs.py"
OPENARM = "mani_skill/agents/robots/openarm/openarm.py"
README = "README.md"
ACTION_LENGTH = 3


def _action_values(action_value):
    """The TCP delta and gripper opening from the action object the capability schema describes."""
    if not isinstance(action_value, Mapping):
        raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "action must be an object with tcp_delta and gripper")
    delta = action_value.get("tcp_delta")
    opening = action_value.get("gripper")
    if not isinstance(delta, (list, tuple)) or len(delta) != ACTION_LENGTH:
        raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                           f"action.tcp_delta must be an array of {ACTION_LENGTH} numbers")
    try:
        return [float(value) for value in delta], float(opening)
    except (TypeError, ValueError) as exc:
        raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                           "action.tcp_delta and action.gripper must contain only numbers") from exc


class OpenArmPickCube(Driver):
    device_id = "openarm-pick-cube"
    device_kind = "world.sim"
    resource_id = "world"
    mode = "simulated"
    risk = "R0"
    native = "mani_skill.envs.tasks.tabletop.pick_cube:PickCubeEnv"
    backends = {"fake": ".fake:FakePickCubeEnv"}
    display_name = "OpenArm PickCube-v1 (ManiSkill/SAPIEN)"
    vendor, model = "Enactic", "OpenArm PickCube-v1"
    tags = ["openarm", "mani-skill", "sapien", "pick-cube", "tabletop", "simulation",
            "reinforcement-learning", "robot-arm"]
    facts = [
        Fact("The repository is an overlay: its installation copies the openarm URDF, the agent package and the "
             "four tabletop task files into a ManiSkill checkout rather than installing a package",
             source="upstream_code", ref=f"{README}:41-56"),
        Fact("The required ManiSkill version is v3.0.0b21", source="upstream_code", ref=f"{README}:10"),
        Fact("The clone lists PushCube-v1, PullCube-v1 and PickCube-v1 as its runnable tasks",
             source="upstream_code", ref=f"{README}:64-68"),
        Fact("PickCube-v1 is registered with max_episode_steps=50", source="upstream_code", ref=f"{PICK}:34"),
        Fact("PickCubeEnv defaults the robot to the openarm agent", source="upstream_code", ref=f"{PICK}:52"),
        Fact("The openarm PickCube config uses cube_half_size 0.02, goal_thresh 0.025, cube_spawn_half_size 0.05, "
             "cube_spawn_center (0, 0) and max_goal_height 0.3", source="upstream_code", ref=f"{CFGS}:70-80"),
        Fact("The cube xy position is drawn uniformly from the spawn half-size around the spawn centre and its z is "
             "the cube half-size", source="upstream_code", ref=f"{PICK}:120-128"),
        Fact("The goal xy position uses the same draw and its z is a uniform draw up to max_goal_height above the "
             "cube z", source="upstream_code", ref=f"{PICK}:132-140"),
        Fact("The observation extras are is_grasped, tcp_pose and goal_pos, plus obj_pose, tcp_to_obj_pos and "
             "obj_to_goal_pos when the state observation is used", source="upstream_code", ref=f"{PICK}:148-161"),
        Fact("Success is the goal-site to cube distance at or below goal_thresh and a static robot",
             source="upstream_code", ref=f"{PICK}:163-175"),
        Fact("The dense reward adds a reaching term 1 - tanh(5 * distance), the grasp flag, a placement term and a "
             "static term, and sets 5 where success is true", source="upstream_code", ref=f"{PICK}:177-202"),
        Fact("OpenArm is registered with uid openarm and the URDF at robots/openarm/openarm.urdf",
             source="upstream_code", ref=f"{OPENARM}:16-19"),
        Fact("The openarm reset keyframe is a nine-element joint position array", source="upstream_code",
             ref=f"{OPENARM}:33-48"),
        Fact("The arm has seven openarm_joint joints and the gripper one openarm_finger_joint1",
             source="upstream_code", ref=f"{OPENARM}:50-61"),
        Fact("The arm's pd_ee_delta_pos controller bounds the end-effector position delta to -0.1 and 0.1",
             source="upstream_code", ref=f"{OPENARM}:100-109"),
        Fact("The gripper joint position controllers bound the opening to 0 and 0.0451", source="upstream_code",
             ref=f"{OPENARM}:174-190"),
        Fact("OpenArm.is_grasping checks pairwise contact forces with a minimum force of 0.5 N and a maximum contact "
             "angle of 85 degrees", source="upstream_code", ref=f"{OPENARM}:255-286"),
        Fact("OpenArm.is_static compares the largest absolute joint velocity with a threshold of 0.2",
             source="upstream_code", ref=f"{OPENARM}:288-290"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The contract of the model as deployed on the checked fake (spec 05-fidelity section 2).  The upstream is a
    #: SAPIEN environment; the fake is analytic and its gaps are listed below.
    fidelity = {
        "engine": "sapien:mani_skill:PickCube-v1",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "cap.world.reset.v1 passes the seed to the environment reset and this package's fake uses "
                     "Python's random.Random; the upstream draws its placements from ManiSkill's torch generator, "
                     "so one seed does not produce the same positions on the two",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is an analytic stand-in: the TCP and the cube move by placeholder kinematics, and there is no "
            "rigid-body dynamics, contact, friction, mass, actuator, joint controller or URDF model",
            "the grasp test is a distance test, not the pairwise contact-force test of OpenArm.is_grasping "
            "(openarm.py:255-286), and the robot is always static because the fake has no joint velocities",
            "the clone does not state the environment control timestep, so timestep_ms is 0: one tick is one "
            "environment step and no physical or wall-clock time is modelled",
            "the observation only carries the members of _get_obs_extra (pick_cube.py:148-161); ManiSkill's full "
            "state observation (robot qpos/qvel), the 128 x 128 camera observations and rendering are NOT COVERED",
            "the openarm URDF, the seven-joint arm and its controller are not modelled; the action limits are the "
            "controller config bounds of openarm.py:100-109 and :183-190, not a validated workspace",
            "only PickCube-v1 is covered; PullCube-v1 and PushCube-v1 are not",
            "the upstream SAPIEN environment was never opened or compared with the fake, and no physical device is "
            "modelled or validated",
        ],
    }

    # -- startup -------------------------------------------------------------
    def setup(self):
        """Open the environment at the driver's start seed and keep the first observation."""
        #: placeholder: the seed used before the first explicit reset
        self._seed = 0
        self._pending_seed = None
        self._episode = 0
        self._tick = 0
        self._last_observation = None
        self._last_reward = 0.0
        self._terminated = False
        self._truncated = False
        self._last_observation = self._compact(self.native.reset(seed=self._seed))
        self._episode = 1

    def _compact(self, observation):
        """Keep the observation members this driver publishes and make them JSON values."""
        if not isinstance(observation, Mapping):
            raise DriverFailed("MHS.DEVICE.FAULTED", "the environment returned no observation mapping")
        compact = {}
        for key in ("is_grasped", "tcp_pose", "goal_pos", "obj_pose", "tcp_to_obj_pos", "obj_to_goal_pos"):
            value = observation.get(key)
            if value is None:
                continue
            if isinstance(value, (list, tuple)):
                compact[key] = [float(item) for item in value]
            else:
                compact[key] = value
        if "tcp_pose" not in compact or "goal_pos" not in compact or "obj_pose" not in compact:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               "the environment observation lacks tcp_pose, goal_pos or obj_pose")
        return compact

    def _state_hash(self):
        """A digest of the state this driver publishes."""
        return canonical.digest({
            "observation": self._last_observation,
            "tick": self._tick,
            "episode": self._episode,
            "terminated": bool(self._terminated),
            "truncated": bool(self._truncated),
        })

    # -- resource state ------------------------------------------------------
    @read("observation", type="object",
          description="Last observation: is_grasped, tcp_pose (7), goal_pos (3), obj_pose (7), tcp_to_obj_pos (3) "
                      "and obj_to_goal_pos (3); camera images are not returned")
    def observation(self):
        return self._last_observation

    @read("reward", unit="1", description="Reward of the last step")
    def reward(self):
        return self._last_reward

    @read("terminated", type="boolean", description="Whether the task terminated on the last step")
    def terminated(self):
        return bool(self._terminated)

    @read("truncated", type="boolean", description="Whether the last step reached the 50-step episode limit")
    def truncated(self):
        return bool(self._truncated)

    @read("tick", type="integer", unit="1", description="Environment steps since the last reset")
    def tick(self):
        return int(self._tick)

    @read("episode", type="integer", unit="1", description="Resets since the driver started")
    def episode(self):
        return int(self._episode)

    @read("seed", type="integer", unit="1", description="Seed used by the last reset")
    def seed(self):
        return int(self._seed)

    # -- capabilities --------------------------------------------------------
    @action(cap="cap.world.reset.v1", action_name="reset",
            description="Reset PickCube-v1 to a seeded start state and return the initial observation",
            input={"seed": Field("integer", unit="1",
                                 description="Seed of the reset draw; the pending seed of cap.world.seed.v1 or the "
                                             "last seed is used when omitted")})
    def reset_world(self, seed=None):
        chosen = self._pending_seed if seed is None else int(seed)
        if chosen is None:
            chosen = self._seed
        if chosen < 0:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "seed must be a non-negative integer")
        self.check_cancelled()
        observation = self.native.reset(seed=chosen)
        self._seed = chosen
        self._pending_seed = None
        self._episode += 1
        self._tick = 0
        self._last_reward = 0.0
        self._terminated = False
        self._truncated = False
        self._last_observation = self._compact(observation)
        return {"observation": self._last_observation, "seed": chosen}

    @action(cap="cap.world.step.v1", action_name="step",
            description="Advance PickCube-v1 by bounded environment steps with one end-effector delta and gripper "
                        "opening",
            input={
                "ticks": Field("integer", unit="1",
                               description="Environment steps to advance; the action is applied at every step"),
                "action": Field("object",
                                description="End-effector delta and gripper opening applied at every step",
                                properties={
                                    "tcp_delta": Field("array", items=Field("number", unit="m"),
                                                       length=ACTION_LENGTH, description="End-effector delta x, y "
                                                                                         "and z in metres",
                                                       limit=Limit(min=-0.1, max=0.1, unit="m",
                                                                   source="upstream_code",
                                                                   ref=f"{OPENARM}:100-109")),
                                    "gripper": Field("number", unit="m",
                                                     description="Gripper joint position in metres (0 closed)",
                                                     limit=Limit(min=0, max=0.0451, unit="m",
                                                                 source="upstream_code",
                                                                 ref=f"{OPENARM}:183-190")),
                                }),
            })
    def step_world(self, action, ticks=1):
        delta, opening = _action_values(action)
        if not isinstance(ticks, int) or isinstance(ticks, bool) or ticks < 1:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "ticks must be a positive integer")
        if self._terminated or self._truncated:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "the episode has ended; reset the environment before stepping")
        total_reward = 0.0
        for _ in range(int(ticks)):
            self.check_cancelled()
            observation, reward, terminated, truncated, _info = self.native.step(
                {"tcp_delta": delta, "gripper": opening})
            self._tick += 1
            self._last_observation = self._compact(observation)
            self._last_reward = float(reward)
            self._terminated = bool(terminated)
            self._truncated = bool(truncated)
            total_reward += self._last_reward
            if self._terminated or self._truncated:
                break
        return {
            "observation": self._last_observation,
            "reward": total_reward,
            "terminated": bool(self._terminated),
            "truncated": bool(self._truncated),
            "tick": int(self._tick),
            "state_hash": self._state_hash(),
        }

    @action(cap="cap.world.seed.v1", action_name="seed",
            description="Set the seed the next reset uses without resetting the environment",
            input={"seed": Field("integer", unit="1", description="Seed used by the next reset")})
    def seed_world(self, seed):
        chosen = int(seed)
        if chosen < 0:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "seed must be a non-negative integer")
        self._pending_seed = chosen
        return {"seed": chosen, "accepted": True}

    def teardown(self):
        """Release the environment."""
        self.native.close()
