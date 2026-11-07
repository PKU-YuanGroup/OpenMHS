"""Holder for backend objects of :class:`mhs.driver.PythonObjectDriver` instances (internal).

:class:`mhs.bridge.python.PythonObjectBridge` imports its target as
``module:attr``; a family driver creates its backend object itself (fake,
hardware or a test recorder) and registers it here under a unique attribute,
so the bridge resolves ``mhs.driver._natives:<token>`` to exactly that object.
"""
