"""Hardware backend: opens the ZEN blue connector of the upstream package.

Used only with backend="hardware" and an operator's allow_hardware decision.  This package is model-authored and
unreviewed, and it is R1: the loader refuses the hardware backend of an unreviewed model-written package only at
R2 and R3, so this module claims no such protection and the hardware path must not be inferred to be reviewed.
The acceptance gate runs the fake backend and never imports this module or the microscope_automation package.

The upstream connector is Windows-only: ``ConnectMicroscope(connect_dll=True)`` imports ``win32com.client`` and
takes the running ZEN application through ``GetActiveObject("Zeiss.Micro.Scripting.ZenWrapperLM")``
(microscope_automation/connectors/connect_zen_blue.py:60-90).  With ``connect_dll=False`` the same constructor
loads the clone's dummy ZEN objects (microscope_automation/connectors/connect_zen_blue.py:66-71); that path is an
upstream simulator, not this driver's fake, and it is not installed or imported by the gate.
"""


def connect(connect_dll=True, **_options):
    from microscope_automation.connectors.connect_zen_blue import ConnectMicroscope

    return ConnectMicroscope(connect_dll=connect_dll)
