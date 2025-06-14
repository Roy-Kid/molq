# Backwards compatibility for old package name ``h_submitor``.
from importlib import import_module

_module = import_module('molq')
for attr in getattr(_module, '__all__', []):
    globals()[attr] = getattr(_module, attr)

