OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.avidbots/flatland

Every fact cites the pinned clone at commit `fd636eea6c283d36eb662c36604daae45266eaf9`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the
statement spans adjacent lines. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| Timekeeper advertises rosgraph_msgs/Clock on the absolute /clock topic with queue size 1. | upstream_code | flatland_server/src/timekeeper.cpp:53-54 |
| Timekeeper initializes simulated time to ros::Time(0, 0) and, on StepTime, advances it by max_step_size_ before publishing the clock. | upstream_code | flatland_server/src/timekeeper.cpp:53-61 |
| ServiceManager registers the relative pause and resume services on its node handle. | upstream_code | flatland_server/src/service_manager.cpp:63-65 |
| ServiceManager::Pause and ServiceManager::Resume take std_srvs/Empty requests, call World::Pause/World::Resume and return true. | upstream_code | flatland_server/src/service_manager.cpp:150-159 |
| World::Pause sets service_paused_, World::Resume clears it, and World::IsPaused is also true while the internal marker manager is manipulating. | upstream_code | flatland_server/src/world.cpp:333-340 |
| World::Update skips the before-physics plugin hook, the Box2D step and Timekeeper::StepTime while IsPaused is true; only int_marker_manager_.update() still runs. | upstream_code | flatland_server/src/world.cpp:101-110 |
| The flatland_server node defaults update_rate to 200 Hz and step_size to 1/200 s, each overridable by a ROS parameter. | upstream_code | flatland_server/src/flatland_server_node.cpp:89-93 |
| SimulationManager sets Timekeeper's maximum step size from step_size_ before the loop. | upstream_code | flatland_server/src/simulation_manager.cpp:108 |
| The simulation loop sleeps for positive remaining expected-cycle time unless benchmarking. | upstream_code | flatland_server/src/simulation_manager.cpp:139-155 |

## Scope

The package exposes `/clock` only as an explicit observation capability, and the `/pause` and `/resume`
services. The clock is not a resource snapshot: its non-latched publisher emits no fresh sample while paused
(`flatland_server/src/timekeeper.cpp:54-66`, `flatland_server/src/world.cpp:101-108`). A clock observation during
pause therefore waits for a fresh sample and fails at its deadline; it does not return a held sample. It has no numeric input, so it declares no `Limit`. `pause` is the
simulator's stop: it stops the simulated world from stepping; it neither
commands a zero velocity nor claims a physical emergency stop. The services
are registered with relative names, so the driver records the upstream tokens
`pause` and `resume` as `source_name` and configures the resolved root
endpoints `/pause` and `/resume`; a deployment that namespaces the node must
expose them at those endpoints. `/clock` is an absolute name in the clone.

`World::IsPaused` is also true while the internal marker manager is
manipulating, so a held clock sample alone does not prove that the pause
service set the flag.

## Fidelity contract

`driver.py` describes the deployed fake: engine `analytic:ROS recording fake (no physics)`,
level F0, determinism `none`, `timestep_ms: 0` (event-driven state transitions with no
physics step), `realtime_factor: 0` (not paced), reset `none`, and no snapshot/restore.
The optional clock mode is omitted because this fake has no advancing simulator clock.
Upstream update-rate and step-size defaults remain source facts, not claims about the
fake's fidelity. The gaps disclose absent physics, placeholder observations and the
unexposed step/reset capabilities.

## Safety

The device is simulated at R0. `pause` is an input-free `safe_state=True`
action and is also the acknowledged `/pause` service bound as the simulator
stop; the runtime latches in software before calling it. After an e-stop the resume
command is refused until `mhs.safety.reset` clears the latch. `mhs.resource.read`, catalogued read capabilities
and declared safe-state actions remain permitted; observational extension actions such as the clock capability
remain latched because the server does not trust an extension's read verb as a safety exemption. The fake has
no physical stop and makes no hardware-safety claim.

## Tags

`ros`, `ros1`, `simulation`, `flatland`, `clock`, `pause`
