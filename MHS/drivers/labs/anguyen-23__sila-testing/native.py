"""Hardware factory of the Phenix package: it refuses.

Sila2Driver refuses every non-fake backend before it resolves this factory (MHS/sdk/src/mhs/driver/sila2.py), and
this function refuses as well, so no SiLA client, gRPC channel, comtypes RCI object or upstream module is ever
created or imported. A native route needs a reviewed SiLA 2 client, a server that is not in simulation mode, a
source-proven retirement and stop readback, and a human hardware review (README.md, "Honest limits").
"""


def connect(**_options):
    raise RuntimeError("native SiLA 2 admission is refused: this package is a controlled fake contract only")
