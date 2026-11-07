"""Hardware backend: opens an Agilent PSA analyser through pyvisa and the upstream AgilentE44nn class.

Used only with backend="hardware" and allow_hardware=True, an operator decision.  This package is model-authored and
unreviewed, and its risk is R1: the loader of this SDK holds back the hardware backend of an unreviewed model-written
package only at R2 and R3, so nothing here is protected by a review gate -- do not enable this backend without a
person deciding to.  The acceptance gate runs the fake backend and never imports this module, pyvisa or labtoolkit.

``connect`` mirrors the two construction paths of the upstream package: the loader passes the open VISA resource to
the driver class, ``driver(self.rm.open_resource(instrument.Resource))`` (src/labtoolkit/__init__.py:96-99), and the
README's manual demo does ``AgilentE44nn(rm.open_resource('GPIB0::18::INSTR'))`` (README.md:46-47).  The class sets
its own read and write termination (src/labtoolkit/Instrument.py:18-19) and, in ``__post__``, turns on verbose command
errors (src/labtoolkit/SpectrumAnalyser/AgilentE44nn.py:17-19).

Options of the backend: ``resource`` (required) is a VISA resource string such as ``GPIB0::18::INSTR`` or
``TCPIP0::192.168.0.10::inst0::INSTR``; ``resource_manager`` is passed to ``pyvisa.ResourceManager`` (empty: pyvisa's
default backend) and any other option goes to ``open_resource``.
"""


def connect(resource, resource_manager="", **options):
    from labtoolkit.SpectrumAnalyser.AgilentE44nn import AgilentE44nn
    import pyvisa

    manager = pyvisa.ResourceManager(resource_manager)
    handle = manager.open_resource(resource, **options)
    return AgilentE44nn(handle)
