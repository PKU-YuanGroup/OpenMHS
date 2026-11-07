"""ROS-free contract fake for the warehouse_robot_simulation order topic.

The fake models the declared rosbridge wire traffic: one advertise and publish
pair for ``/warehouse/order/add`` with ``std_msgs/String``, plus the companion
gazebo_ros services ``/gazebo/pause_physics`` and
``/gazebo/get_physics_properties`` (the e-stop and its read-back).  A paused
flag stands for the Gazebo world's paused flag: the pause sets it and the
read-back reports it.  A call of ``/gazebo/unpause_physics`` is answered with
result false and does not clear that flag.
A publication has no response in rosbridge, so the fake never manufactures an
upstream acknowledgement, a queue receipt, a motion result or a stop.  It may
classify the String with a placeholder parser solely so repository tests can
show that a malformed order is still only a transmission.  That classification
runs even while the flag is set; the pinned node does not, because its loop
does not return from ``ros::Rate::sleep`` while simulated time is stopped.

All state values and counters below are test data, not device facts.
"""

from mhs.bridge.ros_transport import RecordingRosTransport

_PAUSE = "/gazebo/pause_physics"
_READBACK = "/gazebo/get_physics_properties"
_UNPAUSE = "/gazebo/unpause_physics"


def _parse_order_placeholder(text):
    """Placeholder model of the upstream plain-string parse.

    Returns ``(dispatch, products)`` for a string that has a dispatch token and
    at least one product with a positive integer quantity, otherwise ``None``.
    This is deliberately not a claim that the real node accepted the order.
    """
    tokens = str(text).split()
    if len(tokens) < 3:
        return None
    dispatch, rest = tokens[0], tokens[1:]
    if len(rest) % 2:
        return None
    products = []
    try:
        for index in range(0, len(rest), 2):
            product = rest[index]
            quantity = int(rest[index + 1])
            if quantity > 0:
                products.append((product, quantity))
    except (TypeError, ValueError):
        return None
    if not products:
        return None
    return dispatch, products


def _service_response(message, result, values):
    return {
        "op": "service_response",
        "service": message.get("service"),
        "id": message.get("id"),
        "result": result,
        "values": values,
    }


class FakeWarehouseRobotSimulation(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.advertised = []             # placeholder record
        self.published = []              # placeholder record
        self.parsed_orders = []          # placeholder classification
        self.discarded_orders = []       # placeholder classification
        self.publish_count = 0           # placeholder counter
        self.fail_next_publish = False   # placeholder negative-path switch
        self.paused = False              # placeholder: the fake starts running
        self.fail_pause = False          # placeholder negative-path switch: the pause is not answered
        self.fail_readback = False       # placeholder negative-path switch: a non-ODE engine
        self.ignore_pause = False        # placeholder negative-path switch: another client unpaused

    def _respond(self, message):
        operation = message.get("op")
        if operation == "advertise":
            self.advertised.append(message.get("topic"))  # placeholder record
            return None
        if operation == "publish":
            if self.fail_next_publish:
                self.fail_next_publish = False
                raise ConnectionError("placeholder rosbridge publication failure")
            if message.get("topic") != "/warehouse/order/add":
                return None
            self.publish_count += 1  # placeholder counter
            body = message.get("msg") if isinstance(message.get("msg"), dict) else {}
            data = body.get("data")
            self.published.append(data)  # placeholder record
            parsed = _parse_order_placeholder(data)
            if parsed is None:
                self.discarded_orders.append(data)  # placeholder classification
            else:
                self.parsed_orders.append(parsed)  # placeholder classification
            # No response: rosbridge publication is fire-and-forget.
            return None
        if operation == "call_service":
            service = message.get("service")
            if service == _UNPAUSE:
                # The package offers no unpause.  A true result would clear the flag.
                return _service_response(message, False, {})
            if service == _PAUSE:
                if self.fail_pause:
                    return None  # no answer: the e-stop's request times out
                self.paused = True
                return _service_response(message, True, {})
            if service == _READBACK:
                if self.fail_readback:
                    return _service_response(message, False, "get_physics_properties not supported")  # placeholder
                return _service_response(message, True, {
                    "time_step": 0.001,  # placeholder
                    "pause": self.paused and not self.ignore_pause,
                    "max_update_rate": 1000.0,  # placeholder
                    "gravity": {"x": 0.0, "y": 0.0, "z": -9.8},  # placeholder
                    "ode_config": {},  # placeholder
                    "success": True,  # placeholder
                    "status_message": "placeholder",
                })
            return _service_response(message, False, {})
        return None
