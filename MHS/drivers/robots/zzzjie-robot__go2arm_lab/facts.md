# Facts and tags for gh.zzzjie-robot/go2arm_lab

Every fact cites the clone at commit `5791648e28c1878f4fa5b97ccf111d97f8843f0e`. The same facts are written into
`driver.py` (`facts = [...]`); `reference.json` is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Go2Arm is a Unitree Go2 quadruped base with an Interbotix WidowX 250s manipulator; the repository trains RL policies for it | upstream_code | README.md:22-25 |
| Isaac-Go2Arm-Flat and Isaac-Go2Arm-Flat-Play are registered with entry_point `Go2Arm_Lab.env.manager_env:ManagerRLEnv` and the `Go2ARMFlatEnvCfg` / `Go2ARMFlatEnvCfg_PLAY` configs | upstream_code | source/Go2Arm_Lab/Go2Arm_Lab/tasks/manager_based/go2arm_lab/config/__init__.py:14-31 |
| `ManagerRLEnv.__init__` takes `cfg` and `render_mode` and calls the Isaac Lab base with `cfg` | upstream_code | source/Go2Arm_Lab/Go2Arm_Lab/env/manager_env.py:6-7 |
| `step` processes the action through the action manager and advances the Isaac Sim scene `cfg.decimation` times per call | upstream_code | source/Go2Arm_Lab/Go2Arm_Lab/env/manager_env.py:17-34 |
| `step` returns six values: observation, reward, arm reward, terminated, time-out and extras | upstream_code | source/Go2Arm_Lab/Go2Arm_Lab/env/manager_env.py:88 |
| The configuration sets `decimation` 4, `episode_length_s` 20.0 and `sim.dt` 0.005 seconds | upstream_code | source/Go2Arm_Lab/Go2Arm_Lab/tasks/manager_based/go2arm_lab/go2arm_lab_env_cfg.py:550-553 |
| The action configuration has two `JointPositionAction` terms: 12 leg joints with scale 0.25 and 6 arm joints with scale 0.5, both around the default joint offsets | upstream_code | source/Go2Arm_Lab/Go2Arm_Lab/tasks/manager_based/go2arm_lab/go2arm_lab_env_cfg.py:263-289 |
| The policy observation group concatenates seven history terms (base angular velocity 3, joint positions 18, joint velocities 18, last actions 18, velocity command 3, end-effector pose command 7, projected gravity 3, each with `history_length` 10) and five privileged terms (base mass 1, end-effector mass 1, joint torques 18, base linear velocity 3, foot contacts 4) | upstream_code | source/Go2Arm_Lab/Go2Arm_Lab/tasks/manager_based/go2arm_lab/go2arm_lab_env_cfg.py:300-323 |
| Termination includes a time-out and illegal contact of the base, thighs, arm links and calves at a contact threshold of 0.5 | upstream_code | source/Go2Arm_Lab/Go2Arm_Lab/tasks/manager_based/go2arm_lab/go2arm_lab_env_cfg.py:489-508 |
| The repository targets Isaac Lab v2.2.0, an external simulator framework | upstream_code | README.md:27-30 |
| The package's own `install_requires` lists only `psutil` | upstream_code | source/Go2Arm_Lab/setup.py:18-22 |

## Limits

The driver declares no `Limit`. The `cap.world.step.v1` action bounds are derived from the fake's action space by the
Gymnasium bridge; the fake uses `[-1, 1]` per action element as a **placeholder deployment envelope**, not a bound
stated by the clone. No text in the clone states an action bound: the manager environment passes the action to the
action manager, and the training wrapper applies `clip_actions` (`scripts/rsl_rl/local_rsl_rl/wrappers/VecEnvWrapper.py:182-183`)
outside the environment. The production adapter therefore leaves `action_space` unbounded unless the deployment passes
`clip_actions`; the fake's bounds are listed in the fidelity `gaps`. A deployment that needs an operator envelope must
supply it through its own wrapper/site configuration; this package does not invent one.

## Fidelity

The common contract is the deployed Isaac Lab simulator: engine `isaaclab:Isaac-Go2Arm-Flat-Play`, level F1,
`timestep_ms` 20 (decimation 4 * `sim.dt` 0.005 s), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot.
Determinism is `statistical` for the deployment (the cfg seed is set at construction; Isaac Sim/PhysX replay from a
reset seed is not proven) and `seeded` for the fake (its `reset(seed)` reseeds `random.Random`).

The fake is analytic F0, not a recording: it models the registered action shape (18), the policy observation shape
(727) and the configured 20 s time-out (1000 control steps), but no dynamics, contacts, actuators, sensors or noise.
Its observation, reward and action bounds are placeholders. The production factory (`driver.make_env`) builds
`ManagerRLEnv` with `Go2ARMFlatEnvCfg` for one environment and normalizes its six-value step to Gymnasium's five,
moving the arm reward to `info["arm_reward"]`; it was not run because it needs Isaac Lab v2.2.0, Isaac Sim and a GPU.

## Safety

Simulated R0 (spec 04-safety: isolated simulation stepping is R0; the card's `risk_floor` is R0). There is no
hardware backend. The e-stop is the SDK's software latch: after it the bridge refuses `step`, `reset` and `seed`, the
last observation stays readable, and `mhs.safety.reset` clears the latch without re-arming any device. No physical
stop exists to cite.

## Tags

gymnasium, isaaclab, isaac-sim, go2, widowx, legged-manipulation, simulation
