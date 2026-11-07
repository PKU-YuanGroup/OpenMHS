"""The ``sim`` backend entry: builds the pinned PandaReach-v1 environment inside the isolated simulator host.

The endpoint never imports this module.  ``process_by_backend["sim"]`` in driver.py makes the SDK start a child
process (``mhs.bridge.sim_host``) that imports this module and calls :func:`make_env` on its main thread, where
rospy can initialise its node.  Everything the constructor starts belongs to that process: roscore when no master
runs (``core/ros_launcher.py:37-43``), the ``panda_gazebo`` world launched paused through ``roslaunch`` in a shell
subprocess (``task_envs/panda/panda_reach.py:307-317``, ``core/ros_launcher.py:159-184``), MoveIt and the
controllers.  Its exits (``ros_exit_gracefully``: a global ``rospy.signal_shutdown`` and ``sys.exit``,
``core/helpers.py:325-339``) end calls in that process only.

Construction is a deployment step, never run by the gate or by this package's tests: it needs ROS Noetic, Gazebo,
MoveIt and a catkin workspace with ``panda_gazebo`` and ``panda_moveit_planner_server``.  When a package is missing
the upstream clones it and rebuilds the workspace, including ``sudo -S rosdep install`` (``core/ros_launcher.py:
133-139``, ``core/helpers.py:552``, ``:372-377``, ``:672``), and with ``outdated_warning`` it fetches the remotes of
packages it cloned (``core/helpers.py:314``, ``:569``): prepare the workspace beforehand.  Importing
``ros_gazebo_gym`` registers ``PandaReach-v1`` (``src/ros_gazebo_gym/__init__.py:15-21``), and ``gymnasium.make``
adds the 500-step time limit (``task_envs/task_envs_list.py:21-24``).
"""


def make_env(control_type="effort", **options):
    """``gymnasium.make("PandaReach-v1", control_type=...)`` in the host process (imports happen here only)."""
    import gymnasium
    import ros_gazebo_gym  # noqa: F401  (registers the task environments)

    return gymnasium.make("PandaReach-v1", control_type=control_type, **options)
