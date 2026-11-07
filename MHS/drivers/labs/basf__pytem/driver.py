"""OpenMHS driver for gh.basf/pytem: the BASF in-house scripting interface of a Thermo Fisher TEM.

A direct Driver (decorated methods) over the upstream class pyTEM.Interface:Interface.  The class is a thin Python
wrapper over the Thermo Fisher TEMScripting COM objects: it has no transport of its own and its constructor takes no
options (pyTEM/Interface.py:77-98), so the hardware backend is a factory that only constructs it (native.py).

* reads: the five stage position axes, the stage home test, the beam blanker, the fluorescent screen, the column
  valve, the column and accelerator vacuum, and the instrument, projection and illumination modes;
* writes: the five stage axes.  The clone states a bound for each axis in StageMixin.set_stage_position, so every
  write has a sourced limit;
* actions: reset the stage to x=y=z=alpha=beta=0 and enter the native safe state (column valve closed, beam blanked,
  fluorescent screen inserted);
* safety: the @estop method is the native Interface.make_safe, and the safe-state action calls it too.

Every Fact cites a line of the clone at the pinned commit d2b2800329524c205c266fe72a35c7fd477cc735.  This package is
model-authored and unreviewed: it is checked on the fake backend only, and its hardware backend is refused by the
loader while reviewed_by is null (R3).
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write


class PytemInterface(Driver):
    device_id = "pytem"
    device_kind = "instrument.microscope"
    mode = "hardware"
    risk = "R3"
    native = "pyTEM.Interface:Interface"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeInterface"}
    vendor, model = "BASF SE", "Talos F200i TEM"
    display_name = "BASF pyTEM TEM interface (pyTEM.Interface.Interface)"
    tags = ["tem", "electron-microscope", "stage", "vacuum", "beam-blanker"]
    facts = [
        Fact("The stage position is kept in micrometres for x, y and z and in degrees for alpha and beta",
             source="upstream_code", ref="pyTEM/Interface.py:87-91"),
        Fact("A stage x move is refused when the absolute x value exceeds 1000 um",
             source="upstream_code", ref="pyTEM/lib/mixins/StageMixin.py:141-145"),
        Fact("A stage y move is refused when the absolute y value exceeds 1000 um",
             source="upstream_code", ref="pyTEM/lib/mixins/StageMixin.py:155-159"),
        Fact("A stage z move is refused when the absolute z value exceeds 375 um",
             source="upstream_code", ref="pyTEM/lib/mixins/StageMixin.py:169-173"),
        Fact("A stage alpha tilt is refused when the absolute alpha value exceeds 80 degrees",
             source="upstream_code", ref="pyTEM/lib/mixins/StageMixin.py:183-187"),
        Fact("A stage beta tilt is refused when the absolute beta value exceeds 29.7 degrees",
             source="upstream_code", ref="pyTEM/lib/mixins/StageMixin.py:203-207"),
        Fact("The stage speed is a fraction of the standard speed, clamped to 0.00032 at the low end and 1.0 at the "
             "high end", source="upstream_code", ref="pyTEM/lib/mixins/StageMixin.py:85-93"),
        Fact("reset_stage_position sets x, y, z, alpha and beta to zero",
             source="upstream_code", ref="pyTEM/lib/mixins/StageMixin.py:396-402"),
        Fact("stage_is_home compares every axis against the home position with a default threshold of 0.1",
             source="upstream_code", ref="pyTEM/lib/mixins/StageMixin.py:404-418"),
        Fact("make_safe closes the column valve, blanks the beam and inserts the fluorescent screen",
             source="upstream_code", ref="pyTEM/Interface.py:107-114"),
        Fact("get_column_vacuum and get_accelerator_vacuum return a log value or a pressure in pascals",
             source="upstream_code", ref="pyTEM/lib/mixins/VacuumMixin.py:61-97"),
        Fact("The column valve position is 'open' or 'closed'",
             source="upstream_code", ref="pyTEM/lib/mixins/VacuumMixin.py:117-126"),
        Fact("The fluorescent screen position is 'retracted' or 'inserted'",
             source="upstream_code", ref="pyTEM/lib/mixins/ScreenMixin.py:21-34"),
        Fact("beam_is_blank reports whether the beam is blanked",
             source="upstream_code", ref="pyTEM/lib/mixins/BeamBlankerMixin.py:20-27"),
        Fact("The instrument mode is TEM or STEM", source="upstream_code",
             ref="pyTEM/lib/mixins/ModeMixin.py:23-37"),
        Fact("The projection mode is imaging or diffraction", source="upstream_code",
             ref="pyTEM/lib/mixins/ModeMixin.py:64-76"),
        Fact("The illumination mode is nanoprobe or microprobe", source="upstream_code",
             ref="pyTEM/lib/mixins/ModeMixin.py:139-153"),
    ]
    safe_state = ("column valve closed, beam blanked and fluorescent screen inserted "
                  "(the native Interface.make_safe)")

    # -- stage reads ------------------------------------------------------------------------------------------------
    @read("stage_x", unit="um", description="Stage position along the x-axis")
    def stage_x(self):
        return self.native.get_stage_position_x()

    @read("stage_y", unit="um", description="Stage position along the y-axis")
    def stage_y(self):
        return self.native.get_stage_position_y()

    @read("stage_z", unit="um", description="Stage position along the z-axis")
    def stage_z(self):
        return self.native.get_stage_position_z()

    @read("stage_alpha", unit="deg", description="Stage tilt along alpha")
    def stage_alpha(self):
        return self.native.get_stage_position_alpha()

    @read("stage_beta", unit="deg", description="Stage tilt along beta")
    def stage_beta(self):
        return self.native.get_stage_position_beta()

    @read("stage_home", type="boolean",
          description="True when the stage is at x=y=z=alpha=beta=0 within the native home threshold")
    def stage_home(self):
        return bool(self.native.stage_is_home())

    # -- instrument reads ---------------------------------------------------------------------------------------------
    @read("beam_blanked", type="boolean", description="True while the electron beam is blanked")
    def beam_blanked(self):
        return bool(self.native.beam_is_blank())

    @read("screen_position", type="string",
          description="Fluorescent screen position: 'retracted' or 'inserted'")
    def screen_position(self):
        return self.native.get_screen_position()

    @read("column_valve_position", type="string", description="Column valve position: 'open' or 'closed'")
    def column_valve_position(self):
        return self.native.get_column_valve_position()

    @read("column_vacuum", unit="Pa", description="Pressure of the column vacuum gauge")
    def column_vacuum(self):
        return float(self.native.get_column_vacuum(units="Pascal"))

    @read("accelerator_vacuum", unit="Pa", description="Pressure of the accelerator vacuum gauge")
    def accelerator_vacuum(self):
        return float(self.native.get_accelerator_vacuum(units="Pascal"))

    @read("mode", type="string", description="Instrument mode: TEM or STEM")
    def instrument_mode(self):
        return self.native.get_mode()

    @read("projection_mode", type="string", description="Projection mode: imaging or diffraction")
    def projection_mode(self):
        return self.native.get_projection_mode()

    @read("illumination_mode", type="string", description="Illumination mode: nanoprobe or microprobe")
    def illumination_mode(self):
        return self.native.get_illumination_mode()

    # -- stage writes -------------------------------------------------------------------------------------------------
    @write("stage_x", unit="um", description="Move the stage along x, in micrometres",
           limit=Limit(min=-1000, max=1000, source="upstream_code",
                       ref="pyTEM/lib/mixins/StageMixin.py:141"))
    def set_stage_x(self, value):
        self.native.set_stage_position_x(value)

    @write("stage_y", unit="um", description="Move the stage along y, in micrometres",
           limit=Limit(min=-1000, max=1000, source="upstream_code",
                       ref="pyTEM/lib/mixins/StageMixin.py:155"))
    def set_stage_y(self, value):
        self.native.set_stage_position_y(value)

    @write("stage_z", unit="um", description="Move the stage along z, in micrometres",
           limit=Limit(min=-375, max=375, source="upstream_code",
                       ref="pyTEM/lib/mixins/StageMixin.py:170"))
    def set_stage_z(self, value):
        self.native.set_stage_position_z(value)

    @write("stage_alpha", unit="deg", description="Tilt the stage along alpha, in degrees",
           limit=Limit(min=-80, max=80, source="upstream_code",
                       ref="pyTEM/lib/mixins/StageMixin.py:184"))
    def set_stage_alpha(self, value):
        self.native.set_stage_position_alpha(value)

    @write("stage_beta", unit="deg", description="Tilt the stage along beta, in degrees",
           limit=Limit(min=-29.7, max=29.7, source="upstream_code",
                       ref="pyTEM/lib/mixins/StageMixin.py:204"))
    def set_stage_beta(self, value):
        self.native.set_stage_position_beta(value)

    # -- actions ------------------------------------------------------------------------------------------------------
    @action(name="x-cap.basf.reset_stage_position.v1",
            description="Reset the stage to x=y=z=alpha=beta=0 (the native reset_stage_position)",
            output={"home": Field("boolean",
                                  description="True when the stage reports the home position after the reset")})
    def reset_stage_position(self):
        self.native.reset_stage_position()
        return {"home": bool(self.native.stage_is_home())}

    @action(name="x-cap.basf.enter_safe_state.v1", safe_state=True,
            description="Enter the native safe state: close the column valve, blank the beam and insert the screen",
            output={"applied": Field("boolean",
                                     description="True when the native Interface.make_safe routine returned")})
    def enter_safe_state(self):
        self.native.make_safe()
        return {"applied": True}

    # -- safety -------------------------------------------------------------------------------------------------------
    @estop
    def make_safe(self):
        """The native safe state: close the column valve, blank the beam and insert the screen."""
        self.native.make_safe()
