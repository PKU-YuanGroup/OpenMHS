"""Hardware backend: opens the Raspberry Pi camera and the OpenFlexure stage and returns the Microscope object.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored and
no human has reviewed it.  The loader refuses the hardware backend of such a package only at R2 and above; this one is
R1, so nothing stops an operator from enabling it: run it first with a person at the device
(MHS/handoff/REVIEW.md, section 1).  The
acceptance gate runs the fake backend and never imports this module, picamera or the stage driver; nothing here ran on
a microscope.

The upstream class takes an already initialised camera and stage (openflexure_microscope/microscope.py:100-105); the
upstream test jig opens the camera as ``PiCamera(sensor_mode=3, resolution=(3280,2464))`` and the stage as
``OpenFlexureStage()`` (tests/test_picamera.py:20-21, README.rst:49-59).  A caller may pass its own ``camera`` and
``stage`` objects instead.
"""


def connect(camera=None, stage=None, **options):
    """Open the camera and the stage and return them inside the upstream Microscope object."""
    from openflexure_microscope.microscope import Microscope

    if camera is None:
        from picamera import PiCamera

        camera = PiCamera(sensor_mode=3, resolution=(3280, 2464))
    if stage is None:
        from openflexure_stage import OpenFlexureStage

        stage = OpenFlexureStage(options.get("stage_port"))
    return Microscope(camera=camera, stage=stage)
