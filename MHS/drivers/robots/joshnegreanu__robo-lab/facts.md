# Facts and tags for gh.joshnegreanu/robo-lab

Every fact cites its source at commit `f7d677dd46324e1805ad13057e1cf3359a166443`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

The model is the card's `models[0]`, `assets/trlc_dk1/scene_blocks.xml`; it is read from the read-only clone in
place and is never copied into this package. The card's second model, `assets/trlc_dk1/scene_dishes.xml`, is
documented below but is not served by this driver.

| fact | source | ref |
|---|---|---|
| The repository is teleoperated data collection and imitation learning for a TRLC DK1 bimanual arm pair, with a MuJoCo simulator and WebXR control from a Meta Quest | vendor_doc | README.md:3 |
| The two environments are blocks (default), two 4.5 cm cubes and a bowl with the instruction 'put both blocks in the bowl', and dishes, plate, bowl, cup, fork, knife, spoon and a static dish rack with the instruction 'put all the dishes and silverware in the dish rack' | vendor_doc | README.md:110-113 |
| The gripper jaws open to 82 mm; the plate is 277 mm across, the bowl 144 mm and the cup 83 mm | vendor_doc | README.md:131 |
| Each environment's scene is generated and committed as assets/trlc_dk1/scene_<env>.xml, one per environment | vendor_doc | README.md:325-327 |
| The blocks scene is an MJCF model whose root element is '<mujoco model="MuJoCo Model">' | upstream_code | assets/trlc_dk1/scene_blocks.xml:1 |
| The scene compiles angles in radians and resolves mesh files from the model's own directory | upstream_code | assets/trlc_dk1/scene_blocks.xml:2 |
| The scene selects the implicitfast integrator and sets no timestep: its option element carries only integrator | upstream_code | assets/trlc_dk1/scene_blocks.xml:4 |
| The left arm has six hinge joints named left_joint1 to left_joint6 with ranges +-2.0944, -0.0872665 to 3.14159, -0.0872665 to 4.71239, -1.95 to 1.5708, +-1.5708 and +-2.0944, and two slide joints left_gripper_left and left_gripper_right with range -0.045 to 0.001 | upstream_code | assets/trlc_dk1/scene_blocks.xml:82-112 |
| The right arm has six hinge joints named right_joint1 to right_joint6 with ranges +-2.0944, -0.0872665 to 3.14159, -0.0872665 to 4.71239, -1.95 to 1.5708, +-1.5708 and +-2.0944, and two slide joints right_gripper_left and right_gripper_right with range -0.045 to 0.001 | upstream_code | assets/trlc_dk1/scene_blocks.xml:133-163 |
| The two target bodies left_target and right_target are declared mocap bodies (mocap='true') | upstream_code | assets/trlc_dk1/scene_blocks.xml:181-186 |
| The blocks scene places two free-jointed cubes, red_cube and blue_cube, with 0.045 kg box geoms of half-size 0.0225 m, and a free-jointed dish_bowl body | upstream_code | assets/trlc_dk1/scene_blocks.xml:187-196 |
| The actuator block has 16 general actuators, eight per arm: one position actuator per hinge joint and per gripper slide joint | upstream_code | assets/trlc_dk1/scene_blocks.xml:299-315 |
| The joint actuator control ranges are +-2.0944, -0.0872665 to 3.14159, -0.0872665 to 4.71239, -1.95 to 1.5708, +-1.5708 and +-2.0944 on both arms, and the four gripper actuators have ctrlrange -0.045 to 0.001 | upstream_code | assets/trlc_dk1/scene_blocks.xml:300-315 |
| The left gripper actuators are force-limited to -20 to 20 and carry a gain of 300 | upstream_code | assets/trlc_dk1/scene_blocks.xml:306-307 |
| The right gripper actuators are force-limited to -20 to 20 and carry a gain of 300 | upstream_code | assets/trlc_dk1/scene_blocks.xml:314-315 |
| The dishes scene, the card's second model, has a static dish_rack body with no joint and six free-jointed pieces: dish_plate, dish_bowl, dish_cup, utensil_fork, utensil_knife and utensil_spoon | upstream_code | assets/trlc_dk1/scene_dishes.xml:330-516 |

Limits: the driver declares none and there is no `site-limits.example.json`. The only action bound is the control
vector, which the MuJoCo bridge derives at run time from the model's `actuator_ctrlrange`: 16 channels, the six
joint ranges and the gripper range `-0.045` to `0.001` of each arm, from `scene_blocks.xml:300-315`. `ticks` is
bounded by the class input schema (1 to 10000). The device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `mujoco:scene_blocks`, level F1, `realtime_factor` 0,
clock `lockstep`, reset `full`; determinism and `snapshot_restore` are derived by the bridge. The gaps say that the
fake backend is a stand-in for the MuJoCo library rather than MuJoCo (placeholder first-order integration, no
meshes, contacts or constraints), that the model states no timestep so the published step comes from the stand-in's
placeholder default, that the stand-in resets qpos to zero rather than model `qpos0`, and that no trajectory was
compared with the real engine.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the
integration state stays readable.

Tags: trlc-dk1, bimanual, robot-arm, manipulation, mujoco, simulation, robo-lab
