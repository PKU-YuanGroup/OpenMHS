"""Hardware backend of the ADwin Gold II driver: the upstream QCoDeS instrument.

The gate never imports this module.  ``connect`` runs only when an operator loads the hardware backend (at R1 the
loader does not require a human ``reviewed_by``; this package is blocked because no stop is proven), and it is then
the only code that imports the upstream class.  The class is the file
``ADwin_Gold2.py`` at the pinned clone root; it is not a Python package, so deployment puts the clone root on
``PYTHONPATH``.  The external ``ADwin`` package, QCoDeS, numpy and tqdm are deployment prerequisites
(README.md:15-29).

The constructor needs the boot file and the process file of the installed ADwin program.  Both are deployment data
and are never guessed.  Constructing ``ADwin_Gold2`` opens the ADwin, boots it, loads and starts the process and
clears both FIFOs before it returns (ADwin_Gold2.py:711-736); a failure there raises before the driver serves
anything.  QCoDeS keeps a registry of instrument names, so ``name`` must be unique in the process.  Nothing here
was run: the package has never opened an ADwin.
"""


def connect(*, boot_file, process_file, adwin_no=1, name="adwin_gold2"):
    if not isinstance(boot_file, str) or not boot_file.strip():
        raise ValueError("boot_file must be the path of the ADwin boot binary on the deployment host")
    if not isinstance(process_file, str) or not process_file.strip():
        raise ValueError("process_file must be the path of the ADwin process binary on the deployment host")
    if isinstance(adwin_no, bool) or not isinstance(adwin_no, int) or adwin_no < 1:
        raise ValueError("adwin_no must be a positive integer ADwin device number")
    if not isinstance(name, str) or not name.isidentifier():
        raise ValueError("name must be a Python identifier (QCoDeS instrument names are identifiers)")
    from ADwin_Gold2 import ADwin_Gold2

    return ADwin_Gold2(name, boot_file, process_file, adwin_no=adwin_no)
