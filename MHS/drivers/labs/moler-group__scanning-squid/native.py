"""Hardware backend of the scanning SQUID microscope: the upstream ``SusceptometerMicroscope``.

The gate never imports this module.  ``connect`` runs only when an operator loads the hardware backend; the package is
R2 and model-authored, so the loader refuses that backend until a human signs ``reviewed_by`` in driver.lock.json.
Nothing here was run.

The repository is not an installable package (setup.py names a package directory ``scanning_squid`` that the
checkout does not have; the code lives in ``scanning-squid/``), so, as its documentation says
(docs/pages/workflow.rst:15; the example notebook appends the directory to ``sys.path``), the operator puts the
clone's ``scanning-squid`` directory on ``PYTHONPATH`` and starts the endpoint in a working directory the microscope may
write to.  ``connect`` then imports ``microscope.susceptometer`` and builds the microscope from the deployment's
configuration file and temperature mode (``LT`` or ``RT``), exactly as the example notebook does.

Opening the backend acts on the hardware before the driver serves anything, and these effects are the upstream's:

* importing the module writes ``squid_units.txt`` into the working directory (microscope.py:62-69,
  susceptometer.py:39-46);
* the constructor closes every open QCoDeS instrument, creates ``logs/`` and a log file (microscope.py:91-108);
* it initialises the ANC300: each axis frequency and voltage set to the configured values and each axis grounded, and it
  prints to stdout (atto.py:305-319), which an MHS server talking over stdio must isolate;
* it connects the Lakeshore 372 and 331 and the SR830 lock-ins (microscope.py:136-158, 186-199);
* it builds the Scanner, whose constructor moves the scanner to [0, 0, 0] V through the DAQ outputs (scanner.py:61):
  the operator opens the backend only with the SQUID retracted from the sample, and this package cannot stop that
  move (a scanner ramp is not stoppable, scanner.py:159-168).
"""


def connect(*, config_file, temp):
    if not isinstance(config_file, str) or not config_file.strip():
        raise ValueError("config_file must be the path of the microscope configuration JSON file")
    if temp not in ("LT", "RT"):
        raise ValueError("temp must be 'LT' or 'RT' (the microscope's temperature mode)")
    from microscope.susceptometer import SusceptometerMicroscope

    return SusceptometerMicroscope(config_file, temp)
