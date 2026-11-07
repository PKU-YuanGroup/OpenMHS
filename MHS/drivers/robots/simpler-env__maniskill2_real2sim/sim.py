"""Live backend: GraspSingleCokeCanInScene-v0 with a package-owned physics tick counter.

Nothing is imported until the sim backend opens (the gate never opens it).

The pinned environment has no physics clock: SAPIEN integrates only through
``self._scene.step()``, called once per substep of a control call
(``BaseEnv.step_action``, sapien_env.py:569-573, followed each time by the
``_after_simulation_step`` hook) and in the settling loop of a reset
(``CustomSceneEnv._settle``, base_env.py:220-224).  ``counting_subclass``
subclasses the registered task class and counts every completed
``scene.step()`` at those two sites; ``mhs_physics_clock_s`` is that count
times ``sim_timestep`` (1 / sim_freq).  The SDK's physics_ticks_v1 timing
(driver.py) reads it: 25 ticks per control call, and resets that integrate
their settling ticks, measured and reported in the reset receipt.

``connect`` builds the task as ``gym.make`` would (registration.py:31-34,
64-116 and 154-160: the registered default keyword arguments, then a TimeLimit
of the registered max_episode_steps), except that gymnasium's OrderEnforcing
wrapper is not added (the bridge always resets before the first step).  This route
has not been run: SAPIEN, the asset tree and the package are not installed
where the gate runs.
"""

from mhs.driver import DriverDefinitionError

ENV_ID = "GraspSingleCokeCanInScene-v0"


def counting_subclass(base):
    """``base`` with a counter of completed physics substeps and a clock derived from it."""

    class PhysicsTickCounted(base):
        mhs_physics_ticks = 0

        def _after_simulation_step(self):
            # BaseEnv.step_action calls this once after each self._scene.step() (sapien_env.py:569-573).
            self.mhs_physics_ticks += 1
            super()._after_simulation_step()

        def _settle(self, t):
            # The loop of CustomSceneEnv._settle (base_env.py:220-224), counting each completed scene.step().
            for _ in range(int(self.sim_freq * t)):
                self._scene.step()
                self.mhs_physics_ticks += 1

        @property
        def mhs_physics_clock_s(self):
            return self.mhs_physics_ticks * self.sim_timestep

    return PhysicsTickCounted


def connect(**options):
    if options:
        raise DriverDefinitionError("the SimplerEnv live route serves only the registered default configuration")
    import copy

    import gymnasium
    import mani_skill2_real2sim.envs  # noqa: F401 - registers the custom scenes (an upstream import side effect)
    from mani_skill2_real2sim.utils.registration import REGISTERED_ENVS

    spec = REGISTERED_ENVS[ENV_ID]
    env = counting_subclass(spec.cls)(**copy.deepcopy(spec.default_kwargs))
    try:
        return gymnasium.wrappers.TimeLimit(env, max_episode_steps=spec.max_episode_steps)
    except BaseException:
        env.close()
        raise
