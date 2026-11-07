# Facts and tags for gh.rlxai/rbot

Every fact cites its source at commit `47af3fc3780bd582837f48ce3785d3d68834a1b7`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md) or `upstream_code` (`path/in/clone:LINE`). The driver reproduces these facts in
`facts = [Fact(...)]`; the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The 2-D LiDAR is a Gazebo `gpu_lidar` sensor named `lidar_2d` on the absolute `/scan` topic with update rate 15 Hz. | upstream_code | `src/robot/rlai_description/urdf/gazebo/gazebo_sensors.urdf.xacro:39-44` |
| The sensor publishes 720 horizontal samples with resolution 1 and angle bounds -3.14159265 to 3.14159265 rad. | upstream_code | `src/robot/rlai_description/urdf/gazebo/gazebo_sensors.urdf.xacro:47-53` |
| The sensor range is 0.30 to 25.0 m with 0.01 resolution and Gaussian noise standard deviation 0.01. | upstream_code | `src/robot/rlai_description/urdf/gazebo/gazebo_sensors.urdf.xacro:55-63` |
| The sensor frame id is `lidar_2d_link`. | upstream_code | `src/robot/rlai_description/urdf/gazebo/gazebo_sensors.urdf.xacro:45` |
| The `ros_gz_bridge` maps the absolute `/scan` topic from `gz.msgs.LaserScan` to `sensor_msgs/msg/LaserScan` in the GZ_TO_ROS direction. | upstream_code | `src/simulation/rlai_gazebo/config/ros_gz_bridge.yaml:18-22` |
| The 2-D LiDAR mount comment names the topic `/scan` (LaserScan). | upstream_code | `src/robot/rlai_description/urdf/sensors/lidar_2d.urdf.xacro:5-8` |
| The architecture overview lists `/scan` as the 2D lidar signal consumed by the Nav2 costmaps and AMCL. | vendor_doc | `docs/architecture/overview.md:103` |
| The sensor testing guide checks laser data with `ros2 topic echo /scan --once`. | vendor_doc | `docs/sensors/testing-in-rich-worlds.md:21-25` |
| The README lists 2-D LiDAR among the simulated sensors. | vendor_doc | `README.md:50` |
| The top-level simulation launch exposes `lidar_2d_enabled` with default true. | upstream_code | `src/bringup/rlai_bringup/launch/simulation.launch.py:75` |
| The Gazebo launch starts the `ros_gz_bridge` node with `config/ros_gz_bridge.yaml`. | upstream_code | `src/simulation/rlai_gazebo/launch/gazebo.launch.py:235-246` |

The selected device is the simulated 2-D LiDAR. This package observes its `/scan` publication only; it does not
command the mobile base, does not expose the `/e_stop` toggle and declares no stop or safe-state binding.

The bridge refuses non-finite JSON numbers: a live scan whose no-return or out-of-range samples arrive as
non-finite values fails the observation instead of returning a substituted number (a package case covers it; model
review 2026-11-05).

Tags (short lowercase keywords): `ros`, `ros2`, `gazebo`, `simulation`, `lidar`, `laser`, `scan`, `sensor`.
