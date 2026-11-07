"""Fake backend of the Rigol DS1054Z driver: a stateful stand-in for the upstream ``RigolDS1054Z`` object.

The gate replaces the transport with this object and counts every native call.  Each public method below has the
same name as the method of the upstream class (G7 reads the clone's AST); the private helpers keep the state and
are not part of that surface.  Every initial value is test data, not a device fact: the comments mark them
``# placeholder``.  Nothing here talks to an instrument.
"""


class FakeRigolDS1054Z:
    def __init__(self, **_options):
        self._identity = "RIGOL TECHNOLOGIES,DS1054Z,DS1ZA000000000,00.04.03.00.03"  # placeholder
        self._acquire_type = "NORMAL"  # placeholder
        self._averages = 2  # placeholder
        self._memory_depth = 14000  # placeholder
        self._sample_rate = 1.0e9  # placeholder
        self._timebase_mode = "MAIN"  # placeholder
        self._timebase_scale = 1.0e-3  # placeholder
        self._timebase_offset = 0.0  # placeholder
        self._trigger_mode = "EDGE"  # placeholder
        self._trigger_sweep = "AUTO"  # placeholder
        self._trigger_status = "STOP"  # placeholder
        self._edge_source = "CHANnel1"  # placeholder
        self._edge_slope = "POSITIVE"  # placeholder
        self._edge_level = 0.0  # placeholder
        # placeholder: the channel settings below are test data
        self._channels = {
            number: {
                "display": True,
                "coupling": "DC",
                "scale": 1.0,
                "offset": 0.0,
                "probe": 1.0,
                "bw_limit": "OFF",
                "invert": False,
            }
            for number in (1, 2, 3, 4)
        }

    # -- private state helpers -----------------------------------------------------------------------------
    def _channel(self, channel):
        if channel not in self._channels:
            raise ValueError(f"channel must be 1..4, got {channel!r}")
        return self._channels[channel]

    # -- identity and acquisition --------------------------------------------------------------------------
    def get_id(self):
        return self._identity

    def get_acquire_type(self):
        return self._acquire_type

    def set_acquire_type(self, acquire_type):
        self._acquire_type = str(acquire_type)

    def set_acquire_averages(self, count):
        self._averages = int(count)

    def set_acquire_memory_depth(self, mdep):
        self._memory_depth = int(mdep)

    def get_sample_rate(self):
        return self._sample_rate

    # -- timebase ------------------------------------------------------------------------------------------
    def get_timebase_mode(self):
        return self._timebase_mode

    def get_timebase_scale(self):
        return self._timebase_scale

    def set_timebase_scale(self, scale):
        self._timebase_scale = float(scale)

    def get_timebase_offset(self):
        return self._timebase_offset

    def set_timebase_offset(self, offset):
        self._timebase_offset = float(offset)

    # -- trigger -------------------------------------------------------------------------------------------
    def get_trigger_mode(self):
        return self._trigger_mode

    def get_trigger_sweep(self):
        return self._trigger_sweep

    def set_trigger_sweep(self, sweep):
        self._trigger_sweep = str(sweep)

    def get_trigger_status(self):
        return self._trigger_status

    def get_edge_trigger_source(self):
        return self._edge_source

    def set_edge_trigger_source(self, source):
        self._edge_source = str(source)

    def get_edge_trigger_slope(self):
        return self._edge_slope

    def set_edge_trigger_slope(self, slope):
        self._edge_slope = str(slope)

    def get_edge_trigger_level(self):
        return self._edge_level

    def set_edge_trigger_level(self, level):
        self._edge_level = float(level)

    # -- channel settings ----------------------------------------------------------------------------------
    def get_channel_display(self, channel):
        return bool(self._channel(channel)["display"])

    def set_channel_display(self, channel, state):
        self._channel(channel)["display"] = bool(state)

    def get_channel_coupling(self, channel):
        return self._channel(channel)["coupling"]

    def set_channel_coupling(self, channel, coupling):
        self._channel(channel)["coupling"] = str(coupling)

    def get_channel_scale(self, channel):
        return self._channel(channel)["scale"]

    def set_channel_scale(self, channel, scale):
        self._channel(channel)["scale"] = float(scale)

    def get_channel_offset(self, channel):
        return self._channel(channel)["offset"]

    def set_channel_offset(self, channel, offset):
        self._channel(channel)["offset"] = float(offset)

    def get_channel_probe(self, channel):
        return self._channel(channel)["probe"]

    def set_channel_probe(self, channel, attenuation):
        self._channel(channel)["probe"] = float(attenuation)

    def get_channel_bw_limit(self, channel):
        return self._channel(channel)["bw_limit"]

    def set_channel_bw_limit(self, channel, bw):
        self._channel(channel)["bw_limit"] = str(bw)

    def get_channel_invert(self, channel):
        return bool(self._channel(channel)["invert"])

    def set_channel_invert(self, channel, state):
        self._channel(channel)["invert"] = bool(state)

    # -- acquisition control -------------------------------------------------------------------------------
    def run(self):
        self._trigger_status = "AUTO"  # placeholder: the status a running acquisition reports

    def stop(self):
        self._trigger_status = "STOP"  # placeholder: the status a stopped acquisition reports

    def force_trigger(self):
        self._trigger_status = "TD"  # placeholder: the status a forced trigger reports
