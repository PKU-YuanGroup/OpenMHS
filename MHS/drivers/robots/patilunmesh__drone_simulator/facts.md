# Facts and tags for gh.patilunmesh/drone_simulator

Every fact cites the pinned clone at commit `a9d0857f1ad4fe57df0250659b107cfc72f44023`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the statement
spans adjacent lines. The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The CBF node declares start_pose, my_id and cbf_param ROS parameters and reads cbf_param as a double; the launch value 15.0 is a configurable parameter, not a numeric bound. | upstream_code | drone_simulation/CBF_Demo/cbf_sim.py:41-50 |
| The CBF node imports ResetSim from tutorial_interfaces.srv. | upstream_code | drone_simulation/CBF_Demo/cbf_sim.py:33 |
| The CBF node creates a ResetSim service on the constructed relative name /drone<my_id>/ResetSim. | upstream_code | drone_simulation/CBF_Demo/cbf_sim.py:74-77 |
| ResetSim.srv declares request fields reset (bool), cbf_param (float32) and response field done (bool). | upstream_code | tutorial_interfaces/srv/ResetSim.srv:1-4 |
| reset_callback resets i, updates cbf_param when the request differs, regenerates the trajectory and LQR sequence, zeros tru_pose, destroys and recreates the timer, and sets response.done=True. | upstream_code | drone_simulation/CBF_Demo/cbf_sim.py:194-232 |
| The launch file runs drone_cbf_sim in namespace drone1 with start_pose [0, 0, 0], my_id 1 and cbf_param 15.0. | upstream_code | drone_simulation/launch/single_agent_cbf_launch.py:17-25 |
| The CBF node creates a nav_msgs/Odometry publisher on the relative true_pose topic with queue size 1. | upstream_code | drone_simulation/CBF_Demo/cbf_sim.py:53-54 |
| The CBF node imports nav_msgs/Odometry. | upstream_code | drone_simulation/CBF_Demo/cbf_sim.py:18 |
| The CBF node creates a 10 Hz timer, and its callback reads the precomputed trajectory, publishes the pose and increments the trajectory index. | upstream_code | drone_simulation/CBF_Demo/cbf_sim.py:125-159 |
| The CBF README says the CBF parameter controls cautiousness, the default is 15, and running the client resets the simulation to the initial state. | vendor_doc | drone_simulation/CBF_Demo/README.md:27-33 |

## Scope

The selected runtime is the CBF demo node `DroneCBFSim` launched by
`single_agent_cbf_launch.py`. It advances a precomputed 3-DOF trajectory on a
10 Hz timer, publishes `nav_msgs/msg/Odometry` on the relative `true_pose`
topic, and creates `tutorial_interfaces/srv/ResetSim` on
`/drone<my_id>/ResetSim` (`drone_simulation/CBF_Demo/cbf_sim.py:54,71-77`).
The launch file resolves the topic to `/drone1/true_pose` and the service to
`/drone1/ResetSim` with namespace `drone1` and `my_id` 1
(`drone_simulation/launch/single_agent_cbf_launch.py:17-25`). The driver
declares the pose/twist reads and the ResetSim command. The service binding
uses the `/ResetSim` token shown in the source and requires the operator to
remap `/drone1/ResetSim` to `/ResetSim`, or expose the same root name; that
remap is a deployment assumption, not an upstream fact.

`ResetSim` takes `reset: bool` and `cbf_param: float32` and returns
`done: bool` (`tutorial_interfaces/srv/ResetSim.srv:1-4`). The callback does
not branch on `request.reset`; it resets `i`, optionally updates `cbf_param`
when the request differs, regenerates the trajectory and LQR sequence, zeros
`tru_pose`, destroys and recreates the timer, and sets `response.done = True`
(`drone_simulation/CBF_Demo/cbf_sim.py:194-232`). The `done` flag is therefore
an acknowledgement from the callback, not a claim that the simulation stopped
or that a trajectory was reached.

The CBF node states no numeric range for `cbf_param`; the launch value 15.0
and the README default 15 are configurable values, not device limits. The
input is `Limit.operator_required`; without an operator overlay every
`ResetSim` request that names `cbf_param` is refused `MHS.SAFETY.LIMITS_UNSET`.

## Safety

The node creates no pause, stop, hold or disarm service or action. The only
service in this node is `ResetSim`; the reset callback destroys and recreates
the timer (`drone_simulation/CBF_Demo/cbf_sim.py:228-229`), so the simulation
resumes after the response. It is not a safe state and this package does not
declare it as one. The package declares no e-stop binding. A stock e-stop
therefore latches in software and reports the safe state unreached; the fake
cannot prove a stopped simulator. This is an upstream stop gap, not a missing
fake feature, and `RESULT.json` records it as blocked.

## Fidelity contract

`driver.py` describes the deployed fake: engine `analytic:ROS recording fake (no
physics)`, level F0, determinism `none`, `timestep_ms: 0` (event-driven state
transitions), `realtime_factor: 0` (not paced), reset `partial` (one modeled
ResetSim transition), and no snapshot/restore. The gaps disclose the absent CBF
node, trajectory generator, LQR controller, obstacle detector, 10 Hz timer,
ROS graph, RViz, the placeholder pose/twist values and the missing stop path.

## Tags

`ros`, `ros2`, `simulation`, `uav`, `drone`, `cbf`, `reset`, `odometry`
