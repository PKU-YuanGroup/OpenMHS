"""Hardware backend: opens the card's PyMoDAQ plugin and runs its normal master initialization.

Used only with backend="hardware" and allow_hardware=True (an operator decision), with a state_dir for the e-stop
latch.  This package is model-authored and unreviewed, and its risk is R1: the loader refuses the hardware backend of
an unreviewed model-written package only at R2 and R3, so no human review is required to start this one.  That is a
statement about the loader's rules, not evidence that this path works.  The acceptance gate runs the fake backend and
never imports this module or the upstream package; nothing here was ever executed.

The upstream class is a PyMoDAQ viewer plugin
(src/pymodaq_plugins_oceaninsight/daq_viewer_plugins/plugins_1D/daq_1Dviewer_Omnidriver.py:26).  Its supported
lifecycle is: create it with no parent, then call ``ini_detector()`` as master: the method creates the
``NETWrapper``, discovers the connected spectrometers and creates the per-spectrometer settings and wavelength axes
(:79-124).  A Qt application is required for the plugin's QObject and its Parameter tree; the plugin itself calls
``QApplication.processEvents()`` while it initializes (:118).  The factory creates the application when the process
has none and keeps a module-level reference to it.  OmniDriver's ``NETOmniDriver-NET40`` assembly and the
``omnidriver_path`` of the plugin configuration must already be installed on the machine (:16-23); this factory does
not install anything.

Options of the backend: none are used.  The OmniDriver location is the plugin's own configuration
(resources/config_template.toml, key ``omnidriver_path``), not an OpenMHS option.
"""

#: The one Qt application of this process (PyQt/PySide cannot create a second one).
_QAPP = None


def connect(**options):
    """Create the plugin as master, discover its spectrometers and return it as the driver's native object."""
    global _QAPP
    from qtpy.QtWidgets import QApplication

    from pymodaq_plugins_oceaninsight.daq_viewer_plugins.plugins_1D.daq_1Dviewer_Omnidriver import (
        DAQ_1DViewer_Omnidriver,
    )

    if QApplication.instance() is None:
        _QAPP = QApplication([])                    # the plugin needs a Qt application for QObject and Parameter
    viewer = DAQ_1DViewer_Omnidriver()
    viewer.ini_detector()                           # upstream :68-128: NETWrapper, discovery, settings, axes
    return viewer
