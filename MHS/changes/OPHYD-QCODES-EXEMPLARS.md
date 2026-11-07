OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Ophyd and QCoDeS family exemplars

The registry families `ophyd` and `qcodes` waited on `helper:ophyd` and `helper:qcodes` although `OphydDriver` and `QcodesDriver` existed: no complete package showed the helpers on a real upstream class. Each family now has an exemplar package that passes the full G1-G9 fake gate and `collect.py --strict`, and the triage family table names the helper and the exemplar.

## Exemplars

- `MHS/drivers/labs/bcda-aps__apstools` (Ophyd, R0): `ApsMachineParametersDevice`, a read-only monitor of seven EpicsSignalRO Components. Every read is `get(use_monitor=False)`; the one capability is the observational extension `x-cap.bcda-aps.ring_current.v1` over the proven `current.get`. The nested `aps_cycle` and `operator_messages` Components and the cached `inUserOperations` property are not served. It declares no write and no native stop: the Device has nothing to actuate.
- `MHS/drivers/labs/qcodes__qcodes_contrib_drivers` (QCoDeS, R1): the Thorlabs PM100D optical power meter of the contrib driver pack. Seven explicit Parameters; `power_range` (`Limit.operator_required`) and `auto_range` are written through `cap.device.configure.v1`; the native stop is `write("ABOR")`, the abort command the upstream sends before it re-initializes a measurement. `wavelength` and `beam_diameter` (a `scale` without `get_parser`), `averaging` writes (a `set_cmd` without a value placeholder), `attenuation` writes (dB) and the `MEAS:CURR?`/`MEAS:FREQ?` reads are not served, each with its source line.

Both cards' scanned entry symbols cannot be expressed with the helpers (the apstools synApps record classes fail the Ophyd source proof; the contrib pack's ERASynth stop remains blocked and its other entries construct no provable Parameter). Registry overrides in `MHS/registry/overrides/labs.json` set the entry symbol of each card to the exemplar's class; their justifications start `Model review for the ... exemplar`. With the triage entries `Family("qcodes", "QcodesDriver", None, <exemplar>)` and `Family("ophyd", "OphydDriver", None, <exemplar>)` the registry rebuild clears `helper:qcodes` and `helper:ophyd` from 20 cards: the two exemplars are done and 18 cards become dispatchable (12 in wave 2, 6 in wave 3), and 614 other cards change their rank only.

## SDK changes

- `OphydDriver` gains the get-only profile `classic_epics_ro_v1` for `Component(EpicsSignalRO, ...)`. It requires `set: False` and `get_kwargs` `{"use_monitor": false}`, compiles only the fresh read, and G7 accepts only an unshadowed `EpicsSignalRO` imported from `ophyd` or `ophyd.signal` for it; an EpicsSignalRO Component stays refused under `classic_epics_v1` and an EpicsSignal under the new profile. EpicsSignalRO is the most common read-only Signal of classic Ophyd devices; without it no observational Device of the eleven waiting cards could be bound.
- `mhs.driver new --like` failed for every card whose helper is `OphydDriver` (the card kind `ophyd` was not a template kind). `OphydDriver` and `QcodesDriver` cards now scaffold from the `python-object` templates.

- The task-card schema (`MHS/registry/schema/taskcard.schema.json`) accepts `QcodesDriver` and `OphydDriver` as a card's `helper`; without it gate G1 refuses every card of the two families as `CARD_INVALID`.

Seven profile tests and two scaffolding tests are new; seven of the nine fail on the unchanged SDK. Four registry tests that encoded "Ophyd and QCoDeS are blocked" now use `pymmcore-plus`, which stays blocked, and two new tests cover the enabled families. The family pages (`bluesky-ophyd.md`, `qcodes.md`) are generated from new `recipes.py` entries that state the configuration surface, the capability mapping and what is not expressible; `driver-authoring.md`, `ophyd-driver.md` and `qcodes-driver.md` point at them.

## Fitness of the waiting cards

Ophyd (11 cards): only the apstools exemplar is expressible. bcs-ophyd-zmq, ophyd-ads and smarpod-ophyd use custom Signal classes or transports; ari_sxn_common and pcdsdevices' entries nest Devices, use `FormattedComponent` or executable class bodies; dodal's entries are ophyd-async or nested; pamila has no Ophyd Components; hxn-profile-collection has no entry class; BEC keeps its identity and Status blockers; Basler's primary output is an image that the Python-object bridge cannot publish as an artifact.

QCoDeS (9 cards): only the contrib pack's PM100D (and ERASynth, whose native stop stays blocked) construct Parameters the source proof accepts. Most QCoDeS drivers use `add_parameter`, which needs a separately reviewed source profile; instrumentserver and zhinst-qcodes are proxy and generated frameworks; python-instrument-control has no QCoDeS Parameters; qickodes' initializers and class bodies fall outside the grammar.

## Not verified

No hardware, IOC, VISA session, QCoDeS, Ophyd or upstream code was run or imported; both fakes are source-shaped stand-ins and the evidence is `contract_checked`. No human reviewed either package (`reviewed_by` is null). The new profile and the scaffolding fix have not had an independent review.
