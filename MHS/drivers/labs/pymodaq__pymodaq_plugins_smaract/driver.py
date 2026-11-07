"""OpenMHS driver for gh.pymodaq/pymodaq_plugins_smaract: a SmarAct MCS2 motion channel.

A direct Driver (decorated methods) over the upstream object
``pymodaq_plugins_smaract.hardware.mcs2.MCS2_wrapper:SmarActMCS2Wrapper``.  The
wrapper talks to the SmarAct MCS2 DLL and addresses the controller by an unsigned
controller index and one positioner channel; this binding exposes one channel of
one controller (``channel_index`` backend option, 0 by default).

* reads: the channel position in controller base units, the base unit name, the
  base resolution exponent, the positioner type, the controller name and the
  controller channel count;
* actions: move to an absolute position, move by a relative offset, start the
  reference search, and stop the channel (the native stop, as an extension
  action because the catalogue's ``cap.motion.stop.v1`` input schema carries a
  deceleration profile in m/s2 that the MCS2 ``Stop`` call cannot apply);
* safety: the native ``stop`` is the e-stop.  ``safe_state`` is no commanded
  motion on the bound channel.

No text file of the clone states the travel range of a positioner attached to an
MCS2 controller: the base unit and its resolution come from the configured
positioner (the same wrapper notes that it is generally a picometer for a linear
positioner and a nanodegree for a rotary one).  The position and offset inputs
therefore carry ``Limit.operator_required``: every move is refused with
``MHS.SAFETY.LIMITS_UNSET`` until the operator's site-limits overlay supplies the
travel range of the installed positioner in base units.
``site-limits.example.json`` shows the shape of that overlay.

Every Fact cites a line of the clone at the pinned commit
(eeb3fa8ced4ce9eab102951a4ad482ee4152fe6c).  This package is model-authored and
unreviewed; the acceptance gate runs the fake backend only and no hardware was
attached.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read

POSITION_REASON = (
    "no text of the clone states the travel range of the positioner on an MCS2 channel: the base unit and "
    "resolution come from the configured positioner (generally a picometer for linear or a nanodegree for rotary). "
    "The only range in the clone is the MCS1 plugin's -61500 to 61500 um for one SLC-24180, and that plugin says the "
    "bounds depend on the plugged positioner. The operator supplies the range of the installed positioner in base units.")


class SmarActMCS2(Driver):
    device_id = "smaract-mcs2"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R1"
    native = "pymodaq_plugins_smaract.hardware.mcs2.MCS2_wrapper:SmarActMCS2Wrapper"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeMCS2Wrapper"}
    vendor, model = "SmarAct", "MCS2"
    display_name = "SmarAct MCS2 controller channel (pymodaq_plugins_smaract)"
    tags = ["positioner", "motion", "piezo", "mcs2", "smaract"]
    facts = [
        Fact("The wrapper's API is the SmarAct MCS2 Programmers Guide and the channel configuration (sensor type) "
             "is done beforehand with the SmarAct MCS2ServiceTool software",
             source="upstream_code",
             ref="src/pymodaq_plugins_smaract/hardware/mcs2/MCS2_wrapper.py:40-45"),
        Fact("The base unit of a channel is generally a picometer for a linear positioner and a nanodegree for a "
             "rotary one", source="upstream_code",
             ref="src/pymodaq_plugins_smaract/hardware/mcs2/MCS2_wrapper.py:48-49"),
        Fact("get_position reads the POSITION property of the channel and returns an int in base units; its "
             "docstring also describes the value as picometers", source="upstream_code",
             ref="src/pymodaq_plugins_smaract/hardware/mcs2/MCS2_wrapper.py:124-145"),
        Fact("get_units returns the POS_BASE_UNIT enum name in lower case, or None when the base unit is "
             "BaseUnit.NONE", source="upstream_code",
             ref="src/pymodaq_plugins_smaract/hardware/mcs2/MCS2_wrapper.py:102-111"),
        Fact("get_base_resolution returns the POS_BASE_RESOLUTION property as an integer exponent",
             source="upstream_code",
             ref="src/pymodaq_plugins_smaract/hardware/mcs2/MCS2_wrapper.py:113-122"),
        Fact("get_positionner_type returns the POSITIONER_TYPE_NAME property of the channel",
             source="upstream_code",
             ref="src/pymodaq_plugins_smaract/hardware/mcs2/MCS2_wrapper.py:96-100"),
        Fact("get_number_of_channels returns the controller's NUMBER_OF_CHANNELS; the docstring says it is not "
             "the number of connected positioners", source="upstream_code",
             ref="src/pymodaq_plugins_smaract/hardware/mcs2/MCS2_wrapper.py:83-94"),
        Fact("absolute_move sets MOVE_MODE to CL_ABSOLUTE and calls Move with the value in base units",
             source="upstream_code",
             ref="src/pymodaq_plugins_smaract/hardware/mcs2/MCS2_wrapper.py:162-178"),
        Fact("relative_move sets MOVE_MODE to CL_RELATIVE and calls Move with the value in base units",
             source="upstream_code",
             ref="src/pymodaq_plugins_smaract/hardware/mcs2/MCS2_wrapper.py:180-197"),
        Fact("absolute_move and relative_move abort the movement without notice when a mechanical end stop is "
             "detected", source="upstream_code",
             ref="src/pymodaq_plugins_smaract/hardware/mcs2/MCS2_wrapper.py:163-167"),
        Fact("find_reference starts the reference search in the forward direction and resets the position to zero "
             "if the configuration says so", source="upstream_code",
             ref="src/pymodaq_plugins_smaract/hardware/mcs2/MCS2_wrapper.py:147-160"),
        Fact("stop calls Stop for the channel and also stops the hold position feature of closed-loop commands",
             source="upstream_code",
             ref="src/pymodaq_plugins_smaract/hardware/mcs2/MCS2_wrapper.py:200-208"),
        Fact("The PyMoDAQ plugin converts a controller position to the plugin unit as 10**base_resolution times "
             "the position", source="upstream_code",
             ref="src/pymodaq_plugins_smaract/daq_move_plugins/daq_move_SmarActMCS2.py:60-62"),
        Fact("The PyMoDAQ plugin applies the user-configured bounds with check_bound before an absolute move; the "
             "bound is a PyMoDAQ setting, not a controller limit", source="upstream_code",
             ref="src/pymodaq_plugins_smaract/daq_move_plugins/daq_move_SmarActMCS2.py:135"),
        Fact("The MCS1 plugin's -61500 to 61500 um bounds correspond to one positioner, the SLC-24180",
             source="upstream_code",
             ref="src/pymodaq_plugins_smaract/daq_move_plugins/daq_move_SmarActMCS1.py:24-26"),
        Fact("The MCS1 plugin comments that the minimum and maximum bounds depend on which positioner is plugged",
             source="upstream_code",
             ref="src/pymodaq_plugins_smaract/daq_move_plugins/daq_move_SmarActMCS1.py:63-64"),
    ]
    safe_state = ("no motion is commanded on the bound MCS2 channel (native stop); the positioner is left at its "
                  "current position")
    #: Binding choice, not a device bound: the controller channel this instance drives (backend option
    #: ``channel_index``).  A controller channel is selected when the endpoint is opened; the value is not a
    #: position.
    _channel = 0

    def setup(self):
        self._channel = int(self.options.get("channel_index", 0))

    def teardown(self):
        self.native.close_communication()

    # -- reads ------------------------------------------------------------------------------------------------
    @read("position", type="integer",
          description="Current position of the bound channel in controller base units (multiply by "
                      "10**base_resolution for the value in the unit of 'units')")
    def position(self):
        return self.native.get_position(self._channel)

    @read("units", type=Field("string", nullable=True, description="Base unit of the bound channel, or null when the "
                                                                    "channel reports BaseUnit.NONE"))
    def units(self):
        return self.native.get_units(self._channel)

    @read("base_resolution", type="integer",
          description="Base-resolution exponent of the bound channel: one base unit is 10**base_resolution of the "
                      "unit reported by 'units'")
    def base_resolution(self):
        return self.native.get_base_resolution(self._channel)

    @read("positioner_type", type="string", description="Positioner type name reported by the bound channel")
    def positioner_type(self):
        return self.native.get_positionner_type(self._channel)

    @read("device_name", type="string", description="Name of the MCS2 controller")
    def device_name(self):
        return self.native.get_device_name()

    @read("number_of_channels", type="integer",
          description="Number of channels the controller can handle (not the number of connected positioners)")
    def number_of_channels(self):
        return self.native.get_number_of_channels()

    @read("channel", type="integer", description="Controller channel this driver instance is bound to")
    def channel(self):
        return self._channel

    # -- actions ----------------------------------------------------------------------------------------------
    @action(name="x-cap.pymodaq.smaract_absolute_move.v1",
            description="Move the bound MCS2 channel to an absolute position given in controller base units",
            input={"position": Field(
                "integer", unit="1",
                description="Absolute target in controller base units: the position value this driver reads, "
                            "whose physical value is position times 10**base_resolution of 'units'",
                limit=Limit.operator_required(POSITION_REASON))},
            output={"position": Field("integer", unit="1",
                                      description="Position in base units read back after the move command was "
                                                  "issued (the controller moves asynchronously)"),
                    "target": Field("integer", unit="1", description="Absolute target the command sent")})
    def absolute_move(self, position):
        target = int(position)
        self.native.absolute_move(self._channel, target)
        return {"position": self.native.get_position(self._channel), "target": target}

    @action(name="x-cap.pymodaq.smaract_relative_move.v1",
            description="Move the bound MCS2 channel by a relative offset given in controller base units",
            input={"offset": Field(
                "integer", unit="1",
                description="Relative offset in controller base units (signed); the native move is relative to the "
                            "current closed-loop position",
                limit=Limit.operator_required(POSITION_REASON))},
            output={"position": Field("integer", unit="1",
                                      description="Position in base units read back after the move command was "
                                                  "issued (the controller moves asynchronously)"),
                    "offset": Field("integer", unit="1", description="Relative offset the command sent")})
    def relative_move(self, offset):
        step = int(offset)
        self.native.relative_move(self._channel, step)
        return {"position": self.native.get_position(self._channel), "offset": step}

    @action(name="x-cap.pymodaq.smaract_find_reference.v1",
            description="Start the reference search of the bound MCS2 channel (the native find_reference); the "
                        "search itself is asynchronous",
            output={"started": Field("boolean", description="True once the reference command was issued")})
    def find_reference(self):
        self.native.find_reference(self._channel)
        return {"started": True}

    @action(name="x-cap.pymodaq.smaract_stop.v1",
            description="Stop motion on the bound MCS2 channel (the native stop); the controller applies its "
                        "configured stop profile and the call takes no profile",
            output={"stopped": Field("boolean", description="True once the native stop call returned")})
    def stop_motion(self):
        self.native.stop(self._channel)
        return {"stopped": True}

    # -- safety -----------------------------------------------------------------------------------------------
    @estop(native="stop")
    def stop(self):
        """The native stop: the runtime latches first, then calls Stop on the bound channel."""
        self.native.stop(self._channel)
