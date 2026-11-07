# MHS-A — Core Capability Catalogue

| Field | Value |
|---|---|
| Document | MHS-A (generated; informative in presentation, normative in content) |
| Generated from | [`capabilities.json`](capabilities.json) by `python3 MHS/sdk/tools/gen_appendices.py` — do not edit by hand |
| Layer | appendix of the core: the capability catalogue ([profiles.md](profiles.md) §2) |
| Classes | 63 |
| Specification | OpenMHS 0.9 (wire revision 1) |

This appendix is a generated projection of [`capabilities.json`](capabilities.json).
The JSON file is the machine-readable registry source; this table is its reviewable
rendering. Chapter [MHS-003](03-capability-registry.md) §7 describes the catalogue; the
JSON carries the full input and output schemas, units, limits and one example input
per class. If this table and the JSON disagree, the JSON wins and this file MUST be
regenerated.

Column meanings: **Class** — `capability_id`; **Verb** — `read` (never changes state or
the revision), `write` (sets named parameters) or `invoke` (an action); **Status** —
`stable`, `experimental` (binding requires `x-mhs-experimental`) or `deprecated` (still
valid; see the replacement below); **Profile** — `core`, or `sim` for Sim/Fidelity
profile classes that only simulated, hybrid or replay devices bind; **Resource kinds**
— resource `kind` values the class may bind to (`*`: any kind the device declares);
**Risk** — class-level risk floor (a binding MAY raise it, never lower it); **Since** —
the OpenMHS specification release (`spec_version`, as MAJOR.MINOR.PATCH) that introduced
the class in its current form, independent of the class MAJOR and of the wire revision.
Tags are the registry search keys. Fields marked `x-mhs-delta` in the JSON (a tolerance
or a rate in `K`, `K/min`) are temperature differences: conversions never apply the
Kelvin/Celsius offset to them.

Distribution: world 7, motion 9, manipulation 4, sensing 5, fluid 6, sample 6, imaging 3, optics 3, measure 9, thermal 1, actuation 3, compute 2, process 1, device 4.

## World (7 classes)

| Class | Verb | Status | Profile | Resource kinds | Summary | Tags | Risk | Since |
|---|---|---|---|---|---|---|---|---|
| `cap.world.reset.v1` | invoke | stable | sim | world.sim | Reset the simulated world to a scenario start state and return the initial observation. When a seed is supplied the endpoint records it in the receipt; otherwise the endpoint's declared default seed applies. | world reset, simulation start, scenario initialisation, seeded reset, episode start | R0 | 0.9.0 |
| `cap.world.step.v1` | invoke | stable | sim | world.sim | Advance the simulated world by a bounded number of fixed timesteps, optionally applying an action for each step, and return the resulting observation and terminal flags. | simulation step, advance time, apply action, physics tick, reinforcement learning step | R0 | 0.9.0 |
| `cap.world.state.v1` | read | deprecated | sim | world.sim | Return the complete normative state of a simulated world together with its revision and canonical state hash. | world state, simulation observation, state snapshot, read world, deterministic state | R0 | 0.9.0 |
| `cap.world.snapshot.v1` | invoke | deprecated | sim | world.sim | Capture a restorable snapshot of the complete world state, including the revision and state hash, for deterministic restore later. | snapshot, save state, checkpoint, restore point, deterministic capture | R0 | 0.9.0 |
| `cap.world.restore.v1` | invoke | deprecated | sim | world.sim | Restore the world to a previously captured snapshot, replacing the current state; the device revision advances and the state hash MUST equal the snapshot's. | restore, load state, rollback, checkpoint restore, deterministic rewind | R0 | 0.9.0 |
| `cap.world.render.v1` | invoke | stable | sim | world.sim | Render the current simulated world through a named camera and return an image artifact reference. Rendering does not advance simulated time. | render, camera, visualisation, image capture, headless rendering | R0 | 0.9.0 |
| `cap.world.seed.v1` | write | stable | sim | world.sim | Set the seed used by the simulated world's random number generators for subsequent steps, without resetting the world. The accepted seed is echoed in the receipt. | seed, random seed, reproducibility, determinism control, rng | R0 | 0.9.0 |

