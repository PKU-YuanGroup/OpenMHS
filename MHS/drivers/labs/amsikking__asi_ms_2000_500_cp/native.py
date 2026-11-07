"""Hardware backend factory for the ASI MS-2000-500-CP driver.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  The acceptance gate runs the fake
backend and never imports this module or the upstream package, so the path below was never executed.

The upstream is a single module at the clone root, ``asi_MS_2000_500_CP.py``.  The operator makes it importable
(for example by putting the clone root on PYTHONPATH) and installs the Silicon Labs VCP USB driver the clone README
names (README.md:4).  This factory builds the upstream ``Controller`` with the three axes this package serves.

The travel arguments are required and have no defaults: the upstream takes the travel envelope from its caller
(asi_MS_2000_500_CP.py:57-64), so this factory cannot know it.  ``axes_min_mm`` and ``axes_max_mm`` are tuples of
three numbers in millimetres, and ``lead_screws`` is a tuple of three codes from the upstream table (UC, SC, S, F,
XF; asi_MS_2000_500_CP.py:43-48).  ``encoder_counts_per_um`` is optional and passed through to the upstream
constructor, whose default is 10 counts per micrometre (asi_MS_2000_500_CP.py:65-69).  ``use_pwm`` initializes the
LED output at construction (asi_MS_2000_500_CP.py:85-87); set it false only for a controller without that output.

No hardware was attached while writing this package, and no hardware backend ran.
"""

#: The three axes this package serves; the upstream accepts this tuple (asi_MS_2000_500_CP.py:39).
AXES = ("X", "Y", "Z")


def connect(port, *, lead_screws, axes_min_mm, axes_max_mm, encoder_counts_per_um=None,
            use_pwm=True, name="MS-2000-500-CP", verbose=False, **options):
    """Open the serial controller and return the upstream ``Controller`` object."""
    if options:
        raise TypeError(f"unknown connection option(s): {', '.join(sorted(options))}")
    from asi_MS_2000_500_CP import Controller

    counts = None if encoder_counts_per_um is None else tuple(encoder_counts_per_um)
    return Controller(
        which_port=port,
        axes=AXES,
        lead_screws=tuple(lead_screws),
        axes_min_mm=tuple(axes_min_mm),
        axes_max_mm=tuple(axes_max_mm),
        encoder_counts_per_um=counts,
        use_pwm=bool(use_pwm),
        name=str(name),
        verbose=bool(verbose),
    )
