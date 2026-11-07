"""Fake backend of the Festo FPosBAPI driver: an in-memory stand-in for FPosBAPIClient.

Gate G7: every public method defined here exists on
``applied_motion.backends.fposbapi_client:FPosBAPIClient``.  The fake keeps
the position and the PLC parameter 103 in memory, answers ``ROB_POS`` through
``send_command`` (the driver's only raw command) and makes the native stop
(``HALT``) observable.  The values are test data, not a recording of a
device, and nothing here talks to hardware.
"""


class FakeFPosBAPIClient:
    def __init__(self, **_options):
        self._x = 0.0               # placeholder: test start position
        self._y = 0.0               # placeholder: test start position
        self._z = 0.0               # placeholder: test start position
        self._parameters = {103: 50.0}  # placeholder: parameter 103 is the speed, test start value
        self._status = "IDLE"       # placeholder: canned SYS_STATUS value
        self._error_active = False  # placeholder: canned IS_ERROR value
        self._error_text = ""       # placeholder: canned READ_ERR value
        self._fieldbus_error = ""   # placeholder: canned FPB_ERROR value
        self._closed = False

    def _terminal(self, command, *fields):
        """One canned terminal line in the FPosBAPI layout (message id 1 for every reply)."""
        values = [str(item) for item in fields]
        return ", ".join(["1", command, *values, "0", "NULL", "SUCCESS"])  # placeholder: canned reply

    def send_command(self, command, *params, timeout=None):
        if command == "ROB_POS":
            return [self._terminal("ROB_POS", self._x, self._y, self._z)]
        raise ValueError(f"fake FPosBAPI client does not answer {command!r}")

    def get_par(self, par_id):
        if par_id in self._parameters:
            return [self._parameters[par_id]]
        return []  # placeholder: no other parameter is modelled

    def set_par(self, par_id, *values):
        if values:
            self._parameters[par_id] = float(values[0])

    def home(self):
        self._x = 0.0  # placeholder: HOME reference position
        self._y = 0.0  # placeholder: HOME reference position
        self._z = 0.0  # placeholder: HOME reference position
        self._status = "IDLE"  # placeholder: canned status after HOME

    def move_loc(self, a1, a2, a3, tool_id=0, move_typ=0, retract_z=0, slow_app=0):
        self._x = float(a1)
        self._y = float(a2)
        self._z = float(a3)
        self._status = "IDLE"  # placeholder: canned status after MOVE_LOC

    def halt(self):
        self._status = "HALTED"  # placeholder: canned status after HALT

    def sys_status(self):
        return self._status

    def is_error(self):
        return self._error_active

    def fpb_error(self):
        return self._fieldbus_error

    def read_err(self):
        return self._error_text

    def reset_err(self):
        self._error_active = False
        self._error_text = ""  # placeholder: canned cleared error text

    def list_commands(self):
        return ["HOME", "MOVE_LOC", "HALT", "ROB_POS"]  # placeholder: canned command list

    def close(self):
        self._closed = True
