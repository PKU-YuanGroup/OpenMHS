# Facts and tags for gh.lifelong-robot-learning/libero

Every fact cites its source at commit `8f1084e3132a39270c3a13ebe37270a43ece2a01`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

The package is a direct `Driver` over `libero.libero.envs.env_wrapper:OffScreenRenderEnv` (the card's entry symbol)
because that upstream object is a BDDL-driven robosuite environment, not a bare MJCF model. This is a DEVIATION from
the card's `MujocoDriver` helper; the card's `decision` is already `direct-driver`.

| fact | source | ref |
|---|---|---|
| ControlEnv reads the BDDL problem information and builds the robosuite task class TASK_MAPPING[problem_name] from the BDDL file | upstream_code | libero/libero/envs/env_wrapper.py:49-56 |
| OffScreenRenderEnv forces has_renderer False and has_offscreen_renderer True before it builds the ControlEnv | upstream_code | libero/libero/envs/env_wrapper.py:152-159 |
| ControlEnv.step passes the action straight to the robosuite environment | upstream_code | libero/libero/envs/env_wrapper.py:87-88 |
| ControlEnv.reset calls env.reset() until it returns and retries when the environment raises RandomizationError | upstream_code | libero/libero/envs/env_wrapper.py:90-101 |
| ControlEnv.seed delegates to env.seed(seed) | upstream_code | libero/libero/envs/env_wrapper.py:133-134 |
| BDDLBaseDomain.seed calls np.random.seed(seed) | upstream_code | libero/libero/envs/bddl_base_domain.py:162-163 |
| ControlEnv.set_init_state loads the supplied state and regenerates the observations through regenerate_obs_from_state | upstream_code | libero/libero/envs/env_wrapper.py:136-145 |
| ControlEnv.get_sim_state returns the flattened MuJoCo simulation state | upstream_code | libero/libero/envs/env_wrapper.py:118-120 |
| ControlEnv.close closes the robosuite environment | upstream_code | libero/libero/envs/env_wrapper.py:147-149 |
| ControlEnv defaults to the OSC_POSE controller | upstream_code | libero/libero/envs/env_wrapper.py:17 |
| ControlEnv defaults control_freq to 20 control steps per second, so one control step lasts 50 ms | upstream_code | libero/libero/envs/env_wrapper.py:27 |
| ControlEnv defaults horizon to 1000 | upstream_code | libero/libero/envs/env_wrapper.py:28 |
| The default camera names are agentview and robot0_eye_in_hand with camera heights and widths 128 | upstream_code | libero/libero/envs/env_wrapper.py:31-36 |
| BDDLBaseDomain is the robosuite SingleArmEnv task base class | upstream_code | libero/libero/envs/bddl_base_domain.py:37 |
| The task base imports the mujoco Python bindings | upstream_code | libero/libero/envs/bddl_base_domain.py:13 |
| BDDLBaseDomain.step calls super().step(action) and then reports done as _check_success() | upstream_code | libero/libero/envs/bddl_base_domain.py:800-809 |
| BDDLBaseDomain.reward returns 1.0 when _check_success() and 0.0 otherwise, scaled by reward_scale | upstream_code | libero/libero/envs/bddl_base_domain.py:179-189 |
| BDDLBaseDomain._assert_problem_name requires the parsed problem name to equal the class name in lower case | upstream_code | libero/libero/envs/bddl_base_domain.py:191-195 |
| The robosuite observation vector of LIBERO concatenates robot0_gripper_qpos, robot0_eef_pos and robot0_eef_quat | upstream_code | libero/libero/envs/bddl_base_domain.py:828 |
| The README example constructs OffScreenRenderEnv from a BDDL file, seeds and resets it, sets an initial state, and steps a seven-element action that returns (obs, reward, done, info) | upstream_code | README.md:116-130 |
| The Libero_Kitchen_Tabletop_Manipulation problem class is registered with register_problem and extends BDDLBaseDomain | upstream_code | libero/libero/envs/problems/libero_kitchen_tabletop_manipulation.py:11-12 |
| The kitchen BDDL file defines the problem LIBERO_Kitchen_Tabletop_Manipulation and its language instruction | upstream_code | libero/libero/bddl_files/libero_10/KITCHEN_SCENE3_turn_on_the_stove_and_put_the_moka_pot_on_it.bddl:1-3 |
| The clone pins robosuite 1.4.0 and bddl 1.0.1 as its simulation and BDDL dependencies | upstream_code | requirements.txt:10-11 |

## Limits

The driver declares **no `Limit`**. The only bounds that exist without a device-specific source are the catalogue
class's own input-schema bounds on `cap.world.step.v1` (`ticks` 1 to 10000) and `cap.world.reset.v1` (`seed` at least
0); the runtime validates them as input schema before any native call (`MHS.CAPABILITY.INPUT_INVALID`), which the
driver test checks. The seven OSC_POSE action values have no bound in the clone: the controller and its input range
come from robosuite 1.4.0, which `requirements.txt:10` pins but the clone does not state. The driver therefore does not
invent an action envelope and declares no `operator_required` path; an operator who needs an envelope should supply a
site-limits overlay for the deployed model, and the driver's `observation`/`tick`/`seed` state makes the applied
actions auditable. No limit came from the exemplar.

## Fidelity contract

`driver.py` publishes engine `mujoco:libero`, level `F1` (rigid-body dynamics with contacts), determinism `seeded`
with `seed_control` `parameter`, `timestep_ms` 50.0 (the clone's default `control_freq` 20, `env_wrapper.py:27`),
`realtime_factor` 0, clock `lockstep`, reset `full`, `snapshot_restore` false, and eight `gaps`. The gaps disclose that
the fake is not MuJoCo/robosuite, that the task reward and success predicate are not modelled, that the camera images
(128 x 128 x 3 per camera) are **NOT COVERED** and only the low-dimensional observation members are returned, that the
fake's nine-number state is not the MuJoCo qpos layout, and that snapshot/restore and rendering are not bound.

## Safety

Simulated R0 device. The e-stop is the runtime's software latch: there is no native stop and no hardware backend, so
after an e-stop no step or reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable.
No hardware was attached, no hardware backend is declared, and this package is model-authored and unreviewed
(`driver.lock.json` `reviewed_by` is null).

## Coverage of the upstream interface

Served: `cap.world.reset.v1` (optional seed; calls `env.seed(seed)` and `env.reset()`), `cap.world.step.v1` (one
control step per tick, seven action values, output observation, reward, terminal flags, tick and state hash) and the
world resource (`observation`, `reward`, `terminated`, `truncated`, `tick`, `episode`, `seed`). NOT COVERED: the camera
arrays, the full MuJoCo state, rendering, snapshot/restore, the BDDL task predicate and the task success reward. The
upstream simulator itself was not opened; the only exercised backend is `fake`.

Tags: libero, robosuite, mujoco, simulation, manipulation, reinforcement-learning
