"""Fake backend for the Thorlabs compact-spectrometer channel.

Gate G7: every public method defined here exists on ``components.pyCCT.pyCCT:SpectrometerWrapper``
(src/components/pyCCT/pyCCT.py:222-409).  The methods mirror the upstream signatures, including the optional
``cancellation_token`` argument that a real .NET call would use.  The returned values are in-memory test data and
never facts: the spectrometer state stays constant except for the settings this class is asked to change, and the
64-point spectrum is marked ``# placeholder``.  Nothing here talks to a device.
"""


class FakeSpectrometerWrapper:
    def __init__(self, **_options):
        self._device_id = "fake-spectrometer"                                  # placeholder
        self._exposure_ms = 10.0                                               # placeholder
        self._frames = 1                                                       # placeholder
        self._input_trigger = (False, False, False)                            # placeholder
        self._output_delay_ms = 0.0                                            # placeholder
        self._amplitude_correction = False
        self._shutter_open = True
        self._wavelengths = [340.0 + index * (760.0 / 63.0) for index in range(64)]  # placeholder
        self._intensities = [100.0 + index for index in range(64)]              # placeholder

    def get_device_id(self):
        return self._device_id

    def set_manual_exposure(self, exposure_time, cancellation_token=None):
        self._exposure_ms = float(exposure_time)
        return True

    def get_manual_exposure(self):
        return round(self._exposure_ms, 2)

    def set_hardware_average(self, ave_frames, cancellation_token=None):
        self._frames = int(ave_frames)
        return True

    def get_hardware_average(self):
        return int(self._frames)

    def acquire_single_spectrum(self, cancellation_token=None):
        return list(self._wavelengths), list(self._intensities), self.get_manual_exposure(), self.get_hardware_average()

    def set_shutter(self, open_position, cancellation_token=None):
        self._shutter_open = bool(open_position)
        return True

    def set_input_hw_trigger(self, enabled, ave_no_wait, slope_falling_edge, cancellation_token=None):
        self._input_trigger = (bool(enabled), bool(ave_no_wait), bool(slope_falling_edge))
        return True

    def get_input_hw_trigger_state(self):
        return self._input_trigger

    def set_output_hw_trigger_delay(self, delay_ms, cancellation_token=None):
        self._output_delay_ms = float(delay_ms)
        return True

    def get_output_hw_trigger_delay(self):
        return round(self._output_delay_ms, 2)

    def get_use_amplitude_correction(self):
        return self._amplitude_correction

    def set_use_amplitude_correction(self, state):
        self._amplitude_correction = bool(state)
