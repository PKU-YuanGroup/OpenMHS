"""OpenMHS driver for gh.aics-int/microscope_automation: the ZEN blue microscope connection.

A direct Driver (decorated methods) over ``microscope_automation.connectors.connect_zen_blue:ConnectMicroscope``.
The upstream package is an automation layer for Carl Zeiss ZEN blue on Windows; the classes ``Pump``, ``Camera``
and ``Stage`` are descriptions that take a ZEN COM ``communication_object`` on every call, while
``ConnectMicroscope`` is the object that owns the ZEN COM application and performs the device operations.  This
package therefore drives that connector directly instead of the card's ``PythonObjectDriver`` mapping.

The package binds the observational part of the connector: the stage position and objective readout, ZEN live
mode, and a single-image snap.  It deliberately does not expose ``move_stage_to``, ``move_focus_to``,
``switch_objective`` or ``trigger_pump``: the clone states no travel range for the stage or focus axis and no
bound for the syringe pump, and the connector's ``stop()`` only writes a log line (it commands no hardware).  A
driver over those actuators would need an independent stop that the clone does not document.

Safety: ``live_mode_stop`` is the native stop action and is also declared ``safe_state=True``; the ``@estop``
method calls the same native method.  The safe state is therefore "live acquisition stopped"; this package cannot
start a stage, focus or pump movement, so those cannot be left running by this driver.  There is no physical
e-stop citation in the clone and none is claimed.

Every Fact cites a line of the clone at the pinned commit cdac7bdb191ea2d85965574b32ec65e3c2a7e22d.  The package
is model-authored and unreviewed; the hardware backend was never run (README.md and RESULT.json).
"""

from mhs.driver import Driver, Fact, Field, action, estop, read


class ZenMicroscope(Driver):
    device_id = "zen-microscope"
    device_kind = "instrument.microscope"
    mode = "hardware"
    risk = "R1"
    native = "microscope_automation.connectors.connect_zen_blue:ConnectMicroscope"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeConnectMicroscope"}
    vendor, model = "Carl Zeiss", "ZEN blue microscope connection"
    display_name = "Zeiss ZEN blue microscope (microscope_automation ConnectMicroscope)"
    tags = ["microscope", "zeiss", "zen", "imaging", "live-mode", "windows"]
    facts = [
        Fact("ConnectMicroscope(connect_dll=False) loads the connect_zen_blue_dummy module and runs the class "
             "against simulated hardware", source="upstream_code",
             ref="microscope_automation/connectors/connect_zen_blue.py:66-71"),
        Fact("snap_image stores the acquired image in self.image and uses the active experiment when experiment "
             "is None", source="upstream_code",
             ref="microscope_automation/connectors/connect_zen_blue.py:182-190"),
        Fact("live_mode_start starts ZEN live mode and returns the live ZenImage; live_mode_stop stops it",
             source="upstream_code", ref="microscope_automation/connectors/connect_zen_blue.py:382-439"),
        Fact("get_stage_pos returns the stage x and y position in micrometers", source="upstream_code",
             ref="microscope_automation/connectors/connect_zen_blue.py:499-506"),
        Fact("get_objective_name returns the name of the objective in imaging position and get_objective_position "
             "returns its turret position", source="upstream_code",
             ref="microscope_automation/connectors/connect_zen_blue.py:1037-1077"),
        Fact("get_microscope_name returns the fixed string 'get_microscope_name not implemented'",
             source="upstream_code", ref="microscope_automation/connectors/connect_zen_blue.py:1164-1176"),
        Fact("stop() writes only the log line 'Microscope operation aborted' and sends no command",
             source="upstream_code", ref="microscope_automation/connectors/connect_zen_blue.py:1178-1180"),
        Fact("trigger_pump starts the RS232 Braintree pump and sleeps for the requested number of seconds",
             source="upstream_code", ref="microscope_automation/connectors/connect_zen_blue.py:1121-1156"),
        Fact("Braintree.close_connection stops the pump and closes the serial port", source="upstream_code",
             ref="microscope_automation/hardware/RS232.py:56-66"),
    ]
    safe_state = ("live acquisition stopped (ZEN live mode off); this package starts no stage, focus or pump "
                  "movement")
    _live = False

    # -- reads ------------------------------------------------------------------------------------------------
    @read("stage_x", unit="um", description="Current stage x position")
    def stage_x(self):
        return self.native.get_stage_pos()[0]

    @read("stage_y", unit="um", description="Current stage y position")
    def stage_y(self):
        return self.native.get_stage_pos()[1]

    @read("objective_name", type="string", description="Name of the objective in imaging position")
    def objective_name(self):
        return self.native.get_objective_name()

    @read("objective_position", type="integer", description="Position of the active objective in the turret")
    def objective_position(self):
        return self.native.get_objective_position()

    @read("microscope_name", type="string", description="Name reported by the ZEN connector")
    def microscope_name(self):
        return self.native.get_microscope_name()

    @read("live", type="boolean", description="True after this driver started ZEN live mode and until it stops it")
    def live(self):
        return self._live

    # -- actions ----------------------------------------------------------------------------------------------
    @action(name="x-cap.aics-int.live_mode_start.v1",
            description="Start ZEN live mode for an experiment (the active experiment when none is named)",
            input={"experiment": Field("string",
                                       description="ZEN experiment name; omit to use the active experiment")},
            output={"live": Field("boolean", description="True once live mode was started"),
                    "experiment": Field("string",
                                        description="Experiment named in the call, or '' for the active one")})
    def live_mode_start(self, experiment=None):
        self.native.live_mode_start(experiment)
        self._live = True
        return {"live": True, "experiment": experiment or ""}

    @action(name="x-cap.aics-int.live_mode_stop.v1", safe_state=True,
            description="Stop ZEN live mode (the native stop; the safe-state action); it takes no input",
            output={"live": Field("boolean", description="False once live mode is stopped")})
    def live_mode_stop(self):
        self.native.live_mode_stop()
        self._live = False
        return {"live": False}

    @action(name="x-cap.aics-int.snap_image.v1",
            description="Acquire one image from an experiment (the active experiment when none is named)",
            input={"experiment": Field("string",
                                       description="ZEN experiment name; omit to use the active experiment")},
            output={"acquired": Field("boolean", description="True once the connector acquired the image"),
                    "experiment": Field("string",
                                        description="Experiment named in the call, or '' for the active one")})
    def snap_image(self, experiment=None):
        self.native.snap_image(experiment)
        return {"acquired": True, "experiment": experiment or ""}

    # -- safety -----------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: ZEN live mode is stopped (the connector's stop() only logs)."""
        self.native.live_mode_stop()
        self._live = False
