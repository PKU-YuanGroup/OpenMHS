"""Fake backend of the TDS3054C driver: an in-memory stand-in for the upstream scope class.

Gate G7: every public method defined here exists on ``zmq_server.drivers.TDS3054C:TDS3054C``
(TDS3054C.py).  The class keeps the same method surface and signatures the driver calls, and it
records every command instead of opening a socket.  Every number below is test data of this fake,
not a fact about any scope; each is marked ``# placeholder``.
"""


class FakeTDS3054C:
    def __init__(self, connection_params: dict | None = None, **_options):
        self._connection_params = dict(connection_params or {})
        self._selected = 1                    # placeholder: the control channel
        self._enabled = {1: True, 2: False, 3: False, 4: False}  # placeholder: display states
        self._vertical_scale = {1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0}  # placeholder: volts/div
        self._vertical_position = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}  # placeholder: native values
        self._horizontal_scale = 0.001        # placeholder: seconds/div
        self._horizontal_position = 0.0       # placeholder: native value
        self._trigger_channel = 1             # placeholder: source channel
        self._trigger_level = 0.0             # placeholder: native trigger level
        self._trigger_slope = "RISE"          # placeholder: the upstream Slope.RISING value
        self._acquiring = False               # placeholder: acquisition state
        self._commands: list[str] = []        # placeholder: the commands this fake received

    # -- transport --------------------------------------------------------------------------------
    def query(self, cmd: str, channel: int = None) -> str:
        self._commands.append(str(cmd))
        if cmd == "SELECT?":
            states = ";".join(f"CH{number} {1 if self._enabled[number] else 0}"
                              for number in (1, 2, 3, 4))
            return f":SELECT:{states};MATH 0;CONTROL CH{self._selected}"  # placeholder reply
        if cmd == "*IDN?":
            return "TEKTRONIX,TDS 3054C,0,CF:91.1CT FV:v1.00"  # placeholder identification
        if cmd == "WFMPre:XINcr?":
            return "2.5E-07"                 # placeholder: seconds per sample
        return ""                            # placeholder: an empty write acknowledgement

    def write(self, cmd: str, channel: int = None) -> None:
        self._commands.append(str(cmd))
        if cmd == "ACQ:STATE STOP":
            self._acquiring = False

    # -- settings ---------------------------------------------------------------------------------
    def set_channel(self, channel: int) -> None:
        self._selected = int(channel)

    def set_channel_state(self, channel: int, enabled: bool) -> None:
        self._enabled[int(channel)] = bool(enabled)

    def set_vertical_scale(self, channel: int, scale: float) -> None:
        self._vertical_scale[int(channel)] = float(scale)

    def set_vertical_position(self, channel: int, offset: float) -> None:
        self._vertical_position[int(channel)] = float(offset)

    def set_horizontal_scale(self, scale: float) -> None:
        self._horizontal_scale = float(scale)

    def set_horizontal_position(self, offset: float) -> None:
        self._horizontal_position = float(offset)

    def set_trigger_level(self, channel: int, level: float) -> None:
        self._trigger_level = float(level)

    def set_trigger_slope(self, slope: str) -> None:
        self._trigger_slope = str(slope)

    def set_trigger_channel(self, channel: int) -> None:
        self._trigger_channel = int(channel)

    # -- acquisition ------------------------------------------------------------------------------
    def get_horizontal_increment(self) -> str:
        return "2.5E-07"                     # placeholder: seconds per sample

    def sample(self, timeout: int = 60) -> None:
        self._acquiring = True                 # placeholder: the acquisition starts
        self._acquiring = False                # placeholder: and finishes immediately

    # -- lifecycle --------------------------------------------------------------------------------
    def end_connection(self) -> None:
        return None
