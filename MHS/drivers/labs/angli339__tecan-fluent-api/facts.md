# Facts and tags for gh.angli339/tecan-fluent-api

Every fact cites its source at commit `d087edd9a4cd415961c8337fc82a300bf24fda11`. `upstream_code` is a code or
comment line of the clone; `vendor_doc` is documentation text of the clone (README.md). The same facts are written
into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Tecan is the entry class; its constructor attaches to a running FluentControl and keeps the runtime controller in self.rt | upstream_code | tecan_fluent/tecan_ctrl.py:19-26 |
| run_command raises when the API channel is not open and otherwise sends the command with ExecuteCommand | upstream_code | tecan_fluent/tecan_ctrl.py:41-44 |
| liha_aspirate builds Object_LihaAspirateScriptCommandDataV5 from volumes, selected tips, labware, selected wells and a liquid class | upstream_code | tecan_fluent/tecan_ctrl.py:89-103 |
| liha_dispense builds LihaDispenseScriptCommandDataV4 from the same fields | upstream_code | tecan_fluent/tecan_ctrl.py:105-117 |
| liha_mix builds Object_LihaMixScriptCommandDataV4 with n_cycles and the volume list | upstream_code | tecan_fluent/tecan_ctrl.py:119-133 |
| mca_aspirate takes a float volume, a labware and a liquid class and builds Object_Mca384AspirateScriptCommandDataV2 | upstream_code | tecan_fluent/tecan_ctrl.py:158-164 |
| mca_dispense takes a float volume, a labware and a liquid class and builds Object_Mca384DispenseScriptCommandDataV2 | upstream_code | tecan_fluent/tecan_ctrl.py:166-172 |
| The LiHa pipetting command data requires exactly eight volumes and raises ValueError otherwise | upstream_code | tecan_fluent/command_elements_liha.py:87-88 |
| The LiHa well-selection element hardcodes the 96-well names from range(1, 12+1) over ABCDEFGH | upstream_code | tecan_fluent/command_elements_liha.py:43 |
| A 96-well name maps to a Tecan well number as i_col * 8 + i_row | upstream_code | tecan_fluent/utils.py:23-25 |
| The README examples give wellname96_to_tecan_well_no('A1') -> 0 and ('B1') -> 1 | vendor_doc | README.md:120-123 |
| The RuntimeController provides StopMethod and GetFluentStatus | vendor_doc | README.md:180-183 |
| The library targets the Tecan.VisionX.API.V2 .NET library and expects FluentControl under C:/Program Files (x86)/Tecan/FluentControl | vendor_doc | README.md:29-36 |
| The author used the library on a Tecan Fluent 1080 system | vendor_doc | README.md:22 |
| The MCA path supports only whole-plate pipetting; partial tip mounting with an offset is not implemented | vendor_doc | README.md:147-151 |

Limits: no text file of the clone states a volume range, a LiHa tip count or a maximum mix-cycle count. The volume,
tip and n_cycles inputs are `Limit.operator_required`; every call that sets one is refused
`MHS.SAFETY.LIMITS_UNSET` until the site supplies its range in `site-limits.json`.
`site-limits.example.json` is an example overlay for a deployment, not a bound of any Tecan Fluent unit.

Safety: the `@estop` and the safe-state action `x-cap.angli339.stop.v1` call `RuntimeController.StopMethod()` and
then detach the API channel (`self.ch = None`), after which `run_command` refuses further commands
(tecan_fluent/tecan_ctrl.py:41-44). The clone documents no independent hardware e-stop, so `estop_physical_ref` is
not set; the safe-state action satisfies SAFE-045 for this R2 hardware driver. The e-stop runs on the fake object;
no hardware was attached or run.

Tags: liquid-handler, pipetting, tecan, fluent, fluentcontrol, execution-channel
