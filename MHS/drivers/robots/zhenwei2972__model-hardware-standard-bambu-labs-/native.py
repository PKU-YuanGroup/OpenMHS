"""Hardware backend: builds the pinned upstream ``BambuPrinter`` from the driver options.

Used only with ``backend="hardware"`` (an operator decision).  This package is model-authored and unreviewed, and it
is R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in driver.lock.json.  The
acceptance gate runs the fake backend and never imports this module or the upstream package; nothing here ran on a
printer.

Deployment blocker: the pinned upstream distribution ``mhs-printer`` installs the top-level Python package ``mhs``
(src/mhs/__init__.py), the same top-level package as the OpenMHS SDK.  Both cannot be imported in one interpreter.
The factory therefore takes ``upstream_module`` (default ``mhs.drivers.bambu.printer``): a deployment that vendors
or renames the upstream package can pass the renamed module, for example
``upstream_module="bambu_mhs.drivers.bambu.printer"`` with the upstream source installed as ``bambu_mhs``.  Without
that, the import fails here with an explicit message instead of silently loading the SDK's namespace.

Options: ``host`` (printer IP), ``serial`` (TLS certificate name), ``access_code``, ``model`` (default A1 mini),
``mqtt_port`` 8883, ``ftps_port`` 990, ``camera_port`` 6000, ``tls_mode`` verify, ``upload_dir`` cache,
``device_id``.  They are passed to the upstream ``DeviceConfig`` (src/mhs/config.py:52-70); the upstream
``BambuPrinter`` then builds the MQTT, FTPS and camera clients (src/mhs/drivers/bambu/printer.py:66-92).
"""


def connect(upstream_module="mhs.drivers.bambu.printer", **options):
    """Build ``BambuPrinter`` from a separately installed/renamed copy of the pinned upstream package."""
    import importlib

    root = str(upstream_module).split(".drivers", 1)[0]
    try:
        printer_module = importlib.import_module(str(upstream_module))
        config_module = importlib.import_module(f"{root}.config")
    except ImportError as exc:
        raise RuntimeError(
            "the upstream mhs-printer package installs the top-level package 'mhs', which collides with the OpenMHS "
            "SDK; both cannot be imported in one interpreter. Install/rename the upstream package under another "
            "top-level name (for example 'bambu_mhs') and pass "
            "upstream_module='bambu_mhs.drivers.bambu.printer', or run the hardware backend through an isolated "
            "bridge. This model-authored R2 package is unreviewed, so the loader refuses its hardware backend until "
            "a human signs reviewed_by in driver.lock.json."
        ) from exc
    printer_class = getattr(printer_module, "BambuPrinter")
    config_class = getattr(config_module, "DeviceConfig")
    config = config_class(
        device_id=str(options.get("device_id", "bambu-printer")),
        driver="bambu",
        model=str(options.get("model", "A1 mini")),
        host=str(options.get("host", "")),
        serial=str(options.get("serial", "")),
        access_code=str(options.get("access_code", "")),
        tls_mode=str(options.get("tls_mode", "verify")),
        upload_dir=str(options.get("upload_dir", "cache")),
        camera_port=int(options.get("camera_port", 6000)),
        mqtt_port=int(options.get("mqtt_port", 8883)),
        ftps_port=int(options.get("ftps_port", 990)),
    )
    config.validate()
    return printer_class(config)
