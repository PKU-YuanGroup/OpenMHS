"""Fake backend of the SmarAct MCS2 driver: an in-memory stand-in for SmarActMCS2Wrapper.

Gate G7: every public method defined here is a method of
``pymodaq_plugins_smaract.hardware.mcs2.MCS2_wrapper:SmarActMCS2Wrapper`` in the
clone, with the same signature.  The wrapper keeps the controller index in
``self.controller_index`` and receives the channel index as an argument; this
fake does the same, so the driver's calls look exactly like the calls on the
hardware wrapper.

The starting values are test data only (each is marked ``# placeholder``), not
facts about a SmarAct device: the channel count, base unit, base-resolution
exponent and positioner type depend on the controller and positioner the
operator configured.  The fake never talks to a device; a closed-loop move is
applied immediately so the position read after a move shows the new value.
"""


class FakeMCS2Wrapper:
    """In-memory MCS2 wrapper: one controller, three channels."""

    def __init__(self, **_options):
        self.controller_index = None          # set by open_communication, as upstream
        self._device_name = "SmarAct MCS2 controller"          # placeholder
        self._units = ["meter", "meter", "meter"]              # placeholder
        self._base_resolution = [-12, -12, -12]                # placeholder
        self._positioner_type = ["SLC-24180", "SLC-24180", "SLC-24180"]  # placeholder
        self._position = [0, 0, 0]                             # placeholder (base units)
        self._open = False
        self._stop_calls = 0

    def open_communication(self, controller_locator, configuration: str = ''):
        self.controller_index = 0                              # placeholder controller index
        self._open = True

    def close_communication(self):
        self._open = False

    def get_device_name(self) -> str:
        return self._device_name

    def get_number_of_channels(self):
        return len(self._position)

    def get_positionner_type(self, channel_index) -> str:
        return self._positioner_type[channel_index]

    def get_units(self, channel_index: int):
        return self._units[channel_index]

    def get_base_resolution(self, channel_index: int) -> int:
        return self._base_resolution[channel_index]

    def get_position(self, channel_index: int):
        return self._position[channel_index]

    def find_reference(self, channel_index):
        # the reference search resets the position to zero when the configuration says so
        self._position[channel_index] = 0                      # placeholder outcome

    def absolute_move(self, channel_index, value: int):
        self._position[channel_index] = int(value)

    def relative_move(self, channel_index, value: int):
        self._position[channel_index] += int(value)

    def stop(self, channel_index: int):
        self._stop_calls += 1
