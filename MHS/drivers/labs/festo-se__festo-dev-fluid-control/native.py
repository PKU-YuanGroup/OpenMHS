"""Hardware backend: opens a Festo pressure-over-liquid component and wraps it in FluidControlSession.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is
model-authored and unreviewed, and it is R2: the loader refuses its hardware backend until a human
signs ``reviewed_by`` in driver.lock.json (the loader does this at R2 and R3 only; an R0 or R1 package
must not claim it).  The acceptance gate runs the fake backend and never imports this module or the
fluid_control package.

Options of the backend:
    config (dict): the full instrument configuration the upstream component reads; required.
    component: ``"dispenser"``, ``"pipettor"`` or ``"aspirator"`` (the concrete engine class); required.
    component_id (str): the component key inside ``config["components"]``; the upstream default is
        ``<component_type>_1`` when omitted (src/fluid_control/fluid_control.py:250-252).
    mount_arm: an already-connected ``applied_motion`` axis, or None for a static component.
    disable_axes: axes disabled during tip engagement moves; defaults to an empty tuple upstream.
    gantry: an optional connected ``applied_motion`` gantry for the session's motion commands.
    mount_axis_name: the session's mount-axis name; the upstream default is ``"Z"``.

The factory only constructs the component (the upstream constructor opens the PGVA/VAEM connections)
and the session; it sends no fluid command.
"""


def connect(config, component, component_id=None, mount_arm=None, disable_axes=(), gantry=None,
            mount_axis_name="Z"):
    from fluid_control import Aspirator, Dispenser, Pipettor
    from fluid_control.cli.session import FluidControlSession

    classes = {"aspirator": Aspirator, "dispenser": Dispenser, "pipettor": Pipettor}
    try:
        component_class = classes[str(component).lower()]
    except KeyError as exc:
        raise ValueError(f"component must be one of {sorted(classes)}, got {component!r}") from exc
    engine = component_class(
        config=config,
        component_id=component_id,
        mount_arm=mount_arm,
        disable_axes=tuple(disable_axes),
    )
    return FluidControlSession(engine, gantry=gantry, mount_axis_name=mount_axis_name)
