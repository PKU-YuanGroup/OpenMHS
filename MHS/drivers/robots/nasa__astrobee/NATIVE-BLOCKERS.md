OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Astrobee native deployment remains unverified

The full declared Motion MOVE pose sequence and independently acknowledged GNC Control STOP are preserved. Each nested position coordinate now requires operator limits; `site-limits.example.json` is explicitly fake test data, not an installed keep-in zone or physical workspace. The stock server refuses MOVE without all required limits and rejects an out-of-envelope coordinate in any array element before sending a partial sequence.

Pinned source `bf43a42d5f89bf0679e51ab25e7a9b7800313e9c` establishes the following narrower software contract. `gnc/ctl/src/ctl_ros.cc:397-403` commands MODE_STOP; the STOPPING completion is driven by the EKF velocity/omega thresholds at lines 235-259 and the success transition at 92-96. The selected relative endpoint names are `gnc/control` and `mob/motion` in `shared/ff_common/include/ff_common/ff_names.h:133,230`. These source facts do not prove every deployed simulator profile.

Native admission evidence still needs an explicit robot namespace, flight-mode configuration, active EKF/use_truth path and installed operator workspace. `ctl_ros.cc:235-259,271-286,569-570` makes the feedback selection/configuration relevant. The package's root-level topics and canned fake do not establish those choices.

The independent controlled peer verifies that an unresolved Motion terminal keeps achieved safety false, a late terminal alone does not confirm it, and a fresh STOP is required afterward. This recognizes the accepted generic action ownership rules. It does not prove internal planner/GNC ordering or cessation across native child actions: `choreographer_nodelet.cc:807-826` cancels its child on cancellation/preemption, and `shared/ff_util/include/ff_util/ff_action.h:261-271` sends cancellation then stops tracking the goal. No native child-lifecycle test has been run.

Keep native profile admission blocked pending those source-backed deployment and lifecycle checks. A software STOP acknowledgement is not a physical emergency stop or an automatic authorization to run hardware. No ROS graph, simulator, source node or hardware was executed for these repairs.
