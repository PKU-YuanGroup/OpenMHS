OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.kscalelabs/kbot

Every fact cites its source at commit `76aba70e3372fecf3583ed6dbe5f379d44c8511c`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (a file of the clone at its pinned commit). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| K-Bot is an open-source humanoid robot from K-Scale Labs | vendor_doc | README.md:3 |
| The project is in public alpha and the README warns that breaking changes are expected | vendor_doc | README.md:15 |
| The repository tracks ksim-kbot as a git submodule at path ksim-kbot with URL git@github.com:kscalelabs/ksim-kbot.git | upstream_code | .gitmodules:5-8 |
| The mechanical design notes say the hands can be swapped through a lens mount interface and use the same 48 volt power and CAN bus lines as the arm actuators | vendor_doc | mechanical/README.md:11 |

## Why no fact cites the MJCF model

The card's model files (`ksim-kbot/ksim_kbot/kscale-assets/kbot-v2-feet/scene.mjcf` and its `robot.mjcf` include)
live inside the `ksim-kbot` git submodule. The pinned superproject commit records `ksim-kbot` as a gitlink
(160000 commit), so the gate's G4 tree reader cannot read a line inside it and a `path:LINE` citation there would
fail `G4.REF_MISSING`. The model is still read from the checkout at run time, and its control envelope is derived by
the bridge from `actuator_ctrlrange`, not copied into a `Limit` or a Fact. This is the same treatment the repository
uses for another driver whose model lives in a submodule.

## Limits

The driver declares none. `cap.world.step.v1` takes `action.ctrl` with one interval per actuator, and the bridge
derives that interval from the loaded model's `actuator_ctrlrange` (source `upstream_code`, ref
`kbot-v2-feet/scene.mjcf:actuator_ctrlrange`; the bridge marks it as derived, so it is not a package Limit). `ticks` is bounded
by the family (1 to `max_ticks`, 10000 by default). The device is simulated (R0), so no limit is
`operator_required`.

## Fidelity contract

`driver.py`'s `fidelity = {...}` publishes engine `mujoco:k-bot_v2_feet`, level F1, determinism `seeded` with
`seed_control` `none`, `realtime_factor` 0, clock `lockstep`, reset `full`, and the gaps. The bridge derives the
time step from the loaded model's `opt.timestep` (the served model sets none, so the library default applies). The
gaps say that the fake backend is a stand-in for the `mujoco` library, that it loads no mesh, texture or heightfield
and resolves no contact, and that nothing was compared with the real engine or with a physical K-Bot.

## Safety

Simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or reset is
accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state stays
readable.

Tags: humanoid, k-scale, kbot, mujoco, robot, simulation
