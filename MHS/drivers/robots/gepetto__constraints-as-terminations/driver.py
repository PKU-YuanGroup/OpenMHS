"""OpenMHS driver for gh.gepetto/constraints-as-terminations: the CaT Solo12 locomotion simulation.

DEVIATION FROM THE CARD: the card names this package as a ``GymnasiumDriver`` family member.  The upstream
environment is a Gymnasium environment, but its ``step`` does not return the Gymnasium five-tuple: ``CaTEnv.step``
returns ``(obs_buf, reward_buf, dones, reset_time_outs, extras)`` where ``dones`` is the constraint probability
``cstr_prob`` (``cat_env.py:99-107``) and not a termination flag.  The cleanrl loop reads it that way and uses the
fourth value, ``timeouts``, as the true done (``cleanrl/ppo.py:215-226``).  The environment is also vectorized
(``num_envs=4096`` in the base config and 50 in the Play variant, ``cat_flat_env_cfg.py:464`` and ``:505``) and
returns torch tensors with a policy observation mapping.  A ``GymnasiumDriver`` derives its contract from the
environment's spaces and the bridge treats the third step value as ``terminated`` (``mhs.bridge.gymnasium``), so it
would turn every non-zero constraint probability into a termination and would not expose the fourth value.  This
package is therefore a direct ``Driver`` over the clone's entry class (``native`` is the card's
``cat_envs.tasks.utils.cat.cat_env:CaTEnv``) with the package fake.  ``cap.world.step.v1`` accepts the class's
``ticks`` and an ``action`` object carrying the twelve joint-position values in ``action.values``;
``cap.world.reset.v1`` calls the upstream ``reset()`` and returns its policy observation.  ``cap.world.seed.v1`` is
deliberately not bound: the upstream seeds through ``env_cfg.seed`` before ``gym.make`` (``train.py:109-111``), not
through an integer reset argument, so the class's seed input has no faithful mapping.

The upstream needs Isaac Lab 2.1.0 and Isaac Sim (``README.md:15`` and ``:40-45``), which are not available where the
gate runs; package code never imports the clone.  The ``fake`` backend is this package's pure Python kinematic stand-in
(``fake.py``); it was not compared with the upstream environment.  A ``sim`` backend is not offered because there is no
tested native factory for the GPU-bound Isaac Lab environment.  The device is simulated at R0: there is no hardware
backend and no e-stop path to a machine.

Every Fact cites a line of the clone at the pinned commit 5fc729b789a27d39bf95df1b58fbc32b794106ff.  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from collections.abc import Mapping

from mhs import canonical
from mhs.driver import Driver, DriverFailed, Fact, Field, action, read

CAT_ENV = "exts/cat_envs/cat_envs/tasks/utils/cat/cat_env.py"
SOLO12 = "exts/cat_envs/cat_envs/tasks/locomotion/velocity/config/solo12"
CLEANRL_PPO = "exts/cat_envs/cat_envs/tasks/utils/cleanrl/ppo.py"

#: The policy observation the fake serves: one value per member of the six concatenated terms of the Solo12
#: config.  The upstream member sizes (three for base_ang_vel, velocity_commands and projected_gravity, twelve for
#: joint_pos, joint_vel and actions) are the config's terms; the fake's values themselves are test data.
OBSERVATION_DIM = 45
#: The number of joint-position actions of the Solo12 action term (twelve joint names, cat_flat_env_cfg.py:116-129).
ACTION_DIM = 12


class ConstraintsAsTerminations(Driver):
    device_id = "cat-solo12"
    device_kind = "world.sim"
    resource_id = "world"
    mode = "simulated"
    risk = "R0"
    native = "cat_envs.tasks.utils.cat.cat_env:CaTEnv"
    backends = {"fake": ".fake:FakeCaTEnv"}
    display_name = "CaT Solo12 locomotion environment (Isaac Lab simulation)"
    vendor, model = "Gepetto", "constraints-as-terminations"
    tags = ["constraints-as-terminations", "cat", "solo12", "isaac-lab", "locomotion", "reinforcement-learning",
            "simulation"]
    facts = [
        Fact("The repository registers Isaac-Velocity-CaT-Flat-Solo12-v0 and "
             "Isaac-Velocity-CaT-Flat-Solo12-Play-v0 with entry_point=CaTEnv",
             source="upstream_code", ref=f"{SOLO12}/__init__.py:16-31"),
        Fact("CaTEnv subclasses ManagerBasedRLEnv imported from isaaclab.envs.manager_based_rl_env",
             source="upstream_code", ref=f"{CAT_ENV}:13-17"),
        Fact("CaTEnv.step takes an action whose shape is (num_envs, action_dim)",
             source="upstream_code", ref=f"{CAT_ENV}:56"),
        Fact("CaTEnv.step performs cfg.decimation simulation steps with self.sim.step(render=False)",
             source="upstream_code", ref=f"{CAT_ENV}:71-78"),
        Fact("CaTEnv records the termination manager's terminated and time_outs flags as reset_terminated and "
             "reset_time_outs before computing the constraint probabilities",
             source="upstream_code", ref=f"{CAT_ENV}:94-97"),
        Fact("The third value CaTEnv.step returns is a constraint probability (dones = cstr_prob.clone()); "
             "it is not a termination flag", source="upstream_code", ref=f"{CAT_ENV}:99-107"),
        Fact("CaTEnv.step returns observations, rewards, the constraint probabilities, self.reset_time_outs and "
             "self.extras", source="upstream_code", ref=f"{CAT_ENV}:146-147"),
        Fact("The action term is a joint position action over the twelve named HAA, HFE and KFE joints with scale "
             "0.5 and use_default_offset=True", source="upstream_code", ref=f"{SOLO12}/cat_flat_env_cfg.py:114-133"),
        Fact("The policy observation group concatenates the base angular velocity, velocity commands, projected "
             "gravity, joint positions, joint velocities and last actions terms",
             source="upstream_code", ref=f"{SOLO12}/cat_flat_env_cfg.py:145-176"),
        Fact("The configuration sets decimation 4, episode_length_s 10.0 and the physics step sim.dt 0.005 s",
             source="upstream_code", ref=f"{SOLO12}/cat_flat_env_cfg.py:479-484"),
        Fact("The time_out termination term is configured with time_out=True",
             source="upstream_code", ref=f"{SOLO12}/cat_flat_env_cfg.py:362"),
        Fact("The default scene config sets num_envs=4096", source="upstream_code",
             ref=f"{SOLO12}/cat_flat_env_cfg.py:464"),
        Fact("The Play variant sets scene.num_envs to 50", source="upstream_code",
             ref=f"{SOLO12}/cat_flat_env_cfg.py:505"),
        Fact("The constraints config sets joint_torque limit 3.0, joint_velocity limit 16.0, joint_acceleration "
             "limit 800.0 and action_rate limit 80.0", source="upstream_code",
             ref=f"{SOLO12}/cat_flat_env_cfg.py:262-285"),
        Fact("The constraints config also sets foot_contact_force limit 50.0, front_hfe_position limit 1.3 and "
             "upsidedown limit 0.0", source="upstream_code", ref=f"{SOLO12}/cat_flat_env_cfg.py:295-312"),
        Fact("The README states the code relies on IsaacLab version 2.1.0", source="vendor_doc", ref="README.md:15"),
        Fact("The installation installs Isaac Lab first and then runs pip install -e exts/cat_envs",
             source="vendor_doc", ref="README.md:40-45"),
        Fact("The CleanRL training script sets env_cfg.seed = agent_cfg.seed before gym.make",
             source="upstream_code", ref="scripts/clean_rl/train.py:109-111"),
        Fact("The CleanRL training script creates the environment with gym.make(task, cfg=env_cfg, "
             "render_mode=...)", source="upstream_code", ref="scripts/clean_rl/train.py:130-131"),
        Fact("The CleanRL play script reads env.reset()[0]['policy'], so reset returns an observation mapping "
             "with a policy member", source="upstream_code", ref="scripts/clean_rl/play.py:115"),
        Fact("The CleanRL loop unpacks envs.step(action) into next_obs, reward, next_done, timeouts and info, then "
             "reads next_obs['policy'] and stores timeouts as the true done", source="upstream_code",
             ref=f"{CLEANRL_PPO}:215-226"),
        Fact("The CleanRL loop reads envs.unwrapped.num_envs, single_observation_space['policy'].shape and "
             "single_action_space.shape", source="upstream_code", ref=f"{CLEANRL_PPO}:158-161"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the world state stays readable")
    #: The model as deployed is the package fake: a kinematic stand-in with no physics (F0).  The upstream model is
    #: Isaac Lab/PhysX rigid-body dynamics, which was not run and is not served by this package.
    fidelity = {
        "engine": "custom:cat-solo12-kinematic-stand-in",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "seed_control": "none",
            "notes": "the fake transitions are deterministic, but the upstream seed is an env_cfg field set before "
                     "gym.make (train.py:109-111), not an integer reset argument, and the fake has no RNG; this "
                     "package makes no seeded replay claim and does not bind cap.world.seed.v1",
        },
        "timestep_ms": 5.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "no dynamics: the fake integrates a placeholder joint position from the action; it models no physics, "
            "no contacts, no actuator, no sensor and no noise",
            "one cap.world.step.v1 tick is one CaTEnv.step, which runs cfg.decimation 4 physics steps of sim.dt "
            "0.005 s = 20 ms; timestep_ms names the 5 ms physics step (cat_flat_env_cfg.py:479-484, FID-015)",
            "the upstream environment is vectorized (num_envs=4096 in the base config, 50 in Play) and returns "
            "torch tensors; the fake serves one environment with plain Python lists and a fixed 45-value policy "
            "observation",
            "the third upstream step value is a constraint probability, not a termination flag; the driver exposes "
            "it as constraint_probability and reads the termination manager's reset_terminated and reset_time_outs "
            "for the terminal flags, but the fake sets the constraints to a placeholder zero and does not model "
            "the eleven constraint terms",
            "the fake was never compared with the upstream Isaac Lab environment; Isaac Lab 2.1.0 and Isaac Sim "
            "were not run where the gate runs, and no sim backend is offered",
            "no seed control: cap.world.seed.v1 is not bound, and cap.world.reset.v1 only records a supplied seed "
            "in its receipt because the upstream seed is applied to env_cfg before construction and the fake reset "
            "is deterministic",
            "no wall-clock pacing: realtime_factor 0, the simulation advances only when step or reset is called",
            "no rendering is served: cap.world.render.v1 needs an artifact store, and the fake renders nothing",
            "snapshot and restore are not offered: the fake and the driver expose no get_state/set_state",
            "no physical device is modelled and nothing was validated against one",
        ],
    }

    def __init__(self, **options):
        super().__init__(**options)
        self._tick = 0
        self._episode = 0
        self._last_observation = {"policy": [0.0] * OBSERVATION_DIM}
        self._last_reward = 0.0
        self._constraint_probability = 0.0
        self._timed_out = False
        self._terminated = False
        self._started = False
        self._seed = 0

    # ------------------------------------------------------------------ state
    def _observation_value(self) -> dict:
        return {"policy": list(self._last_observation["policy"])}

    def _apply_observation(self, observation) -> None:
        if isinstance(observation, Mapping):
            policy = observation.get("policy")
            if policy is None:
                raise DriverFailed("MHS.DEVICE.FAULTED",
                                   "CaTEnv.reset/step returned a mapping without a policy observation")
        else:
            policy = observation
        try:
            values = [float(value) for value in policy]
        except (TypeError, ValueError) as exc:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               "CaTEnv.reset/step observation is not a sequence of numbers") from exc
        if len(values) != OBSERVATION_DIM:
            raise DriverFailed(
                "MHS.DEVICE.FAULTED",
                f"CaTEnv observation has {len(values)} values; this driver serves the "
                f"{OBSERVATION_DIM}-value policy observation")
        self._last_observation = {"policy": values}

    @staticmethod
    def _scalar(value):
        item = getattr(value, "item", None)
        if callable(item):
            try:
                return item()
            except (TypeError, ValueError):
                pass
        if isinstance(value, (list, tuple)) and len(value) == 1:
            return value[0]
        return value

    def _reset_from_native(self) -> None:
        result = self.native.reset()
        observation = result[0] if isinstance(result, tuple) and result else result
        self._apply_observation(observation)
        self._last_reward = 0.0
        self._constraint_probability = 0.0
        self._timed_out = False
        self._terminated = False
        self._tick = 0
        self._episode += 1
        self._started = True

    def _ensure_started(self) -> None:
        if not self._started:
            self._reset_from_native()

    @read("observation", type="object", description="Policy observation of the last transition",
          properties={"policy": Field("array", unit="1", length=OBSERVATION_DIM,
                                      items=Field("number", description="One policy observation value"),
                                      description="Concatenated policy observation values")})
    def observation(self) -> dict:
        return self._observation_value()

    @read("reward", unit="1", description="Reward returned by the last step invocation")
    def reward(self) -> float:
        return self._last_reward

    @read("constraint_probability", unit="1",
          description="Constraint probability CaTEnv returns in the third step slot (the CaT signal, not a "
                      "termination flag)")
    def constraint_probability(self) -> float:
        return self._constraint_probability

    @read("timed_out", type="boolean", description="True when the last step reached the time-out term")
    def timed_out(self) -> bool:
        return self._timed_out

    @read("terminated", type="boolean",
          description="True when the last step reached a non-time-out termination term")
    def terminated(self) -> bool:
        return self._terminated

    @read("tick", type="integer", unit="1", description="CaTEnv steps applied since the last reset")
    def tick(self) -> int:
        return self._tick

    @read("episode", type="integer", unit="1", description="Resets performed since the backend opened")
    def episode(self) -> int:
        return self._episode

    # ---------------------------------------------------------------- actions
    @action(cap="cap.world.step.v1",
            description="Advance the CaT environment by ticks, applying one joint-position action per tick",
            input={
                "ticks": Field("integer", unit="1",
                               description="CaTEnv steps to advance; the action is applied at every step"),
                "action": Field("object", description="The joint-position action of the upstream environment",
                                properties={
                                    "values": Field("array", unit="1", length=ACTION_DIM,
                                                    items=Field("number",
                                                                description="One joint-position action value"),
                                                    description="One value per Solo12 joint-position actuator"),
                                }),
            })
    def step(self, ticks: int, action: dict) -> dict:
        if not isinstance(action, Mapping) or "values" not in action:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "action.values is required")
        try:
            values = [float(value) for value in action["values"]]
        except (TypeError, ValueError) as exc:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "action.values must be numbers") from exc
        if len(values) != ACTION_DIM:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                               f"action.values needs {ACTION_DIM} joint positions, got {len(values)}")
        if self._timed_out or self._terminated:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "the episode has ended; reset the world before the next step")
        self._ensure_started()
        reward_total = 0.0
        for _ in range(int(ticks)):
            result = self.native.step(values)
            try:
                observation, reward, constraint_probability, time_out, _info = result
            except (TypeError, ValueError) as exc:
                raise DriverFailed("MHS.DEVICE.FAULTED",
                                   "CaTEnv.step did not return the five values "
                                   "(observations, reward, constraint probabilities, time-outs, extras)") from exc
            self._apply_observation(observation)
            self._last_reward = float(self._scalar(reward))
            self._constraint_probability = float(self._scalar(constraint_probability))
            self._timed_out = bool(self._scalar(time_out))
            self._terminated = bool(self._scalar(getattr(self.native, "reset_terminated", False)))
            self._tick += 1
            reward_total += self._last_reward
            if self._timed_out or self._terminated:
                break
        observation = self._observation_value()
        return {
            "observation": observation,
            "reward": reward_total,
            "terminated": self._terminated,
            "truncated": self._timed_out,
            "tick": self._tick,
            "state_hash": canonical.digest({
                "observation": observation,
                "reward": reward_total,
                "terminated": self._terminated,
                "truncated": self._timed_out,
                "tick": self._tick,
            }),
        }

    @action(cap="cap.world.reset.v1",
            description="Reset the CaT environment and return its policy observation",
            input={
                "seed": Field("integer", unit="1",
                              description="Recorded in the reset receipt; the fake reset is deterministic and "
                                          "ignores it"),
                "options": Field("object",
                                 description="Accepted for the class contract; the fake has no reset options"),
            })
    def reset_world(self, seed=None, options=None) -> dict:
        if seed is not None:
            self._seed = int(seed)
        self._reset_from_native()
        return {"observation": self._observation_value(), "seed": self._seed}
