"""OpenMHS driver for gh.festo-se/festo-dev-fluid-control: a Festo pressure-over-liquid instrument.

A direct Driver (decorated methods) over the upstream session class
``fluid_control.cli.session:FluidControlSession``.  The session wraps a
Dispenser, Pipettor or Aspirator and exposes the manual-operation interface of
the library; the card's first entry symbol is that session class.  The
underlying engine is ``PressureOverLiquidControl``: the PGVA pressure generator
pressurises the liquid reservoir and the VAEM valve electronics opens a
solenoid valve for a calibrated duration (docs/index.md:9).

* reads: the active valve channel IDs, the configured liquid-class names, the
  fluid-control status code and the current output pressure;
* one write: the output pressure in mbar.  No text file of the clone states the
  pressure range of a configured PGVA, and the upstream pressure validator is a
  no-op TODO (src/fluid_control/fluid_control.py:740-742), so the bound is
  ``Limit.operator_required``: every write is refused ``MHS.SAFETY.LIMITS_UNSET``
  until the site supplies the range of its instrument
  (``site-limits.example.json`` shows the overlay);
* actions: aspirate, dispense and mix on one valve channel with a liquid class,
  and a safe-state action that releases the pressure and deselects the valves.

The native stop path is the session's ``set_pressure(0)``: it issues the
pressure command to the PGVA and waits for the reading (0 mbar is the neutral
value documented at src/fluid_control/cli/session.py:145-146).  The e-stop is
``set_pressure(0)``; the safe-state action also calls the upstream
``PressureOverLiquidControl.__exit__``, which releases the pressure, deselects
every valve and clears the status (src/fluid_control/fluid_control.py:774-780).
The clone documents no independent hardware e-stop, so ``estop_physical_ref``
is absent and this package does not claim one.

Every Fact cites a line of the clone at the pinned commit
(2da14c5d6b202d3aca1ca1ca6e173f68eaf266c3).  This package is model-authored and
unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write

_CHANNEL_LIMIT = Limit.operator_required(
    "the active valve terminals come from the instrument configuration "
    "(src/fluid_control/device_config.py:76-78), not from a fixed channel range; "
    "the site supplies the channel set of its VAEM")
_VOLUME_LIMIT = Limit.operator_required(
    "the calibration maps a volume in uL to a valve opening time, but no text file "
    "of the clone states a volume range for the tips and the reservoir; the site "
    "supplies the volume envelope")
_CYCLES_LIMIT = Limit.operator_required(
    "no text file of the clone states a mix-cycle bound; the cycles stress the "
    "valves and the liquid, so the site supplies the limit")
_PRESSURE_LIMIT = Limit.operator_required(
    "no text file of the clone states the PGVA output-pressure range of a configured "
    "instrument; set_pressure passes the value to the controller and the upstream "
    "pressure validator is a no-op TODO (src/fluid_control/fluid_control.py:740-742), "
    "so the site supplies the range")


class FestoFluidControl(Driver):
    device_id = "festo-fluid-control"
    device_kind = "lab.liquid_handler"
    mode = "hardware"
    risk = "R2"
    native = "fluid_control.cli.session:FluidControlSession"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeFestoDevFluidControl"}
    vendor, model = "Festo", "pressure-over-liquid dispenser/pipettor (PGVA + VAEM)"
    display_name = "Festo pressure-over-liquid instrument (FluidControlSession)"
    tags = ["festo", "pressure-over-liquid", "dispenser", "pipettor", "liquid-handling"]
    facts = [
        Fact("A pressure-over-liquid instrument pressurises a liquid reservoir with the PGVA and opens a "
             "solenoid valve via the VAEM for a calibrated duration; the calibration maps target volume "
             "(uL) to valve opening time (ms)", source="vendor_doc", ref="docs/index.md:9"),
        Fact("The Dispenser class is the fixed-volume, non-aspirating entry point; the Pipettor class extends "
             "it with aspirate, mix and tip-handling operations", source="vendor_doc", ref="docs/index.md:25"),
        Fact("Dispense takes a mapping of channel IDs to {volume in uL, liquid_class} commands and applies the "
             "pressure-over-liquid process to each selected valve channel",
             source="upstream_code", ref="src/fluid_control/capabilities.py:45-71"),
        Fact("Aspirate takes the same channel-command mapping as dispense and runs the aspirate calibration "
             "process", source="upstream_code", ref="src/fluid_control/capabilities.py:77-94"),
        Fact("Mix repeats an aspirate and a dispense on the channel for the requested number of cycles",
             source="upstream_code", ref="src/fluid_control/capabilities.py:100-121"),
        Fact("A transfer aspirates a volume and then dispenses it; both operations take the same "
             "channel-command mapping but use their own calibrated pressure",
             source="vendor_doc", ref="docs/examples/pipettor.md:49-52"),
        Fact("The calibration parameter parameters.pressure is the PGVA output pressure in mbar for one "
             "liquid class and process", source="vendor_doc", ref="docs/configuration/index.md:258"),
        Fact("The active valve channel IDs come from active_valve_terminals and the channel count from "
             "fluid-channel-count in the component configuration",
             source="upstream_code", ref="src/fluid_control/device_config.py:76-78"),
        Fact("The liquid classes are the keys of the live calibration mapping",
             source="upstream_code", ref="src/fluid_control/device_config.py:105-107"),
        Fact("The session returns the active channel IDs, the liquid-class names and the combined "
             "fluid-control, pressure and valve status", source="upstream_code",
             ref="src/fluid_control/cli/session.py:409-438"),
        Fact("set_pressure takes a target pressure in mbar, sends it to the pressure controller and blocks "
             "until the reading stabilises", source="upstream_code",
             ref="src/fluid_control/cli/session.py:239-248"),
        Fact("An output pressure of 0 mbar is the neutral value the manual valve command uses by default",
             source="upstream_code", ref="src/fluid_control/cli/session.py:145-146"),
        Fact("The component context-manager exit sets the pressure to 0, deselects every valve and clears the "
             "fluid-control status", source="upstream_code",
             ref="src/fluid_control/fluid_control.py:774-780"),
        Fact("_wait_output_pressure issues set_output_pressure and then polls get_output_pressure until the "
             "reading is within 1 mbar of the target", source="upstream_code",
             ref="src/fluid_control/fluid_control.py:650-665"),
        Fact("The pressure-readiness and valve-readiness polling loops are bounded by a 30 second timeout",
             source="upstream_code", ref="src/fluid_control/fluid_control.py:31-34"),
        Fact("The engine rejects a negative volume, a channel that is not in the active channel "
             "configuration and a non-positive valve opening time", source="upstream_code",
             ref="src/fluid_control/fluid_control.py:718-738"),
        Fact("The fluid-control status codes are 0 clear, 1 error and 2 busy",
             source="upstream_code", ref="src/fluid_control/fluid_control.py:783-793"),
        Fact("The upstream pressure validator is a no-op TODO, so the library itself does not enforce a "
             "pressure range", source="upstream_code", ref="src/fluid_control/fluid_control.py:740-742"),
    ]
    safe_state = ("output pressure released to 0 mbar (neutral), all valve channels deselected, "
                  "fluid-control status clear")

    # -- reads ---------------------------------------------------------------------------------------------------
    @read("channels", type="array", items=Field("integer", unit="1",
                                                description="Active valve channel ID"),
          description="Active valve channel IDs from the instrument configuration")
    def channels(self):
        return [int(channel) for channel in self.native.get_channels()]

    @read("liquid_classes", type="array", items=Field("string",
                                                      description="Liquid-class key"),
          description="Liquid-class keys present in the live calibration mapping")
    def liquid_classes(self):
        return [str(item) for item in self.native.get_liquid_classes()]

    @read("fluid_status", type="integer", unit="1", enum=[0, 1, 2],
          description="Fluid-control status code: 0 clear, 1 error, 2 busy")
    def fluid_status(self):
        return int(self.native.get_status()["fluid_control_status"])

    @read("pressure", unit="mbar", description="Current PGVA output pressure in mbar")
    def pressure(self):
        return float(self.native.component.pressure_control.get_output_pressure())

    # -- the one write -------------------------------------------------------------------------------------------
    @write("pressure", unit="mbar", description="PGVA output pressure in mbar, applied before the next action",
           limit=_PRESSURE_LIMIT)
    def set_pressure(self, value):
        self.native.set_pressure(pressure_mbar=int(value))
        return int(value)

    # -- actions -------------------------------------------------------------------------------------------------
    @action(name="x-cap.festo-se.aspirate.v1",
            description="Aspirate a volume on one valve channel with a configured liquid class",
            input={
                "channel": Field("integer", unit="1", description="Active valve channel ID",
                                 limit=_CHANNEL_LIMIT),
                "volume": Field("number", unit="uL", description="Volume to aspirate",
                                limit=_VOLUME_LIMIT),
                "liquid_class": Field("string", max_length=64,
                                      description="Liquid-class key from the live calibration mapping"),
            },
            output={
                "aspirated_volume": Field("number", unit="uL", description="Volume passed to the native aspirate"),
                "channel": Field("integer", unit="1", description="Valve channel used"),
            })
    def aspirate(self, channel, volume, liquid_class):
        self.native.aspirate(channel=int(channel), volume_ul=float(volume), liquid_class=str(liquid_class))
        return {"aspirated_volume": float(volume), "channel": int(channel)}

    @action(name="x-cap.festo-se.dispense.v1",
            description="Dispense a volume on one valve channel with a configured liquid class",
            input={
                "channel": Field("integer", unit="1", description="Active valve channel ID",
                                 limit=_CHANNEL_LIMIT),
                "volume": Field("number", unit="uL", description="Volume to dispense",
                                limit=_VOLUME_LIMIT),
                "liquid_class": Field("string", max_length=64,
                                      description="Liquid-class key from the live calibration mapping"),
            },
            output={
                "dispensed_volume": Field("number", unit="uL", description="Volume passed to the native dispense"),
                "channel": Field("integer", unit="1", description="Valve channel used"),
            })
    def dispense(self, channel, volume, liquid_class):
        self.native.dispense(channel=int(channel), volume_ul=float(volume), liquid_class=str(liquid_class))
        return {"dispensed_volume": float(volume), "channel": int(channel)}

    @action(name="x-cap.festo-se.mix.v1",
            description="Mix by repeating aspirate and dispense on one valve channel",
            input={
                "channel": Field("integer", unit="1", description="Active valve channel ID",
                                 limit=_CHANNEL_LIMIT),
                "volume": Field("number", unit="uL", description="Volume per aspirate and dispense",
                                limit=_VOLUME_LIMIT),
                "liquid_class": Field("string", max_length=64,
                                      description="Liquid-class key from the live calibration mapping"),
                "cycles": Field("integer", unit="1", description="Number of aspirate/dispense cycles",
                                limit=_CYCLES_LIMIT),
            },
            output={
                "cycles": Field("integer", unit="1", description="Cycles passed to the native mix"),
                "volume": Field("number", unit="uL", description="Volume per cycle passed to the native mix"),
            })
    def mix(self, channel, volume, liquid_class, cycles):
        self.native.mix(channel=int(channel), volume_ul=float(volume), liquid_class=str(liquid_class),
                        cycles=int(cycles))
        return {"cycles": int(cycles), "volume": float(volume)}

    @action(name="x-cap.festo-se.deactivate.v1", safe_state=True,
            description="Return the instrument to its safe state: release the pressure and deselect every valve",
            output={
                "pressure": Field("number", unit="mbar",
                                  description="Output pressure after the native safe-state exit"),
            })
    def deactivate(self):
        self.native.set_pressure(pressure_mbar=0)
        self.native.component.__exit__(None, None, None)
        return {"pressure": float(self.native.component.pressure_control.get_output_pressure())}

    # -- safety --------------------------------------------------------------------------------------------------
    @estop(native="set_pressure")
    def emergency_stop(self):
        """The native stop: the runtime latches first, then sends output pressure 0 mbar."""
        self.native.set_pressure(pressure_mbar=0)
