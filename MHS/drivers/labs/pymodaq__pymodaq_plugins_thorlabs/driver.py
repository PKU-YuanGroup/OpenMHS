"""OpenMHS driver for gh.pymodaq/pymodaq_plugins_thorlabs: one channel of a Kinesis brushless DC motor controller.

A direct Driver (decorated methods) over the upstream controller class
``pymodaq_plugins_thorlabs.hardware.kinesis:BrushlessDCMotor``.  The upstream wrapper talks to the Thorlabs Kinesis
.NET assemblies through pythonnet (kinesis.py:1-13) and exposes a controller whose axes are the
``BrushlessMotorChannel`` objects created by ``init_channel`` (kinesis.py:230-233).  This package binds one of those
channels (backend option ``channel``, default 1) and calls the controller with the channel index, exactly as the
PyMoDAQ plugin does (daq_move_BrushlessDCMotor.py:58-68, 105-115).

* reads: the channel position and target position in the unit the controller reports, the unit name, whether the
  channel is homed, and the bound channel index;
* actions: an absolute move, a relative move, a home move and the native stop;
* no write: the channel-parameter write of the upstream wrapper, ``BrushlessMotorChannel.set_property``
  (kinesis.py:193-195), sets raw stage-axis numbers with no unit and no range anywhere in the clone, so a
  configuration write would need both an invented unit and an operator-supplied bound; the package does not expose
  it.  The base class also has a ``backlash`` property setter (kinesis.py:87-89); the package does not expose that
  either;
* safety: the native ``stop`` calls ``Stop(0)`` on the bound channel (kinesis.py:260-263, 91-92); it is the e-stop and
  the safe state is no commanded motion on the bound channel.

No text file of the clone states the travel range of the stage attached to the controller: the PyMoDAQ plugin applies
its own user-configured bounds with ``check_bound`` before an absolute move (daq_move_BrushlessDCMotor.py:121-133).
The position and offset inputs therefore carry ``Limit.operator_required``: every move is refused
``MHS.SAFETY.LIMITS_UNSET`` until the operator's site overlay supplies the travel of the installed stage in controller
units.  ``site-limits.example.json`` shows the shape of that overlay with example values only.

Every Fact cites a line of the clone at the pinned commit 4aaf06acf6ea46b93fb900b76701f077dee44e28.  This package is
model-authored and unreviewed; the acceptance gate runs the fake backend only and no hardware was attached.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read

#: The stage and its travel are configuration, not a property of the controller code: the clone's plugin keeps the
#: travel in its own PyMoDAQ settings and checks it before a move (daq_move_BrushlessDCMotor.py:121-133).
TRAVEL_REASON = (
    "no text file of the clone states the travel range of the stage attached to the Kinesis controller: the "
    "PyMoDAQ plugin applies its own user-configured bounds with check_bound before an absolute move "
    "(daq_move_BrushlessDCMotor.py:121-133). The operator supplies the travel of the installed stage in controller "
    "position units, the unit the 'units' read reports")


class ThorlabsBrushlessChannel(Driver):
    device_id = "thorlabs-brushless-channel"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R1"
    native = "pymodaq_plugins_thorlabs.hardware.kinesis:BrushlessDCMotor"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeBrushlessDCMotor"}
    vendor, model = "Thorlabs", "Kinesis Benchtop Brushless Motor controller"
    display_name = "Thorlabs Kinesis brushless DC motor controller channel"
    tags = ["thorlabs", "kinesis", "brushless", "motor", "stage", "motion"]
    facts = [
        Fact("The Kinesis wrapper loads the Thorlabs Kinesis .NET assemblies through pythonnet and appends "
             "'C:\\Program Files\\Thorlabs\\Kinesis' to sys.path", source="upstream_code",
             ref="src/pymodaq_plugins_thorlabs/hardware/kinesis.py:1-13"),
        Fact("The module builds the device list at import and filters the connected serial numbers by device prefix",
             source="upstream_code", ref="src/pymodaq_plugins_thorlabs/hardware/kinesis.py:40-52"),
        Fact("Kinesis.connect connects the device, waits up to 5000 ms for settings initialization and starts "
             "polling every 250 ms", source="upstream_code",
             ref="src/pymodaq_plugins_thorlabs/hardware/kinesis.py:61-64"),
        Fact("Kinesis.close stops polling, disconnects and disposes the device", source="upstream_code",
             ref="src/pymodaq_plugins_thorlabs/hardware/kinesis.py:66-73"),
        Fact("Kinesis.stop calls Stop(0) on the device", source="upstream_code",
             ref="src/pymodaq_plugins_thorlabs/hardware/kinesis.py:91-92"),
        Fact("Kinesis.move_abs converts the position to System.Decimal and calls MoveTo with a callback (or 0); "
             "home calls Home with the same callback handling", source="upstream_code",
             ref="src/pymodaq_plugins_thorlabs/hardware/kinesis.py:97-116"),
        Fact("is_homed, is_moving and is_homing read the IsHomed, IsInMotion and IsHoming flags of the device Status",
             source="upstream_code", ref="src/pymodaq_plugins_thorlabs/hardware/kinesis.py:118-128"),
        Fact("get_target_position returns the device Position converted from System.Decimal to float",
             source="upstream_code", ref="src/pymodaq_plugins_thorlabs/hardware/kinesis.py:133-134"),
        Fact("get_units returns the unit converter's RealUnits, or default_units when reading it fails",
             source="upstream_code", ref="src/pymodaq_plugins_thorlabs/hardware/kinesis.py:136-144"),
        Fact("BrushlessDCMotor.connect accepts a serial number from the controller's device list and init_channel "
             "creates and connects a BrushlessMotorChannel", source="upstream_code",
             ref="src/pymodaq_plugins_thorlabs/hardware/kinesis.py:224-233"),
        Fact("BrushlessDCMotor forwards get_position, move_abs, home, is_homed, stop, get_units and "
             "get_target_position to the channel selected by channel index", source="upstream_code",
             ref="src/pymodaq_plugins_thorlabs/hardware/kinesis.py:235-275"),
        Fact("The PyMoDAQ BrushlessDCMotor plugin reads the position with get_position(axis) and the unit with "
             "get_units(axis)", source="upstream_code",
             ref="src/pymodaq_plugins_thorlabs/daq_move_plugins/daq_move_BrushlessDCMotor.py:58-68"),
        Fact("The PyMoDAQ plugin maps the axis names '1', '2' and '3' to controller channel indices 1, 2 and 3",
             source="upstream_code",
             ref="src/pymodaq_plugins_thorlabs/daq_move_plugins/daq_move_BrushlessDCMotor.py:27-28"),
        Fact("The PyMoDAQ plugin applies its user-configured bounds with check_bound before an absolute move; the "
             "bound is a PyMoDAQ setting, not a controller limit", source="upstream_code",
             ref="src/pymodaq_plugins_thorlabs/daq_move_plugins/daq_move_BrushlessDCMotor.py:121-133"),
        Fact("The PyMoDAQ plugin implements a relative move by adding the offset to the current position and calling "
             "the controller's absolute move", source="upstream_code",
             ref="src/pymodaq_plugins_thorlabs/daq_move_plugins/daq_move_BrushlessDCMotor.py:135-147"),
        Fact("The README describes the BrushlessDCMotor plugin as Kinesis control of a DC brushless motor tested "
             "with the BBD201 controller", source="vendor_doc", ref="README.rst:44"),
        Fact("The package declares pythonnet and pywin32 as dependencies", source="upstream_code",
             ref="pyproject.toml:16-17"),
    ]
    safe_state = ("no motion is commanded on the bound channel after the native Stop(0); the stage is left at the "
                  "position where it stopped")
    #: Binding choice, not a device fact: the controller channel this instance drives (backend option ``channel``).
    _channel = 1

    def setup(self):
        self._channel = int(self.options.get("channel", 1))

    def teardown(self):
        self.native.close()

    # -- reads ------------------------------------------------------------------------------------------------
    @read("position", description="Current position of the bound channel in the unit the 'units' read reports")
    def position(self):
        return float(self.native.get_position(self._channel))

    @read("target_position",
          description="Target position of the bound channel in the unit the 'units' read reports")
    def target_position(self):
        return float(self.native.get_target_position(self._channel))

    @read("units", type="string",
          description="Position unit the controller reports for the bound channel (the wrapper falls back to its "
                      "default unit when the controller has no unit converter)")
    def units(self):
        return self.native.get_units(self._channel)

    @read("homed", type="boolean", description="True when the bound channel reports that it is homed")
    def homed(self):
        return bool(self.native.is_homed(self._channel))

    @read("channel", type="integer", description="Controller channel this driver instance is bound to")
    def channel(self):
        return self._channel

    # -- actions ----------------------------------------------------------------------------------------------
    @action(name="x-cap.pymodaq.thorlabs_move_abs.v1",
            description="Move the bound Kinesis channel to an absolute target with the controller's native MoveTo",
            input={"position": Field(
                "number", unit="1",
                description="Absolute target in the controller position unit the 'units' read reports, not a "
                            "converted physical unit",
                limit=Limit.operator_required(TRAVEL_REASON))},
            output={"target": Field("number", unit="1",
                                    description="Absolute target the native MoveTo was given"),
                    "position": Field("number", unit="1",
                                      description="Position read back right after the move command was issued; the "
                                                  "controller moves asynchronously")})
    def move_abs(self, position):
        target = float(position)
        self.native.move_abs(target, channel=self._channel)
        return {"target": target, "position": float(self.native.get_position(self._channel))}

    @action(name="x-cap.pymodaq.thorlabs_move_rel.v1",
            description="Move the bound Kinesis channel by a relative offset; the target is computed from the "
                        "current position and issued through the native absolute move, as the PyMoDAQ plugin does",
            input={"offset": Field(
                "number", unit="1",
                description="Signed offset in the controller position unit the 'units' read reports, not a converted "
                            "physical unit",
                limit=Limit.operator_required(TRAVEL_REASON))},
            output={"offset": Field("number", unit="1", description="Signed offset the command applied"),
                    "target": Field("number", unit="1",
                                    description="Absolute target computed from the current position plus the offset"),
                    "position": Field("number", unit="1",
                                      description="Position read back right after the move command was issued; the "
                                                  "controller moves asynchronously")})
    def move_rel(self, offset):
        step = float(offset)
        target = float(self.native.get_position(self._channel)) + step
        self.native.move_abs(target, channel=self._channel)
        return {"offset": step, "target": target, "position": float(self.native.get_position(self._channel))}

    @action(name="x-cap.pymodaq.thorlabs_home.v1",
            description="Start the native home move of the bound Kinesis channel; the controller performs the move "
                        "asynchronously",
            output={"started": Field("boolean", description="True once the native home command was issued")})
    def home(self):
        self.native.home(channel=self._channel)
        return {"started": True}

    @action(name="x-cap.pymodaq.thorlabs_stop.v1",
            description="Stop motion of the bound Kinesis channel with the native Stop(0); the call takes no "
                        "deceleration profile",
            output={"stopped": Field("boolean", description="True once the native Stop(0) call returned")})
    def stop_motion(self):
        self.native.stop(self._channel)
        return {"stopped": True}

    # -- safety -----------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: the runtime latches first, then calls Stop(0) on the bound channel."""
        self.native.stop(self._channel)