## Motion (9 classes)

| Class | Verb | Status | Profile | Resource kinds | Summary | Tags | Risk | Since |
|---|---|---|---|---|---|---|---|---|
| `cap.motion.joint_position.v1` | invoke | stable | core | robot.arm, motion.axis | Command one or more actuated joints to target positions in joint space, optionally over a declared duration, and report whether the target was reached within tolerance. | joint motion, move arm, joint position, trajectory, position control | R1 | 0.9.0 |
| `cap.motion.joint_velocity.v1` | invoke | stable | core | robot.arm, motion.axis | Command continuous joint velocities for a bounded duration. The operation stops at the end of the duration or when cancelled. | joint velocity, velocity control, continuous motion, jog, bounded motion | R1 | 0.9.0 |
| `cap.motion.joint_torque.v1` | invoke | experimental | core | robot.arm | Apply commanded joint torques for a bounded duration for compliant or force-controlled motion. Torque magnitude is bounded by the binding safety envelope. | torque control, compliance, force control, joint torque, impedance | R2 | 0.9.0 |
| `cap.motion.cartesian_pose.v1` | invoke | stable | core | robot.arm | Move the tool centre point to a Cartesian position and orientation in a named frame. The endpoint solves inverse kinematics; an unreachable target is rejected before motion. | cartesian motion, move to pose, inverse kinematics, tool centre point, waypoint | R1 | 0.9.0 |
| `cap.motion.cartesian_twist.v1` | invoke | experimental | core | robot.arm | Move with a commanded linear and angular velocity for a bounded duration, in a named frame. | velocity motion, twist, cartesian velocity, teleoperation, servo | R1 | 0.9.0 |
| `cap.motion.mobile_base.v1` | invoke | stable | core | robot.mobile_base | Drive a mobile base with a commanded linear and angular velocity for a bounded duration, or to a target pose. Obstacle and zone limits are enforced by the binding safety envelope. | mobile robot, base motion, drive, navigation, differential drive | R2 | 0.9.0 |
| `cap.motion.stop.v1` | invoke | stable | core | robot.arm, robot.mobile_base, motion.axis | Stop all motion on the resource with a declared deceleration profile and report the stopping position. This capability is always cancellable=false and is exempt from rate limiting. | stop, halt, decelerate, safe stop, emergency deceleration | R1 | 0.9.0 |
| `cap.motion.home.v1` | invoke | experimental | core | robot.arm, motion.axis | Drive axes to their declared home position or reference switch, establishing the coordinate reference needed by other motion capabilities. | homing, reference, calibration motion, home position, axis setup | R1 | 0.9.0 |
| `cap.motion.estop.v1` | invoke | deprecated | core | robot.arm, robot.mobile_base, motion.axis, world.sim | Engage the device-level emergency stop: motion stops within the declared latency, outputs transition to the declared safe state, and the device latches until mhs.safety.reset. | emergency stop, e-stop, halt device, safety stop, latch | R0 | 0.9.0 |

## Manipulation (4 classes)

| Class | Verb | Status | Profile | Resource kinds | Summary | Tags | Risk | Since |
|---|---|---|---|---|---|---|---|---|
| `cap.manipulation.grasp.v1` | invoke | stable | core | robot.gripper, robot.arm | Close the gripper on a target object with a bounded force and report the achieved grasp width. A failed grasp is a completed operation with grasped=false, not a silent success. | grasp, gripper close, pick object, force grasp, contact | R1 | 0.9.0 |
| `cap.manipulation.release.v1` | invoke | experimental | core | robot.gripper | Open the gripper to release the held object, optionally to a declared opening width, and report the achieved width. | release, gripper open, drop object, ungrasp, place handoff | R1 | 0.9.0 |
| `cap.manipulation.place.v1` | invoke | stable | core | robot.arm, robot.gripper | Place the held object at a declared target location with an approach height, release the gripper and verify the object is no longer held. | place, put down, deposit, assembly, position object | R2 | 0.9.0 |
| `cap.manipulation.pick.v1` | invoke | stable | core | robot.arm, robot.gripper | Move to a declared source, grasp the object, lift it by a declared clearance and verify the grasp still holds. Combines cartesian motion and grasp under one receipt. | pick, pick and place, retrieve, lift object, bin picking | R2 | 0.9.0 |

