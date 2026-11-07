# Facts and tags for gh.px4-gazebo-simulation/drl_uav

Every fact cites the pinned clone at commit `55e2a0a97c70f584b0a272176999148985f5ee46`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the
statement spans adjacent lines. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The clone describes deep reinforcement learning for a UAV in a Gazebo simulation environment. | vendor_doc | ReadMe.md:2 |
| The documented deployment is Gazebo, Pixhawk and ROS SITL, started together with MAVROS, an external state_machine node and this package's talker.py. | vendor_doc | ReadMe.md:91-122 |
| The documented DRL state is [Pos_z, Vel_z, Thrust], the action set is {0, 1, -1} (0 decreases thrust, 1 increases thrust and -1 restarts the environment), and the reward is 1 inside 19.7 < Pos_z < 20.3 and 0 otherwise. | vendor_doc | ReadMe.md:15-30 |
| The clone lists Gazebo constraints thrust [0.40, 0.78], Vel_z [-3.0, 3.0] and Pos_z [10, 30] for training; these describe the external Gazebo environment, not the game topic envelope. | vendor_doc | ReadMe.md:124-130 |
| talker.py imports Num, Input_Game and Output_Game from the generated drl_uav.msg package. | upstream_code | scripts/talker.py:16-18 |
| talker.py advertises Input_Game on the relative game_input topic with queue size 10. | upstream_code | scripts/talker.py:219 |
| talker.py publishes the current env_input action on game_input in interact(). | upstream_code | scripts/talker.py:267 |
| talker.py subscribes Output_Game on the relative game_status topic. | upstream_code | scripts/talker.py:312 |
| talker.py sets the action to -1.0 and publishes it to restart the game after a done condition. | upstream_code | scripts/talker.py:408-411 |
| game_test.py describes itself as a test platform of the game environment and advertises Output_Game on the relative game_status topic with queue size 10. | upstream_code | scripts/game_test.py:1-15 |
| game_test.py subscribes Input_Game on the relative game_input topic. | upstream_code | scripts/game_test.py:41 |
| The toy game resets pos1 to 3.5 when the action is greater than 100.0, adds 0.1 to pos1 for action 1.0 and subtracts 0.1 for action 0.0. | upstream_code | scripts/game_test.py:24-32 |
| game_test.py publishes game_status at 10 Hz from a rospy.Rate(10) loop. | upstream_code | scripts/game_test.py:49-58 |
| game_test.py initializes the game status with vel1 0.5 and pos1 3.5. | upstream_code | scripts/game_test.py:16-18 |
| player_test.py sets the action to 200.0 when the reported UAV altitude is outside [8.0, 30.0] to restart the environment. | upstream_code | scripts/player_test.py:43-45 |
| Input_Game contains one float64 field named action. | upstream_code | msg/Input_Game.msg:1 |
| Output_Game contains four float64 fields named vel1, vel2, pos1 and pos2. | upstream_code | msg/Output_Game.msg:1-4 |
| The package declares only message files; its service and action sections are commented out. | upstream_code | CMakeLists.txt:51-74 |
| talker.py ends with a Python 2 print statement, so the script is not importable under Python 3. | upstream_code | scripts/talker.py:458 |

## Scope

The package serves the clone's only in-repo environment contract: the relative `game_status` topic
(`drl_uav/Output_Game`) as resource reads and an explicit observation, and one publication of
`drl_uav/Input_Game` on the relative `game_input` topic. Both names are relative in the clone; the driver
configures the root-resolved `/game_status` and `/game_input`, so a namespaced deployment must expose or
remap the same resolved endpoints. This is a deployment assumption, not an upstream Fact.

The real environment is external. `ReadMe.md:91-122` starts MAVROS, PX4/Gazebo and an external
`state_machine` node, and the DRL node also reads `mavros/local_position/pose`,
`mavros/local_position/velocity` and `/mavros/setpoint_raw/attitude`; those topics, their message types,
the Gazebo/PX4 dynamics and the state machine are NOT COVERED. The in-clone `scripts/game_test.py` is a toy
test platform, not the UAV simulator.

## Limits

The single numeric input is the `float64` action field of `Input_Game`. The ReadMe states the DRL action
vocabulary `{0, 1, -1}` (`ReadMe.md:18-24`), and the driver declares exactly that set. The clone is
inconsistent about the restart sentinel: `scripts/game_test.py:24` restarts when `action > 100.0` and
`scripts/player_test.py:44-45` publishes 200.0, while `scripts/talker.py:408-411` publishes -1.0. The
driver follows the documented README vocabulary and discloses that a deployment using 100/200 is outside
its envelope. `Output_Game`'s four fields have no documented unit or physical meaning; the driver asserts
neither.

## Fidelity contract

`driver.py` describes the deployed fake: engine `analytic:ROS-free recording fake for the drl_uav game
topic contract (no physics)`, level F0, determinism `none`, `timestep_ms: 0`, `realtime_factor: 0`,
reset `none`, and no snapshot/restore. The fake models the toy `game_test.py` semantics only; it runs no
UAV dynamics, no 10 Hz pacing and no Gazebo/PX4/MAVROS/state_machine process. It ignores the README's -1
restart request exactly as `game_test.py` does.

## Safety

The device is simulated at R0: the served contract has no physical effect. The clone defines no stop
service or stop action (`CMakeLists.txt:62-74`), so the driver declares no e-stop or safe-state binding.
An MHS e-stop engages only the software latch, calls nothing upstream and reports
`MHS.SAFETY.SAFE_STATE_UNREACHED`; the external game environment keeps running. A publication has no
execution acknowledgement and is never a stop, a restart confirmation or a quiescence proof. This is a
model-authored, unreviewed package; no ROS graph, simulator, hardware or human review is claimed.

## Tags

`ros`, `ros1`, `simulation`, `reinforcement-learning`, `uav`, `game`, `drl`
