# Facts and tags for gh.carlosferrazza/humanoid-bench

Every fact cites its source at commit `cb1189039151c8aadaaa987b442da54383c87fab`: `vendor_doc` (a text file
of the clone, here README.md) or `upstream_code` (`path/in/clone:LINE`). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| h1-stand-v0 is registered by the loop that registers one <robot>-<task>-v0 environment for every robot and task, with entry point humanoid_bench.env:HumanoidEnv and the task's max_episode_steps | upstream_code | humanoid_bench/__init__.py:5-21 |
| The environment id h1-stand-v0 is documented in the benchmark's environment list | vendor_doc | README.md:131 |
| The H1 robot has dof 26 | upstream_code | humanoid_bench/robots.py:1-2 |
| The Stand observation space is a Box from -inf to +inf with shape (robot.dof * 2 - 1,) | upstream_code | humanoid_bench/envs/basic_locomotion_envs.py:40-44 |
| The observation concatenates qpos and qvel into one flat vector | upstream_code | humanoid_bench/tasks.py:32-36 |
| HumanoidEnv replaces the controller space with a Box from -1 to 1 of the model's actuator shape | upstream_code | humanoid_bench/env.py:162-166 |
| The model path is built as envs/{robot}_{control}_{task}.xml under the assets directory, so h1-stand-v0 loads envs/h1_pos_stand.xml | upstream_code | humanoid_bench/env.py:123-130 |
| The registration loop uses control pos for every robot except g1 and digit | upstream_code | humanoid_bench/__init__.py:5-9 |
| The h1_pos model has 19 position actuators in its actuator block | upstream_code | humanoid_bench/assets/robots/h1_pos.xml:231-251 |
| The stand model's MuJoCo timestep is 0.002 s | upstream_code | humanoid_bench/assets/envs/h1_pos_stand.xml:2 |
| Task.frame_skip is 10, so one environment step advances 10 physics frames | upstream_code | humanoid_bench/tasks.py:10 |
| Task.step calls do_simulation with frame_skip | upstream_code | humanoid_bench/tasks.py:60-62 |
| The default episode limit is 1000 steps | upstream_code | humanoid_bench/tasks.py:12 |
| The Stand task sets _move_speed = 0 and success_bar = 800 | upstream_code | humanoid_bench/envs/basic_locomotion_envs.py:100-102 |
| The stand reward is small_control * stand_reward * dont_move | upstream_code | humanoid_bench/envs/basic_locomotion_envs.py:67-76 |
| The episode terminates when the root height qpos[2] is below 0.2 | upstream_code | humanoid_bench/envs/basic_locomotion_envs.py:96-97 |
| Task.step always returns truncated=False; truncation is not performed by the task | upstream_code | humanoid_bench/tasks.py:69 |
| HumanoidEnv.step delegates to self.task.step(action) | upstream_code | humanoid_bench/env.py:226-227 |
| A reset restores the keyframe, adds uniform noise of +-randomness to qpos and returns the task's reset observation | upstream_code | humanoid_bench/env.py:229-242 |
| The default reset randomness is 0.01 | upstream_code | humanoid_bench/env.py:64 |
| seed(seed) calls numpy.random.seed(seed) | upstream_code | humanoid_bench/env.py:244-245 |

Limits: the driver declares none of its own. The only bound is the action space, which the Gymnasium bridge
derives from the environment (`Box(-1, 1)` with the model's actuator shape, `humanoid_bench/env.py:162-166`)
with no source and the ref `action_space of the fake backend .fake:FakeHumanoidStand`, plus the bridge's
`ticks` bound (1 to 10000). The device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `mujoco:h1-stand-v0`, level F1 (MuJoCo rigid-body
dynamics with contacts, no validation), determinism `seeded` with `seed_control` `parameter`, timestep 20 ms
(10 frames of 0.002 s, `humanoid_bench/tasks.py:10` and `humanoid_bench/assets/envs/h1_pos_stand.xml:2`),
`realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps say what the fake does
not model and that it was never compared with the upstream environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no
step or reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that),
and the last world state stays readable.

Tags: humanoid, humanoid-bench, mujoco, stand, reinforcement-learning, simulation, gymnasium
