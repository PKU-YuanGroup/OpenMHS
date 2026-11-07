"""Hardware backend: opens a python-microscope focus stage through MagScope's adapter.

Used only with ``backend="hardware"``; the acceptance gate never imports this module and nothing here was run.  This
package is model-authored and unreviewed: no human has reviewed or tested it, and no hardware run is claimed.

``device_uri`` is the python-microscope device-server URI (the adapter's ``connect()`` builds a Pyro4 proxy for it,
magscope/python_microscope.py:59-73 and 170-176).  ``position_scale`` is required: it must make the adapter report
MagScope Z in nanometres.  The connection guide's example uses 1000.0 when the microscope axis reports micrometres
(docs/source/connect_hardware.rst:75).  The upstream optional dependency is ``pip install magscope[python-microscope]``
(docs/source/connect_hardware.rst:56-58).
"""


def connect(device_uri, *, position_scale, axis_name="z", **options):
    from magscope.python_microscope import PythonMicroscopeFocusMotor

    motor = PythonMicroscopeFocusMotor(
        device_uri=device_uri,
        axis_name=axis_name,
        position_scale=position_scale,
        **options,
    )
    motor.connect()
    return motor
