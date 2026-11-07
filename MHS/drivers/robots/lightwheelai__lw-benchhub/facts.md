# Facts and tags for gh.lightwheelai/lw-benchhub

Every fact cites a file tracked by the read-only clone at commit `b2bcb2d00edef691f9fcc49039cbf0bcc7464605`.  The same
facts are in `driver.py` (`facts = [...]`); `reference.json` and `REFERENCE.md` are generated from the driver, not from
this page.  Paths under `third_party/IsaacLab-Arena` are submodule content and are not present in the parent commit's
tree, so no Fact cites them.

| fact | source | ref |
|---|---|---|
| LW-BenchHub describes itself as a unified benchmark hub built on Isaac Lab-Arena for embodied AI | vendor_doc | README.md:7 |
| The package description is "Isaac Lab based Benchmark for Robotics" | vendor_doc | pyproject.toml:11 |
| The Gymnasium id Robocasa-Rl-G1LiftObjStateRL is registered with entry_point isaaclab.envs:ManagerBasedRLEnv and an env_cfg_entry_point in lw_benchhub_rl.lift_obj.lift_obj | upstream_code | lw_benchhub_rl/__init__.py:18-27 |
| LwEnvBuilder takes the arena environment, the parsed arguments and the RL config, and lets the RL config modify the environment config | upstream_code | lw_benchhub/core/env_builder/env_builder.py:29-45 |
| LwTaskBase is the base class of the package's task definitions | upstream_code | lw_benchhub/core/tasks/base.py:163 |
| LwTaskBase.modify_env_cfg sets an 8.0 s episode, a 1/100 s physics step (100 Hz) and decimation 2 | upstream_code | lw_benchhub/core/tasks/base.py:241-249 |
| The task termination config binds success to the task's check_success_caller | upstream_code | lw_benchhub/core/tasks/base.py:204-205 |
| The LiftObj task is named LiftObj | upstream_code | lw_benchhub_tasks/lightwheel_robocasa_tasks/single_stage/lift_obj.py:40 |
| The LiftObj task fixes the object pose at (2.94, -4.08, 0.95) | upstream_code | lw_benchhub_tasks/lightwheel_robocasa_tasks/single_stage/lift_obj.py:44 |
| The LiftObj object is sampled from the cube group and marked graspable | upstream_code | lw_benchhub_tasks/lightwheel_robocasa_tasks/single_stage/lift_obj.py:58-66 |
| LiftObj success requires the object root height to be at least 0.965 m | upstream_code | lw_benchhub_tasks/lightwheel_robocasa_tasks/single_stage/lift_obj.py:88-89 |
| The G1 RL right-arm action is a joint-position action over right_shoulder.*, right_wrist.* and right_elbow.* | upstream_code | lw_benchhub/core/robots/unitree/g1.py:194-197 |
| The Dex3 right hand uses a BinaryJointPositionActionCfg in the rl hand mode | upstream_code | lw_benchhub/core/models/grippers/dex3.py:72-79 |
| The state-based G1 policy observation group concatenates joint position, joint velocity, the object pose command, the last action and the object position | upstream_code | lw_benchhub_rl/lift_obj/lift_obj.py:63-79 |
| The RL task resets the object with x and y offsets in (-0.08, 0.08) and a yaw in (0, 90) degrees | upstream_code | lw_benchhub_rl/lift_obj/lift_obj.py:139-146 |

Limits: the driver declares none.  The upstream environment builds its action space from the action manager in the
Isaac Lab submodule and it is an unbounded Box, so no numeric action bound exists in a text of the parent clone;
inventing one would be false.  The bridge still publishes the action structure (8 numbers for one environment) and
refuses a wrong length.  The device is simulated R0, so there is no operator-required limit.

Action dimension: the G1 RL action config has a right-arm joint-position term over the right shoulder, elbow and
wrist joints (`g1.py:194-197`) and a binary Dex3 hand term (`dex3.py:72-79`).  The stand-in uses 8 numbers: the seven
right-arm joints named by the robot model plus one binary hand command.  The exact `action_dim` properties and the
unbounded Box class live in the Isaac Lab submodule, which is not part of the pinned parent tree; they are named in
the driver prose and in the fake's comments, not in a Fact.  The real action space is batched over `num_envs`; the
fake models one environment.

Observation: the real observation space is a Dict of batched Boxes, one per active observation group.  The state-based
policy group concatenates joint position, joint velocity, a 7-number object pose command, the last action and the
object position (`lift_obj.py:63-79`).  The exact group dimension is computed at run time by Isaac Lab's observation
manager; the fake publishes a `policy` group of 104 numbers built from the G1 43-dof joint count (43 + 43 + 7 + 8 + 3)
as a stand-in, and `RESULT.json` names that choice.  The fake does not model the other observation groups.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `isaaclab`, level F1 (rigid-body dynamics with contacts),
timestep 20 ms of control time (8.0 s episode / (1/100 s physics step * decimation 2), `base.py:241,247,249`; the
10 ms physics substep is named in the gaps), determinism `seeded` with `seed_control` `parameter`, `realtime_factor`
0, clock `lockstep`, reset `full`, no snapshot/restore (the upstream ManagerBasedRLEnv defines no get_state/set_state),
and gaps for the unmodelled engine, scene, cameras, wall-clock pacing and the fake's placeholder dynamics.
No GPU run of the upstream environment was made.

Safety: simulated R0 device (the catalogue `cap.world.*` classes are R0).  The e-stop is the runtime's software latch
(no native stop exists); after it no step or reset is accepted until `mhs.safety.reset` clears the latch, and the
environment state stays readable.  No hardware backend exists, and nothing was attached.

Tags: lw-benchhub, robocasa, unitree-g1, manipulation, isaac-lab-arena, reinforcement-learning, simulation, gymnasium
