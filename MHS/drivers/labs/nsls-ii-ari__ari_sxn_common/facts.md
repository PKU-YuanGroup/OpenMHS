# Facts and tags for gh.nsls-ii-ari/ari_sxn_common

Every fact cites the clone at commit `13892fc39dd2605a8641d76649e7b13c434d9183`.  `upstream_code` is a code or
comment line of the clone; `vendor_doc` is documentation text.  The `ref` is the path from the clone root, which
keeps its `src/` layout.

| fact | source | ref |
|---|---|---|
| M1 is the ophyd Device for the ARI M1 mirror section and extends DeviceWithLocations | upstream_code | src/ari_sxn_common/ari_ophyd.py:38 |
| M1 declares the five mirror motor Components Ry_coarse, Ry_fine, Rz, x and y as ID29EpicsMotor | upstream_code | src/ari_sxn_common/ari_ophyd.py:97-106 |
| M1 declares vacuum as _VacuumDevices, slits as BaffleSlit and diag as Diagnostic | upstream_code | src/ari_sxn_common/ari_ophyd.py:108-140 |
| M1.trigger calls the parent trigger, the slits trigger and the diag trigger, and returns their combined status | upstream_code | src/ari_sxn_common/ari_ophyd.py:142-155 |
| ID29EpicsMotor is a subclass of ophyd EpicsMotor | upstream_code | src/ari_sxn_common/common_ophyd.py:116 |
| ID29EpicsMotor.__init__ sets the kind of user_setpoint and of user_readback | upstream_code | src/ari_sxn_common/common_ophyd.py:146-147 |
| ID29EpicsSignalRO is a subclass of ophyd EpicsSignalRO | upstream_code | src/ari_sxn_common/common_ophyd.py:154 |
| _AriSxnC declares ccg, tcg and ip as ID29EpicsSignalRO and gv as ID29TwoButtonShutter | upstream_code | src/ari_sxn_common/ari_ophyd.py:16-23 |
| BaffleSlit declares top, bottom, inboard and outboard as ID29EpicsMotor and currents as ID29EM | upstream_code | src/ari_sxn_common/common_ophyd.py:751-761 |
| Diagnostic declares blade and filter as ID29EpicsMotor, camera as Prosilica and currents as ID29EM | upstream_code | src/ari_sxn_common/common_ophyd.py:661-671 |
| DeviceWithLocations declares locations as a Component of its own LocationSignal | upstream_code | src/ari_sxn_common/common_ophyd.py:590-591 |
| LocationSignal.get evaluates the parent's configured locations and puts the matching flags at read time | upstream_code | src/ari_sxn_common/common_ophyd.py:509-516 |
| BaffleSlit aliases the mean_value of currents.current1 through current4 as top, bottom, inboard and outboard | upstream_code | src/ari_sxn_common/common_ophyd.py:734-746 |
| Diagnostic exposes currents.current1 through current4 and their mean_value members | upstream_code | src/ari_sxn_common/common_ophyd.py:647-659 |
| M1.__init__ renames diag.currents.current1.mean_value to <name>_photocurrent, hints it and exposes it as the photocurrent attribute | upstream_code | src/ari_sxn_common/ari_ophyd.py:86-94 |
| ID29EM derives from NSLS_EM, imported from ophyd.quadem | upstream_code | src/ari_sxn_common/common_ophyd.py:180 |
| Prosilica combines SingleTrigger, imported from ophyd.areadetector.trigger_mixins, with ProsilicaDetector | upstream_code | src/ari_sxn_common/common_ophyd.py:245 |
| ID29EM.__init__ puts 'EM180' into the nd_array_port of current1 to current4 while it is constructed | upstream_code | src/ari_sxn_common/common_ophyd.py:212-224 |
| Diagnostic.trigger reads the camera array counter, then triggers the camera, the currents and the parent and combines their statuses | upstream_code | src/ari_sxn_common/common_ophyd.py:673-688 |
| BaffleSlit.trigger triggers the currents and the parent and combines their statuses | upstream_code | src/ari_sxn_common/common_ophyd.py:763-771 |

Tags: `ophyd`, `bluesky`, `epics`, `nsls-ii`, `ari`, `mirror`, `baffle-slit`, `diagnostic`, `read-only`.

## Scope and provenance notes

The card proposes the config-only `OphydDriver` helper.  The source proof accepts only direct
`Component(EpicsSignal | EpicsSignalRO | Signal, "literal")` declarations on the selected class, while every
served `M1` member is a nested `BaffleSlit`, `Diagnostic`, `_VacuumDevices` or `ID29EpicsMotor` custom Device.
The package is a direct `Driver` over the confirmed `M1` entry symbol; `RESULT.json` records the deviation.

The package is read only.  It publishes the motor readbacks, the baffle-slit and diagnostic blade readbacks, the
current means, the vacuum gauge signals, the parent location flags, and one observational extension action,
`x-cap.nsls-ii-ari.m1_photocurrent.v1`, a fresh read of `diag.currents.current1.mean_value` (the signal `M1.__init__`
exposes as `photocurrent`).  It does not expose a trigger, a motor or slit setpoint, `LocationSignal.set`, `Diagnostic.camera`, or the
`gv` shutter.  The clone states no travel bound for any motor or slit, so no write limit can be sourced; adding a
write would require an operator envelope and a source-backed stop path.

The clone states no engineering unit for any motor, current or vacuum record, so no field declares one.  The
`locations` field reports the names the deployment configured in `locations_data`; their number is not fixed by the
clone.  All fake numbers and location names are placeholders, not facts, limits or deployment defaults.

Model review (2026-11-05): the author served `M1.trigger()` (status not awaited) as the only capability.  Its
children's triggers are ophyd code outside the clone: the currents are `ID29EM`, an ophyd `NSLS_EM`
(`common_ophyd.py:180`), and the camera is `Prosilica` with ophyd's `SingleTrigger` mixin (`common_ophyd.py:245`);
classic ophyd refuses to trigger such a detector unless it is staged, and the package never stages the Device, while
the fake's trigger always returned a done status.  The trigger is therefore not served; staging would also change the
camera's and electrometer's acquisition settings.  The photocurrent observation replaces it: a fresh Channel Access
read of the statistics plugin's last computed mean, whose age depends on whether the electrometer is acquiring.
Constructing `M1` writes `EM180` into eight `nd_array_port` PVs (`common_ophyd.py:212-224`) before the driver serves
anything.  The camera array and its image artifact are outside this package, as are the `gv` shutter state and all
motion commands.

The package is model-authored and unreviewed (`reviewed_by` is null).  It has run on the fake backend only, never
on hardware, and the hardware factory `native.py` has never been imported or run.
