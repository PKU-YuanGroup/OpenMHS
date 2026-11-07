"""Analytic package fake for the PyRoboSim ``World`` surface.

This module is a pure-Python stand-in for the public methods the driver uses.
It does not import pyrobosim, NumPy, ROS 2 or the clone, and it models no
physics.  Every name, open state and the inflation radius below is test data
marked ``# placeholder``; none is a fact, a limit or a reference.
"""


class _Status:
    """Small stand-in for ``pyrobosim.planning.actions.ExecutionStatus``."""

    def __init__(self, name):
        self.name = name


class _ExecutionResult:
    """Small stand-in for ``pyrobosim.planning.actions.ExecutionResult``."""

    def __init__(self, status, message=None):
        self.status = _Status(status)
        self.message = message

    def is_success(self):
        return self.status.name == "SUCCESS"


class _Dynamics:
    """Stand-in for ``RobotDynamics2D``: the velocity reset the stop path uses."""

    def __init__(self):
        self.velocity = [0.0, 0.0, 0.0]                 # placeholder

    def reset(self, pose=None, velocity=None):
        self.velocity = [0.0, 0.0, 0.0] if velocity is None else list(velocity)


class _Robot:
    """Stand-in for ``Robot``: only the members World.shutdown and the stop path use."""

    def __init__(self, name):
        self.name = name
        self.dynamics = _Dynamics()
        self._busy = False                              # placeholder
        self._sensors_stopped = False

    def is_busy(self):
        return self._busy

    def cancel_actions(self):
        self._busy = False

    def stop_sensor_threads(self):
        self._sensors_stopped = True


class _Entity:
    """Stand-in for the openable part of ``Location``, ``Hallway`` and ``Room``."""

    def __init__(self, name, is_open=True, is_locked=False):
        self.name = name
        self.is_open = is_open
        self.is_locked = is_locked

    def set_open(self, state, recursive=True):
        self.is_open = state


class FakePyrobosim:
    """Pure-Python stand-in for the ``World`` methods this driver calls.

    The public method names are exactly the upstream ``World`` members the
    driver uses, so G7 can compare the fake surface with the clone's AST.
    """

    def __init__(self, **_options):
        self.inflation_radius = 0.0                     # placeholder
        self.last_seed = -1                             # placeholder
        self.shutdown_calls = 0                         # placeholder counter
        # placeholder negative-path switch, set through the backend options by the tests
        self.fail_shutdown = bool(_options.get("fail_shutdown", False))
        self._initial = self._placeholder_world()       # placeholder
        self._install(self._initial)

    def _placeholder_world(self):
        # placeholder names and open states; this is not the world YAML
        return {
            "rooms": ["kitchen", "living_room"],
            "hallways": {"hallway_0": _Entity("hallway_0", is_open=True)},
            "locations": {
                "table": _Entity("table", is_open=False),
                "shelf": _Entity("shelf", is_open=False),
                "fridge": _Entity("fridge", is_open=True),
                "cabinet": _Entity("cabinet", is_open=False, is_locked=True),
            },
            "objects": ["apple", "cracker"],
            "robots": {"robot": _Robot("robot")},
        }

    def _install(self, state):
        self.rooms = state["rooms"]
        self.hallways = state["hallways"]
        self.locations = state["locations"]
        self.objects = state["objects"]
        self.robots = state["robots"]

    # -- World surface used by the driver ------------------------------------
    def reset(self, deterministic=False, seed=-1):
        self.last_seed = seed
        self._install(self._placeholder_world())
        self.inflation_radius = 0.0                     # placeholder
        return True

    def shutdown(self):
        if self.fail_shutdown:
            raise RuntimeError("placeholder shutdown transport failure")
        self.shutdown_calls += 1
        for robot in self.robots.values():
            if robot.is_busy():
                robot.cancel_actions()
        for robot in self.robots.values():
            robot.stop_sensor_threads()

    def set_inflation_radius(self, inflation_radius=0.0):
        self.inflation_radius = inflation_radius

    def get_room_names(self):
        return list(self.rooms)

    def get_hallway_names(self):
        return list(self.hallways)

    def get_hallway_by_name(self, name):
        entity = self.hallways.get(name)
        return entity if isinstance(entity, _Entity) else None

    def get_locations(self, category_list=None):
        return list(self.locations.values())

    def get_object_names(self, category_list=None):
        return list(self.objects)

    def get_robot_names(self):
        return list(self.robots)

    def get_robot_by_name(self, name):
        return self.robots.get(name)

    def get_entity_by_name(self, name):
        for table in (self.rooms, self.hallways, self.locations):
            if isinstance(table, dict) and name in table:
                return table[name]
        if name in self.objects:
            return _Entity(name)
        return None

    def open_location(self, location):
        entity = self._openable(location)
        if entity is None:
            return _ExecutionResult("INVALID_ACTION", f"Cannot open {location!r}.")
        if entity.is_open:
            return _ExecutionResult("SUCCESS", f"{entity.name} is already open.")
        if entity.is_locked:
            return _ExecutionResult("PRECONDITION_FAILURE", f"{entity.name} is locked.")
        entity.set_open(True, recursive=True)
        return _ExecutionResult("SUCCESS")

    def close_location(self, location, ignore_robots=[]):
        entity = self._openable(location)
        if entity is None:
            return _ExecutionResult("INVALID_ACTION", f"Cannot close {location!r}.")
        if not entity.is_open:
            return _ExecutionResult("SUCCESS", f"{entity.name} is already closed.")
        if entity.is_locked:
            return _ExecutionResult("PRECONDITION_FAILURE", f"{entity.name} is locked.")
        entity.set_open(False, recursive=True)
        return _ExecutionResult("SUCCESS")

    def _openable(self, location):
        if isinstance(location, _Entity):
            return location
        if not isinstance(location, str):
            return None
        if location in self.locations:
            return self.locations[location]
        return self.hallways.get(location)