## Sensing (5 classes)

| Class | Verb | Status | Profile | Resource kinds | Summary | Tags | Risk | Since |
|---|---|---|---|---|---|---|---|---|
| `cap.sensing.read.v1` | read | stable | core | sensor, sensor.imu, sensor.force_torque | Read the current value of one or more sensor channels and return the values with a sampling timestamp and a monotone sequence number. Volatile channels are also available by subscription. | sensor read, telemetry, measurement, observation, channel value | R0 | 0.9.0 |
| `cap.sensing.image.v1` | invoke | stable | core | sensor.camera | Capture a single image from a named camera with a declared resolution and exposure and return an image artifact reference. | camera, image capture, snapshot, vision, photograph | R0 | 0.9.0 |
| `cap.sensing.point_cloud.v1` | invoke | stable | core | sensor.depth | Capture a depth point cloud over a declared range and return a point-cloud artifact reference with the point count and coordinate frame. | point cloud, depth, lidar, 3d scan, range image | R0 | 0.9.0 |
| `cap.sensing.force_torque.v1` | read | stable | core | sensor.force_torque | Read the current force and torque vector in a declared frame and return the wrench with its sampling timestamp. | force torque, wrench, contact force, load cell, six axis | R0 | 0.9.0 |
| `cap.sensing.imu.v1` | read | stable | core | sensor.imu | Read linear acceleration, angular velocity and orientation from an inertial measurement unit, with the declared reference frame and timestamp. | imu, accelerometer, gyroscope, orientation, inertial | R0 | 0.9.0 |

## Fluid (6 classes)

| Class | Verb | Status | Profile | Resource kinds | Summary | Tags | Risk | Since |
|---|---|---|---|---|---|---|---|---|
| `cap.fluid.aspirate.v1` | invoke | stable | core | lab.liquid_handler, lab.pipette | Draw a specified volume of liquid from a declared labware well into a pipette tip, with a bounded flow rate and an optional liquid-level offset. | liquid handling, pipetting, aspirate, volume, labware | R1 | 0.9.0 |
| `cap.fluid.dispense.v1` | invoke | stable | core | lab.liquid_handler, lab.pipette | Dispense a specified volume from the pipette into a declared labware well, with optional blowout and mixing after dispense. | liquid handling, dispense, pipette, well, reagent addition | R2 | 0.9.0 |
| `cap.fluid.transfer.v1` | invoke | stable | core | lab.liquid_handler, lab.pipette | Aspirate a volume from a source well and dispense it into a target well as one receipted operation, so a failed transfer cannot leave an untracked half-state. | transfer, pipetting, liquid movement, plate to plate, reagent transfer | R2 | 0.9.0 |
| `cap.fluid.mix.v1` | invoke | experimental | core | lab.liquid_handler, lab.pipette | Mix the contents of a declared well by repeated aspiration and dispense cycles at a bounded volume and speed. | mix, homogenise, resuspend, agitation, well mixing | R1 | 0.9.0 |
| `cap.fluid.wash.v1` | invoke | experimental | core | lab.liquid_handler | Wash a declared well or the pipette tip with a bounded volume of wash solution, discarding waste to a declared waste container. | wash, rinse, tip wash, well wash, decontamination | R1 | 0.9.0 |
| `cap.fluid.level.v1` | read | experimental | core | lab.liquid_handler, lab.labware | Detect and report the liquid level and estimated volume in a declared container using a declared detection method. | liquid level, volume estimate, meniscus, capacitance detection, pressure detection | R0 | 0.9.0 |

