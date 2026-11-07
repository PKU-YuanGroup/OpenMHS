# Facts and tags for gh.huggingface/lerobot-libero

Every fact cites the clone at commit `14fd6f022ff6647defc24e73563b95aa36670f43`; the same facts are written in
`driver.py` (`facts = [...]`), and the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| LIBERO is designed for studying knowledge transfer in multitask and lifelong robot learning | vendor_doc | README.md:26 |
| LIBERO provides 130 tasks grouped into four task suites: LIBERO-Spatial, LIBERO-Object, LIBERO-Goal and LIBERO-100 | vendor_doc | README.md:32 |
| The README creates OffScreenRenderEnv with a 128x128 camera, calls env.seed(0) and then env.reset() | vendor_doc | README.md:119-126 |
| The README steps the environment with a seven-element zero action and unpacks obs, reward, done, info | vendor_doc | README.md:131-133 |
| The README says only a sparse reward is supported: +1 when the task is finished | vendor_doc | README.md:136 |
| The package is published as libero and requires Python >=3.8 | upstream_code | pyproject.toml:6-14 |
| The runtime pins robosuite==1.4.0 and bddl==1.0.1 | upstream_code | pyproject.toml:23-24 |
| The entry class is registered with @register_problem and subclasses BDDLBaseDomain | upstream_code | libero/libero/envs/problems/libero_coffee_table_manipulation.py:11-12 |
| BDDLBaseDomain subclasses robosuite's SingleArmEnv | upstream_code | libero/libero/envs/bddl_base_domain.py:37 |
| The constructor requires bddl_file_name and robots and parses the BDDL problem from that file | upstream_code | libero/libero/envs/bddl_base_domain.py:42-45 |
| The constructor parses the BDDL problem file into parsed_problem | upstream_code | libero/libero/envs/bddl_base_domain.py:124-125 |
| seed calls np.random.seed(seed) | upstream_code | libero/libero/envs/bddl_base_domain.py:162-163 |
| reward is 0.0, or 1.0 when _check_success returns true | upstream_code | libero/libero/envs/bddl_base_domain.py:179-189 |
| step calls the robosuite step and then replaces done with _check_success | upstream_code | libero/libero/envs/bddl_base_domain.py:800-809 |
| The coffee-table success check ANDs every predicate of the parsed goal_state | upstream_code | libero/libero/envs/problems/libero_coffee_table_manipulation.py:133-141 |
| The base constructor defaults to camera observations (use_camera_obs=True) | upstream_code | libero/libero/envs/bddl_base_domain.py:51 |
| The default camera is agentview at 256x256 pixels | upstream_code | libero/libero/envs/bddl_base_domain.py:67-69 |
| get_robot_state_vector concatenates robot0_gripper_qpos, robot0_eef_pos and robot0_eef_quat | upstream_code | libero/libero/envs/bddl_base_domain.py:826-829 |
| language_instruction returns the parsed problem's language string | upstream_code | libero/libero/envs/bddl_base_domain.py:840-842 |

## Limits

The driver declares no `Limit` of its own. The only numeric bounds on its inputs come from the catalogue classes and
the runtime enforces them:

- `cap.world.step.v1` bounds `ticks` to 1..10000 and describes `action` as an open object;
- `cap.world.reset.v1` bounds `seed` to a non-negative integer.

The environment's action vector shape and its control period come from constructor options (`controller_configs` and
`control_freq`, `bddl_base_domain.py:47` and `:63`), not from a fixed device property, so no `Limit` is invented for
them. The device is simulated R0, so no limit is `operator_required` and there is no `site-limits.example.json`.

## Fidelity

The driver publishes F0. The backend this package can run is the package's physics-free fake: MuJoCo, robosuite and
bddl are not installed (checked with importlib.util.find_spec), the upstream package is never installed, and the
clone is never imported. The gaps in `driver.py` state that no dynamics, contacts, actuators, sensors, cameras or
noise are modelled, that the observation arrays are placeholders, that the BDDL file is not parsed, and that
`control_freq` is a constructor option rather than a fixed timestep. Camera arrays are not served; RESULT.json
records the `NOT COVERED` note.

## Safety

Simulated R0 device. There is no hardware backend and no native stop; an e-stop is the runtime's software latch,
after which no step or reset is accepted until `mhs.safety.reset` clears it, and the last observation stays readable.

Tags: libero, robosuite, mujoco, manipulation, simulation, benchmark
