OpenMHS is independent and is not affiliated with, endorsed by, or a reimplementation of Anthropic's MHS research preview.

# Three ROS 1 sensed-stop records blocked until the BL-17 fix lands

On 2026-11-06 the user chose to block darienmt/px4-sitl-ros-example, tfly6/opendrone and derek-th-wang/quadruped_ctrl
(each a simulator at risk R2) on `SDK_BUG`, failing closed. The review of the p5-sdk-stampless unit (Codex gpt-6.1-sol,
round 5, of work by Grok grok-4.7) accepted an SDK change for backlog item BL-17: on ROS 1 a topic latched by several
publishers replays one stale sample per publisher on subscription, and the current discard-first rule discards only one,
so a ROS 1 sensed-confirmation stop could accept a stale sample. With that change every ROS 1 stamp sample is discarded,
and these three packages can no longer confirm their stop (their gates fail G6 and G8 there).

The change landed later on 2026-11-06 (`P5-SDK-STAMPLESS-ALL.md`, its Integration section): every ROS 1 stamp sample is now
discarded, the three records stay `blocked` on `SDK_BUG`, and their recorded gate digests are the fixed SDK's (G6 and G8
fail). The same change repaired inria-paris-robotics-lab/unitree_simulation and centre-for-biorobotics/eeuvsim_gazebo.
Codex's review of that composition found three more passing ROS 1 sensed-stop records that the fix stops from
confirming (autorally/autorally, epfl-lasa/kuka-rviz-simulation, larics/decentralized_multi_robot_exploration, added after
the unit's base); following the user's choice they are blocked on `SDK_BUG` the same way, with re-recorded digests. The
leading sentence of the four records already blocked now says the current evidence state is none (the gate fails).
`reviewed_by` stays null; no hardware or simulator run is claimed.