## Sample (6 classes)

| Class | Verb | Status | Profile | Resource kinds | Summary | Tags | Risk | Since |
|---|---|---|---|---|---|---|---|---|
| `cap.sample.move.v1` | invoke | stable | core | lab.sample, lab.labware | Move a sample, plate or other labware object from one declared location to another using the device's transport mechanism. | move plate, transfer labware, sample transport, plate mover, carrier | R1 | 0.9.0 |
| `cap.sample.incubate.v1` | invoke | stable | core | lab.incubator | Hold samples at a declared temperature, and optionally a declared atmosphere, for a declared duration. The achieved temperature and duration are reported in the output and receipt. | incubate, temperature hold, cell culture, thermal protocol, environmental control | R2 | 0.9.0 |
| `cap.sample.centrifuge.v1` | invoke | stable | core | lab.centrifuge | Spin declared samples at a target speed for a declared duration, optionally at a controlled temperature, then report the achieved speed and duration. | centrifuge, spin, pellet, phase separation, rpm | R2 | 0.9.0 |
| `cap.sample.seal.v1` | invoke | experimental | core | lab.plate_sealer | Apply a declared seal type to a microplate and report completion; the seal consumable is recorded as a consumable use. | seal plate, foil seal, adhesive seal, plate preparation, consumable | R1 | 0.9.0 |
| `cap.sample.unseal.v1` | invoke | experimental | core | lab.plate_sealer | Remove the seal from a microplate so that the wells are accessible, reporting completion. | unseal, remove seal, peel, plate preparation, open plate | R1 | 0.9.0 |
| `cap.sample.store.v1` | invoke | experimental | core | lab.storage, lab.sample | Place samples into a declared storage location at a declared temperature and record the storage location in the output so later retrieval is unambiguous. | store, archive, cold storage, sample inventory, freezer | R2 | 0.9.0 |

## Imaging (3 classes)

| Class | Verb | Status | Profile | Resource kinds | Summary | Tags | Risk | Since |
|---|---|---|---|---|---|---|---|---|
| `cap.imaging.capture.v1` | invoke | stable | core | instrument.microscope | Acquire a microscope image of the current field of view for a declared channel, exposure, binning and region of interest, returning an image artifact. | microscope, imaging, fluorescence, brightfield, camera acquisition | R0 | 0.9.0 |
| `cap.imaging.focus.v1` | invoke | stable | core | instrument.microscope | Move the focus axis to a target Z position or run an autofocus search over a declared range, returning the achieved Z position and focus score. | focus, autofocus, z stage, focal plane, sharpness | R1 | 0.9.0 |
| `cap.imaging.illumination.v1` | write | stable | core | instrument.microscope, light.source | Set the illumination channel and intensity used for subsequent imaging or observation, with an optional bounded on-duration after which the light is turned off. | illumination, light source, led, fluorescence excitation, brightness | R1 | 0.9.0 |

## Optics (3 classes)

| Class | Verb | Status | Profile | Resource kinds | Summary | Tags | Risk | Since |
|---|---|---|---|---|---|---|---|---|
| `cap.optics.set_power.v1` | write | experimental | core | optics.laser, optics.source | Set the emitted optical power of a laser or light source to a declared setpoint, optionally ramping over a declared duration. Bindings for class 3B+ sources raise the risk class to R3. | laser power, optical power, excitation, setpoint, emission control | R2 | 0.9.0 |
| `cap.optics.shutter.v1` | invoke | experimental | core | optics.shutter | Open or close a mechanical or electronic shutter in the optical path, reporting the resulting state and, for an open shutter, the open duration. | shutter, beam block, optical path, exposure control, safety shutter | R2 | 0.9.0 |
| `cap.optics.align.v1` | invoke | experimental | core | optics.stage, optics.mirror | Adjust an optical element along declared axes until a target coupling or position is reached, reporting the achieved offset and alignment quality. | alignment, optical alignment, coupling, mirror adjustment, beam steering | R2 | 0.9.0 |

