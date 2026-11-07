"""Live backend factory: the pinned ProjectAirSimDroneLandingEnv, constructed only when the sim backend opens.

Nothing is imported at module import time (the gate never opens this backend).
Deployment requirements, none of which the package can establish or the gate
checks: the ``projectairsim`` client and its dependencies installed from the
pinned clone, a running Project AirSim server with the drone-landing scene
(its clock is steppable and pauses on start), and no other client advancing
that scene's clock.  The SDK's asyncio_owned_loop_v1 profile (driver.py) runs
every native step, reset, close and stop on one owned event loop.

Constructor unwind: the base constructor connects a ProjectAirSimClient before
it builds the World (gym_env.py:27-29); if a later part of construction raises,
the connected client is disconnected here before the error propagates.  The
disconnect itself joins the client's receive thread without a bound
(client.py:419-424) and is not verified against a server.
"""

from mhs.driver import DriverDefinitionError


def make_env(**options):
    if options:
        raise DriverDefinitionError("the Project AirSim live route takes no backend options "
                                    "(the scene file is fixed by the pinned environment)")
    from projectairsim.gym_envs.projectairsim_dronelanding_env import ProjectAirSimDroneLandingEnv

    return construct(ProjectAirSimDroneLandingEnv)


def construct(env_class):
    """Build ``env_class()`` and disconnect a client that a failed constructor already connected."""
    env = env_class.__new__(env_class)
    try:
        env.__init__()
    except BaseException:
        client = getattr(env, "client", None)   # set before connect() at gym_env.py:27
        if client is not None:
            try:
                client.disconnect()
            except Exception:  # noqa: BLE001 - the construction error is the one reported
                pass
        raise
    return env
