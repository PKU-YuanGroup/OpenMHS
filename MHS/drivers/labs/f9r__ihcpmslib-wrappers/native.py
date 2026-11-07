"""Hardware backend: opens an INHECO SCILA through the upstream pythonnet wrapper.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed, and it is R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json (the loader does this at R2 and R3 only; an R0 or R1 package must not claim it).  The acceptance
gate runs the fake backend and never imports this module or the ihcWrappers package.

The upstream modules read ``config.ini`` from the working directory when they are imported
(``src/ihcWrappers/scila.py:1-5`` and ``src/ihcWrappers/pms.py:10-13``), and ``PmsWrapper.Create`` chooses the
wrapper from the ``ODTC`` and ``SCILA`` flags (``src/ihcWrappers/pms.py:88-96``).  ``config_dir`` selects a directory
that holds such a file; ``app/config.ini:3`` shows ``SCILA = True``.  The vendor IHC_PMS_Lib assemblies and .NET
Framework 4.8 or Mono must be installed by the operator (README.md:3-9); nothing here installs them.

Options of the backend: ``wsdl_uri`` (required) is the device WSDL URL, or an IPv4 address from which the URL used by
the example is built (``app/main.py:74-77``); ``lock_id`` is the upstream SiLA lock id; ``config_dir`` is the
directory holding config.ini; ``ip_address_index`` selects the network interface for a multihomed host
(``src/ihcWrappers/pms.py:60-65``).
"""

import os


def connect(wsdl_uri, lock_id=None, config_dir=None, ip_address_index=None, **options):
    previous = os.getcwd()
    if config_dir is not None:
        os.chdir(config_dir)
    try:
        from ihcWrappers.pms import PmsWrapper
    finally:
        os.chdir(previous)

    pms = PmsWrapper()
    if ip_address_index is not None:
        pms.IpAddressIndex(int(ip_address_index))
    if "://" not in wsdl_uri:
        wsdl_uri = f"http://{wsdl_uri}/scila.wsdl"
    device = pms.Create(wsdl_uri, lock_id)
    if device is None:
        raise RuntimeError("PmsWrapper.Create returned no device: check config.ini (SCILA = True) and the WSDL URI")
    if not hasattr(device, "GetTemperature"):
        raise RuntimeError("PmsWrapper.Create did not return a ScilaWrapper (check the device type and config.ini)")
    return device
