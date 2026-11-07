"""OpenMHS driver for gh.angli339/tecan-fluent-api: a Tecan Fluent liquid handler through FluentControl.

A direct Driver over the upstream ``tecan_fluent.tecan_ctrl:Tecan`` class.  The upstream does not speak a text or
byte protocol of its own: it builds an XML ``GenericCommand`` for every operation and sends it to a running
FluentControl instance through the .NET ``Tecan.VisionX.API.V2`` Execution Channel.  A SerialDriver or ScpiDriver
command table cannot express those commands; the card's python-object helper would turn a vendor SDK robot into a
command table, so this is a direct Driver with decorated methods, per-field limits and a safe-state action (the card
named the python-object family).

* reads: the FluentControl run status and whether the API channel is open;
* actions: LiHa aspirate, dispense and mix, MCA aspirate and dispense, and a no-input stop;
* no write parameter: the upstream class exposes no set-point-like state, only script commands;
* the stop path is ``RuntimeController.StopMethod()``; the driver then detaches the API channel so ``run_command``
  refuses further commands (``tecan_fluent/tecan_ctrl.py:41-44``).  The same helper is the safe-state action, because
  no independent hardware e-stop is documented in the clone.

No text file of the clone states a volume range, a tip count or a mix-cycle limit.  Every numeric action input is
therefore ``Limit.operator_required``: the site supplies its ranges in ``site-limits.json`` and until then every
call that sets a field is refused ``MHS.SAFETY.LIMITS_UNSET``.  ``site-limits.example.json`` is an example overlay,
not a statement about a unit.  This package is model-authored and unreviewed; only the fake backend is checked, and
the hardware backend is refused by the loader until a human signs ``reviewed_by`` (R2).
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, reset

#: No text file of the clone states a volume range; the capacity depends on the DiTi mounted on the unit.
_VOLUME_LIMIT = Limit.operator_required(
    "no text file of the clone states a volume range, and the capacity depends on the DiTi mounted on the unit; "
    "the site supplies the range for its tips")
#: No text file of the clone states how many LiHa channels a unit has.
_TIP_LIMIT = Limit.operator_required(
    "no text file of the clone states how many LiHa tips a unit has; the site supplies the valid tip indexes")
#: No text file of the clone states a maximum mix-cycle count.
_CYCLES_LIMIT = Limit.operator_required(
    "no text file of the clone states a maximum mix cycle count; the site supplies it")

_ROWS = "ABCDEFGH"


def _well_index(well: str) -> int:
    """Tecan well number of a 96-well name: ``i_col * 8 + i_row`` (utils.py:23-25, README.md:120-123).

    The upstream LiHa well-selection element hardcodes the 96-well names ``A1`` to ``H12``
    (command_elements_liha.py:43), so a name outside that grid is a precondition failure, not a silently
    truncated index.
    """
    text = str(well).strip().upper()
    if len(text) < 2 or text[0] not in _ROWS or not text[1:].isdigit():
        raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET", f"well {well!r} is not a 96-well name such as A1")
    column = int(text[1:])
    if column < 1 or column > 12:
        raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                           f"well {well!r} is outside the 96-well grid A1-H12 this LiHa command supports")
    return (column - 1) * 8 + _ROWS.index(text[0])


class TecanFluent(Driver):
    device_id = "tecan_fluent"
    device_kind = "lab.liquid_handler"
    mode = "hardware"
    risk = "R2"
    native = "tecan_fluent.tecan_ctrl:Tecan"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeTecan"}
    vendor, model = "Tecan", "Fluent liquid handler"
    display_name = "Tecan Fluent liquid handler through FluentControl (tecan_fluent.tecan_ctrl.Tecan)"
    tags = ["liquid-handler", "pipetting", "tecan", "fluent", "fluentcontrol", "execution-channel"]
    facts = [
        Fact("Tecan is the entry class; its constructor attaches to a running FluentControl and keeps the runtime "
             "controller in self.rt", source="upstream_code", ref="tecan_fluent/tecan_ctrl.py:19-26"),
        Fact("run_command raises when the API channel is not open and otherwise sends the command with "
             "ExecuteCommand", source="upstream_code", ref="tecan_fluent/tecan_ctrl.py:41-44"),
        Fact("liha_aspirate builds Object_LihaAspirateScriptCommandDataV5 from volumes, selected tips, labware, "
             "selected wells and a liquid class", source="upstream_code", ref="tecan_fluent/tecan_ctrl.py:89-103"),
        Fact("liha_dispense builds LihaDispenseScriptCommandDataV4 from the same fields",
             source="upstream_code", ref="tecan_fluent/tecan_ctrl.py:105-117"),
        Fact("liha_mix builds Object_LihaMixScriptCommandDataV4 with n_cycles and the volume list",
             source="upstream_code", ref="tecan_fluent/tecan_ctrl.py:119-133"),
        Fact("mca_aspirate takes a float volume, a labware and a liquid class and builds "
             "Object_Mca384AspirateScriptCommandDataV2", source="upstream_code",
             ref="tecan_fluent/tecan_ctrl.py:158-164"),
        Fact("mca_dispense takes a float volume, a labware and a liquid class and builds "
             "Object_Mca384DispenseScriptCommandDataV2", source="upstream_code",
             ref="tecan_fluent/tecan_ctrl.py:166-172"),
        Fact("The LiHa pipetting command data requires exactly eight volumes and raises ValueError otherwise",
             source="upstream_code", ref="tecan_fluent/command_elements_liha.py:87-88"),
        Fact("The LiHa well-selection element hardcodes the 96-well names from range(1, 12+1) over ABCDEFGH",
             source="upstream_code", ref="tecan_fluent/command_elements_liha.py:43"),
        Fact("A 96-well name maps to a Tecan well number as i_col * 8 + i_row",
             source="upstream_code", ref="tecan_fluent/utils.py:23-25"),
        Fact("The README examples give wellname96_to_tecan_well_no('A1') -> 0 and ('B1') -> 1",
             source="vendor_doc", ref="README.md:120-123"),
        Fact("The RuntimeController provides StopMethod and GetFluentStatus", source="vendor_doc",
             ref="README.md:180-183"),
        Fact("The library targets the Tecan.VisionX.API.V2 .NET library and expects FluentControl under "
             "C:/Program Files (x86)/Tecan/FluentControl", source="vendor_doc", ref="README.md:29-36"),
        Fact("The author used the library on a Tecan Fluent 1080 system", source="vendor_doc", ref="README.md:22"),
        Fact("The MCA path supports only whole-plate pipetting; partial tip mounting with an offset is not "
             "implemented", source="vendor_doc", ref="README.md:147-151"),
    ]
    safe_state = ("the FluentControl method is stopped with RuntimeController.StopMethod() and the API channel is "
                  "detached so run_command refuses further commands")

    # -- reads -----------------------------------------------------------------------------------------------------
    @read("fluent_status", type="string", description="FluentControl run status reported by the runtime controller")
    def fluent_status(self):
        return str(self.native.rt.GetFluentStatus())

    @read("channel_open", type="boolean", description="True while the Execution Channel is attached")
    def channel_open(self):
        return self.native.ch is not None

    # -- LiHa actions ---------------------------------------------------------------------------------------------
    @action(name="x-cap.angli339.liha_aspirate.v1",
            description="Aspirate a volume through one LiHa tip from a 96-well labware well",
            input={
                "volume_ul": Field("number", unit="uL", description="Volume to aspirate",
                                   limit=_VOLUME_LIMIT),
                "tip": Field("integer", unit="1", description="LiHa tip index", limit=_TIP_LIMIT),
                "labware": Field("string", description="Labware label on the Fluent worktable"),
                "well": Field("string", description="96-well name such as A1"),
                "liquid_class": Field("string", description="FluentControl liquid class name"),
            },
            output={"aspirated_volume": Field("number", unit="uL", description="Volume sent to the tip")})
    def liha_aspirate(self, volume_ul, tip, labware, well, liquid_class):
        self.native.liha_aspirate(
            volumes=[volume_ul] * 8,             # the upstream command data requires eight volumes
            i_selected_tips=[tip],
            labware=labware,
            i_selected_wells=[_well_index(well)],
            liquid_class=liquid_class,
        )
        return {"aspirated_volume": volume_ul}

    @action(name="x-cap.angli339.liha_dispense.v1",
            description="Dispense a volume through one LiHa tip into a 96-well labware well",
            input={
                "volume_ul": Field("number", unit="uL", description="Volume to dispense",
                                   limit=_VOLUME_LIMIT),
                "tip": Field("integer", unit="1", description="LiHa tip index", limit=_TIP_LIMIT),
                "labware": Field("string", description="Labware label on the Fluent worktable"),
                "well": Field("string", description="96-well name such as A1"),
                "liquid_class": Field("string", description="FluentControl liquid class name"),
            },
            output={"dispensed_volume": Field("number", unit="uL", description="Volume sent to the tip")})
    def liha_dispense(self, volume_ul, tip, labware, well, liquid_class):
        self.native.liha_dispense(
            volumes=[volume_ul] * 8,             # the upstream command data requires eight volumes
            i_selected_tips=[tip],
            labware=labware,
            i_selected_wells=[_well_index(well)],
            liquid_class=liquid_class,
        )
        return {"dispensed_volume": volume_ul}

    @action(name="x-cap.angli339.liha_mix.v1",
            description="Mix a volume in a 96-well labware well with one LiHa tip",
            input={
                "n_cycles": Field("integer", unit="1", description="Number of mix cycles", limit=_CYCLES_LIMIT),
                "volume_ul": Field("number", unit="uL", description="Volume mixed per cycle", limit=_VOLUME_LIMIT),
                "tip": Field("integer", unit="1", description="LiHa tip index", limit=_TIP_LIMIT),
                "labware": Field("string", description="Labware label on the Fluent worktable"),
                "well": Field("string", description="96-well name such as A1"),
                "liquid_class": Field("string", description="FluentControl liquid class name"),
            },
            output={"cycles": Field("integer", unit="1", description="Number of cycles sent"),
                    "mixed_volume": Field("number", unit="uL", description="Volume sent per cycle")})
    def liha_mix(self, n_cycles, volume_ul, tip, labware, well, liquid_class):
        self.native.liha_mix(
            n_cycles=n_cycles,
            volumes=[volume_ul] * 8,             # the upstream command data requires eight volumes
            i_selected_tips=[tip],
            labware=labware,
            i_selected_wells=[_well_index(well)],
            liquid_class=liquid_class,
        )
        return {"cycles": n_cycles, "mixed_volume": volume_ul}

    # -- MCA actions ----------------------------------------------------------------------------------------------
    @action(name="x-cap.angli339.mca_aspirate.v1",
            description="Aspirate a volume from a whole plate with the MCA head",
            input={
                "volume_ul": Field("number", unit="uL", description="Volume to aspirate",
                                   limit=_VOLUME_LIMIT),
                "labware": Field("string", description="Labware label on the Fluent worktable"),
                "liquid_class": Field("string", description="FluentControl liquid class name"),
            },
            output={"aspirated_volume": Field("number", unit="uL", description="Volume sent to the MCA")})
    def mca_aspirate(self, volume_ul, labware, liquid_class):
        self.native.mca_aspirate(volume=volume_ul, labware=labware, liquid_class=liquid_class)
        return {"aspirated_volume": volume_ul}

    @action(name="x-cap.angli339.mca_dispense.v1",
            description="Dispense a volume into a whole plate with the MCA head",
            input={
                "volume_ul": Field("number", unit="uL", description="Volume to dispense",
                                   limit=_VOLUME_LIMIT),
                "labware": Field("string", description="Labware label on the Fluent worktable"),
                "liquid_class": Field("string", description="FluentControl liquid class name"),
            },
            output={"dispensed_volume": Field("number", unit="uL", description="Volume sent to the MCA")})
    def mca_dispense(self, volume_ul, labware, liquid_class):
        self.native.mca_dispense(volume=volume_ul, labware=labware, liquid_class=liquid_class)
        return {"dispensed_volume": volume_ul}

    # -- safety ----------------------------------------------------------------------------------------------------
    #: The channel the e-stop detached, so an accepted operator reset can re-attach the same object.
    _saved_channel = None

    def _stop_native(self) -> None:
        """Stop the running FluentControl method and detach the channel so no further command can run."""
        if self.native.ch is not None and getattr(self, "_saved_channel", None) is None:
            self._saved_channel = self.native.ch
        self.native.rt.StopMethod()
        self.native.ch = None

    @reset
    def reattach_channel(self):
        """Re-attach the channel the e-stop detached; the upstream object itself has no reset call."""
        channel = getattr(self, "_saved_channel", None)
        if channel is not None:
            self.native.ch = channel
            self._saved_channel = None

    @action(name="x-cap.angli339.stop.v1", safe_state=True,
            description="Stop the FluentControl method and detach the API channel (the safe state); it takes no input",
            output={"stopped": Field("boolean", description="True once the stop and detach were sent")})
    def stop_fluent(self):
        self._stop_native()
        return {"stopped": True}

    @estop(native="rt.StopMethod")
    def stop(self):
        """The native stop: RuntimeController.StopMethod(), then detach the API channel."""
        self._stop_native()
