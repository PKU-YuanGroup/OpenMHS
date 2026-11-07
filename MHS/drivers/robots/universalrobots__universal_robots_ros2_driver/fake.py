"""ROS-free recording fake for the UR ROS 2 dashboard client endpoints.

It models the pinned upstream wire contract for two private services:

* ``/dashboard_client/stop`` of type ``std_srvs/srv/Trigger`` with the
  response fields ``success`` and ``message``;
* ``/dashboard_client/program_running`` of type
  ``ur_dashboard_msgs/srv/IsProgramRunning`` with the response fields
  ``answer``, ``program_running`` and ``success``.

Every canned string, flag and counter below is test data, not a device fact;
invented values are marked ``# placeholder``.  The transport opens no socket
and runs no ROS node.
"""

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeUniversalRobotsRos2Driver(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.program_running = True              # placeholder start state
        self.stop_calls = 0                      # placeholder call counter
        self.running_queries = 0                 # placeholder call counter
        self.fail_stop_transport = False         # placeholder negative-path switch
        self.fail_stop_application = False       # placeholder negative-path switch
        self.stop_missing_success = False        # placeholder negative-path switch
        self.fail_running_transport = False      # placeholder negative-path switch
        self.fail_running_application = False    # placeholder negative-path switch
        self.running_missing_success = False     # placeholder negative-path switch
        self.running_missing_field = False       # placeholder negative-path switch

    def _respond(self, message):
        if message.get("op") != "call_service":
            return None
        service = message.get("service")
        if service == "/dashboard_client/stop":
            self.stop_calls += 1
            if self.fail_stop_transport:
                return {
                    "op": "service_response",
                    "service": service,
                    "id": message.get("id"),
                    "result": False,
                    "values": {"success": False, "message": "transport failed"},  # placeholder
                }
            if self.stop_missing_success:
                return {
                    "op": "service_response",
                    "service": service,
                    "id": message.get("id"),
                    "result": True,
                    "values": {"message": "missing success"},  # placeholder
                }
            if self.fail_stop_application:
                return {
                    "op": "service_response",
                    "service": service,
                    "id": message.get("id"),
                    "result": True,
                    "values": {"success": False, "message": "dashboard rejected stop"},  # placeholder
                }
            self.program_running = False
            return {
                "op": "service_response",
                "service": service,
                "id": message.get("id"),
                "result": True,
                "values": {"success": True, "message": "program stopped"},  # placeholder
            }
        if service == "/dashboard_client/program_running":
            self.running_queries += 1
            if self.fail_running_transport:
                return {
                    "op": "service_response",
                    "service": service,
                    "id": message.get("id"),
                    "result": False,
                    "values": {"success": False, "program_running": False, "answer": "transport failed"},  # placeholder
                }
            if self.running_missing_success:
                return {
                    "op": "service_response",
                    "service": service,
                    "id": message.get("id"),
                    "result": True,
                    "values": {"program_running": bool(self.program_running), "answer": "missing success"},  # placeholder
                }
            if self.fail_running_application:
                return {
                    "op": "service_response",
                    "service": service,
                    "id": message.get("id"),
                    "result": True,
                    "values": {"success": False, "program_running": False, "answer": "query rejected"},  # placeholder
                }
            values = {
                "answer": "program running state",  # placeholder
                "program_running": bool(self.program_running),
                "success": True,
            }
            if self.running_missing_field:
                values.pop("program_running")
            return {
                "op": "service_response",
                "service": service,
                "id": message.get("id"),
                "result": True,
                "values": values,
            }
        return {
            "op": "service_response",
            "service": service,
            "id": message.get("id"),
            "result": False,
            "values": {"success": False, "message": "undeclared fake service"},  # placeholder
        }
