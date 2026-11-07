"""Hardware backend of the DMM6500 driver: opens a Keithley DMM6500 through the upstream pymeasure class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored and
no human has reviewed it.  The loader refuses the hardware backend of such a package only at R2 and above; this one is
R1, so nothing stops an operator from enabling it: run it first with a person at the instrument
(MHS/handoff/REVIEW.md, section 1).  The acceptance gate runs the fake backend and never imports this module or the
pymeasure package.

``resource`` (required) is what the upstream ``Instrument`` accepts as an adapter: a VISA resource string such as
``TCPIP::192.0.2.10::inst0::INSTR`` or ``ASML/dev/ttyUSB0::INSTR``, or an integer GPIB address
(pymeasure/instruments/instrument.py:50-70); any other keyword goes to the upstream constructor and then to
pymeasure's VISAAdapter (pymeasure/instruments/instrument.py:85-87).  The upstream class only uses the SCPI command
set (pymeasure/instruments/keithley/keithleyDMM6500.py:160-164).  Nothing here was run against an instrument.
"""


def connect(resource, **options):
    from pymeasure.instruments.keithley.keithleyDMM6500 import KeithleyDMM6500

    return KeithleyDMM6500(resource, **options)
