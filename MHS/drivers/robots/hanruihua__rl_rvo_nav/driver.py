"""OpenMHS driver for gh.hanruihua/rl_rvo_nav: the multi-robot navigation environment ``mrnav-v1``.

DEVIATION FROM THE CARD: the card's ``gymnasium`` family cannot express this upstream.  ``mrnav`` is a ``gym.Env``
subclass but it defines no ``step``: its transition method is ``step_ir(action, vel_type='omni', stop=True)``, which
takes one absolute velocity command per robot and returns four per-robot lists (``mrnav.py:18-30``), and its
``reset(mode=0)`` resets the robots but takes no seed (``mrnav.py:38-40``).  A ``GymnasiumDriver`` is configuration
only and the Gymnasium bridge calls ``env.step`` and ``env.reset(seed=...)``, so no fake could be honest about both the
upstream surface and the bridge.  This package is therefore a direct :class:`mhs.driver.Driver` over the upstream
class named by the card (``native = "gym_env.envs:mrnav"``), with a package fake.

What is served:

* ``cap.world.step.v1`` -- ``{ticks, action}`` where ``action`` is ``{robots: [[vx, vy], ...]}``, one absolute
  velocity command per robot (m/s), and ``ticks`` calls ``step_ir`` once each.  The output observation is an object
  ``{robots, rewards, dones, infos}`` holding the upstream's four lists; the class's scalar ``reward`` is their sum and
  ``terminated`` is true when any robot reports ``done``.  The upstream has no truncation, so ``truncated`` is false.
* ``cap.world.reset.v1`` -- ``{options: {mode}}`` calls ``mrnav.reset(mode=...)`` and returns the reset observation.
  The clone has no seed argument, so the seed input is not accepted and the required class output field ``seed`` is 0
  (the fidelity contract declares ``determinism.kind = none``).

The action space ``Box([-1,-1],[1,1])`` (``ir_gym.py:24``) is the space of the policy's normalised output; the
training loop converts it to an absolute velocity with ``abs_action = acceler * a + current velocity`` before
``step_ir`` (``multi_ppo.py:183-187``).  It is therefore not a bound on this binding's velocity commands and this
simulated R0 driver declares no limit on them.

The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no operator-required
bound.  This package is model-authored and unreviewed, and its evidence is the fake backend only; the upstream
package is never imported or run (it needs gym 0.20.0, torch and the external ir-sim v2.5, README.md:17-27).  Every
Fact and constant cites a line of the clone at the pinned commit 6cdb70c731293dd92fa6f84cd6878a28bf259191.
"""

from collections.abc import Mapping

from mhs import canonical
from mhs.driver import Driver, DriverFailed, Fact, Field, action, read

MR = "gym_env/gym_env/envs/mrnav.py"
IR = "gym_env/gym_env/envs/ir_gym.py"
REG = "gym_env/gym_env/__init__.py"
WORLD = "gym_env/gym_test_world.yaml"


def _plain(value):
    """A JSON-safe copy of an upstream value (numpy arrays and scalars become lists and numbers)."""
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if hasattr(value, "tolist"):
        return _plain(value.tolist())
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return value
    return value


