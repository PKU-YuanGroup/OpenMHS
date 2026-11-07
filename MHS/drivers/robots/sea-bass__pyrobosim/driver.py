"""OpenMHS driver for the PyRoboSim world simulator (gh.sea-bass/pyrobosim).

DEVIATION FROM THE CARD: the card names the ``ros`` family and the
``RosDriver`` helper, but PyRoboSim describes itself as a 2D mobile robot
simulator with an *optional* ROS 2 interface (``docs/source/index.rst:6``).
The primary interface is the Python :class:`pyrobosim.core.world.World`
object, whose ``reset``, ``open_location``, ``close_location`` and
``set_inflation_radius`` methods are the simulator's world-level control.
The ROS 2 wrapper is a separate node that embeds that Python world; it is
not the interface this package controls.  The package therefore uses a
direct ``Driver`` over ``pyrobosim.core.world:World``.

Scope: world reset (``cap.world.reset.v1``), location/hallway open and close,
the world inflation radius, and a read-only world state.  Robot navigation,
pick/place, dynamics stepping, editing of world entities, sensors, rendering
and the optional ROS 2 interface are NOT COVERED.  The fake backend is an
analytic package stand-in; it never imports or runs the clone.  This package
is model-authored and unreviewed, and it is checked on the fake backend only.
"""

from mhs.driver import (
    Driver,
    DriverFailed,
    Fact,
    Field,
    Limit,
    action,
    estop,
    read,
    write,
)

#: ``World.reset`` treats a negative seed as "no fixed seed" and seeds NumPy
#: only for a non-negative one.  That comparison is the sourced lower bound.
_SEED_REF = "pyrobosim/pyrobosim/core/world.py:113"
_INFLATION_REF = "pyrobosim/pyrobosim/core/world.py:1257-1270"
_RESET_REF = "pyrobosim/pyrobosim/core/world.py:100-128"
_SHUTDOWN_REF = "pyrobosim/pyrobosim/core/world.py:130-143"
_OPEN_REF = "pyrobosim/pyrobosim/core/world.py:674-715"
_CLOSE_REF = "pyrobosim/pyrobosim/core/world.py:717-771"

_OPEN_RESULT = {
    "status": Field("string", description="Native ExecutionStatus name, for example SUCCESS"),
    "message": Field("string", description="Native result message, empty when the upstream set none"),
    "success": Field("boolean", description="True only when the native ExecutionResult is a success"),
}


