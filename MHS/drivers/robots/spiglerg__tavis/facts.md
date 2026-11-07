# Facts and tags for gh.spiglerg/tavis

Every fact cites its source at commit `a114648a0db232a1a8d4b142c65251b29afa795a`: `upstream_code` (code of the
clone) or `vendor_doc` (a text file of the clone). The same facts are written into `driver.py` (`facts = [...]`);
the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| TAVIS is a benchmark for egocentric active-vision imitation learning on humanoid torsos with eight simulated manipulation tasks across the Fourier GR1T2 and Pollen Reachy 2 robots | vendor_doc | README.md:7-10 |
| The same tasks run on both humanoid torsos with a canonical 19-D action layout | vendor_doc | README.md:27-30 |
| make_env.py is described as the single environment-construction entry point | vendor_doc | README.md:252 |
| make_tavis_env composes an embodiment, a task and an optional scene, and defaults to 1 environment, cameras enabled, a 20 Hz robot control rate and 100 s episodes | upstream_code | tavis/make_env.py:14-22 |
| make_tavis_env builds an IsaacLabArenaEnvironment named tavis_env | upstream_code | tavis/make_env.py:56-61 |
| make_tavis_env builds and registers the environment with ArenaEnvBuilder.build_registered | upstream_code | tavis/make_env.py:72-75 |
| make_tavis_env creates the environment with gym.make(name, cfg=cfg).unwrapped and resets it once | upstream_code | tavis/make_env.py:90-93 |
| make_tavis_env wraps the environment in CanonicalFrameWrapper before returning it | upstream_code | tavis/make_env.py:99-100 |
| CanonicalFrameWrapper extends gymnasium.Wrapper so downstream wrappers see a Gymnasium Env | upstream_code | tavis/wrappers/canonical_frame_wrapper.py:58 |
| CanonicalFrameWrapper.step adds the embodiment's canonical-frame offset to the left and right arm IK position targets before stepping the wrapped environment | upstream_code | tavis/wrappers/canonical_frame_wrapper.py:86-92 |
| GR1T2Embodiment is the GR1T2 robot embodiment with Robotiq 2F-85 grippers and NullspaceIK control | upstream_code | tavis/robots/gr1t2.py:400-401 |
| The GR1T2 action space is 19-D: left and right arm IK (7 each), head roll (1), head pitch and yaw (2) and one gripper command per hand (1 each) | upstream_code | tavis/robots/gr1t2.py:8-10 |
| GR1T2Embodiment.modify_env_cfg sets the simulation timestep to 1/60 s | upstream_code | tavis/robots/gr1t2.py:461-465 |
| Reachy2Embodiment is the Reachy 2 robot embodiment with NullspaceIK control | upstream_code | tavis/robots/reachy2.py:596-597 |
| Simulation, data collection and evaluation need an NVIDIA GPU with ray-tracing support, and RTX is required at rendering time | vendor_doc | README.md:47-49 |
| The installer bootstraps the pinned stack into a conda environment on Python 3.11 | vendor_doc | README.md:57-59 |
| The package requires Python >=3.10 | vendor_doc | pyproject.toml:11 |
| isaacsim, isaaclab and isaaclab-arena must be installed separately and are not on PyPI | vendor_doc | pyproject.toml:32 |
| Plain pip install -e . will not install correctly; pyproject.toml instructs uv pip install -e . | vendor_doc | pyproject.toml:34 |

## Native symbol and the fake

The card's first entry symbol, `tavis.make_env:make_tavis_env`, is a function (make_env.py:14), while gate G7 resolves
`native` as a class. The driver therefore names the card's GR1T2 embodiment class (`GR1T2Embodiment`,
gr1t2.py:400). The registered environment class is Isaac Lab's `ManagerBasedRLEnv`, which is external to the clone,
and the wrapper returned by the factory is `CanonicalFrameWrapper` (canonical_frame_wrapper.py:58). The fake stands
in for the registered environment; G7 compares its Gymnasium interface with the embodiment class, whose base
`EmbodimentBase` is also external, so `action_space`, `observation_space`, `reset` and `step` are reported as
`G7.MAYBE_ABSENT` warnings by design. This is a package limitation stated in the notes, not a claim that the
embodiment class is the environment.

## Limits

The driver declares no numeric bound of its own. The clone states the GR1T2 action layout and the control rate but no
per-element bound on an action, and the fake action Box is unbounded, so the bridge publishes no finite action limit.
The catalogued `cap.world.step.v1` schema bounds `ticks` (1 to the bridge's `max_ticks`, 10000) and
`cap.world.seed.v1` bounds `seed` to a non-negative integer, both enforced by the runtime. No field is
`operator_required`: the device is simulated R0 and the operator has no device bound to supply. There is no
`site-limits.example.json` because every bound is either a catalogue class bound or absent.

## Fidelity

The deployed model is F0 (kinematic/analytic): engine `tavis:make_tavis_env`, determinism `seeded` with
`seed_control` `parameter`, `timestep_ms` 50 (the default 20 Hz control period of make_env.py:20), `realtime_factor`
0, clock `lockstep`, reset `full`, `snapshot_restore` false. The gaps in `driver.py` state what is not modelled: Isaac
Sim physics, IK, contacts, actuator/sensor/noise/rendering models, the batched 19-D action Box and its
canonical-frame conversion, the camera-bearing Dict observation, the vectorized `num_envs`, the task and episode
limit, the absent fixed `env_id` to `gym.make`, and that the upstream stack was never started here. The fake's action
and observation arrays have the same 19-element policy width as the GR1T2 action layout but no camera image, so the
real observation is larger than the fake's.

## Safety

Simulated R0 device. The e-stop is the runtime's software latch: after it, no step or reset is accepted until
`mhs.safety.reset` clears the latch, the fake is not advanced, and the state stays readable. No physical stop exists
and none is claimed. The upstream environment drives simulated humanoid torsos under IK; the model-authored package
was checked on the fake backend only and is unreviewed.

Tags: tavis, isaac-lab, isaac-sim, isaaclab-arena, humanoid, active-vision, imitation-learning, simulation, gymnasium
