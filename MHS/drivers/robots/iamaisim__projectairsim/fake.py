"""Analytic stand-in for the Project AirSim drone-landing Gym environment, with the native calling convention.

The pinned ``ProjectAirSimDroneLandingEnv`` connects a ``ProjectAirSimClient``
to a running Project AirSim scene.  Its ``reset()`` is synchronous and takes
no arguments; its ``step(action)`` is a coroutine that awaits
``move_by_velocity_async`` (which returns a task for the remote command),
advances the steppable world with the blocking ``continue_for_sim_time``, then
awaits the move task and returns the legacy four-tuple.  That runtime is
external to the clone and cannot be opened by the package or by the gate.

This fake keeps that shape so the SDK's owned event loop is exercised exactly
as the native environment would use it: ``step`` is ``async def`` and awaits a
command task that the world's ``continue_for_sim_time`` completes; ``reset``
is synchronous without arguments; ``world.pause()`` and ``world.is_paused()``
model the steppable clock's pause and its read-back.  Nothing here imports
upstream code or contacts a simulator.

Every number in this file is test data, not a device fact.  The action bounds
are copied from the pinned ``Box(-1.0, 1.0, ...)`` line named by
``action_space_ref`` in driver.py.
"""

import asyncio
import math


class Box:
    """Duck-typed ``gym.spaces.Box`` with the attributes the bridge reads."""

    def __init__(self, low, high, shape, dtype="float32"):
        self.shape = tuple(shape)
        count = 1
        for item in self.shape:
            count *= item
        self.low = [float(low)] * count
        self.high = [float(high)] * count
        self.dtype = dtype


class _SteppableWorld:
    """Stand-in for World over a steppable clock: time advances only inside continue_for_sim_time."""

    def __init__(self):
        self.sim_time_ns = 0          # placeholder simulated clock
        self.paused = True            # placeholder: the scene pauses on start
        self.pending = []             # (velocity, duration_ns, future) of commanded moves
        self.pose = None
        self.pauses = 0

    def load_scene(self, pose):
        self.sim_time_ns = 0
        self.paused = True
        self.pending = []
        self.pose = list(pose)

    def continue_for_sim_time(self, delta_time_nanos, wait_until_complete=True):
        """Advance the placeholder world by delta_time_nanos, then pause (blocking, like the native call)."""
        del wait_until_complete
        self.paused = False
        dt_s = float(delta_time_nanos) / 1e9
        for velocity, _duration, future in self.pending:
            for axis in range(3):
                self.pose[axis] += velocity[axis] * dt_s
            if not future.done():
                future.set_result(True)
        self.pending = []
        self.sim_time_ns += int(delta_time_nanos)
        self.paused = True
        return self.sim_time_ns

    def pause(self):
        self.pauses += 1
        self.paused = True
        return f"Sim time paused at t = {self.sim_time_ns}"

    def is_paused(self):
        return self.paused


class _Drone:
    """Stand-in for the Drone actor: a velocity command returns a task completed by the world."""

    def __init__(self, world):
        self._world = world

    async def move_by_velocity_async(self, v_north, v_east, v_down, duration=0.001):
        future = asyncio.get_running_loop().create_future()
        self._world.pending.append(((float(v_north), float(v_east), float(v_down)), duration, future))

        async def response():
            return await future

        return asyncio.ensure_future(response())


class FakeProjectAirSimDroneLanding:
    """Same calling convention as the native environment; analytic kinematics only."""

    def __init__(self, **_options):
        # Bounds copied from the pinned action-space line cited by driver.action_space_ref.
        self.action_space = Box(-1.0, 1.0, (3,))  # placeholder action bounds
        self.observation_space = Box(-math.inf, math.inf, (4,))  # placeholder observation bounds
        self.dt = 0.100  # placeholder step period, seconds
        self.world = _SteppableWorld()
        self.actor = None
        self.done = False  # placeholder terminal flag; upstream sets it only on collision
        self._start = [5.0, 5.0, -5.0, 0.0]  # placeholder dx, dy, dz (m), dyaw (rad)
        self._closed = False

    def reset(self):
        """Reload the placeholder scene and actor; no seed, no options (the native signature)."""
        if self._closed:
            raise RuntimeError("the environment is closed")
        self.done = False
        self.world.load_scene(self._start)
        self.actor = _Drone(self.world)
        return self.get_observation()

    async def step(self, action):
        """Command a velocity, advance the world by dt, await the command task (the native order)."""
        if self._closed:
            raise RuntimeError("the environment is closed")
        if self.actor is None:
            raise RuntimeError("reset() is required before step()")
        if hasattr(action, "tolist"):
            action = action.tolist()
        values = list(action)
        if len(values) != 3:
            raise ValueError("the drone-landing action must have three velocity components")
        v_north, v_east, v_down = values
        move_task = await self.actor.move_by_velocity_async(v_north, v_east, v_down, duration=(self.dt - 1e-3))
        self.world.continue_for_sim_time(self.dt * 1e9)
        await move_task
        next_obs = self.get_observation()
        reward = self.get_reward()
        done = self.done
        info = {"status": "Running"}  # copied from the pinned step result
        return (next_obs, reward, done, info)

    def get_observation(self):
        """Placeholder pose relative to the pad (dx, dy, dz) and yaw."""
        pose = self.world.pose or self._start
        return [pose[0], pose[1], pose[2], pose[3]]

    def get_reward(self):
        """Placeholder L2 distance between the pad and the actor."""
        pose = self.world.pose or self._start
        return math.sqrt(pose[0] * pose[0] + pose[1] * pose[1] + pose[2] * pose[2])

    def close(self):
        """Mark the stand-in closed; there is no client or simulator to disconnect."""
        self._closed = True
