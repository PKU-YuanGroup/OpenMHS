"""Fake backend of the Korad KC3405P driver: an in-memory stand-in for ``korad:KC3405P``.

Gate G7: every public method defined here exists on the upstream class (korad.py:28-475).  The stand-in implements
the methods the driver calls and keeps one plain state dictionary per channel:

* ``get_voltage`` / ``get_current`` (korad.py:92-102) and their settings (korad.py:104-114);
* ``set_voltage`` / ``set_current`` (korad.py:116-134), kept with three decimals like the upstream format string;
* the overvoltage and overcurrent protection settings (korad.py:184-212) and their on/off states (korad.py:214-256);
* ``enable_output`` / ``disable_output`` (korad.py:144-182), where channel 0 addresses all four channels;
* the private ``_send_command`` send path (korad.py:38-41), which the driver's e-stop and safe-state action use to
  send ``OUT1234:0`` without waiting for a status reply;
* ``get_device_info`` (korad.py:49-69) and ``get_status`` (korad.py:71-90).

The measured voltage and current follow the set points while the corresponding output is on and are zero while it
is off; that is test behaviour, not a claim about a real instrument.  Every number below is test data for this
stand-in, never a Fact, a Limit or a reference: each one is marked ``# placeholder``.  Nothing here talks to a
device.
"""


class FakeKC3405P:
    def __init__(self, **_options):
        #: placeholder test data: four channels, each with its own state
        self._channels = (1, 2, 3, 4)  # placeholder
        self._voltage_setting = {ch: 0.0 for ch in self._channels}     # placeholder starting voltage
        self._current_setting = {ch: 0.0 for ch in self._channels}     # placeholder starting current
        self._ocp_setting = {ch: 5.1 for ch in self._channels}         # placeholder starting OCP setting
        self._ovp_setting = {ch: 31.0 for ch in self._channels}        # placeholder starting OVP setting
        self._ocp_enabled = {ch: True for ch in self._channels}        # placeholder starting OCP state
        self._ovp_enabled = {ch: True for ch in self._channels}        # placeholder starting OVP state
        self._output_enabled = {ch: False for ch in self._channels}    # placeholder starting output state

    def _channel(self, channel):
        channel = int(channel)
        if channel not in self._channels:
            raise ValueError("channel must be one of the four output channels")
        return channel

    def _send_command(self, cmd: str):
        """The upstream send path (korad.py:38-41); the stand-in parses only the safe-state stop line."""
        if cmd != "OUT1234:0":  # placeholder test behaviour: the only line this stand-in parses
            raise ValueError(f"the fake stand-in does not model the command {cmd!r}")
        for channel in self._channels:
            self._output_enabled[channel] = False  # placeholder test data: all outputs off
        return self

    # -- device information and status ---------------------------------------------------------------
    def get_device_info(self) -> dict:
        return {
            "system_dhcp": 0,                        # placeholder test data
            "system_ip_address": "192.0.2.10",       # placeholder test data (TEST-NET-1)
            "system_netmask": "255.255.255.0",       # placeholder test data
            "system_gateway": "192.0.2.1",           # placeholder test data
            "system_mac_address": "02:00:00:00:00:01",  # placeholder test data
            "system_udp_port": 18190,                # placeholder test data
            "system_baud_rate": 9600,                # placeholder test data
            "system_gpib_address": 1,                # placeholder test data
        }

    def get_status(self) -> dict:
        status = {}
        for channel in self._channels:              # placeholder test data: channels 1-4
            status[f"ch{channel}_mode"] = "cv" if self._output_enabled[channel] else "cc"  # placeholder
            status[f"ch{channel}_output"] = "on" if self._output_enabled[channel] else "off"  # placeholder
        return status

    # -- measurements and set points ----------------------------------------------------------------
    def get_voltage(self, channel: int) -> float:
        channel = self._channel(channel)
        return self._voltage_setting[channel] if self._output_enabled[channel] else 0.0  # placeholder

    def get_current(self, channel: int) -> float:
        channel = self._channel(channel)
        return self._current_setting[channel] if self._output_enabled[channel] else 0.0  # placeholder

    def get_voltage_setting(self, channel: int) -> float:
        return self._voltage_setting[self._channel(channel)]

    def get_current_setting(self, channel: int) -> float:
        return self._current_setting[self._channel(channel)]

    def set_voltage(self, channel: int, voltage: float) -> None:
        channel = self._channel(channel)
        self._voltage_setting[channel] = round(float(voltage), 3)  # placeholder test data: three decimals

    def set_current(self, channel: int, current: float) -> None:
        channel = self._channel(channel)
        self._current_setting[channel] = round(float(current), 3)  # placeholder test data: three decimals

    # -- protection settings ------------------------------------------------------------------------
    def get_overcurrent_protection_setting(self, channel: int) -> float:
        return self._ocp_setting[self._channel(channel)]

    def set_overcurrent_protection(self, channel: int, current: float) -> None:
        channel = self._channel(channel)
        self._ocp_setting[channel] = round(float(current), 3)  # placeholder test data: three decimals

    def get_overvoltage_protection_setting(self, channel: int) -> float:
        return self._ovp_setting[self._channel(channel)]

    def set_overvoltage_protection(self, channel: int, voltage: float) -> None:
        channel = self._channel(channel)
        self._ovp_setting[channel] = round(float(voltage), 3)  # placeholder test data: three decimals

    # -- protection states --------------------------------------------------------------------------
    def get_ocp_status(self, channel: int) -> bool:
        return bool(self._ocp_enabled[self._channel(channel)])

    def enable_overcurrent_protection(self, channel: int):
        self._ocp_enabled[self._channel(channel)] = True  # placeholder test data: enabled

    def disable_overcurrent_protection(self, channel: int):
        self._ocp_enabled[self._channel(channel)] = False  # placeholder test data: disabled

    def get_ovp_status(self, channel: int) -> bool:
        return bool(self._ovp_enabled[self._channel(channel)])

    def enable_overvoltage_protection(self, channel: int):
        self._ovp_enabled[self._channel(channel)] = True  # placeholder test data: enabled

    def disable_overvoltage_protection(self, channel: int):
        self._ovp_enabled[self._channel(channel)] = False  # placeholder test data: disabled

    # -- outputs ------------------------------------------------------------------------------------
    def enable_output(self, channel: int = 0):
        targets = self._channels if int(channel) == 0 else (self._channel(channel),)  # placeholder: 0 = all
        for target in targets:
            self._output_enabled[target] = True  # placeholder test data: output on

    def disable_output(self, channel: int = 0):
        targets = self._channels if int(channel) == 0 else (self._channel(channel),)  # placeholder: 0 = all
        for target in targets:
            self._output_enabled[target] = False  # placeholder test data: output off
