"""Native admission refusal before any client import or effectful constructor."""


def connect(**options):
    raise RuntimeError('HTTP native admission blocked: pinned server retirement, approved effect envelope and deployment policy are unresolved')
