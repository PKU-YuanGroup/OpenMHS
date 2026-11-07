# ROS-INSTALL-RECIPES — identify root build tools from pinned source

Task-card generation previously treated any root `package.xml` as a colcon build
and any `setup.py` as pip-installable. That produced incorrect recipes for the
Catkin packages in the ROS batch, including ROS Gazebo Gym and MultiROS.

The installation scanner now reads the root `package.xml`, `CMakeLists.txt` and
`setup.py` from regular Git blobs at the selected commit. It records build-tool
markers with their file/line and pin. Explicit Catkin evidence selects
`catkin_make`, with the prerequisite that the package is in a configured Catkin
workspace's `src` directory and the command runs from the workspace root. Ament
evidence selects `colcon build`. Ambiguous, conditional, unavailable or unknown
ROS build evidence leaves an installation reconnaissance requirement instead of
guessing. A Catkin setup script no longer emits `pip install .`.

The reader does not execute setup code, import the clone, infer a ROS
distribution or supply a complete dependency recipe. Symlinks, gitlinks,
unavailable explicit pins, oversized files and unsupported XML declarations fail
closed. Comments and quoted example text do not identify a build tool. Nested
ROS packages remain outside this root-only decision. Other existing scanner
facts still use their prior worktree scan; this change does not claim to pin
those facts. Scanner version 11 invalidates the old cached scan.

The isolated patch passed 165 tests, including 17 new pinned-source and recipe
cases. Exact local source probes classified ROS Gazebo Gym and MultiROS as Catkin
and ros2_usb_camera as ament; repositories with only nested ROS packages did not
receive an invented root recipe. The parent integrated six reviewed files with
matching before/after hashes. Integrated testing and registry regeneration are
recorded in the combined completion run; no ROS installation or build was run.

Private patch, original files, pinned probe evidence and test logs are under
`work/handoff-runs/mhs-build-20261102/development/install-recipes/`.

The November 3 export checkpoint exposed an outdated test allowlist that omitted
the now-supported `catkin_make` recipe. The correction adds only that exact
literal. An independent inventory checked all 2967 task cards and the pinned
build-tool evidence for all 124 ROS build recipes. All 302 actual registry tests
pass after integration. Production scanning, generated cards and schemas were
unchanged by this test correction. Corrected export checkpoint 2 subsequently
passed all 19 steps, including all 302 registry tests inside the isolated export.
All 17308 actual export inputs remained unchanged.
