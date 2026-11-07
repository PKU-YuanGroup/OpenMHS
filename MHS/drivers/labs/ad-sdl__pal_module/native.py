"""Hardware backend: opens the PAL3 service through the upstream Windows/.NET driver.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored and
unreviewed, and it is R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json (the loader does this at R2 and R3 only; an R0 or R1 package must not claim it).  The acceptance gate
runs the fake backend and never imports this module or the upstream package.  The package is blocked (model review,
2026-11-05): the upstream has no source-backed stop, so its e-stop never reports a safe state.

Importing the upstream module already needs Windows: at import PAL3_driver imports clr and keyboard, adds a reference
to System, calls os.getlogin(), appends a Windows Dropbox path to sys.path and imports CustomTracker and
ContainerManager from it (PAL3_driver.py:1-22); neither module is in the clone.  The constructor loads the
PalPlusDriver and PalPlusDriverObjects DLLs from the Windows user's Dropbox path and calls sys.exit(0) when one is
missing (PAL3_driver.py:584, 592-593, 651-658), imports .NET System and the Ctc.Palplus assemblies
(PAL3_driver.py:595-611), starts the DirectFactory routing on a loopback endpoint and calls start_remote_service
(PAL3_driver.py:612-626), which connects to the host and runs direct_service.Reset, calling sys.exit(0) when that
Reset raises (PAL3_driver.py:682-699).  Without a host option it connects to the PAL1 address 192.168.99.230
(PAL3_driver.py:514-525).  The module is imported lazily inside ``connect`` so that this file is importable on a
non-Windows host; the hardware path was never run.

The factory follows the upstream MADSci node: construct PALService and call std_start (PAL_module.py:40-42), which
locks the left head, creates an execution session and homes the arm (PAL3_driver.py:664-671), so opening this backend
moves the arm without a command; do_lock calls sys.exit(0) after five failed lock attempts (PAL3_driver.py:719-748).
``std_start`` calls ``set_active_modules``, which only loads the module handles for the two built-in host addresses
PAL1 and NMR (PAL3_driver.py:803-824); a different host leaves them unset.  The deployment must therefore validate
the host, the rail/tray layout, the clear workspace for the startup home, and the Ctc.Palplus assembly installation.
"""


def connect(host=None, session_name="mhs", **options):
    """Construct PALService and run the upstream standard start; return the service object."""
    if options:
        raise TypeError("the PAL3 hardware backend accepts only host and session_name options")
    from PAL3_driver import PALService  # noqa: PLC0415 - Windows and .NET only; never imported by the gate

    service = PALService(host)
    service.std_start(session_name)
    return service
