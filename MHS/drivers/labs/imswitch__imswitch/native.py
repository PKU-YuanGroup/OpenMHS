"""Hardware backend: opens the Standa rotation mount through ImSwitch's StandaMotor class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed.  It is R1, so the loader does not refuse the hardware backend on review grounds (that refusal is for
R2 and R3 only); the backend was never executed and no hardware run is claimed.

The four options are the ones the upstream manager reads from the setup JSON (StandaRotatorManager.py:15-20) and
passes to the constructor (StandaRotatorManager.py:57-60):

* ``motor_index``: the controller index, ``motorListIndex`` upstream (the first positional argument of StandaMotor,
  which the upstream class calls ``device_id``, standamotor.py:18);
* ``lib_loc``: the local libximc directory, ``ximcLibLocation`` upstream; the upstream class adds its Python wrapper
  to sys.path and, on Python 3.8+, changes to its library directory (standamotor.py:152-165);
* ``steps_per_turn``: the step count of one turn, ``stepsPerTurn`` upstream;
* ``microsteps_per_step``: the microstep count of one step, ``microstepsPerStep`` upstream.

The upstream class is imported here, only when the hardware backend is selected.  The gate never imports this module
or the upstream package.
"""


def connect(motor_index, lib_loc, steps_per_turn, microsteps_per_step, **_options):
    from imswitch.imcontrol.model.interfaces.standamotor import StandaMotor

    return StandaMotor(motor_index, lib_loc, steps_per_turn, microsteps_per_step)
