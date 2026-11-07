"""Fake backend of the Reglo ICC driver: an in-memory stand-in for reglo_icc_pump._driver:RegloIccPump.

Gate G7: every public method and property defined here exists on the upstream class (the methods get_max_flow_rate,
set_tubing_id, pump_vol, dispense_vol, aspirate_vol, stop and is_running, and the properties pump_addr, channel_nos,
model_no, serial_no, sw_ver and head_code); ``ser_port`` is an attribute the upstream __init__ sets
(reglo_icc_pump/_driver.py:83).  Like the upstream class, pump_vol starts a channel, and stop(None) stops every
channel.  The values below are test data, not facts about a pump: each is marked ``# placeholder``.  Nothing here
talks to a device.
"""


class _FakeSerialPort:
    """The serial object the upstream class keeps as ``ser_port``; the driver only closes it."""

    def __init__(self):
        self.is_open = True

    def close(self):
        self.is_open = False


class FakeRegloIccPump:
    def __init__(self, **_options):
        self.ser_port = _FakeSerialPort()
        self._pump_addr = 1                       # placeholder
        self._channel_nos = [1, 2, 3, 4]          # placeholder
        self._serial_no = "FAKE-SERIAL"           # placeholder
        self._model_no = "FAKE-MODEL"             # placeholder
        self._sw_ver = "FAKE-VERSION"             # placeholder
        self._head_code = "FAKE-HEAD"             # placeholder
        self.tubing_ids = {ch: 1.52 for ch in self._channel_nos}       # placeholder
        self._max_flow_rate = {ch: 10.0 for ch in self._channel_nos}   # placeholder
        self._running = {ch: False for ch in self._channel_nos}
        self._calls = []

    @property
    def pump_addr(self):
        return self._pump_addr

    @property
    def channel_nos(self):
        return list(self._channel_nos)

    @property
    def model_no(self):
        return self._model_no

    @property
    def serial_no(self):
        return self._serial_no

    @property
    def sw_ver(self):
        return self._sw_ver

    @property
    def head_code(self):
        return self._head_code

    def get_max_flow_rate(self, ch_no):
        return self._max_flow_rate[ch_no]

    def set_tubing_id(self, ch_no, inner_diam):
        self.tubing_ids[ch_no] = float(inner_diam)
        self._max_flow_rate[ch_no] = 10.0         # placeholder: the pump recomputes it for the new tubing
        self._calls.append(("set_tubing_id", ch_no, float(inner_diam)))
        return self.tubing_ids[ch_no]

    def pump_vol(self, ch_no, direction, vol, rate, blocking=True):
        self._calls.append(("pump_vol", ch_no, direction, float(vol), float(rate), bool(blocking)))
        self._running[ch_no] = True
        self._running[ch_no] = False
        return None

    def dispense_vol(self, ch_no, vol, rate, *args, **kwargs):
        self._calls.append(("dispense_vol", ch_no, float(vol), float(rate), bool(kwargs.get("blocking", True))))
        return self.pump_vol(ch_no, "cw", vol, rate, **kwargs)

    def aspirate_vol(self, ch_no, vol, rate, **kwargs):
        self._calls.append(("aspirate_vol", ch_no, float(vol), float(rate), bool(kwargs.get("blocking", True))))
        return self.pump_vol(ch_no, "ccw", vol, rate, **kwargs)

    def stop(self, ch_no=None):
        self._calls.append(("stop", ch_no))
        if ch_no is None:
            for channel in self._channel_nos:
                self._running[channel] = False
        else:
            self._running[ch_no] = False
        return None

    def is_running(self, ch_no):
        return self._running[ch_no]
