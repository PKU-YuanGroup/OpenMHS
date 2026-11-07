# Facts and tags for gh.ehehee/variational-automation-benchmark

Every fact cites its source at commit `edcc4bf005446839c0c6f43f8a3bf416702af030`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md, or a PDF page as `docs/manual.pdf:PAGE`) or `upstream_code`
(`path/in/clone.py:LINE`). The same facts are written into `driver.py` (`facts = [...]`); the reference file is
generated from the driver, not from this page.

The package serves the card's first entry symbol, `libero.vab.env:VABEnv`, a single-arm robosuite environment. It is a
direct `Driver`, which is the card's `decision` (`direct-driver`). The card's `helper` (`MujocoDriver`) is not used:
`models` is empty and VABEnv is a robosuite environment that builds its MuJoCo scene at run time, not an MJCF file
the family could load. The bimanual class (`libero.vab.bimanual_env:VABBimanualEnv`) and `load_task` are not served.

| fact | source | ref |
|---|---|---|
| VAB is a self-contained-YAML manipulation benchmark: one file per task supplies arena, robot, objects, initial states, success predicate and language | vendor_doc | README.md:3-5 |
| The documented quick start loads a task YAML with load_task, builds the environment with task.make_env(), calls reset(init_index=i), then step(action) and unpacks a four-tuple | vendor_doc | README.md:39-46 |
| The README calls the 50 initial states of a single-arm task seeds and loops over task.n_inits | vendor_doc | README.md:42-43 |
| The README states the observation contract: images are uint8[H,W,3] per camera, proprio is joint_pos[7], joint_vel[7], eef_pos[3], eef_quat[4] (xyzw) and gripper_qpos[2] | vendor_doc | README.md:54-63 |
| Success is returned only as info['success']; a multi-target predicate also surfaces completion_rate in 0..1 and delivery_progress() | vendor_doc | README.md:69-73 |
| The README example sets cameras agentview and robot0_eye_in_hand at camera_height 128 and camera_width 128 | vendor_doc | README.md:92-94 |
| The README lists 62 tasks across 8 suites under tasks/ | vendor_doc | README.md:9 |
| load_task resolves the YAML path, parses it with yaml.safe_load and validates it into a Task | upstream_code | libero/libero/vab/loader.py:11-24 |
| Task.make_env dispatches to VABBimanualEnv when the YAML lists two robots and to VABEnv otherwise | upstream_code | libero/libero/vab/schema.py:87-94 |
| VABEnv subclasses robosuite's SingleArmEnv | upstream_code | libero/libero/vab/env.py:50 |
| VABEnv selects renderer='mujoco' and passes the task's control frequency, horizon and camera names to robosuite | upstream_code | libero/libero/vab/env.py:103-112 |
| reset(init_index) defaults to task.default_init_index, applies that initial state and returns the filtered observation | upstream_code | libero/libero/vab/env.py:200-212 |
| reset raises IndexError when init_index is not below len(task.inits) | upstream_code | libero/libero/vab/env.py:189-193 |
| step unwraps robosuite's (obs, reward, done, info), adds success, language and completion_rate to info, and returns the filtered observation | upstream_code | libero/libero/vab/env.py:214-228 |
| The filtered observation has exactly the images and proprio keys; images are keyed by the task camera names and proprio holds joint_pos, joint_vel, eef_pos, eef_quat and gripper_qpos | upstream_code | libero/libero/vab/env.py:255-275 |
| language_instruction returns task.language and action_dim returns robots[0].action_dim | upstream_code | libero/libero/vab/env.py:277-283 |
| delivery_progress returns a (delivered, total) pair or None, and reward is 1.0 on success and 0.0 otherwise | upstream_code | libero/libero/vab/env.py:239-253 |
| The bimanual class is VABBimanualEnv, a TwoArmEnv subclass | upstream_code | libero/libero/vab/bimanual_env.py:38 |
| VABBimanualEnv.action_dim is the sum of both robots' action dimensions | upstream_code | libero/libero/vab/bimanual_env.py:215-217 |
| The task YAML example names robot panda with controller OSC_POSE and the two cameras at 128 x 128 | upstream_code | tasks/libero_object_target_pos_var20x20/pick_up_the_cream_cheese_and_place_it_in_the_basket.yaml:4-7 |
| The smoke test asserts the observation keys are exactly images and proprio, asserts the agentview shape from the task's camera height and width, and asserts success and language in info | upstream_code | tests/test_smoke.py:32-44 |
| requirements.txt pins robosuite 1.4.0 with numpy, opencv-python, matplotlib, pyyaml and pydantic | vendor_doc | requirements.txt:1-6 |
| setup.py declares python_requires >=3.8 and name libero | upstream_code | setup.py:12-18 |

## Capabilities and limits

`cap.world.step.v1` takes `ticks` and an action object whose `values` array is the control vector. The driver applies
the vector at every tick and calls `VABEnv.step`; the catalogue class's own `ticks` bound (1 to 10000) is enforced by
the served input schema, not by a driver-declared `Limit`. `cap.world.reset.v1` takes the integer `seed`, which is the
environment's initial-state index (`reset(init_index=seed)`), and returns the selected index as its required `seed`
output. `cap.world.seed.v1` is not bound: the environment exposes no RNG seed, only the initial-state selector.

The driver declares no `Limit` and no `operator_required` bound. The clone states no numeric bound on the control
vector: the YAML names the `OSC_POSE` controller, but its action width and its per-element ranges belong to
robosuite, not to this clone (`env.py:282-283` returns `robots[0].action_dim` and states no number). The number of
initial states is per-task: `README.md:13-19` shows 50 seeds for the single-arm suites and `README.md:20` shows 5 for
the crate task; the fake has 50 placeholder indices, and the real environment raises `IndexError` outside its own
`inits` (`env.py:189-193`).

## Fidelity

The fake backend (`fake.py`) is a pure Python stand-in for VABEnv: it implements the same `reset`, `step`,
`delivery_progress`, `reward`, `language_instruction` and `action_dim` members (gate G7) but no MuJoCo, robosuite
scene, contact, controller or success-predicate logic. Its camera frames are 2 x 2 x 3 placeholders; the real task
YAMLs request 128 x 128 x 3 (`README.md:93-94`). Its proprio arrays use the documented lengths but Python floats
rather than float32 numpy arrays. The fake was never compared with the upstream environment because robosuite,
MuJoCo, numpy and pyyaml were not installed where the gate ran. The gaps are listed in the `fidelity` attribute of
`driver.py`.

The package is model-authored and unreviewed (`driver.lock.json` `reviewed_by` is null). It is checked on the fake
backend only; no hardware was attached and no hardware or sim-environment run is claimed.

Tags: simulation, robosuite, mujoco, manipulation, robot, benchmark, reinforcement-learning
