OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Unitree A1 original declaration remains rejected

The complete original twelve-joint position/velocity/effort/gain surface and twenty-entry LowState observation are retained unchanged. All twelve selected A1 URDF limit elements and all thirty-six numeric position/velocity/effort bounds match the pinned primary source. Gains remain operator-required. This does not establish a valid or safe deployment.

The original G3 definition failure and G7 source-name rejection remain real blockers. `unitree_controller/src/servo.cpp:223` composes the `_gazebo/lowState/state` suffix, while the declaration's source-name claim does not equal that quoted suffix. The rejected safe-state publication targets one FR hip; it cannot acknowledge complete twelve-joint cessation. `unitree_legged_control/src/joint_controller.cpp:136-183` applies retained commands, and `stopping():205-206` is empty. BRAKE is damping, not a confirmed whole-device stop.

The full original source and original generated references match the frozen author bytes. `REFERENCE.md` and `reference.json` are nevertheless **stale relative to the final rejected declaration**, and have not been regenerated as if that declaration could load. They remain historical evidence. A future candidate must repair provenance and complete stop/ownership proof without deleting controls, replacing them with LowState-only scope, inventing pause endpoints or making the retained single-joint brake look safe.

Message schemas were read from exact `unitree_ros_to_real` gitlink `b989870124913091fbe75e0dcfb047eb4ca00a09` of parent commit `5994d4faef0a9cadd3287f8de0199a67eeb2a259`. No upstream code, Gazebo, ROS node or hardware was run. Package status remains **blocked**; no human signature or source pin changed.
