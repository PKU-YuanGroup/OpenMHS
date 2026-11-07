"""Fake backend of the BMG driver: an in-memory stand-in for sidecar.bmg_interface:BmgCom.

Gate G7: every public method defined here exists on BmgCom in the clone.  The fake keeps the part of the upstream
surface this package uses (open_connection, close_connection, get_version, get_status, get_error, set_temp,
read_temps) and follows the upstream method bodies (sidecar/bmg_interface.py:18-112 and 147-152) over an in-memory
stand-in of the COM object: GetInfo answers are raw values that read_temps divides by 10, a value float() cannot parse
gives None, a status or error that is not a string reads 'unknown', and set_temp applies the upstream validator of
the range the constructor flag selects, sends ("Temp", str(temp)) through ExecuteAndWait and raises when the answer
is not 0.  The upstream passes GetInfo items as ctypes.c_char_p; the fake keys them by plain strings.  The plate tray,
Init and the assay run are not served by the package, so the fake leaves them out.

Every literal value below is test data, marked ``# placeholder``, except the validator bounds copied from the
upstream.  The start values are not the device's temperatures or status, and the fake answers at once: it is not a
recording and shows nothing about how the reader times its commands.
"""


class _FakeRemoteControl:
    """In-memory stand-in for the BMG_ActiveX.BMGRemoteControl COM object (tests change its answers)."""

    def __init__(self):
        self.version = "fake BMG remote control"           # placeholder
        self.info = {                                      # placeholder raw GetInfo answers
            "Status": "Idle ",
            "Error": "",
            "Temp1": "250",
            "Temp2": "250",
            "Temp3": "250",
        }
        self.responses = {}                                # ExecuteAndWait answer per command name; 0 when absent
        self.executed = []                                 # every ExecuteAndWait argument tuple, in order
        self.connected = False

    def OpenConnection(self, control_name):  # noqa: N802 - the COM method name
        self.connected = True
        return 0

    def CloseConnection(self):  # noqa: N802 - the COM method name
        self.connected = False
        return 0

    def GetVersion(self):  # noqa: N802 - the COM method name
        return self.version

    def GetInfo(self, item):  # noqa: N802 - the COM method name
        return self.info.get(item)

    def ExecuteAndWait(self, args):  # noqa: N802 - the COM method name
        self.executed.append(tuple(args))
        return self.responses.get(args[0], 0)


class FakeBmgCom:
    """Stand-in for BmgCom over an in-memory COM object; all state is local to this object."""

    def __init__(self, control_name="CLARIOstar", extended_temperature_range_model=False, **_options):
        self.control_name = control_name
        self.extended_temperature_range_model = bool(extended_temperature_range_model)
        self.com = _FakeRemoteControl()
        self.open_connection()

    def open_connection(self) -> None:
        res = self.com.OpenConnection(self.control_name)
        if res:
            raise Exception(f"OpenConnection failed: {res}")

    def close_connection(self) -> None:
        res = self.com.CloseConnection()
        if res:
            raise Exception(f"CloseConnection failed: {res}")

    def get_version(self) -> str:
        return self.com.GetVersion()

    def get_status(self) -> str:
        status = self.com.GetInfo("Status")
        return status.strip() if isinstance(status, str) else "unknown"

    def get_error(self) -> str:
        status = self.com.GetInfo("Error")
        return status.strip() if isinstance(status, str) else "unknown"

    def set_temp(self, temp: float) -> None:
        min_temp, max_temp = (
            (10.0, 60.0) if self.extended_temperature_range_model else (25.0, 45.0)  # upstream bmg_interface.py:78-80
        )
        if not min_temp <= temp <= max_temp and temp not in [0.0, 0.1]:
            raise ValueError(f"Temp must be a float between {min_temp} and {max_temp}, or 0.0/0.1")
        response = self._exec("Temp", str(temp))
        if response != 0:
            raise Exception(f"Failed to set temperature. response = {response}")

    def read_temps(self) -> dict:
        def _parse(name):
            raw = self.com.GetInfo(name)
            try:
                return float(raw) / 10
            except (TypeError, ValueError):
                return None

        return {
            "Temp1": _parse("Temp1"),
            "Temp2": _parse("Temp2"),
            "Temp3": _parse("Temp3"),
        }

    def _exec(self, cmd, *args):
        return self.com.ExecuteAndWait((cmd, *args))
