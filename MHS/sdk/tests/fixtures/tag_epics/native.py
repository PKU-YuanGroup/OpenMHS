"""Synthetic fixture: there is no native transport; every hardware factory call refuses (no import)."""


def connect(**_options):
    raise RuntimeError("synthetic tag-bridge fixture: no native transport exists")