class RlRvoNav(Driver):
    device_id = "rl-rvo-nav"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R0"
    native = "gym_env.envs:mrnav"
    backends = {"fake": ".fake:FakeMrnav"}
    display_name = "rl_rvo_nav multi-robot navigation (mrnav-v1)"
    vendor, model = "Han Ruihua", "rl_rvo_nav"
    tags = ["multi-robot", "navigation", "reinforcement-learning", "rvo", "simulation", "gym"]
    safe_state = ("the simulation stops advancing: cap.world.step.v1 and cap.world.reset.v1 are refused after an "
                  "e-stop until mhs.safety.reset clears the latch; the world state stays readable")
    facts = [
        Fact("mrnav-v1 is registered with entry point gym_env.envs:mrnav", source="upstream_code", ref=f"{REG}:3-6"),
        Fact("The environment class is mrnav, a gym.Env subclass with __init__, step_ir, render, reset, reset_one "
             "and show", source="upstream_code", ref=f"{MR}:4-46"),
        Fact("mrnav wraps ir_gym and copies its observation_space and action_space",
             source="upstream_code", ref=f"{MR}:7-10"),
        Fact("The declared observation space is Box(-inf, inf, shape=(5,), dtype=float32)",
             source="upstream_code", ref=f"{IR}:23"),
        Fact("The declared action space is Box(low=[-1, -1], high=[1, 1], dtype=float32)",
             source="upstream_code", ref=f"{IR}:24"),
        Fact("step_ir(action, vel_type='omni', stop=True) returns obs_list, reward_list, done_list and info_list",
             source="upstream_code", ref=f"{MR}:18-30"),
        Fact("A robot observation concatenates current velocity, desired velocity, heading and collision radius with "
             "the RVO neighbour features, rounded to two decimals", source="upstream_code", ref=f"{IR}:96-109"),
        Fact("rvo_state_dim is 8", source="upstream_code", ref=f"{IR}:30"),
        Fact("A collision sets done true and the robot's arrival flag is returned as info",
             source="upstream_code", ref=f"{IR}:116-117"),
        Fact("The movement reward is the collision parameter p7 on a collision plus the arrival parameter p8 on the "
             "first arrival", source="upstream_code", ref=f"{IR}:121-131"),
        Fact("The per-robot reward is the RVO reward plus the movement reward",
             source="upstream_code", ref=f"{MR}:28-29"),
        Fact("reset(mode=0, **kwargs) forwards to ir_gym.env_reset and returns the list of robot observations",
             source="upstream_code", ref=f"{MR}:38-40"),
        Fact("env_reset calls robots_reset and then rebuilds the observations; the method does not reset obstacle "
             "state", source="upstream_code", ref=f"{IR}:173-179"),
        Fact("The reset path takes a mode and forwards it to robots_reset; it supplies no seed value",
             source="upstream_code", ref=f"{IR}:175"),
        Fact("The world configuration sets the simulation step_time to 0.1 s",
             source="upstream_code", ref=f"{WORLD}:4"),
        Fact("The training loop builds the absolute velocity command as acceler * policy action + current velocity "
             "before calling step_ir", source="upstream_code", ref="rl_rvo_nav/policy_train/multi_ppo.py:184-187"),
        Fact("The simulator is the external intelligent-robot-simulator (ir-sim) v2.5",
             source="vendor_doc", ref="README.md:21"),
        Fact("The class defines no get_state/set_state and the clone exposes no snapshot or restore path",
             source="upstream_code", ref=f"{MR}:4-46"),
    ]
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The package only knows the
    #: clone; the external ir-sim engine and its random robot initialisation were not run, so this is F0 with
    #: determinism ``none`` and the gaps name every omission.
    fidelity = {
        "engine": "ir-sim",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "the clone's reset takes a mode and supplies no seed (ir_gym.py:175); robot initialisation and "
                     "the dynamics live in the external ir-sim package (README.md:21), which was not run, so this "
                     "package makes no replay claim",
        },
        "timestep_ms": 100.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "partial",
        "snapshot_restore": False,
        "gaps": [
            "no dynamics are modelled by this package's fake: it is a pure Python kinematic stand-in for the "
            "external ir-sim engine, which was not run and was not compared with the fake",
            "the declared observation_space is Box(shape=(5,)) (ir_gym.py:23) but observation_reward builds 6 + 8 = "
            "14 values (ir_gym.py:102-109, :30); the fake returns 14 values for each robot",
            "the reset path resets the robots only (ir_gym.py:173-179); obstacle state and any dynamic obstacles are "
            "not reset by env_reset, so reset is partial",
            "no seed control: the clone's reset path takes a mode and no seed (ir_gym.py:175), so determinism is "
            "none and cap.world.reset.v1 reports seed 0 for the required class field",
            "no wall-clock pacing: realtime_factor is 0 and ticks advance simulated time only by timestep_ms",
            "snapshot and restore are not offered: the class has no get_state/set_state",
            "the fake returns a smaller world than the upstream default (two robots, no obstacles) and its reward "
            "values are test data, not the upstream reward parameters",
        ],
    }

    @read("observation", type="array", items=Field("array", items=Field("number")),
          description="Per-robot observation: current velocity, desired velocity, heading, collision radius and "
                      "the RVO neighbour features")
    def observation(self):
        return _plain(self.native.ir_gym.env_observation())

    @read("tick", type="integer", unit="1", description="Fixed simulation steps since the last reset")
    def tick(self):
        return self._tick

    @action(cap="cap.world.step.v1",
            description="Advance the multi-robot world by ticks fixed steps with one velocity command per robot",
            input={
                "ticks": Field("integer", unit="1",
                               description="Number of fixed simulation steps to advance (one step_ir call each)"),
                "action": Field("object", description="Per-robot velocity commands for this step",
                                properties={"robots": Field(
                                    "array", min_items=1,
                                    description="One [vx, vy] velocity command per robot in m/s, in robot order",
                                    items=Field("array", length=2,
                                                description="A [vx, vy] velocity command in m/s",
                                                items=Field("number", unit="m/s",
                                                            description="Velocity component in m/s")))}),
            })
    def step_world(self, action, ticks=1):
        robots = action.get("robots") if isinstance(action, Mapping) else None
        if not isinstance(robots, list) or not robots:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                               "action.robots must be a non-empty list of [vx, vy] pairs")
        commands = []
        for index, pair in enumerate(robots):
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                                   f"action.robots[{index}] must be a [vx, vy] pair")
            commands.append([float(pair[0]), float(pair[1])])
        if not isinstance(ticks, int) or isinstance(ticks, bool) or ticks < 1:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "ticks must be a positive integer")
        total_reward = 0.0
        for _ in range(ticks):
            obs_list, reward_list, done_list, info_list = self.native.step_ir(commands)
            self._tick += 1
            for reward in reward_list:
                total_reward += float(reward)
        observation = {
            "robots": _plain(obs_list),
            "rewards": _plain(reward_list),
            "dones": _plain(done_list),
            "infos": _plain(info_list),
        }
        return {
            "observation": observation,
            "reward": total_reward,
            "terminated": any(bool(done) for done in done_list),
            "truncated": False,
            "tick": self._tick,
            "state_hash": canonical.digest({"observation": observation, "tick": self._tick,
                                            "episode": self._episode}),
        }

    @action(cap="cap.world.reset.v1", description="Reset the robots and return their initial observations",
            input={"options": Field("object", description="Options passed to mrnav.reset",
                                    properties={"mode": Field("integer", unit="1",
                                                              description="Robot reset mode (mrnav.reset(mode=...))")})})
    def reset_world(self, options=None):
        mode = 0
        if options is not None:
            if not isinstance(options, Mapping):
                raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "options must be an object")
            mode = options.get("mode", 0)
            if not isinstance(mode, int) or isinstance(mode, bool):
                raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "options.mode must be an integer")
        observations = self.native.reset(mode=mode)
        self._tick = 0
        self._episode += 1
        # cap.world.reset.v1 requires a seed in its output; the clone's reset has no seed argument (ir_gym.py:175).
        return {"observation": {"robots": _plain(observations)}, "seed": 0}

    _tick = 0
    _episode = 0
