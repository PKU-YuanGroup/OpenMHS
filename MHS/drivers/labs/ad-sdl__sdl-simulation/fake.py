"""ROS-free analytic fake for the pinned sdl-simulation ROS 1 topic contract.

The fake models only the declarations in ``driver.py``:

* publications to ``/ur_arm/moveit/goal_pose`` (geometry_msgs/Pose),
  ``/move_base_simple/goal`` (geometry_msgs/PoseStamped) and the two
  ``std_msgs/Float64`` gripper command topics;
* subscriptions to ``/move_group/status`` and ``/move_base/status``
  (actionlib_msgs/GoalStatusArray), answered whether or not the paused flag
  is set (this package does not claim those topics go silent);
* the companion services ``/gazebo/pause_physics`` and
  ``/gazebo/get_physics_properties`` (the e-stop and its read-back).

A paused flag stands for the Gazebo world's.  The pause sets it and the
read-back reports it.  The fake starts unpaused so a stop demonstrably sets
the flag; the clone's no-namespace launch starts the real world paused.
It runs no ROS graph, Gazebo world, MoveIt planner, ros_control controller
or navigation stack.  Every number and status text below is test data and is
marked ``# placeholder``; none is a device fact or a safety limit.
"""

import copy

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeSdlSimulation(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.last_arm_goal = None          # placeholder state
        self.last_base_goal = None         # placeholder state
        self.last_left_gripper = None      # placeholder state
        self.last_right_gripper = None     # placeholder state
        self.arm_goal_count = 0            # placeholder counter
        self.base_goal_count = 0           # placeholder counter
        self.left_gripper_count = 0        # placeholder counter
        self.right_gripper_count = 0       # placeholder counter
        self.reject_publish = False        # placeholder negative-path switch
        self.malformed_status = False      # placeholder negative-path switch
        self.paused = False                # placeholder: the fake starts running
        self.fail_pause = False            # placeholder negative-path switch: the pause is not answered
        self.fail_readback = False         # placeholder negative-path switch: a non-ODE engine
        self.ignore_pause = False          # placeholder negative-path switch: another client unpaused
        self.arm_status_list = [self._entry("placeholder-initial-arm", 3, "placeholder initial arm status")]
        self.nav_status_list = [self._entry("placeholder-initial-nav", 3, "placeholder initial nav status")]

    @staticmethod
    def _entry(goal_id, status, text):
        return {
            "goal_id": {
                "id": goal_id,                                        # placeholder
                "stamp": {"secs": 0, "nsecs": 0},                     # placeholder
            },
            "status": status,                                         # placeholder actionlib code
            "text": text,                                             # placeholder
        }

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            return self._observation(message)
        if operation == "advertise":
            return None
        if operation == "unadvertise":
            return None
        if operation == "unsubscribe":
            return None
        if operation == "publish":
            self._record_publish(message)
            return None
        if operation == "call_service":
            return self._service(message)
        return None

    def _observation(self, message):
        # Status stays available while paused: the package does not claim those topics go silent.
        topic = message.get("topic")
        if topic not in ("/move_group/status", "/move_base/status"):
            return None
        if self.malformed_status:
            return {
                "op": "publish",
                "topic": topic,
                "id": message.get("id"),
                "msg": {
                    "header": {"seq": 0, "stamp": {"secs": 0, "nsecs": 0}, "frame_id": ""},  # placeholder
                    "status_list": "not-a-list",  # placeholder malformed payload
                },
            }
        statuses = self.arm_status_list if topic == "/move_group/status" else self.nav_status_list
        return {
            "op": "publish",
            "topic": topic,
            "id": message.get("id"),
            "msg": {
                "header": {"seq": 0, "stamp": {"secs": 0, "nsecs": 0}, "frame_id": ""},  # placeholder
                "status_list": copy.deepcopy(statuses),
            },
        }

    def _record_publish(self, message):
        if self.reject_publish:
            raise RuntimeError("fake rosbridge transport rejected the publication")  # placeholder failure
        topic = message.get("topic")
        body = message.get("msg") if isinstance(message.get("msg"), dict) else {}
        if topic == "/ur_arm/moveit/goal_pose":
            self.last_arm_goal = copy.deepcopy(body)  # placeholder state
            self.arm_goal_count += 1
            # Placeholder contract effect: a real MoveIt action server publishes a
            # new goal id after it accepts a goal.  This is status, not arrival or
            # completion evidence.  The sample is still published while paused.
            self.arm_status_list = [self._entry(f"placeholder-arm-{self.arm_goal_count}", 1,
                                                "placeholder arm goal accepted")]
        elif topic == "/move_base_simple/goal":
            self.last_base_goal = copy.deepcopy(body)  # placeholder state
            self.base_goal_count += 1
            # Placeholder contract effect: a real move_base action server publishes
            # a new goal id after it accepts a goal.
            self.nav_status_list = [self._entry(f"placeholder-nav-{self.base_goal_count}", 1,
                                                "placeholder nav goal accepted")]
        elif topic == "/left_gripper_position_controller/command":
            self.last_left_gripper = body.get("data")  # placeholder state
            self.left_gripper_count += 1
        elif topic == "/right_gripper_position_controller/command":
            self.last_right_gripper = body.get("data")  # placeholder state
            self.right_gripper_count += 1

    def _service(self, message):
        service = message.get("service")
        if service == "/gazebo/pause_physics":
            if self.fail_pause:
                return None  # no answer: the e-stop's request times out
            self.paused = True
            return {"op": "service_response", "service": service, "id": message.get("id"), "result": True,
                    "values": {}}
        if service == "/gazebo/get_physics_properties":
            if self.fail_readback:
                # A non-ODE engine: the plugin sets success false and returns false (gazebo_ros_api_plugin.cpp:1458-1465).
                return {"op": "service_response", "service": service, "id": message.get("id"),
                        "result": False, "values": "get_physics_properties not supported"}  # placeholder
            return {"op": "service_response", "service": service, "id": message.get("id"), "result": True,
                    "values": {"time_step": 0.001, "pause": self.paused and not self.ignore_pause,  # placeholder
                               "max_update_rate": 1000.0, "gravity": {"x": 0.0, "y": 0.0, "z": -9.8},
                               "ode_config": {}, "success": True, "status_message": "placeholder"}}
        return {"op": "service_response", "service": service, "id": message.get("id"),
                "result": False, "values": {}}  # placeholder rejection
