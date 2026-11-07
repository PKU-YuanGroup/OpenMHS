"""Never imported by Sila2Driver native admission."""

def connect(**_options):
    raise RuntimeError("native SiLA admission is intentionally refused")
