"""Hardware backend: opens the ImSwitch2 Standa rotation mount manager.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed.  It is R1, so the loader does not refuse the hardware backend on review grounds (that refusal is
for R2 and R3 only); the backend was never executed and no hardware run is claimed.  The acceptance gate runs the
fake backend and never imports this module or the imswitch package.

The four options are the fields the upstream manager reads from the rotator setup
(imswitch/imcontrol/model/managers/rotators/StandaRotatorManager.py:15-18) and passes to StandaMotor in the order
device id, library location, steps per turn and microsteps per step
(StandaRotatorManager.py:20, imswitch/imcontrol/model/interfaces/standamotor.py:18):

* ``motor_index``: the controller index, ``motorListIndex`` upstream;
* ``lib_loc``: the local libximc directory, ``ximcLibLocation`` upstream; StandaMotor adds its Python wrapper to
  sys.path and changes to its library directory on Python 3.8+ (standamotor.py:173-186);
* ``steps_per_turn``: the step count of one turn, ``stepsPerTurn`` upstream;
* ``microsteps_per_step``: the microstep count of one step, ``microstepsPerStep`` upstream.

The manager also needs the rotator name.  The upstream application supplies a ``rotatorInfo`` setup object with a
``managerProperties`` mapping; this factory builds that small object from the four options.  The upstream class is
imported here, only when the hardware backend is selected.
"""


def connect(motor_index, lib_loc, steps_per_turn, microsteps_per_step, name="rotator", **_options):
    from types import SimpleNamespace

    from imswitch.imcontrol.model.managers.rotators.StandaRotatorManager import StandaRotatorManager

    rotator_info = SimpleNamespace(managerProperties={
        "motorListIndex": motor_index,
        "ximcLibLocation": lib_loc,
        "stepsPerTurn": steps_per_turn,
        "microstepsPerStep": microsteps_per_step,
    })
    return StandaRotatorManager(rotator_info, name)
