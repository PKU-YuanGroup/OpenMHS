# Facts and tags for gh.edem-ai/robosynchallenge

Every fact cites its source at commit `8818c82df5fa2522809b8105e7018950dcc9a9a8`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| ClickBellEnv is registered as ClickBell with max_episode_steps=600 | upstream_code | robosynchallenge/tasks/click_bell/click_bell.py:34 |
| ClickBellEnv subclasses EmbodiedEnv, imported from the external embodichain package | upstream_code | robosynchallenge/tasks/click_bell/click_bell.py:20-35 |
| ClickBellEnv.__init__ forwards cfg and keyword arguments to EmbodiedEnv and stores action_config when one is given | upstream_code | robosynchallenge/tasks/click_bell/click_bell.py:37-42 |
| compute_task_state reads the button articulation's joint positions with get_qpos | upstream_code | robosynchallenge/tasks/click_bell/click_bell.py:132-133 |
| The source comment describes button.urdf as a single prismatic joint with range [-0.005, 0.0] | upstream_code | robosynchallenge/tasks/click_bell/click_bell.py:135 |
| press_depth is minus the button joint position | upstream_code | robosynchallenge/tasks/click_bell/click_bell.py:137 |
| The ClickBell success threshold movement_threshold is 0.0048 | upstream_code | robosynchallenge/tasks/click_bell/click_bell.py:138 |
| The ClickBell success flag is latched within an episode with \|= current_success | upstream_code | robosynchallenge/tasks/click_bell/click_bell.py:142 |
| compute_task_state returns success, fail and the metrics press_depth and movement_threshold | upstream_code | robosynchallenge/tasks/click_bell/click_bell.py:144-150 |
| is_task_success returns the latched success flag | upstream_code | robosynchallenge/tasks/click_bell/click_bell.py:152-153 |
| reset clears the success flag for the reset ids, defaulting to every environment | upstream_code | robosynchallenge/tasks/click_bell/click_bell.py:154-163 |
| ClickBellTest uses the smaller movement_threshold 0.004 | upstream_code | robosynchallenge/tasks/click_bell/click_bell.py:176 |
| The click-bell action configuration declares right_arm 6, left_arm 6, left_eef 1 and right_eef 1 action dimensions | upstream_code | configs/click_bell/action_config.json:2-56 |
| The documentation states that an arm action dimension is 6 DoF and a gripper action dimension is 1 | vendor_doc | docs/tutorials/configuration.md:319 |
| The legacy replay format stores the robot's 14 active CobotMagic joints | upstream_code | robosynchallenge/replay.py:158 |
| The click-bell random protocol sets max_episode_steps to 361 | vendor_doc | configs/click_bell/random/gym_config.json:4 |
| The click-bell random protocol sets control_freq to 25 | vendor_doc | configs/click_bell/random/gym_config.json:243 |
| The evaluation launcher passes the resolved max_episode_steps to gym.make | upstream_code | scripts/eval_policy.py:468-472 |
| The observation configuration modifies the robot/qpos observation at joint ids 6 and 13 | upstream_code | configs/click_bell/random/gym_config.json:225-232 |
| The OpenPI CLI defaults state_key to robot/qpos and image_key to color | upstream_code | scripts/eval_openpi0_embodichain.py:277-278 |
| The released evaluation records ClickBell success rates for the simulation checkpoints | vendor_doc | evaluation_results/released_checkpoint_results.json:37-43 |
| prepare_episode_reset seeds Python random, NumPy and Torch; its docstring says EmbodiChain's reset(seed) seeds Torch only | upstream_code | scripts/eval_policy.py:301-315 |

Limits: the driver declares none of its own. The only bound is the environment's action space, which the bridge
derives from the environment (`action.values` for this fake). The fake's action space is a **placeholder**
`Box(-1, 1)` with 14 values, so the derived limit has no source and its ref names the fake backend; `action_space_ref`
is deliberately unset because the clone does not state the real bounds (they belong to the external EmbodiChain
`EmbodiedEnv` and the CobotMagic robot). `ticks` is bounded by the bridge (1 to `max_ticks`, 10000 by default). The
device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `embodichain:robosynchallenge/ClickBell`, level F0 (an
analytic contract stand-in: no dynamics, no robot, no contacts), determinism `seeded` with `seed_control` `parameter`
on the fake's placeholder start draw, timestep 40 ms (the random protocol's `control_freq` 25 records at 25 Hz;
`configs/click_bell/random/gym_config.json:243`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and
restore. The gaps state what is a placeholder and that the upstream simulator and the sim backend were not run.

Safety: simulated R0 fake-only contract. The software latch refuses step, environment reset and seed; cached state
stays readable. Releasing the latch does not step or reset the environment. No native stop or halted EmbodiChain
simulator is established; the external base lifecycle was not checked by execution.

Tags: robosynchallenge, click-bell, bimanual, manipulation, reinforcement-learning, simulation, gymnasium
