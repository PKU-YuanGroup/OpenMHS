# shouryash007/robothon-2026 stays blocked: the simulator major is not proved

The integrator did not apply this unit's package files. Codex's package decision was not accept (`robots/shouryash007__robothon-2026` decision `block`). The package directory stays at snapshot-6. The sections below are the unit's own account.


`robots/shouryash007__robothon-2026` stays `blocked` (`HELPER_MISSING`). The E2 fresh-sample read-back and the E3 operator bridges from `COMPANION-TOPIC-READBACK.md` were not declared. REVIEW.md item 13 requires the package side and the lock profile to name the same ROS distro and simulator major, and a mismatch stays blocked. This clone names Humble and never names a simulator major. `LOCK.json` has three Humble simulator profiles: `ros2-humble-gazebo11` (lines 313 and 373), `ros2-humble-gzsim6` (Fortress) and `ros2-humble-gzsim7` (Garden, lines 1039 and 1090). There is no `ros2-humble-gzsim8` entry. Declaring `ros2-humble-gzsim6` would still assert Fortress.

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 as unit `ext-p5-gz-topic--shouryash007__robothon-2026-20261105`. No SDK change. `authored_by` stays `deepseek-v4.1-flash:1017`, run `ros-wave-c-146`. `reviewed_by` stays null.

## What was checked

The pinned clone is `robots/shouryash007/robothon-2026` at `32a2722fda7758d5ea85101a240b11aa55f4e3f0` (clone audit: that HEAD, no tracked changes). No hardware, Gazebo, ROS graph or human review was run. The search for a simulator major covered text files of types md, xml, py, yml, yaml, txt, sh, cmake, sdf, urdf, xacro, rst, in, json, cfg, toml and launch. It found no `Fortress`, `Harmonic`, `Garden`, `ignition-gazebo`, `gz-sim8`, `gz-sim7` or `gz-sim6`.

Humble is named, and only Humble:

- `hackathon_ws/hackathon_ws/src/so101_gazebo/scripts/pick_place_test.py:7` comments `ros-humble-tf-transformations`.
- `hackathon_ws/hackathon_ws/install/setup.sh:34`, a tracked colcon prefix script, sets `COLCON_CURRENT_PREFIX="/opt/ros/humble"`.

The world and the launch, which the triage and the verifier cite, check out, and they still do not name a major:

- `worlds/empty_world.sdf:3` is `<world name="empty">`. Lines 6-7 load `gz-sim-physics-system` and `gz-sim-user-commands-system`.
- `launch/so101_gazebo.launch.py:36` and `:55` pass `-world` `empty`. Line 115 points `gz_args` at `worlds/empty_world.sdf` (`:142-144`, including `-r`). Line 140 includes `ros_gz_sim`'s `gz_sim.launch.py`.
- Lines 121-135 build both `GZ_SIM_RESOURCE_PATH` and `IGN_GAZEBO_RESOURCE_PATH`, and lines 314-315 set both. Setting both is dual compatibility, not a choice of Fortress.
- `README.md:2` launches `so101_gazebo.launch.py`. `README.md:4` is the only bridge, `/d435i/image@sensor_msgs/msg/Image[gz.msgs.Image`. A search of `src` files ending in py, md, xml, yaml, yml or sdf found no `parameter_bridge`, `ControlWorld` or `WorldStatistics`, so an operator bridge of `/world/empty/control` and `/world/empty/stats` would not duplicate a bridge the clone already runs.
- `so101_gazebo/package.xml:16` and `:27` depend on `ros_gz_sim` and `gz_ros2_control` with no version and no distro.

The companions that a Fortress pin would cite contradict a unique major:

