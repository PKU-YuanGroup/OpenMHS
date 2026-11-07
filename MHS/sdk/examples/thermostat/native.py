"""Hardware backend: opens the TH-1 SDK (vendor/thermo, installed as the package 'thermo').

Used only with backend="hardware" and allow_hardware=True (an operator
decision); the acceptance gate runs the fake backend and never imports it.
"""


def connect(**options):
    from thermo.controller import Controller

    return Controller(**options)
