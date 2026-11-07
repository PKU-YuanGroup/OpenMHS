"""Fake backend of the Vacuubrand DCP 3000 driver: an in-memory stand-in for
``vacuubrand.dcp3000.dcp3000:DCP3000``.

Gate G7: every public method defined here is a method of the upstream ``DCP3000`` class
(vacuubrand/dcp3000/dcp3000.py:24-87), and each method has the same signature convention as the upstream:
``transducer_pressure(channel=1)``, ``event_time_interval(value=None)``, ``recording_time_interval(value=None)``,
``on_setpoint(channel, value=None)`` and ``off_setpoint(channel, value=None)`` read without a value and write with one
(dcp3000.py:32-64).  Like the upstream class on an asyncio connection, every method is a coroutine function (the
upstream protocol returns coroutines, protocol.py:113-143).

The starting values and canned replies are copied from the defaults of the upstream ``sinstruments`` simulator
(vacuubrand/simulator.py:22-42) so the fake answers what the project's own simulator answers.  Every number here is
test data, marked ``# placeholder``: none of them is a Fact, a Limit or a reference.  The values never move by
themselves, so reading the state twice gives the same state.  Nothing here talks to a device.
"""


class FakeDCP3000:
    def __init__(self, **_options):
        # All values below are test data from vacuubrand/simulator.py:22-42 unless marked otherwise.
        self._pressure = 1004.1                    # placeholder: simulator.py:79-80 (IN_PV_1)
        self._transducer_pressures = [362.0, 234.0, 278.0, 213.0]   # placeholder: simulator.py:28 (IN_PV_X)
        self._configuration = {                    # placeholder: simulator.py:30 (IN_CFG "1001144")
            "unit": "mbar",                        # placeholder: decode_config of text[1] == "0"
            "acoustic_signal": False,              # placeholder: text[2] == "0"
            "venting_valve_connected": True,       # placeholder: text[3] == "1"
            "fault_indicator_connected": True,     # placeholder: text[4] == "1"
            "nb_active_pressure_transducers": 4,   # placeholder: text[5] == "4"
            "nb_pressure_transducers": 4,          # placeholder: text[6] == "4"
        }
        self._errors = []                          # placeholder: simulator.py:31 (IN_ERR "00000")
        self._version = "DCP 3000  V2.30"          # placeholder: simulator.py:23 (IN_VER)
        self._event_interval = 0                   # placeholder: simulator.py:32 (IN_SP_1 "00:00")
        self._recording_interval = 5940            # placeholder: simulator.py:33 (IN_SP_2 "99:00")
        self._setpoints = {                        # placeholder: simulator.py:34-41 (IN_SP_11..IN_SP_24)
            1: {"on": 111.0, "off": 11.5},         # placeholder
            2: {"on": 222.0, "off": 22.5},         # placeholder
            3: {"on": 333.0, "off": 33.5},         # placeholder
            4: {"on": 444.0, "off": 44.5},         # placeholder
        }
        self._remote = True                        # placeholder: simulator.py:58 (_on = True)
        self._venting_valve = "closed"             # placeholder: no readback exists upstream

    async def pressure(self):
        return self._pressure if self._remote else 0.0      # placeholder: simulator.py:78-80

    async def transducer_pressure(self, channel=1):
        return self._transducer_pressures[channel - 1]

    async def transducer_pressures(self):
        return list(self._transducer_pressures)

    async def config(self):
        return dict(self._configuration)

    async def errors(self):
        return list(self._errors)

    async def version(self):
        return self._version

    async def event_time_interval(self, value=None):
        if value is not None:
            self._event_interval = int(value)
            return None
        return self._event_interval

    async def recording_time_interval(self, value=None):
        if value is not None:
            self._recording_interval = int(value)
        return self._recording_interval

    async def on_setpoint(self, channel, value=None):
        if channel not in {1, 2, 3, 4}:           # placeholder: the same channel set as dcp3000.py:53
            raise AssertionError(f"set point channel {channel} is not one of 1 to 4")
        if value is None:
            return self._setpoints[channel]["on"]
        self._setpoints[channel]["on"] = float(value)
        return None

    async def off_setpoint(self, channel, value=None):
        if channel not in {1, 2, 3, 4}:           # placeholder: the same channel set as dcp3000.py:53
            raise AssertionError(f"set point channel {channel} is not one of 1 to 4")
        if value is None:
            return self._setpoints[channel]["off"]
        self._setpoints[channel]["off"] = float(value)
        return None

    async def switch_on(self):
        self._remote = True

    async def switch_off(self):
        self._remote = False

    async def close_venting_valve(self):
        self._venting_valve = "closed"

    async def open_venting_value(self):
        self._venting_valve = "open"

    async def vent(self):
        self._venting_valve = "venting"
