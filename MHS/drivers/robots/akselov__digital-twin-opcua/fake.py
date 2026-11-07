"""Fake backend of the KUKA KVP driver: an in-memory stand-in for KUKAVARPROXY_communication:KUKA.

Gate G7: the public members here are the upstream class's ``read(var, msgID=0)``, ``write(var, val, msgID=0)`` and
``disconnect()`` (xml/KUKAVARPROXY_communication.py:79-95).  ``read`` returns KVP reply text and ``write`` returns
the KVP write acknowledgement; both keep the native names and parameter order.

The fake keeps six axis values, the four motor arrays and a list of the commands it received.  A write of
``TARGET_AXIS`` parses the same E6AXIS text the upstream control server builds
(opcua-control/opcua-control-server.py:187) and moves the fake's axis values at once; a real KRL ``PTP`` takes time
and the controller's ``$AXIS_ACT`` lags the target.  Every start value and every reply is test data, never a fact
about a robot.  Nothing here talks to a device.
"""

_AXIS_NAMES = ("A1", "A2", "A3", "A4", "A5", "A6")
_MOTOR_VARIABLES = ("$VEL_AXIS_ACT", "$TORQUE_AXIS_ACT", "$CURR_ACT", "$MOT_TEMP")


class FakeKUKA:
    def __init__(self, TCP_IP="127.0.0.1", **options):
        self._address = TCP_IP
        self._axes = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]              # placeholder
        self._target = list(self._axes)                            # placeholder
        self._motor_values = {name: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]  # placeholder
                              for name in _MOTOR_VARIABLES}
        self._connected = True
        self._commands = []
        self._fail_next_read = None
        self._fail_next_write = None
        self._axis_text = None
        self._corrupt_axis_after_write = False

    # -- upstream KUKA surface -----------------------------------------------------------------------------------
    def read(self, var, msgID=0):
        self._commands.append(("read", var, msgID))
        self._maybe_fail("read")
        if var == "$AXIS_ACT":
            if self._axis_text is not None:
                return self._axis_text
            return self._axis_message(self._axes)
        for prefix in _MOTOR_VARIABLES:
            marker = prefix + " ["
            if var.startswith(marker) and var.endswith("]"):
                number = var[len(marker):-1]
                try:
                    index = int(number) - 1
                except ValueError:
                    index = -1
                if 0 <= index < len(self._axes):
                    return str(self._motor_values[prefix][index])
        raise KeyError(f"the fake KVP server has no variable {var!r}")

    def write(self, var, val, msgID=0):
        self._commands.append(("write", var, val, msgID))
        self._maybe_fail("write")
        if var == "TARGET_AXIS":
            self._target = self._parse_axis_message(str(val))
            self._axes = list(self._target)                         # placeholder: no motion over time
            if self._corrupt_axis_after_write:
                self._axis_text = "not an E6AXIS"                    # placeholder: a damaged $AXIS_ACT reply
            return "1"                                              # placeholder: KVP write acknowledgement
        raise KeyError(f"the fake KVP server cannot write {var!r}")

    def disconnect(self):
        self._commands.append(("disconnect",))
        self._connected = False

    # -- test hooks (not KUKA members; the driver never calls them) ----------------------------------------------
    def _force_read_failure(self):
        """The next read raises a normal exception, as a broken KVP link would."""
        self._fail_next_read = RuntimeError("fake KVP read failure")

    def _force_write_failure(self):
        """The next write raises a normal exception; reads before it still work."""
        self._fail_next_write = RuntimeError("fake KVP write failure")

    def _set_axis_text(self, text):
        """Return ``text`` for the next and later ``$AXIS_ACT`` reads."""
        self._axis_text = text

    def _corrupt_axis_read_after_write(self):
        """Damage ``$AXIS_ACT`` when the next TARGET_AXIS write arrives, so the read-back fails."""
        self._corrupt_axis_after_write = True

    def _maybe_fail(self, kind):
        name = "_fail_next_" + kind
        failure, setattr_value = getattr(self, name), None
        setattr(self, name, setattr_value)
        if failure is not None:
            raise failure

    def _axis_message(self, values):
        return "{E6AXIS: " + ", ".join(f"{name} {value}" for name, value in zip(_AXIS_NAMES, values)) + "}"

    def _parse_axis_message(self, text):
        tokens = text.replace(",", "").split()
        if tokens:
            tokens[-1] = tokens[-1].rstrip("}")
        if len(tokens) < 1 + 2 * len(_AXIS_NAMES) or tokens[0] != "{E6AXIS:":
            raise ValueError(f"not an E6AXIS text: {text!r}")
        values = []
        for index, name in enumerate(_AXIS_NAMES):
            if tokens[1 + 2 * index] != name:
                raise ValueError(f"not an E6AXIS text with {name}: {text!r}")
            values.append(float(tokens[2 + 2 * index]))
        return values