class PyrobosimWorld(Driver):
    device_id = "pyrobosim"
    device_kind = "world.sim"
    resource_id = "world"
    mode = "simulated"
    risk = "R1"
    native = "pyrobosim.core.world:World"
    backends = {"fake": ".fake:FakePyrobosim"}
    display_name = "PyRoboSim world simulator"
    vendor = "sea-bass"
    model = "PyRoboSim World"
    tags = ["simulation", "mobile-robot", "world", "navigation", "ros2-optional"]
    facts = [
        Fact("PyRoboSim is a 2D mobile robot simulator for behavior prototyping with an optional ROS 2 "
             "interface.", source="vendor_doc", ref="docs/source/index.rst:6"),
        Fact("World is the core world modeling class and holds the robots, rooms, hallways, locations, "
             "object spawns and objects.", source="upstream_code",
             ref="pyrobosim/pyrobosim/core/world.py:26-63"),
        Fact("World.reset(deterministic=False, seed=-1) reloads the source YAML file (or the stored source "
             "snapshot), marks the world changed and returns True; its docstring says a seed of -1 means no "
             "fixed seed.", source="upstream_code", ref=_RESET_REF),
        Fact("World.reset treats seed < 0 as no fixed seed and otherwise calls np.random.seed(seed) before "
             "the reload.", source="upstream_code", ref="pyrobosim/pyrobosim/core/world.py:113-117"),
        Fact("World.shutdown starts a robot.cancel_actions thread for every robot whose is_busy() is true, "
             "joins those threads, then stops every robot's sensor threads.", source="upstream_code",
             ref=_SHUTDOWN_REF),
        Fact("Robot.is_busy is true only while executing_action, executing_plan or executing_nav is set, "
             "whereas is_moving also counts a non-zero dynamics velocity.", source="upstream_code",
             ref="pyrobosim/pyrobosim/core/robot.py:243-257"),
        Fact("RobotDynamics2D.reset keeps the current pose when pose is None and replaces the velocity with "
             "the supplied array, whose default is [0.0, 0.0, 0.0].", source="upstream_code",
             ref="pyrobosim/pyrobosim/core/dynamics.py:96-107"),
        Fact("World.set_inflation_radius stores inflation_radius and updates the collision polygons of every "
             "location, room and hallway plus the world polygons; its docstring names meters but states no "
             "numeric bound.", source="upstream_code", ref=_INFLATION_REF),
        Fact("World.open_location resolves a string through get_entity_by_name, accepts only a Location or "
             "Hallway, reports an already-open entity as SUCCESS, refuses a locked one, and otherwise sets "
             "it open recursively, updates polygons and marks the world changed.", source="upstream_code",
             ref=_OPEN_REF),
        Fact("World.close_location applies the same name, type and lock checks, refuses to close a hallway "
             "that a robot occupies, and otherwise sets the entity closed recursively and marks the world "
             "changed.", source="upstream_code", ref=_CLOSE_REF),
        Fact("World.get_locations returns the world's Location list, optionally filtered by category.",
             source="upstream_code", ref="pyrobosim/pyrobosim/core/world.py:1440-1450"),
        Fact("World.get_room_names returns the name of every room in self.rooms.",
             source="upstream_code", ref="pyrobosim/pyrobosim/core/world.py:1318-1324"),
        Fact("World.get_hallway_names returns the name of every hallway in self.hallways.",
             source="upstream_code", ref="pyrobosim/pyrobosim/core/world.py:1344-1350"),
        Fact("World.get_hallway_by_name resolves a stored entity only when it is a Hallway.",
             source="upstream_code", ref="pyrobosim/pyrobosim/core/world.py:1352-1368"),
        Fact("World.get_entity_by_name resolves any name through the name_to_entity map.",
             source="upstream_code", ref="pyrobosim/pyrobosim/core/world.py:1677-1684"),
        Fact("World.get_object_names returns the object names, optionally filtered by category.",
             source="upstream_code", ref="pyrobosim/pyrobosim/core/world.py:1623-1633"),
        Fact("World.get_robot_names returns the robot names.", source="upstream_code",
             ref="pyrobosim/pyrobosim/core/world.py:1652-1658"),
        Fact("An Entity declares is_open = True and is_locked = False as class attributes.",
             source="upstream_code", ref="pyrobosim/pyrobosim/core/types.py:43-46"),
        Fact("The world YAML schema documents inflation_radius as the collision padding radius around rooms, "
             "hallways and locations and does not give a numeric range.", source="vendor_doc",
             ref="docs/source/yaml/world_schema.rst:11"),
    ]
    safe_state = (
        "Every robot's dynamics velocity is zeroed, World.shutdown cancels busy simulated robot actions and "
        "stops sensor threads (they stay stopped after a safety reset), and the velocities are zeroed again; it "
        "does not destroy the world, lock the entities or prevent an external client from issuing new work."
    )
    fidelity = {
        "engine": "analytic:package fake (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "seed_control": "none",
            "notes": "The fake has no random generator: it records the reset seed but its placeholder "
                     "world state does not vary with it. A live run forwards the seed to World.reset.",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a pure-Python analytic stand-in: it runs no pyrobosim physics, navigation, "
            "planning, robot dynamics or ROS node, and never imports or executes the clone",
            "every room, hallway, location, object and robot name, every open state and the inflation "
            "radius in the fake are placeholders, not the world YAML or the upstream simulator state",
            "only the world-level reset, location/hallway open and close, inflation-radius configuration "
            "and read-only state are served; robot navigation, pick/place, task plans, dynamics stepping, "
            "sensors, world-entity editing, rendering and the optional ROS 2 interface are NOT COVERED",
            "World.shutdown only cancels robots whose is_busy() is true; Robot.cancel_actions waits for an "
            "in-flight executing_action such as a pick or place to return instead of interrupting it, so "
            "the stop is not proof of immediate quiescence for that action",
            "World.shutdown joins its cancel threads without a timeout; when it outlasts the 1 s default e-stop "
            "budget the e-stop reports MHS.SAFETY.SAFE_STATE_UNREACHED with the latch held while the native "
            "shutdown continues; the fake's shutdown returns at once",
            "the clone states no numeric bound for the world inflation radius; the driver declares it "
            "operator_required and the example overlay is an operator example, not a device bound",
            "World.reset reloads source_yaml_file when it is set and otherwise the in-memory source "
            "snapshot; the fake models only a fixed placeholder initial state",
        ],
    }

    @read("world_state", type="object", description="Names and open states of the simulated world entities",
          properties={
              "rooms": Field("array", items=Field("string"), description="Room names"),
              "hallways": Field("object", description="Map of hallway name to its open state"),
              "locations": Field("object", description="Map of location name to its open state"),
              "objects": Field("array", items=Field("string"), description="Object names"),
              "robots": Field("array", items=Field("string"), description="Robot names"),
          })
    def world_state(self):
        return self._world_state()

    @read("inflation_radius", unit="m", description="Collision-padding radius around world entities")
    def inflation_radius(self):
        return self.native.inflation_radius

    @write("inflation_radius", unit="m", description="Set the collision-padding radius around world entities",
           limit=Limit.operator_required(
               "The clone states no numeric range for the world inflation radius; the operator supplies the "
               "accepted range before this write is allowed."))
    def set_inflation_radius(self, value):
        self.native.set_inflation_radius(value)

    @action(cap="cap.world.reset.v1",
            input={"seed": Field("integer", unit="1", description="Seed recorded for this reset",
                                 limit=Limit(min=0, source="upstream_code", ref=_SEED_REF))},
            description="Reload the world's source YAML and reseed NumPy with the supplied seed")
    def reset_world(self, seed):
        ok = self.native.reset(deterministic=False, seed=seed)
        if ok is not True:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"World.reset returned {ok!r} instead of True")
        return {"observation": self._world_state(), "seed": seed}

    @action(name="x-cap.sea-bass.open_location.v1",
            input={"location": Field("string", description="Name of the location or hallway to open")},
            output=_OPEN_RESULT, risk="R1",
            description="Open a storage location or hallway in the simulated world")
    def open_location(self, location):
        return self._execution_receipt(self.native.open_location(location))

    @action(name="x-cap.sea-bass.close_location.v1",
            input={"location": Field("string", description="Name of the location or hallway to close")},
            output=_OPEN_RESULT, risk="R1",
            description="Close a storage location or hallway in the simulated world")
    def close_location(self, location):
        return self._execution_receipt(self.native.close_location(location))

    @estop
    def stop(self):
        # Zero every robot's dynamics velocity first: World.shutdown joins its
        # cancel threads without a timeout and Robot.cancel_actions waits for an
        # in-flight action, so the non-blocking part of the stop must not wait
        # behind it (model review 2026-11-04).  Then cancel busy robot actions,
        # stop the sensor threads, and zero the velocities again.
        self._zero_velocities()
        self.native.shutdown()
        self._zero_velocities()

    def _zero_velocities(self):
        for name in list(self.native.get_robot_names()):
            robot = self.native.get_robot_by_name(name)
            if robot is not None:
                robot.dynamics.reset()

    def _world_state(self):
        locations = {item.name: bool(item.is_open) for item in self.native.get_locations()}
        hallways = {}
        for name in self.native.get_hallway_names():
            hallway = self.native.get_hallway_by_name(name)
            hallways[name] = bool(hallway.is_open) if hallway is not None else False
        return {
            "rooms": list(self.native.get_room_names()),
            "hallways": hallways,
            "locations": locations,
            "objects": list(self.native.get_object_names()),
            "robots": list(self.native.get_robot_names()),
        }

    @staticmethod
    def _execution_receipt(result):
        status = getattr(result.status, "name", str(result.status))
        message = result.message or ""
        if not result.is_success():
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               message or f"the native execution result was {status}")
        return {"status": status, "message": message, "success": True}
