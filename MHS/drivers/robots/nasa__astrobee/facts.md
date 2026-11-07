OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Source facts for gh.nasa/astrobee

Pinned commit: `bf43a42d5f89bf0679e51ab25e7a9b7800313e9c`. Source declarations and controlled fake results are not native execution.

| Fact | Source | Reference |
|---|---|---|
| The pinned name header defines ACTION_MOBILITY_MOTION as the relative ROS name mob/motion. | upstream_code | `shared/ff_common/include/ff_common/ff_names.h:230` |
| The pinned name header defines ACTION_GNC_CTL_CONTROL as the relative ROS name gnc/control. | upstream_code | `shared/ff_common/include/ff_common/ff_names.h:133` |
| The choreographer source includes the generated ff_msgs/MotionAction header. | upstream_code | `mobility/choreographer/src/choreographer_nodelet.cc:54` |
| ChoreographerNodelet binds the owned MotionAction server to ACTION_MOBILITY_MOTION. | upstream_code | `mobility/choreographer/src/choreographer_nodelet.cc:578-584` |
| The Motion action defines STOP, IDLE, EXEC, MOVE and PREP commands; MOVE is 'Move through a given set of poses'. | upstream_code | `communications/ff_msgs/action/Motion.action:22-26` |
| The Motion action carries a geometry_msgs/PoseStamped array in states and a reference_frame string. | upstream_code | `communications/ff_msgs/action/Motion.action:47-50` |
| The Motion result defines ALREADY_THERE and SUCCESS response codes. | upstream_code | `communications/ff_msgs/action/Motion.action:56-57` |
| GoalCallback rejects a new Motion goal unless the choreographer FSM is IDLE or STOPPED, aborting with NOT_IN_WAITING_MODE. | upstream_code | `mobility/choreographer/src/choreographer_nodelet.cc:1295-1305` |
| GoalCallback rejects a MOVE goal with an empty states vector with UNEXPECTED_EMPTY_STATES. | upstream_code | `mobility/choreographer/src/choreographer_nodelet.cc:1347-1353` |
| The STOP transition from STOPPED or IDLE calls Control(STOP), enters STOPPING, and reports SUCCESS only on CONTROL_SUCCESS. | upstream_code | `mobility/choreographer/src/choreographer_nodelet.cc:353-367` |
| The CONTROLLING/GOAL_CANCEL transition returns CANCELLED rather than sending a Control STOP goal. | upstream_code | `mobility/choreographer/src/choreographer_nodelet.cc:311-317` |
| Result() handles CANCELLED and PREEMPTED by calling client_c_.CancelGoal() in CONTROLLING; it does not command a stop there. | upstream_code | `mobility/choreographer/src/choreographer_nodelet.cc:807-826` |
| SetStateCallback for mob/set_state calls fsm_.SetState(req.state) and then sets res.success true without calling Control(). | upstream_code | `mobility/choreographer/src/choreographer_nodelet.cc:605-610` |
| The choreographer transforms MOVE states from a non-empty reference_frame into the world frame before planning. | upstream_code | `mobility/choreographer/src/choreographer_nodelet.cc:1354-1375` |
| The pinned name header defines the world frame name as world. | upstream_code | `shared/ff_common/include/ff_common/ff_names.h:37` |
| The pinned name header defines TOPIC_MOBILITY_SEGMENT as mob/choreographer/segment. | upstream_code | `shared/ff_common/include/ff_common/ff_names.h:261` |
| The choreographer advertises a latched nav_msgs/Path on TOPIC_MOBILITY_SEGMENT. | upstream_code | `mobility/choreographer/src/choreographer_nodelet.cc:520-522` |
| The choreographer publishes the segment Path with the world frame and its current timestamp. | upstream_code | `mobility/choreographer/src/choreographer_nodelet.cc:1167-1169` |
| The Control action defines STOP, IDLE and NOMINAL commands and the SUCCESS response code. | upstream_code | `communications/ff_msgs/action/Control.action:20-30` |
| The control source includes the generated ff_msgs/ControlAction header. | upstream_code | `gnc/ctl/include/ctl/ctl_ros.h:36` |
| On a Control STOP goal, Ctl::GoalCallback calls Command(MODE_STOP) and then updates the FSM with GOAL_STOP. | upstream_code | `gnc/ctl/src/ctl_ros.cc:397-403` |
| The WAITING/GOAL_STOP transition calls Command(MODE_STOP) and returns STOPPING. | upstream_code | `gnc/ctl/src/ctl_ros.cc:84-90` |
| Ctl checks the EKF velocity and omega magnitudes against stopping thresholds and only then updates GOAL_COMPLETE. | upstream_code | `gnc/ctl/src/ctl_ros.cc:245-259` |
| The STOPPING/GOAL_COMPLETE transition returns SUCCESS. | upstream_code | `gnc/ctl/src/ctl_ros.cc:92-96` |
| Ctl::Result sends a SUCCESS native action result when response is SUCCESS. | upstream_code | `gnc/ctl/src/ctl_ros.cc:169-171` |

## Scope and unresolved admission

The full Motion MOVE pose sequence and separate GNC Control STOP remain. Every nested position x/y/z leaf is operator_required. The example overlay is clearly labeled controlled fake data, not source-stated or installed workspace limits. Missing limits refuse MOVE; supplied bounds apply to all pose-array elements before any goal is sent.

The source-backed STOP application predicate and the accepted generic retained-goal/fresh-stop behavior remain. Native namespace, flight mode, EKF/use_truth path and planner/GNC child-controller ordering remain deployment blockers, described in NATIVE-BLOCKERS.md. A gate on a controlled peer does not establish native free-flight safety.
