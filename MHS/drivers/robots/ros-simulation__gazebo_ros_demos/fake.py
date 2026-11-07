"""ROS-free recording fake for the pinned RRBot joint-position command topics.

The fake records the advertise and publish operations the driver declares:

* ``std_msgs/Float64`` on ``/rrbot/joint1_position_controller/command``;
* ``std_msgs/Float64`` on ``/rrbot/joint2_position_controller/command``.

It is an analytic contract stand-in, not a recording of captured traffic.  It
runs no Gazebo, gazebo_ros_control, controller_manager, PID, physics or ROS
graph.  Every number below is test data and is marked ``# placeholder``; none
is a device fact, a limit or a trajectory.  The pinned clone has no
acknowledged stop, so the fake does not model one.
"""

from mhs.bridge.ros_transport import RecordingRosTransport

_CONTROLLER_COMMAND_TOPICS = (
    "/rrbot/joint1_position_controller/command",
    "/rrbot/joint2_position_controller/command",
)


class FakeGazeboRosDemosRrbot(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.fail_publish = False       # placeholder negative-path switch
        self.joint1_commands = []       # recording helper, no device meaning
        self.joint2_commands = []       # recording helper, no device meaning

    def _respond(self, message):
        operation = message.get("op")
        if operation == "advertise":
            return None
        if operation == "publish":
            self._record_publication(message)
            return None
        return None

    def _record_publication(self, message):
        if self.fail_publish:
            raise RuntimeError("fake rosbridge transport rejected the publication")  # placeholder negative path
        topic = message.get("topic")
        body = message.get("msg") if isinstance(message.get("msg"), dict) else {}
        if topic == _CONTROLLER_COMMAND_TOPICS[0]:
            self.joint1_commands.append(dict(body))
        elif topic == _CONTROLLER_COMMAND_TOPICS[1]:
            self.joint2_commands.append(dict(body))
