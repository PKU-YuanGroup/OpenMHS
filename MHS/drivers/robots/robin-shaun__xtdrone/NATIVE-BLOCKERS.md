OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Scope record: position subset and world pause

The accepted surface of this package is the typhoon_h480_0 position-setpoint subset plus the vendored gazebo_ros world pause. A passing fake gate is `contract_checked` evidence of that surface. It is not a hardware run and it is not a simulator run.

The 2026-11-04 review said not to accept a position-only replacement for the full flight workflow. The 2026-11-05 verifier's safer alternative is the path this repair takes: bind the pause and its read-back, state the scope, and leave arming and OFFBOARD outside MHS. The full workflow stays outside. This file records that boundary. It does not ask the gate to fail.

| Surface | Where the clone shows it | What this package does |
|---|---|---|
| Position setpoint | `contributer_demo/demo1/doc/rostopic list:117`; type import `communication/multirotor_communication.py:4` | Publishes one `geometry_msgs/PoseStamped` on `/typhoon_h480_0/mavros/setpoint_position/local`. The receipt reports `sent_x`, `sent_y` and `sent_z`. Transmission only. |
| Target and pose reads | topic list lines 123 and 84 | Explicit read capabilities. They are not on the device resource, because a paused lockstep world may publish nothing (`sitl_config/models/typhoon_h480/typhoon_h480.sdf:1288` sets `enable_lockstep` true). The fake's silence while paused is that assumption, not a measured PX4 trace. |
| World pause | `sitl_config/gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:508-514` and `:1738-1742`; type at `sitl_config/gazebo_ros_pkgs/gazebo_ros/test/ros_network/gazebo_network_api.yaml:85-86` | E-stop calls `/gazebo/pause_physics`. |
| Paused-flag read-back | plugin `:389-395` and `:1484`; yaml `:55-56`; `GetPhysicsProperties.srv:4` | Confirmed only when `pause` is true. A non-ODE engine returns false (`:1516-1523`) and the e-stop stays unconfirmed with the latch held. |
| Unpause | plugin `:517-523` and `:1744-1748` | Not bound. SAFE-042: `communication/multirotor_communication.py:55-61` republishes `target_motion` until shutdown and `:149-151` ignores `stop controlling`. This package cannot clear that retained target. PX4 offboard retention is not traced here; the PX4 launch is `$(find px4)` (`sitl_config/launch/multi_vehicle.launch:28`). |
| Arm and mode | `communication/multirotor_communication.py:50-51`; `communication/plane_communication.py:40-41`; namespace `sitl_config/launch/multi_vehicle.launch:22` | Citable and intentionally not bound. Arming and OFFBOARD are done outside MHS. The earlier claim that G7 cannot cite these services is dropped. |
| Velocity, acceleration, landing, state | `communication/multirotor_communication.py:35-41`, `:67`, `:127-139` | Outside this package. The acceleration callbacks pass `ax`/`ay`/`az` into a constructor that accepts `afx`/`afy`/`afz` and stay unsupported. |

`mhs.safety.reset` releases the MHS latch and leaves the world paused. The operator recovers outside MHS: disarm or land, then the Gazebo GUI (`empty_world.launch:51-54` starts `gzclient` when `gui` is true, and `multi_vehicle.launch:9` defaults `gui` to true) or `rosservice call /gazebo/unpause_physics`. A GUI or any other client can unpause without MHS watching. `safety_status` returns the cached confirmation from the last successful read-back and does not call `/gazebo/get_physics_properties` again (`MHS/sdk/src/mhs/bridge/ros.py:2199-2232`), so it cannot detect that unpause. The read-back runs inside the e-stop (`ros.py:2099`) and inside `safe_state` (`ros.py:2110-2115`).

The pause covers every vehicle in the world, including `typhoon_h480_1` (`multi_vehicle.launch:51`). This package commands only `typhoon_h480_0`.

Risk is R2 because the MAVROS setpoint is a command a real PX4 can consume (`README.en.md:7`, REVIEW.md item 12). The pause service itself is the simulator world pause. Position bounds stay `operator_required`. `site-limits.example.json` is example test data.

Version evidence in the clone is vendored gazebo_ros 2.8.7 (`package.xml:4`), changelog header `2.8.7 (2020-05-01)`, catkin (`package.xml:22`), README links on `melodic-devel`, and `docs/RELEASE.md:19` listing ROS Melodic with Gazebo 9. The changelog line does not name a distro. This package claims no Noetic build. The deployment must run a ROS 1 gazebo_ros that serves these services, such as this vendored 2.8.7. If `enable_ros_network` is false, `advertiseServices` returns without advertising (`gazebo_ros_api_plugin.cpp:274-277`) and the e-stop fails closed.
