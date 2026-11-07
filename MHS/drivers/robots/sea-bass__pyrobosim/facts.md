# Facts and tags for gh.sea-bass/pyrobosim

Every fact cites the pinned clone at commit `d33280a4de8fc423662fdbe12f43b3bb1a3bf66d`.
`upstream_code` refs name `path/in/clone.py:LINE`; `vendor_doc` refs name a text file of the
clone. The same facts are written into `driver.py` (`facts = [...]`); the reference file is
generated from the driver, not from this page.

## Scope

DEVIATION FROM THE CARD: the card names the `ros` family and the `RosDriver` helper, but the
clone describes PyRoboSim as a 2D mobile robot simulator with an *optional* ROS 2 interface
(`docs/source/index.rst:6`). The primary interface is the Python `World` object
(`pyrobosim/pyrobosim/core/world.py:26`), and the ROS 2 wrapper is a separate node that embeds
that object. A rosbridge driver would not control this world's reset, entity state or geometry
without requiring a ROS graph and a running wrapper. This package is therefore a direct `Driver`
over `pyrobosim.core.world:World`.

The package serves only the world-level interface: `cap.world.reset.v1`, open/close of a
location or hallway, the world inflation radius, and a read-only world state. Robot navigation,
pick/place, task plans, dynamics stepping, sensors, adding or removing world entities,
rendering and the optional ROS 2 interface are NOT COVERED. No live pyrobosim or ROS 2 process
was started; only the package fake was served.

## Facts

| fact | source | ref |
|---|---|---|
| PyRoboSim is a 2D mobile robot simulator for behavior prototyping with an optional ROS 2 interface. | vendor_doc | docs/source/index.rst:6 |
| World is the core world modeling class and holds the robots, rooms, hallways, locations, object spawns and objects. | upstream_code | pyrobosim/pyrobosim/core/world.py:26-63 |
| World.reset(deterministic=False, seed=-1) reloads the source YAML file (or the stored source snapshot), marks the world changed and returns True; its docstring says a seed of -1 means no fixed seed. | upstream_code | pyrobosim/pyrobosim/core/world.py:100-128 |
| World.reset treats seed < 0 as no fixed seed and otherwise calls np.random.seed(seed) before the reload. | upstream_code | pyrobosim/pyrobosim/core/world.py:113-117 |
| World.shutdown starts a robot.cancel_actions thread for every robot whose is_busy() is true, joins those threads, then stops every robot's sensor threads. | upstream_code | pyrobosim/pyrobosim/core/world.py:130-143 |
| Robot.is_busy is true only while executing_action, executing_plan or executing_nav is set, whereas is_moving also counts a non-zero dynamics velocity. | upstream_code | pyrobosim/pyrobosim/core/robot.py:243-257 |
| RobotDynamics2D.reset keeps the current pose when pose is None and replaces the velocity with the supplied array, whose default is [0.0, 0.0, 0.0]. | upstream_code | pyrobosim/pyrobosim/core/dynamics.py:96-107 |
| World.set_inflation_radius stores inflation_radius and updates the collision polygons of every location, room and hallway plus the world polygons; its docstring names meters but states no numeric bound. | upstream_code | pyrobosim/pyrobosim/core/world.py:1257-1270 |
| World.open_location resolves a string through get_entity_by_name, accepts only a Location or Hallway, reports an already-open entity as SUCCESS, refuses a locked one, and otherwise sets it open recursively, updates polygons and marks the world changed. | upstream_code | pyrobosim/pyrobosim/core/world.py:674-715 |
| World.close_location applies the same name, type and lock checks, refuses to close a hallway that a robot occupies, and otherwise sets the entity closed recursively and marks the world changed. | upstream_code | pyrobosim/pyrobosim/core/world.py:717-771 |
| World.get_locations returns the world's Location list, optionally filtered by category. | upstream_code | pyrobosim/pyrobosim/core/world.py:1440-1450 |
| World.get_room_names returns the name of every room in self.rooms. | upstream_code | pyrobosim/pyrobosim/core/world.py:1318-1324 |
| World.get_hallway_names returns the name of every hallway in self.hallways. | upstream_code | pyrobosim/pyrobosim/core/world.py:1344-1350 |
| World.get_hallway_by_name resolves a stored entity only when it is a Hallway. | upstream_code | pyrobosim/pyrobosim/core/world.py:1352-1368 |
| World.get_entity_by_name resolves any name through the name_to_entity map. | upstream_code | pyrobosim/pyrobosim/core/world.py:1677-1684 |
| World.get_object_names returns the object names, optionally filtered by category. | upstream_code | pyrobosim/pyrobosim/core/world.py:1623-1633 |
| World.get_robot_names returns the robot names. | upstream_code | pyrobosim/pyrobosim/core/world.py:1652-1658 |
| An Entity declares is_open = True and is_locked = False as class attributes. | upstream_code | pyrobosim/pyrobosim/core/types.py:43-46 |
| The world YAML schema documents inflation_radius as the collision padding radius around rooms, hallways and locations and does not give a numeric range. | vendor_doc | docs/source/yaml/world_schema.rst:11 |

## Limits

`cap.world.reset.v1` takes `seed`, an integer. `World.reset` treats `seed < 0` as "no fixed seed"
and calls `np.random.seed(seed)` only otherwise (`pyrobosim/pyrobosim/core/world.py:113-117`),
so the driver declares `min=0` from that comparison and no maximum. The world inflation radius
has no numeric range in the clone (`pyrobosim/pyrobosim/core/world.py:1257-1270`,
`docs/source/yaml/world_schema.rst:11`); the driver declares that write `operator_required`, and
`site-limits.example.json` shows the operator-supplied example range. Until an operator supplies
it, every inflation-radius write is refused with `MHS.SAFETY.LIMITS_UNSET`.

## Safety

The device is simulated at R1: the package commands no robot motion. The native stop first zeroes
every robot's dynamics velocity with `RobotDynamics2D.reset()`
(`pyrobosim/pyrobosim/core/dynamics.py:96-107`), then calls `World.shutdown`
(`pyrobosim/pyrobosim/core/world.py:130-143`), which cancels busy robot actions and stops sensor
threads (they stay stopped after a safety reset), and zeroes the velocities again. `World.shutdown`
joins its cancel threads without a timeout; when it outlasts the 1 s default e-stop budget the
e-stop reports `MHS.SAFETY.SAFE_STATE_UNREACHED` with the latch held (model review 2026-11-04 moved
the velocity reset ahead of the blocking shutdown). This is a software stop in
the simulator, not a physical emergency stop. `World.shutdown` only visits robots whose
`is_busy()` is true; `Robot.cancel_actions` waits for an in-flight `executing_action` (for
example a pick or place) to return instead of interrupting it
(`pyrobosim/pyrobosim/core/robot.py:1062-1084`), so the stop is not proof of immediate quiescence
for such an action. The driver does not prevent an external client from issuing new work after
the stop. No hardware exists and no hardware run is claimed.

## Fidelity

The deployed fake is an analytic package stand-in, engine `analytic:package fake (no physics)`,
level F0, determinism `none`, `timestep_ms: 0`, `realtime_factor: 0` (not paced), reset `full`
and no snapshot/restore. It imports neither pyrobosim nor NumPy and runs no physics. Its entity
names, open states and inflation radius are placeholders; they are not the world YAML.

## Tags

`simulation`, `mobile-robot`, `world`, `navigation`, `ros2-optional`