## Measure (9 classes)

| Class | Verb | Status | Profile | Resource kinds | Summary | Tags | Risk | Since |
|---|---|---|---|---|---|---|---|---|
| `cap.measure.voltage.v1` | read | stable | core | instrument.dmm, instrument.smu, sensor | Measure a DC or RMS voltage on a declared channel or terminal pair and return the value with its sampling timestamp and measurement range. | voltage, dmm, electrical measurement, potential difference, read channel | R0 | 0.9.0 |
| `cap.measure.current.v1` | read | stable | core | instrument.dmm, instrument.smu, sensor | Measure current on a declared channel and return the value with its timestamp and range. | current, amperage, dmm, electrical measurement, read channel | R0 | 0.9.0 |
| `cap.measure.resistance.v1` | read | stable | core | instrument.dmm, sensor | Measure resistance or impedance on a declared channel and return the value with its timestamp and excitation method. | resistance, ohmmeter, impedance, continuity, electrical measurement | R0 | 0.9.0 |
| `cap.measure.spectrum.v1` | invoke | stable | core | instrument.spectrometer, instrument.spectrophotometer | Acquire an optical or mass spectrum over a declared wavelength or mass range and return the axis and intensity arrays, or an artifact reference for large spectra. | spectrum, spectroscopy, absorbance, wavelength scan, spectral acquisition | R0 | 0.9.0 |
| `cap.measure.intensity.v1` | read | stable | core | instrument.spectrometer, sensor.optical | Measure optical or radiant intensity at a declared wavelength or channel and return the value with its unit and integration time. | intensity, photometry, optical power, fluorescence intensity, detector count | R0 | 0.9.0 |
| `cap.measure.mass.v1` | read | stable | core | instrument.balance, sensor | Measure the mass on a balance or load cell and report the value and stability flag. | mass, weighing, balance, gravimetry, load cell | R0 | 0.9.0 |
| `cap.measure.temperature.v1` | read | stable | core | instrument.thermometer, sensor.temperature, instrument.incubator | Measure temperature at a declared location and return the value with its timestamp and stability flag. | temperature, thermometer, thermal measurement, probe, sensor | R0 | 0.9.0 |
| `cap.measure.pressure.v1` | read | stable | core | sensor.pressure, instrument.gauge | Measure absolute, gauge or differential pressure at a declared port and return the value with its reference and timestamp. | pressure, gauge, vacuum, baratron, process sensor | R0 | 0.9.0 |
| `cap.measure.flow.v1` | read | stable | core | sensor.flow, instrument.flowmeter | Measure volumetric or mass flow at a declared line and optionally the accumulated volume since a declared instant. | flow, flow rate, flowmeter, liquid flow, gas flow | R0 | 0.9.0 |

## Thermal (1 class)

| Class | Verb | Status | Profile | Resource kinds | Summary | Tags | Risk | Since |
|---|---|---|---|---|---|---|---|---|
| `cap.thermal.setpoint.v1` | write | stable | core | thermal.zone, instrument.incubator, lab.thermal_block | Set the target temperature of a thermal zone and optionally wait for the zone to reach the setpoint within a declared tolerance. | temperature control, setpoint, heater, thermal zone, ramp | R2 | 0.9.0 |

## Actuation (3 classes)

