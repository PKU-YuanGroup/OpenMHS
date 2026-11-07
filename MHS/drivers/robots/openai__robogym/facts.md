# Facts and tags for gh.openai/robogym

Every fact cites its source at commit `9ff1111fd557b1a01911d7d8c9d59a453071c96e`; all are `upstream_code` (an MJCF
or Python file of the clone). The same facts are written into `driver.py` (`facts = [...]`); the reference file is
generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The card's first model is the MJCF scene main.xml, whose root element is '<mujoco>' | upstream_code | robogym/assets/xmls/robot/shadowhand/main.xml:2 |
| The scene includes assets.xml | upstream_code | robogym/assets/xmls/robot/shadowhand/main.xml:4 |
| The scene includes joint_position_actuation.xml, the joint position servos | upstream_code | robogym/assets/xmls/robot/shadowhand/main.xml:6 |
| The hand mount carries the free joint hand_base | upstream_code | robogym/assets/xmls/robot/shadowhand/main.xml:19 |
| The scene includes chain.xml | upstream_code | robogym/assets/xmls/robot/shadowhand/main.xml:20 |
| The model sets the MuJoCo integration step to 0.008 s in its option element | upstream_code | robogym/assets/xmls/robot/shadowhand/assets.xml:14 |
| The asset_class default sets ctrllimited and forcelimited on its actuators | upstream_code | robogym/assets/xmls/robot/shadowhand/assets.xml:78 |
| The actuator section declares 20 general actuators, each with an explicit ctrlrange | upstream_code | robogym/assets/xmls/robot/shadowhand/joint_position_actuation.xml:72-96 |
| The actuator comment says the ctrlranges follow Shadow's technical specification, page 8, except THJ0 whose sign is reversed in this config | upstream_code | robogym/assets/xmls/robot/shadowhand/joint_position_actuation.xml:68-70 |
| The first actuator A_WRJ1 has ctrlrange -0.4887 to 0.1396 rad | upstream_code | robogym/assets/xmls/robot/shadowhand/joint_position_actuation.xml:72 |
| The actuator A_FFJ2 has ctrlrange 0.0 to 1.5708 rad | upstream_code | robogym/assets/xmls/robot/shadowhand/joint_position_actuation.xml:76 |
| The actuator A_THJ0 has ctrlrange -1.5708 to 0.0 rad | upstream_code | robogym/assets/xmls/robot/shadowhand/joint_position_actuation.xml:96 |
| The hand chain is a tree of 24 hinge joints: WRJ1/WRJ0, FFJ0-FFJ3, MFJ0-MFJ3, RFJ0-RFJ3, LFJ0-LFJ4 and THJ0-THJ4 | upstream_code | robogym/assets/xmls/robot/shadowhand/chain.xml:15-239 |
| The wrist joint WRJ1 is a hinge with range -0.4887 to 0.218757 rad | upstream_code | robogym/assets/xmls/robot/shadowhand/chain.xml:15 |
| The wrist joint WRJ0 is a hinge with range -0.8 to 0.4887 rad | upstream_code | robogym/assets/xmls/robot/shadowhand/chain.xml:21 |
| The thumb joint THJ0 is a hinge with range -1.78625 to 0.104035 rad | upstream_code | robogym/assets/xmls/robot/shadowhand/chain.xml:239 |
| ReachEnv loads the card's model as robot/shadowhand/main.xml | upstream_code | robogym/envs/dactyl/reach.py:69 |
| CubeEnv, the base of the dactyl cube environments, loads robot/shadowhand/main.xml | upstream_code | robogym/envs/dactyl/common/cube_env.py:151 |

Limits: the driver declares none of its own. The only bounds are the 20 per-actuator `ctrlrange` values of the model,
which the bridge derives into `action.ctrl` (source `upstream_code`, ref
`robogym/assets/xmls/robot/shadowhand/main.xml:actuator_ctrlrange`), and `ticks` 1 to `max_ticks` (10000, the family default). The device is
simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `mujoco:shadowhand`, level F1, determinism `exact` with
`seed_control` `none`, timestep 8 ms (`assets.xml:14`), `realtime_factor` 0, clock `lockstep`, reset `full`. The
stand-in implements the bridge's snapshot calls and MuJoCo offers `mj_getState`/`mj_setState`, so the family
publishes `snapshot_restore` true; the engine path was not run. The gaps say what is not modelled: the fake is not
MuJoCo, the four tendon-driven actuators move no joint in the stand-in, no mesh/contact/tendon dynamics, the hand
base free joint is not integrated, the environments compose more than this model, and neither the engine nor a
physical hand was run.

Safety: simulated R0 device. The e-stop is the runtime's software latch (the simulator has no native stop); after it
no step or reset is accepted until `mhs.safety.reset` clears the latch, and the integration state stays readable.

Tags: shadowhand, dexterous-hand, manipulation, mujoco, simulation, robot
