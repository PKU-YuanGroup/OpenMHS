# Facts and tags for gh.facebookresearch/house3d

Every fact cites its source at commit `e616837a99c2a209212d5556bdbb3dda75298ca9`. `vendor_doc` facts cite a text
file of the clone; `upstream_code` facts cite `path/in/clone.py:LINE`. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| House3D is a virtual 3D environment of thousands of indoor scenes sourced from the SUNCG dataset, with over 45k indoor 3D scenes | vendor_doc | README.md:7-9 |
| Agents observe RGB images, depth, segmentation masks and top-down 2D map views | vendor_doc | README.md:11-13 |
| RoomNavTask is a gym.Env subclass | upstream_code | House3D/roomnav.py:76 |
| RoomNavTask requires its env argument to be an Environment instance | upstream_code | House3D/roomnav.py:110 |
| The constructor defaults segment_input=True, joint_visual_signal=False, depth_signal=True and discrete_action=False | upstream_code | House3D/roomnav.py:82-87 |
| The observation space is Box(0, 255) with shape (resolution[0], resolution[1], n_channel), where n_channel starts at 3, gains 3 for joint_visual_signal and 1 for depth_signal | upstream_code | House3D/roomnav.py:119-127 |
| The pixel criteria are stated for the default resolution 120 x 90 | upstream_code | House3D/roomnav.py:58 |
| The thirteen discrete actions are forward, left, right, left-forward, right-forward, rotate left, rotate right, backward, small forward, small left, small right, small rotate left and small rotate right | upstream_code | House3D/roomnav.py:49-54 |
| n_discrete_actions is len(discrete_actions) | upstream_code | House3D/roomnav.py:55 |
| discrete_action=True selects spaces.Discrete(n_discrete_actions); otherwise the action space is a Tuple of Box(0, 1, (4,)) and Box(0, 1, (2,)) | upstream_code | House3D/roomnav.py:131-135 |
| rotation_sensitivity is 30 degrees per time step and default_move_sensitivity is 0.5 | upstream_code | House3D/roomnav.py:45-46 |
| success_distance_range is 1.0, success_stay_time_steps is 5 and success_see_target_time_steps is 2 | upstream_code | House3D/roomnav.py:40-42 |
| The reward constants are collision_penalty_reward 0.3, stay_room_reward 0.1 and success_reward 10 | upstream_code | House3D/roomnav.py:30-34 |
| reset clears the episode counters, resets the house and target, draws a birth place with random.choice, teleports the environment and returns the rendered observation | upstream_code | House3D/roomnav.py:215-245 |
| step scales the action tuple by move_sensitivity and rot_sensitivity, rotates then moves, charges the collision penalty when move_forward returns False, adds the in-room reward at distance zero and adds the success reward when _is_success returns True | upstream_code | House3D/roomnav.py:286-319 |
| max_steps > 0 ends the episode when current_episode_step reaches max_steps | upstream_code | House3D/roomnav.py:321-322 |
| Environment.info returns house_id, loc, yaw, grid, front and right | upstream_code | House3D/core.py:259-264 |
| RoomNavTask.info adds dist, scaled_dist, optsteps, collision and target_room | upstream_code | House3D/roomnav.py:370-378 |
| move_forward translates by the forward and horizontal distances and returns whether move accepted the new position | upstream_code | House3D/core.py:196-207 |
| rotate adds the degrees to the camera yaw | upstream_code | House3D/core.py:209-215 |
| Environment.reset teleports the agent to x, y and yaw and draws a random connected coordinate and a yaw in [-180, 180) when they are not given | upstream_code | House3D/core.py:231-246 |
| Setting seed in Environment seeds numpy and Python's random module | upstream_code | House3D/core.py:67-69 |
| MultiHouseEnv builds one House per id in a multiprocessing Pool and reset_house selects a house by index or at random | upstream_code | House3D/core.py:347-381 |
| The upstream install requirements are gym and numpy only | upstream_code | setup.py:17-20 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the environment
(`Discrete(13)` from `House3D/roomnav.py:55,133`: `action.index` from 0 to 12) together with `ticks` (1 to
`max_ticks`, 10000 by default). The device is simulated (R0), so no limit is `operator_required` and there is no
`site-limits.example.json`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `House3D RoomNavTask (kinematic discrete-action
stand-in)`, level F0 (positions and state transitions are modelled directly; there are no dynamics or contacts),
determinism `seeded` with `seed_control` `parameter`, timestep 0 ms (one tick is one navigation step, not a fixed
physics interval), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps say what is
not modelled: no renderer, no SUNCG house, a reduced 4x4x4 observation, reduced reward shaping, a distance-based
success proxy, no continuous action tuple, reset options ignored, and no comparison with the upstream environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable.

Tags: house3d, roomnav, navigation, 3d-scenes, suncg, reinforcement-learning, simulation.
