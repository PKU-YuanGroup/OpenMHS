"""ROS-free recording fake for the Franka TMR spine and battery endpoints.

The fake models the declared rosbridge wire contract only:

* subscriptions on the private spine ``~/position`` and ``~/state`` topics
  and the private battery ``~/battery_state`` topic;
* service calls on the private spine ``~/halt``, ``~/switch_off`` and
  ``~/switch_on`` services and the private battery ``~/stop_wireless_charging``
  and ``~/try_start_wireless_charging`` services;
* ROS 2 native action goals and cancellation on ``~/move_absolute``.

Every state value, flag, counter and canned reply below is test data, not a
device fact.  The numbers are marked ``# placeholder``.  No socket, ROS node
or hardware is used.
"""

import copy
import threading

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeFrankaRos2(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        # Event-controlled callback ordering, not motion dynamics or timing.
        self.hold_move = False                 # placeholder fault/race fixture
        self.pending_goal = None              # placeholder
        self.goal_received = threading.Event()
        self.cancel_received = threading.Event()
        self.cancel_rearmed = threading.Event()
        self.position_valid = True            # placeholder
        self.state_valid = True               # placeholder
        self.state_error_code = ""             # placeholder
        self.state_error_description = ""      # placeholder
        self.position = 0.25                   # placeholder
        self.state = "SwitchedOn"              # placeholder
        self.wireless_charging = False         # placeholder
        self.battery_percentage = 0.73         # placeholder
        self.battery_temperature = 24.0        # placeholder
        self.fail_halt_transport = False       # placeholder negative-path switch
        self.fail_halt_application = False     # placeholder negative-path switch
        self.fail_switch_off_transport = False  # placeholder negative-path switch
        self.fail_switch_off_application = False  # placeholder negative-path switch
        self.missing_switch_off_success = False  # placeholder negative-path switch
        self.fail_switch_on_transport = False  # placeholder negative-path switch
        self.fail_switch_on_application = False  # placeholder negative-path switch
        self.fail_charge_transport = False     # placeholder negative-path switch
        self.fail_charge_application = False   # placeholder negative-path switch
        self.fail_move_protocol = False        # placeholder negative-path switch
        self.fail_move_application = False     # placeholder negative-path switch
        self.missing_move_success = False      # placeholder negative-path switch

    @staticmethod
    def _service(message, result, values):
        return {
            "op": "service_response",
            "service": message.get("service"),
            "id": message.get("id"),
            "result": result,
            "values": values,
        }

    @staticmethod
    def _topic(message, payload):
        return {
            "op": "publish",
            "topic": message.get("topic"),
            "id": message.get("id"),
            "msg": payload,
        }

    def _battery_message(self):
        return {
            "header": {"stamp": {"sec": 0, "nanosec": 0}, "frame_id": ""},  # placeholder
            # The source fills these five fields with NaN. The independently
            # observed rosbridge 2.7.1 JSON wire represents them as null.
            "voltage": None, "current": None, "charge": None,
            "capacity": None, "design_capacity": None,
            "power_supply_health": 0, "power_supply_technology": 0,
            "cell_voltage": [], "cell_temperature": [], "serial_number": "",
            "present": True,                               # placeholder
            "percentage": self.battery_percentage,         # placeholder
            "temperature": self.battery_temperature,       # placeholder
            "power_supply_status": 1 if self.wireless_charging else 2,  # placeholder
            "location": "wireless" if self.wireless_charging else "",  # placeholder
        }

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            topic = message.get("topic")
            if topic == "/franka_spine_node/position":
                return self._topic(message, {
                    "header": {"stamp": {"sec": 0, "nanosec": 0}, "frame_id": ""},  # placeholder
                    "position": self.position,                    # placeholder
                    "valid": self.position_valid,                 # placeholder
                })
            if topic == "/franka_spine_node/state":
                return self._topic(message, {
                    "header": {"stamp": {"sec": 0, "nanosec": 0}, "frame_id": ""},  # placeholder
                    "state": self.state,                         # placeholder
                    "error_code": self.state_error_code,          # placeholder
                    "error_description": self.state_error_description, # placeholder
                    "valid": self.state_valid,                   # placeholder
                })
            if topic == "/franka_battery_node/battery_state":
                return self._topic(message, self._battery_message())
            return None

        if operation == "send_action_goal":
            action = message.get("action")
            ident = message.get("id")
            args = message.get("args") if isinstance(message.get("args"), dict) else {}
            if action != "/franka_spine_node/move_absolute":
                return {"op": "status", "level": "error", "id": ident}  # placeholder error path
            if self.fail_move_protocol:
                return {"op": "status", "level": "error", "id": ident}  # placeholder error path
            if self.fail_move_application:
                values = {"success": False, "stop_by": "Fault", "error": "mock motion refused"}  # placeholder
                return {
                    "op": "action_result",
                    "action": action,
                    "id": ident,
                    "result": True,
                    "status": 4,  # placeholder ROS 2 action status SUCCEEDED
                    "values": values,
                }
            if self.missing_move_success:
                values = {"stop_by": "Finished", "error": ""}  # placeholder
                return {
                    "op": "action_result",
                    "action": action,
                    "id": ident,
                    "result": True,
                    "status": 4,  # placeholder
                    "values": values,
                }
            # Controller.move_absolute:376-385 refuses a disabled drive; a
            # goal is not itself an instruction to switch it on.
            if self.state != "SwitchedOn":
                return {"op": "action_result", "action": action, "id": ident,
                        "result": True, "status": 6,
                        "values": {"success": False, "stop_by": "", "error": "Drive not SwitchedOn"}}
            if self.hold_move:
                self.pending_goal = copy.deepcopy(message)
                self.goal_received.set()
                return None
            self.position = float(args.get("position", 0.0))  # placeholder accepted target
            self.state = "SwitchedOn"                         # placeholder
            return {
                "op": "action_result",
                "action": action,
                "id": ident,
                "result": True,
                "status": 4,  # placeholder ROS 2 action status SUCCEEDED
                "values": {"success": True, "stop_by": "Finished", "error": ""},  # placeholder
            }

        if operation == "cancel_action_goal":
            if self.pending_goal is None or message.get("id") != self.pending_goal["id"]:
                return None
            # Controller:522-528 quick-stops before joining the native worker;
            # after that worker settles, :414-434 re-arms before the terminal.
            self.state = "SwitchedOff"
            self.cancel_received.set()
            return None

        if operation != "call_service":
            return None

        service = message.get("service")
        if service == "/franka_spine_node/halt":
            if self.fail_halt_transport:
                return self._service(message, False, {"success": False, "message": "halt transport failed"})  # placeholder
            if self.fail_halt_application:
                return self._service(message, True, {"success": False, "state": self.state,
                                                     "message": "halt rejected"})  # placeholder
            self.state = "SwitchedOn"  # placeholder upstream re-arms after quick-stop
            return self._service(message, True, {"success": True, "state": self.state,
                                                 "message": "Halt successful"})  # placeholder
        if service == "/franka_spine_node/switch_off":
            if self.fail_switch_off_transport:
                return self._service(message, False, {"success": False, "message": "switch-off transport failed"})  # placeholder
            if self.fail_switch_off_application:
                return self._service(message, True, {"success": False, "state": self.state,
                                                     "message": "switch-off rejected"})  # placeholder
            if self.missing_switch_off_success:
                return self._service(message, True, {"state": self.state,
                                                     "message": "missing success"})  # placeholder
            self.state = "SwitchedOff"  # placeholder
            return self._service(message, True, {"success": True, "state": self.state,
                                                 "message": "Switch off successful"})  # placeholder
        if service == "/franka_spine_node/switch_on":
            # SpineController.switch_on:296-305 posts spine:switch-on and reports
            # the REST result; the fake only moves its placeholder state.
            if self.fail_switch_on_transport:
                return self._service(message, False, {"success": False, "message": "switch-on transport failed"})  # placeholder
            if self.fail_switch_on_application:
                return self._service(message, True, {"success": False, "state": self.state,
                                                     "message": "switch-on rejected"})  # placeholder
            self.state = "SwitchedOn"  # placeholder
            return self._service(message, True, {"success": True, "state": self.state,
                                                 "message": "Switch on successful"})  # placeholder
        if service in ("/franka_battery_node/stop_wireless_charging",
                       "/franka_battery_node/try_start_wireless_charging"):
            if self.fail_charge_transport:
                return self._service(message, False, {"success": False, "message": "charge transport failed"})  # placeholder
            if self.fail_charge_application:
                return self._service(message, True, {"success": False, "message": "charge rejected"})  # placeholder
            self.wireless_charging = service.endswith("try_start_wireless_charging")  # placeholder
            return self._service(message, True, {"success": True, "message": "charge command accepted"})  # placeholder
        return self._service(message, False, {"success": False, "message": "undeclared fake service"})  # placeholder

    def rearm_cancelled_motion(self):
        """Fixture barrier: native motion worker has settled, re-arm occurs."""
        if self.pending_goal is None or not self.cancel_received.is_set():
            raise RuntimeError("no cancelled goal is pending")
        self.state = "SwitchedOn"
        self.cancel_rearmed.set()

    def finish_cancelled_motion(self):
        """Publish the correlated terminal only after the source-shaped re-arm."""
        if self.pending_goal is None or not self.cancel_rearmed.is_set():
            raise RuntimeError("cancel re-arm has not finished")
        goal = self.pending_goal
        self.pending_goal = None
        self.feed({"op": "action_result", "action": goal["action"], "id": goal["id"],
                   "result": True, "status": 5,
                   "values": {"success": False, "stop_by": "", "error": "Motion cancelled"}})

    def source_battery_message(self):
        """Source-shaped pre-wire fixture; it is NOT valid JSON input to MHS."""
        message = self._battery_message()
        for name in ("voltage", "current", "charge", "capacity", "design_capacity"):
            message[name] = float("nan")
        return message
