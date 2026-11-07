# Facts and tags for gh.aalmuzairee/squint

Every fact cites its source at commit `7086fd516eda7df585a5261c541e0670a6d916b4`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| SO101LiftCube-v1 is registered with `max_episode_steps=50`, and LiftCube fixes `item_type` to cube | upstream_code | envs/lift.py:407-410 |
| Lift defaults to `robot_uids='so101'` and `control_mode='pd_joint_target_delta_pos'` | upstream_code | envs/lift.py:59-61 |
| The six-joint delta controller uses lower bounds -0.1 for the arm and -0.2 for the gripper, upper bounds 0.1 and 0.2, and does not set `normalize_action` | upstream_code | envs/robot/so101.py:97-109 |
| The default simulation config is `SimConfig(sim_freq=100, control_freq=10)`: one control step is 0.1 s | upstream_code | envs/base_random_env.py:146-148 |
| The wrist camera renders 128x128 images | upstream_code | envs/base_random_env.py:521-527 |
| The trainer renders at 128 and downsamples the policy input to 16 | upstream_code | train_squint.py:107-110 |
| The state observation includes qvel, grasp flag, item pose, tcp pose, item-to-tcp vector and rest-pose distance | upstream_code | envs/lift.py:328-341 |
| Success requires the item lifted, grasped and the arm within 0.2 of the rest joint pose | upstream_code | envs/lift.py:354-373 |

Limits: the driver declares none. The only bounds are the action space, which the bridge derives from the fake's
spaces (`action.values` -1 to 1 per element, which `REFERENCE.md` prints with `no source: action_space of the fake
backend .fake:FakeSO101LiftCube`), and `ticks` (1 to `max_ticks`, 10000 by default). The -1 to 1 is the upstream's
normalised action: the controller config above does not set `normalize_action`, whose ManiSkill default is True, so
ManiSkill serves `Box(-1, 1)` of the controller's shape and scales each value to the joint deltas above
(`mani_skill/agents/controllers/pd_joint_pos.py:131`, `base_controller.py:70-72` and
`mani_skill/utils/gym_utils.py:104-112`, read in the clone `robots/mani-skill/maniskill` at `62ff3a58`, because
`environment.yaml:15` installs an unpinned `mani_skill_nightly`). Those lines are ManiSkill's, not this clone's, so the driver sets no `action_space_ref` and the
bound has no source. `fake.py` copies the space and the scaling; its other numbers are placeholder test data, not facts
or limits of this package. The device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `maniskill3:squint/SO101LiftCube-v1`, level F0 (the fake is
an analytic kinematic stand-in, no dynamics), determinism `seeded` with `seed_control` `parameter`, timestep 100 ms
(`control_freq=10`, `envs/base_random_env.py:148`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot
and restore. The gaps say what is not modelled, that the real camera is 128x128 while the fake returns 4x4x3, that
the fake was never compared with the upstream environment, and that the step bounds come from ManiSkill.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: so101, manipulation, lift, reinforcement-learning, simulation, maniskill, gymnasium
