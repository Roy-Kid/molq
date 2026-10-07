"""Typed scheduling intent contains no native flags."""

from molq import Scheduling

print(Scheduling(name="calculation", partition="compute", account="research").to_wire())