| Class | Verb | Status | Profile | Resource kinds | Summary | Tags | Risk | Since |
|---|---|---|---|---|---|---|---|---|
| `cap.actuation.gpio.v1` | write | stable | core | io.gpio, io.digital | Drive a general-purpose output pin to a declared digital or analog value, reporting the applied value. The pin's electrical limits are declared per binding. | gpio, digital output, relay, trigger, analog output | R1 | 0.9.0 |
| `cap.actuation.valve.v1` | write | stable | core | actuation.valve, fluid.valve | Open, close or position a valve to a declared state, reporting the achieved position. The port routing map is declared per binding. | valve, open valve, close valve, fluid routing, flow control | R1 | 0.9.0 |
| `cap.actuation.pump.v1` | invoke | stable | core | actuation.pump, fluid.pump | Run a pump at a declared flow rate for a declared duration or volume in a declared direction, reporting the volume moved. | pump, infuse, withdraw, flow control, dosing | R1 | 0.9.0 |

## Compute (2 classes)

| Class | Verb | Status | Profile | Resource kinds | Summary | Tags | Risk | Since |
|---|---|---|---|---|---|---|---|---|
| `cap.compute.submit.v1` | invoke | stable | core | compute.node, host.process | Run a bounded command-line computation on the device host with a declared timeout and return exit code and stdout/stderr artifact references. Always R1 or higher. | compute job, run command, analysis, script execution, bounded process | R1 | 0.9.0 |
| `cap.compute.cancel.v1` | invoke | deprecated | core | compute.node, host.process | Cancel a previously submitted compute job and report the signal used and whether the job terminated. | cancel job, kill process, abort compute, interrupt, stop analysis | R0 | 0.9.0 |

## Process (1 class)

| Class | Verb | Status | Profile | Resource kinds | Summary | Tags | Risk | Since |
|---|---|---|---|---|---|---|---|---|
| `cap.process.run.v1` | invoke | stable | core | process.controller | Execute a named, versioned process recipe on a process controller with declared parameters and return the exit status and a report artifact. | process recipe, unit operation, batch process, recipe execution, process control | R2 | 0.9.0 |

## Device (4 classes)

| Class | Verb | Status | Profile | Resource kinds | Summary | Tags | Risk | Since |
|---|---|---|---|---|---|---|---|---|
| `cap.device.describe.v1` | read | deprecated | core | device, world.sim, robot.arm, instrument | Return the device's generated profile, identity, mode, capability list and the digest of its manifest, so an agent can re-orient without re-discovering the endpoint. | device description, capabilities, self description, manifest, orientation | R0 | 0.9.0 |
| `cap.device.calibrate.v1` | invoke | stable | core | robot.arm, instrument, sensor, optics.laser | Run the device's calibration procedure against a declared reference or standard and return a calibration artifact reference and validity window. | calibration, reference standard, zeroing, accuracy, metrology | R1 | 0.9.0 |
| `cap.device.self_test.v1` | invoke | stable | core | device, instrument, robot.arm | Run the device's built-in self-test and return a pass/fail verdict with per-check results and a report artifact reference. Self-test does not certify safety. | self test, diagnostics, bist, health check, fault detection | R1 | 0.9.0 |
| `cap.device.configure.v1` | write | stable | core | * | Write one or more named parameters of a resource (setpoints, ranges, modes, gains) as a partial patch and report what was applied. The binding's effective input schema is derived from the writable properties of the bound resource's state_schema. | configure, set parameter, write setting, named parameter, setpoint | R1 | 0.9.0 |

## Deprecated classes (6)

These classes duplicate protocol methods. They stay valid and callable for their
deprecation window ([MHS-003](03-capability-registry.md) CAP-006, CAP-040); new drivers
use the replacement.

| Class | Replaced by |
|---|---|
| `cap.world.state.v1` | `mhs.resource.read` |
| `cap.world.snapshot.v1` | `mhs.snapshot` |
| `cap.world.restore.v1` | `mhs.restore` |
| `cap.motion.estop.v1` | `mhs.safety.estop` |
| `cap.compute.cancel.v1` | `mhs.operations.cancel` |
| `cap.device.describe.v1` | `mhs.devices.get` |

## Resource kinds (51)

