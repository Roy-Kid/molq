"""Formal resources; validate/render through the selected Scheduler."""

from molq import Accelerator, Resources

request = Resources(
    nodes=2,
    tasks=8,
    cpus_per_task=4,
    memory_bytes="8589934592",
    time_limit_seconds=3600,
    accelerators=(Accelerator("gpu", 1, "per_node"),),
)
print(request.to_wire())