- `work/companions/LOCK.json` has three Humble simulator profiles, not one. `ros2-humble-gazebo11` is gazebo_ros 3.9.0 (line 313; `needed_by` `gh.atharva-05/unitree_ros2_sim`, `gh.evronix/quadruped_sim2sim` and `gh.novog93/sjtu_drone`) and gazebo_ros2_control 0.4.12 (line 373; `needed_by` the first two of those). `ros2-humble-gzsim7` is gz-sim 7.9.0 Garden (line 1039) and gz-transport 12.2.2 (line 1090); both are `needed_by` `gh.markusbuchholz/gazebosim_blueboat_ardupilot_sitl` only. `ros2-humble-gzsim6` is five entries. `gh.rigbetellabs/tortoisebot` is the whole `needed_by` list only of `gazebosim__gz-sim@ignition-gazebo6_6.18.0` (commit `b90cd2c41a193102d6951857c2d83e13f59bb64b`, profile line 878) and `gazebosim__ros_gz@0.244.27` (commit `856e319ee4da713609b3f6e58c74ac8db7662482`, profile line 925). On the same profile, controller_manager 2.54.4 (line 424), joint_trajectory_controller 2.54.1 (line 475) and gz_ros2_control 0.7.21 (line 526) are `needed_by` `gh.blackcoffeerobotics/bcr_arm` only. There is no `ros2-humble-gzsim8` entry. This unit did not add one, which is the verifier's safer alternative.
- ros_gz `README.md:5-7` pairs Humble with Fortress, Garden and Harmonic. `README.md:58` says Humble binaries are available for Fortress. Line 57 is blank. That sentence is the companion's binary default, not a line of this package.
- `ros_gz_sim/package.xml:22-34` conditions Harmonic on `gz-sim8`, Garden on `gz-sim7` and Fortress on `ignition-gazebo6`. Line 33 defaults an empty `GZ_VERSION` to `ignition-gazebo6`. The package never sets `GZ_VERSION`.
- `ros_gz_bridge/CHANGELOG.rst:136` records that the Humble bridge accepts both gz and ignition message names, so `README.md:4`'s `gz.msgs.Image` does not select Harmonic.
- gz-sim 6.18.0 `src/SystemLoader.cc:73-78` rewrites a plugin filename prefix `gz-sim` to `ignition-gazebo`, so `empty_world.sdf`'s `gz-sim-*` names do not select Fortress either.
- gz_ros2_control 0.7.21 `README.md:20-21` pairs Humble with Fortress (binaries) and with Harmonic (from source). `LOCK.json` lists that clone as `needed_by` `gh.blackcoffeerobotics/bcr_arm` only. This package's unversioned `gz_ros2_control` depend does not choose a row of that table.

TortoiseBot can cite `README.md:36-38` "Ignition Fortress" and `cmd=['ign', 'gazebo', ...]`. This package has no such line. The pause topic names would be the same on Fortress and Harmonic, which is why a wrong profile would still look like a working stop. That is the overclaim this unit refuses.

## What was not changed

No `safety_bindings`, no `operator_bridges`, no companion override and no `needed_by` widening. No unpause and no re-enable: SAFE-042 is not reached, because no resume of a stored trajectory is offered. `driver.py`, `fake.py`, `test_driver.py`, `facts.md`, `driver.lock.json`, `reference.json`, `REFERENCE.md`, `task.json` and `site-limits.example.json` are unchanged. `blocked_on` stays `HELPER_MISSING` because no stop binding is declared. The recorded gate digest stays `sha256:17911835f0a26b7be70bc133db0f8f81fbb7b50c34f3eb6d13620532bc43d7fe` (failed G6 and G8). `publish_review` stays required.

`RESULT.json` notes were already 8000 characters. The author's text before the first `MODEL REVIEW` paragraph was shortened at the sentence ending "the deployed site supplies its own envelope." and closed with ` [...]`. The removed tail is the author's G8, NOT COVERED and FAKE paragraphs; the same limits, the camera exclusion and the F0 fake remain in `facts.md`, and the Claude review paragraph is unchanged. One paragraph was appended, headed `MODEL REVIEW (grok-4.7, a model and not a human, 2026-11-05; reviewed_by stays null): `.

## Stopped attempts

Nothing was taken from either stopped attempt. `development/p5-gz-topic/project` and `development/ext-p5-gz-topic.fast-stopped/project` have the same ten package files and the same `companion-sources-lock.json` bytes as this tree's starting point. The Claude attempt's `logs/widen-lock.json` records a `needed_by` widening for this package (and for two other packages) on the Fortress clones, including `ros-controls__gz_ros2_control@0.7.21`. That widening assumed the profile this unit does not accept, so it was not copied. `work/companions/LOCK.json` was not edited.

## Open point

A later decision can still author the E2/E3 package if a human accepts a profile this clone does not name. The empty `GZ_VERSION` default and the Humble binary sentence at ros_gz `README.md:58` are Fortress, and Garden and Harmonic remain documented pairings. Until the package side names one major, the package stays blocked rather than passing on an inference.

## Round 1

The first review (Codex pass, Grok fix_needed) kept the block. Two record errors were corrected. `ros2-humble-gzsim6` is not the only fetched Humble simulator profile: `LOCK.json` also has `ros2-humble-gazebo11` and `ros2-humble-gzsim7`. TortoiseBot is the `needed_by` list only of the ignition-gazebo 6.18.0 and ros_gz 0.244.27 entries. The Fortress binary sentence is ros_gz `README.md:58`, not line 57, which is blank. The same line number was corrected in the `RESULT.json` notes. The package stays blocked.

## Integration

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 while composing the phase-5 units onto snapshot-6. `reviewed_by` stays null. No simulator or hardware run is claimed.

No package file and no shared edit from this unit was merged. This change record is kept so the exclusion is visible.

Left out:

- MHS/drivers/robots/shouryash007__robothon-2026/RESULT.json: package decision is not accept

Codex package decisions that were not accept:

- `robots/shouryash007__robothon-2026`: decision `block`

Generated files (registry cards and records, task.json, reference.json, REFERENCE.md, check-report.json, CHANGELOG.md) were not copied. The integrator regenerates them.
