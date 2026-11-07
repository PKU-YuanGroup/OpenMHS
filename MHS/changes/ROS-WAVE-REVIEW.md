OpenMHS is not affiliated with, endorsed by, or a reimplementation of Anthropic's MHS research preview.

# ROS continuation package review

The first two and next ten DeepSeek packages were source-reviewed instead of treating their fake gate as evidence of a working ROS deployment. The review corrected native environment routing, selected a concrete Panda task where an abstract template had been chosen, and retained incomplete primary functions as blocked.

| Package | Reviewed disposition |
|---|---|
| tonyzhaozh/aloha | Blocked: native independent stop and image scope are unresolved; hardware factory refuses before import. |
| darshmenon/ur3_ros2_pick_and_place | Fake contract accepted; lazy MuJoCo factory and opt-in five-substep accounting implemented, installed runtime unverified. |
| dyson-ai/grip | Fake contract accepted; shared adapter, irreversible/deferred close and lazy owned PyBullet factory implemented. Live compatibility remains unverified. |
| jackvice/roboterrain | Analytic fake contract accepted with explicit ROS deployment, stop and seed limitations. |
| anurye/gym-turtlebot | Analytic fake contract accepted; no claimed recorded traffic or installed ROS validation. |
| jacopopan/gymnasium-docker-ros2 | Analytic fake contract accepted; source has fixed container/network ownership and stale-reply risks that a future live adapter must address. |
| ut-amrl/socialgym2 | Shared raw ParallelEnv projection repaired; live deployment remains blocked because independent simulator stop and owned lifecycle are unconfirmed. |
| talregev/gym-webots | Blocked: fake-only spaces do not establish a production adapter, and native lifecycle/reward issues remain. |
| rickstaa/ros-gazebo-gym | Abstract-template pass withdrawn; blocked pending authoring against the actual PandaReachEnv and its native contract. |
| realsenseai/realsense-ros | Metadata-only pass withdrawn; primary image acquisition needs artifacts. |
| misterblue/ros2_raspicam_node | Remains blocked on image artifacts. |
| ncbdrck/multiros | Generic runtime/abstract templates, not a concrete task environment. Authored directory moved aside intact; registry classifies it as bridge-runtime. |

The earlier pilot's klintan/ros2_usb_camera is also now blocked on NEEDS_ARTIFACTS: its header.frame_id-only metadata contract does not implement the pinned camera's primary image publication. Existing passing metadata tests remain evidence of that limited subset only.

Independent GRIP/SocialGym review reproduced four additional defects after their first repair: recovery during close, lost deferred cleanup, retired-agent reward injection, and stale active-agent reporting. Version 2 fixes all four; 31 independently rerun non-gate cases pass, and all 22 cumulative file hashes were verified before parent integration. Native calls cannot be resumed after closing starts; cleanup is claimed exactly once after the final active call. SocialGym results exclude retired agents and publish the current unfinished set. Its live factory still refuses before ROS import.

Registry build #3 regenerated 2,967 cards; all 6,517 frozen driver/override inputs stayed unchanged during the build. The parent then synchronized 449 exact generated package cards (437 rank-only) and updated four lock installation records from pinned Catkin/ament evidence. ALOHA's stricter blocked installation notes were preserved. Thirteen affected actual package gates ran: eleven passed; Panda's old abstract draft correctly failed G7 and ALOHA failed G3. Passing gates did not override the blocked scope decisions above. Before the next authoring batch the actual result inventory is 607 packages: 585 pass, 18 blocked and four accepted skip-proposed exclusions. These are local fake-contract/result counts, not hardware validation or final release status. The registry will need reconciliation after the USB scope correction and subsequent authoring.

Every original was preserved under `work/handoff-runs/mhs-build-20261102/`. Detailed evidence is in `next10-review-parent/`, `next10-repairs-bridge/independent-review/`, `next10-bridge-integration-v2.json`, `task-sync-3.json` and `reviewed-wave-gates-3/`. DeepSeek attribution stays intact, reviewed_by stays null, and no camera, ROS graph, upstream simulator, hardware or publication was executed.
