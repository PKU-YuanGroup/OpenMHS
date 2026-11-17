"""OpenMHS driver for gh.kyleellefsen/light_sheet_controller: a two-board NI USB-6001 DAQ.

A direct Driver over the upstream Qt/DAQ class ``light_sheet_controller:LightSheetDriver``
(labs/kyleellefsen/light_sheet_controller/light_sheet_controller.py:118).  The class generates four analog
outputs on two USB-6001 boards: Dev1/ao0 is the piezo scan, Dev1/ao1 the camera TTL, Dev2/ao0 the dither and
Dev2/ao1 the laser TTL (light_sheet_controller.py:135-142).  The driver:

* reads the controller's own state and settings (start/stop, laser selection, sample rate and the waveform
  parameters) through attributes the upstream class exposes;
* writes the waveform settings; the clone states no safe range for the installed piezo, objective or sample,
  so every numeric write is ``Limit.operator_required`` and is refused ``MHS.SAFETY.LIMITS_UNSET`` until the
  operator's site overlay supplies a range (``site-limits.example.json`` is an example only);
* starts and stops the continuous scan, drives the piezo to zero or to the configured end, and selects the
  blue or yellow laser through the upstream methods ``startstop``, ``gotozero``, ``gotoend``,
  ``gotobluelaser`` and ``gotoyellowlaser``;
* exposes ``x-cap.kyleellefsen.stop_scan.v1`` as an ordinary zeroing request.  It clears the two settings
  that make ``calc_ttl`` write a non-zero laser TTL, then calls ``gotozero``: both analog-output tasks are
  stopped and finite zero waveforms are written to the piezo, camera and dither channels.  The upstream has
  no readback of the actual output voltage or of laser emission, so the stop is an actuation, not a sensed
  quiescence. A zero TTL is also used by the yellow-laser selector; the clone supplies no laser-off path.
  The e-stop therefore reports SAFE_STATE_UNREACHED and keeps the latch held. This package is blocked.

Every Fact cites a line of the clone at the pinned commit 69ce700174c9498f7ad27925b751ed47e45ce3b3.  This
package is model-authored and unreviewed: it is checked on the fake backend only, and the loader refuses its
R2 hardware backend until a human sets ``reviewed_by`` in driver.lock.json.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write


class LightSheetController(Driver):
    device_id = "light-sheet-controller"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R2"
    native = "light_sheet_controller:LightSheetDriver"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeLightSheetController"}
    vendor, model = "Kyle Ellefsen", "NI USB-6001 light sheet controller"
    display_name = "Light sheet controller (NI USB-6001 piezo, camera and laser TTL)"
    tags = ["light-sheet", "piezo", "ni-daqmx", "usb-6001", "laser-ttl", "waveform"]
    facts = [
        Fact("The controller expects two NI USB-6001 boards as Dev1 and Dev2 and warns that it continues in "
             "test mode when either board is absent or is another product type",
             source="upstream_code", ref="light_sheet_controller.py:46-57"),
        Fact("createTask builds two analog-output tasks: Dev1/ao0 is the piezo channel, Dev1/ao1 the camera "
             "TTL, Dev2/ao0 the dither and Dev2/ao1 the laser TTL, each configured from -10.0 to 10.0 V",
             source="upstream_code", ref="light_sheet_controller.py:133-144"),
        Fact("createTask starts both analog-output tasks and sets stopped to False",
             source="upstream_code", ref="light_sheet_controller.py:145-148"),
        Fact("startstop from the stopped state recalculates and restarts both tasks; from the running state it "
             "stops both tasks, returns the dither to zero and sets stopped to True",
             source="upstream_code", ref="light_sheet_controller.py:159-173"),
        Fact("refresh recalculates the waveform, stops both tasks, configures continuous sampling and "
             "restarts both tasks while the controller is not stopped",
             source="upstream_code", ref="light_sheet_controller.py:175-188"),
        Fact("gotozero writes a finite zero waveform to the piezo and camera TTL channels, sleeps 0.2 s, stops "
             "the task, returns the dither to zero and sets stopped to True",
             source="upstream_code", ref="light_sheet_controller.py:204-218"),
        Fact("gotoend drives the piezo to maximum_displacement * mV_per_pixel / 1000 V, sleeps 0.2 s, stops "
             "the task, returns the dither to zero and sets stopped to True",
             source="upstream_code", ref="light_sheet_controller.py:220-235"),
        Fact("gotobluelaser sets the blue_laser_on setting to True and gotoyellowlaser sets it to False",
             source="upstream_code", ref="light_sheet_controller.py:237-265"),
        Fact("calc_ttl writes 6 V on the laser TTL when alternate_lasers is set (in one segment) or when "
             "blue_laser_on is true (the whole array), and zeros otherwise",
             source="upstream_code", ref="calc_waveforms.py:140-150"),
        Fact("The generated piezo waveform is clamped to -10.0 to 10.0 V and the code asserts the clamp",
             source="upstream_code", ref="calc_waveforms.py:80-87"),
        Fact("The settings are mV_per_pixel in mV/pixel, maximum_displacement and offset in pixels, nSteps "
             "as a count, step_duration and flyback_duration in ms, total_cycle_period in s and dither_amp "
             "in mV", source="upstream_code", ref="light_sheet_controller.py:388-395"),
        Fact("start_light_sheet_controller builds a Qt application, checks the NI devices and constructs MainGui",
             source="upstream_code", ref="light_sheet_controller.py:539-544"),
        Fact("calc_waveforms imports numpy, scipy.ndimage and QtWidgets from qtpy",
             source="upstream_code", ref="calc_waveforms.py:1-3"),
        Fact("The controller module imports numpy, PyDAQmx, qtpy and pyqtgraph",
             source="upstream_code", ref="light_sheet_controller.py:15-29"),
        Fact("calcPiezoWaveform applies scipy.ndimage.filters.gaussian_filter1d with sigma 3",
             source="upstream_code", ref="calc_waveforms.py:75-76"),
        Fact("Settings loads ~/.lightsheet/config.p with pickle and uses defaults only after an IOError",
             source="upstream_code", ref="light_sheet_controller.py:73-92"),
        Fact("dither_gotozero computes calc_ttl, stops task two, writes with timeout -1, briefly starts it "
             "and stops it again", source="upstream_code", ref="light_sheet_controller.py:190-202"),
    ]
    safe_state = (
        "unconfirmed: gotozero requests zero piezo, camera, dither and laser-TTL values after clearing both "
        "laser flags; zero TTL also selects the yellow laser, and no laser-off state or emission readback "
        "is shown; the e-stop fails with the latch held"
    )

    # -- reads ------------------------------------------------------------------------------------------------
    @read("stopped", type="boolean", description="Cached controller stop flag; no physical-output confirmation")
    def stopped(self):
        return bool(self.native.stopped)

    @read("blue_laser_on", type="boolean",
          description="True when the blue laser selection is active (the yellow selection is the alternative)")
    def blue_laser_on(self):
        return bool(self.native.settings["blue_laser_on"])

    @read("alternate_lasers", type="boolean",
          description="True when the TTL waveform alternates the two lasers during a scan")
    def alternate_lasers(self):
        return bool(self.native.settings["alternate_lasers"])

    @read("triangle_scan", type="boolean",
          description="True when the piezo scan is a triangle instead of a stepped ramp")
    def triangle_scan(self):
        return bool(self.native.settings["triangle_scan"])

    @read("sample_rate", unit="Hz",
          description="Analog-output sample clock rate the tasks are configured with")
    def sample_rate(self):
        return float(self.native.sample_rate)

    @read("samples_per_period", type="integer", unit="1",
          description="Samples per channel in the current waveform")
    def samples_per_period(self):
        return int(self.native.sampsPerPeriod)

    @read("n_steps", type="integer", unit="1", description="Number of steps per scan cycle")
    def n_steps(self):
        return int(self.native.settings["nSteps"])

    @read("step_duration", unit="ms", description="Duration of one scan step")
    def step_duration(self):
        return float(self.native.settings["step_duration"])

    @read("flyback_duration", unit="ms", description="Duration of the flyback that returns the piezo")
    def flyback_duration(self):
        return float(self.native.settings["flyback_duration"])

    @read("total_cycle_period", unit="s", description="Requested duration of one scan cycle")
    def total_cycle_period(self):
        return float(self.native.settings["total_cycle_period"])

    @read("dither_amp", unit="mV", description="Peak amplitude of the dither waveform")
    def dither_amp(self):
        return float(self.native.settings["dither_amp"])

    @read("offset", unit="{pixel}", description="Static displacement offset of the piezo waveform")
    def offset(self):
        return float(self.native.settings["offset"])

    @read("maximum_displacement", unit="{pixel}",
          description="Maximum piezo displacement of a scan cycle")
    def maximum_displacement(self):
        return float(self.native.settings["maximum_displacement"])

    @read("mv_per_pixel", unit="mV/{pixel}",
          description="Piezo drive in mV per pixel of displacement")
    def mv_per_pixel(self):
        return float(self.native.settings["mV_per_pixel"])

    # -- settings writes --------------------------------------------------------------------------------------
    # The clone's GUI sliders bound these controls (light_sheet_controller.py:376-383), but a slider range is
    # not a statement that the range is safe for a given piezo, objective or sample; the operator supplies
    # the ranges of the installed instrument in site-limits.json.

    def _recalculate(self):
        """Apply a changed setting: recalculate when stopped, refresh the running waveform otherwise."""
        if self.native.stopped:
            self.native.calculate()
        else:
            self.native.refresh()

    @write("n_steps", type="integer", unit="1", description="Steps per cycle",
           limit=Limit.operator_required("site sets the installed piezo range"))
    def set_n_steps(self, value):
        self.native.settings["nSteps"] = int(value)
        self._recalculate()

    @write("step_duration", unit="ms", description="Step duration",
           limit=Limit.operator_required("site sets the safe step duration"))
    def set_step_duration(self, value):
        self.native.settings["step_duration"] = float(value)
        self._recalculate()

    @write("flyback_duration", unit="ms", description="Flyback duration",
           limit=Limit.operator_required("site sets the safe flyback duration"))
    def set_flyback_duration(self, value):
        self.native.settings["flyback_duration"] = float(value)
        self._recalculate()

    @write("total_cycle_period", unit="s", description="Cycle period",
           limit=Limit.operator_required("site sets the safe cycle period"))
    def set_total_cycle_period(self, value):
        self.native.settings["total_cycle_period"] = float(value)
        self._recalculate()

    @write("dither_amp", unit="mV", description="Dither amplitude",
           limit=Limit.operator_required("site sets the safe dither amplitude"))
    def set_dither_amp(self, value):
        self.native.settings["dither_amp"] = float(value)
        self._recalculate()

    @write("offset", unit="{pixel}", description="Displacement offset",
           limit=Limit.operator_required("site sets the safe offset"))
    def set_offset(self, value):
        self.native.settings["offset"] = float(value)
        self._recalculate()

    @write("maximum_displacement", unit="{pixel}", description="Maximum displacement",
           limit=Limit.operator_required("site sets the installed piezo range"))
    def set_maximum_displacement(self, value):
        self.native.settings["maximum_displacement"] = float(value)
        self._recalculate()

    @write("mv_per_pixel", unit="mV/{pixel}", description="Drive per pixel",
           limit=Limit.operator_required("site sets the installed piezo scale"))
    def set_mv_per_pixel(self, value):
        self.native.settings["mV_per_pixel"] = float(value)
        self._recalculate()

    # -- actions ----------------------------------------------------------------------------------------------
    @action(name="x-cap.kyleellefsen.set_scan_mode.v1",
            description="Set the triangle-scan and alternate-lasers settings and recalculate the waveform",
            input={"triangle_scan": Field("boolean", description="Use a triangle scan"),
                   "alternate_lasers": Field("boolean", description="Alternate the two lasers")},
            output={"triangle_scan": Field("boolean", description="Triangle scan flag"),
                    "alternate_lasers": Field("boolean", description="Alternate-lasers flag")})
    def set_scan_mode(self, triangle_scan, alternate_lasers):
        self.native.settings["triangle_scan"] = bool(triangle_scan)
        self.native.settings["alternate_lasers"] = bool(alternate_lasers)
        self._recalculate()
        return {"triangle_scan": bool(self.native.settings["triangle_scan"]),
                "alternate_lasers": bool(self.native.settings["alternate_lasers"])}

    @action(name="x-cap.kyleellefsen.start_scan.v1",
            description="Start the continuous piezo scan and TTL waveform from the stopped state (native startstop)",
            output={"running": Field("boolean",
                                     description="True when the analog-output tasks are running")})
    def start_scan(self):
        if self.native.stopped:
            self.native.startstop()
        return {"running": not bool(self.native.stopped)}

    @action(name="x-cap.kyleellefsen.goto_zero.v1",
            description="Drive the piezo to zero, stop the waveform and return the dither to zero (native gotozero)",
            output={"stopped": Field("boolean",
                                     description="True once the analog-output tasks are stopped")})
    def goto_zero(self):
        self.native.gotozero()
        return {"stopped": bool(self.native.stopped)}

    @action(name="x-cap.kyleellefsen.goto_end.v1",
            description="Drive the piezo to the configured maximum displacement and stop (native gotoend)",
            output={"stopped": Field("boolean",
                                     description="True once the analog-output tasks are stopped")})
    def goto_end(self):
        self.native.gotoend()
        return {"stopped": bool(self.native.stopped)}

    @action(name="x-cap.kyleellefsen.select_laser.v1",
            description="Select the blue or the yellow laser with the upstream gotobluelaser or gotoyellowlaser",
            input={"laser": Field("string", enum=["blue", "yellow"],
                                  description="Laser selection applied by the native method")},
            output={"blue_laser_on": Field("boolean",
                                           description="True when the blue laser selection is active")})
    def select_laser(self, laser):
        if laser == "blue":
            self.native.gotobluelaser()
        else:
            self.native.gotoyellowlaser()
        return {"blue_laser_on": bool(self.native.settings["blue_laser_on"])}

    @action(name="x-cap.kyleellefsen.stop_scan.v1",
            description="Clear both laser-selection settings, then stop the tasks and drive the piezo, camera "
                        "and dither to zero; zero laser TTL does not establish laser-off; it takes no input",
            output={"stopped": Field("boolean",
                                     description="True once the analog-output tasks are stopped"),
                    "blue_laser_on": Field("boolean",
                                           description="False once the blue laser selection is cleared")})
    def stop_scan(self):
        self.native.settings["alternate_lasers"] = False
        self.native.settings["blue_laser_on"] = False
        self.native.gotozero()
        return {"stopped": bool(self.native.stopped),
                "blue_laser_on": bool(self.native.settings["blue_laser_on"])}

    # -- safety -----------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """Request zero outputs without certifying an unsupported laser-off state."""
        self.native.settings["alternate_lasers"] = False
        self.native.settings["blue_laser_on"] = False
        self.native.gotozero()
        raise DriverFailed("MHS.SAFETY.SAFE_STATE_UNREACHED",
                           "zero laser TTL also selects the yellow laser; the source shows no laser-off stop")
