"""Fake backend of the Keysight DSOX1200 driver: an in-memory stand-in for keysight_dsox1200.instrument:DSOX1200.

Gate G7: every public method defined here is a method of ``DSOX1200`` in the clone
(src/keysight_dsox1200/instrument.py): the identity and option queries, the channel, timebase, trigger and
acquisition setters and their query counterparts, run/stop/single/autoscale, the automatic measurements and close.
The state attributes are private instance data, so the fake surface is the upstream method surface.

The clone has no simulator for this class, so this file is an in-memory stand-in, not a recording of a session.
Every number and string below is test data, not a fact from the clone or a record of an instrument: each is marked
``# placeholder``.  Nothing here talks to a device.
"""


class FakeDSOX1200:
    """A fresh in-memory oscilloscope per endpoint; all starting values are placeholders."""

    def __init__(self, **_options):
        self._display = True                       # placeholder
        self._coupling = "DC"                      # placeholder
        self._probe = 1.0                          # placeholder
        self._scale = 0.5                          # placeholder
        self._offset = 0.0                         # placeholder
        self._invert = False                       # placeholder
        self._timebase_mode = "MAIN"               # placeholder
        self._timebase_scale = 0.001               # placeholder
        self._timebase_position = 0.0              # placeholder
        self._trigger_source = "CHANnel1"          # placeholder
        self._trigger_level = 0.0                  # placeholder
        self._trigger_slope = "POSitive"           # placeholder
        self._trigger_sweep = "AUTO"               # placeholder
        self._acquire_type = "NORMal"              # placeholder
        self._acquire_count = 2                    # placeholder
        self._acquire_points = 1000                # placeholder
        self._sample_rate = 1000000.0              # placeholder
        self._complete = 100                       # placeholder
        self.closed = False

    # -- identity and options -------------------------------------------------------------------------------------
    def identify(self):
        return "KEYSIGHT TECHNOLOGIES,DSOX1202A,FAKE000000,02.12.2021102901"  # placeholder

    def get_options(self):
        return "0"  # placeholder

    # -- :CHANnel<n> ----------------------------------------------------------------------------------------------
    def channel_display(self, channel, on):
        self._display = bool(on)

    def channel_display_query(self, channel):
        return self._display

    def channel_coupling(self, channel, coupling):
        self._coupling = str(getattr(coupling, "value", coupling))

    def channel_coupling_query(self, channel):
        return self._coupling

    def channel_probe(self, channel, attenuation):
        self._probe = float(attenuation)

    def channel_probe_query(self, channel):
        return self._probe

    def channel_scale(self, channel, volts_per_div):
        self._scale = float(volts_per_div)

    def channel_scale_query(self, channel):
        return self._scale

    def channel_offset(self, channel, offset_volts):
        self._offset = float(offset_volts)

    def channel_offset_query(self, channel):
        return self._offset

    def channel_invert(self, channel, invert):
        self._invert = bool(invert)

    def channel_invert_query(self, channel):
        return self._invert

    # -- :TIMebase ------------------------------------------------------------------------------------------------
    def timebase_mode(self, mode):
        self._timebase_mode = str(getattr(mode, "value", mode))

    def timebase_mode_query(self):
        return self._timebase_mode

    def timebase_scale(self, seconds_per_div):
        self._timebase_scale = float(seconds_per_div)

    def timebase_scale_query(self):
        return self._timebase_scale

    def timebase_position(self, seconds):
        self._timebase_position = float(seconds)

    def timebase_position_query(self):
        return self._timebase_position

    # -- :TRIGger -------------------------------------------------------------------------------------------------
    def trigger_edge_source(self, source):
        self._trigger_source = str(getattr(source, "value", source))

    def trigger_edge_source_query(self):
        return self._trigger_source

    def trigger_edge_level(self, volts):
        self._trigger_level = float(volts)

    def trigger_edge_level_query(self):
        return self._trigger_level

    def trigger_edge_slope(self, slope):
        self._trigger_slope = str(getattr(slope, "value", slope))

    def trigger_edge_slope_query(self):
        return self._trigger_slope

    def trigger_sweep(self, sweep):
        self._trigger_sweep = str(getattr(sweep, "value", sweep))

    def trigger_sweep_query(self):
        return self._trigger_sweep

    # -- :ACQuire -------------------------------------------------------------------------------------------------
    def acquire_type(self, acq_type):
        self._acquire_type = str(getattr(acq_type, "value", acq_type))

    def acquire_type_query(self):
        return self._acquire_type

    def acquire_count(self, n):
        self._acquire_count = int(n)

    def acquire_count_query(self):
        return self._acquire_count

    def acquire_points(self, n):
        self._acquire_points = int(n)

    def acquire_points_query(self):
        return self._acquire_points

    def acquire_srate_query(self):
        return self._sample_rate

    def acquire_complete(self):
        return self._complete

    # -- root commands --------------------------------------------------------------------------------------------
    def run(self):
        self._complete = 0                          # placeholder

    def stop(self):
        self._complete = 0                          # placeholder

    def single(self):
        self._complete = 100                        # placeholder

    def autoscale(self):
        self._scale = 1.0                           # placeholder
        self._offset = 0.0                          # placeholder

    # -- :MEASure -------------------------------------------------------------------------------------------------
    def measure_frequency(self, source=None):
        return 1000.0                               # placeholder

    def measure_period(self, source=None):
        return 0.001                                # placeholder

    def measure_duty_cycle(self, source=None):
        return 50.0                                 # placeholder

    def measure_vmax(self, source=None):
        return 1.25                                 # placeholder

    def measure_vmin(self, source=None):
        return -1.25                                # placeholder

    def measure_vpp(self, source=None):
        return 2.5                                  # placeholder

    def measure_vrms(self, source=None):
        return 0.88                                 # placeholder

    def measure_vaverage(self, source=None):
        return 0.01                                 # placeholder

    def measure_vamplitude(self, source=None):
        return 2.5                                  # placeholder

    def measure_vtop(self, source=None):
        return 1.25                                 # placeholder

    def measure_vbase(self, source=None):
        return -1.25                                # placeholder

    def measure_risetime(self, source=None):
        return 1e-6                                 # placeholder

    def measure_falltime(self, source=None):
        return 1e-6                                 # placeholder

    def measure_phase(self, source=None):
        return 45.0                                 # placeholder

    def measure_delay(self, source=None):
        return 1e-6                                 # placeholder

    def measure_nwidth(self, source=None):
        return 5e-4                                 # placeholder

    def measure_pwidth(self, source=None):
        return 5e-4                                 # placeholder

    def measure_overshoot(self, source=None):
        return 2.5                                  # placeholder

    def measure_preshoot(self, source=None):
        return 1.5                                  # placeholder

    def measure_counter(self, source=None):
        return 1000.0                               # placeholder

    # -- lifecycle ------------------------------------------------------------------------------------------------
    def close(self):
        self.closed = True