The normative resource-kind vocabulary used by the classes above. A binding whose
resource kind is not in its class's `resource_kinds` is `MHS.CAPABILITY.KIND_MISMATCH`.
Overlapping kinds are cross-referenced; prefer one of them consistently.

| Kind | Title | See also |
|---|---|---|
| `actuation.pump` | Pump actuator | `fluid.pump` |
| `actuation.valve` | Valve actuator | `fluid.valve` |
| `compute.node` | Compute node |  |
| `device` | Whole device (generic) |  |
| `fluid.pump` | Fluid-handling pump | `actuation.pump` |
| `fluid.valve` | Fluid-routing valve | `actuation.valve` |
| `host.process` | Host process |  |
| `instrument` | Instrument (generic) |  |
| `instrument.balance` | Balance or scale |  |
| `instrument.dmm` | Digital multimeter |  |
| `instrument.flowmeter` | Flowmeter |  |
| `instrument.gauge` | Pressure or vacuum gauge |  |
| `instrument.incubator` | Incubator instrument | `lab.incubator` |
| `instrument.microscope` | Microscope |  |
| `instrument.smu` | Source-measure unit |  |
| `instrument.spectrometer` | Spectrometer |  |
| `instrument.spectrophotometer` | Spectrophotometer or plate reader |  |
| `instrument.thermometer` | Thermometer |  |
| `io.digital` | Digital I/O line |  |
| `io.gpio` | General-purpose I/O pin |  |
| `lab.centrifuge` | Centrifuge |  |
| `lab.incubator` | Lab incubator | `instrument.incubator` |
| `lab.labware` | Labware (plate, tube, reservoir) |  |
| `lab.liquid_handler` | Liquid handler |  |
| `lab.pipette` | Pipette |  |
| `lab.plate_sealer` | Plate sealer |  |
| `lab.sample` | Sample or plate in transport |  |
| `lab.storage` | Sample storage |  |
| `lab.thermal_block` | Thermal block or cycler |  |
| `light.source` | Light source | `optics.source`, `optics.laser` |
| `motion.axis` | Motion axis or stage |  |
| `optics.laser` | Laser | `optics.source`, `light.source` |
| `optics.mirror` | Optical mirror mount |  |
| `optics.shutter` | Optical shutter |  |
| `optics.source` | Optical source | `light.source`, `optics.laser` |
| `optics.stage` | Optical positioning stage |  |
| `process.controller` | Process controller |  |
| `robot.arm` | Robot arm |  |
| `robot.gripper` | Gripper or end effector |  |
| `robot.mobile_base` | Mobile robot base |  |
| `sensor` | Sensor (generic) |  |
| `sensor.camera` | Camera |  |
| `sensor.depth` | Depth sensor or lidar |  |
| `sensor.flow` | Flow sensor |  |
| `sensor.force_torque` | Force-torque sensor |  |
| `sensor.imu` | Inertial measurement unit |  |
| `sensor.optical` | Optical sensor |  |
| `sensor.pressure` | Pressure sensor |  |
| `sensor.temperature` | Temperature sensor |  |
| `thermal.zone` | Thermal zone |  |
| `world.sim` | Simulated world (Sim profile) |  |

## Generated inventory

| Metric | Value |
|---|---|
| Classes | 63 |
| `read` | 14 |
| `write` | 7 |
| `invoke` | 42 |
| status `stable` | 44 |
| status `experimental` | 13 |
| status `deprecated` | 6 |
| profile `core` | 56 |
| profile `sim` | 7 |
| R0 | 26 |
| R1 | 23 |
| R2 | 14 |
| R3 (class-level floor; bindings may elevate) | 0 |
| Requiring a permit at class level | 5 |
| With declared safety limits | 17 |
| Resource kinds | 51 |

**CAP-046.** Every class listed here MUST resolve via `mhs.schema.get` on an
endpoint that binds it, and the returned class document MUST match the entry in
[`capabilities.json`](capabilities.json) for that `capability_id`.
