"""Defaults persist through RPC; merging occurs only in Runtime."""

from molq import Molq

with Molq() as mq:
    print(
        mq.rpc(
            "presets.set",
            key="small",
            value={"resources": {"tasks": 2, "cpus_per_task": 1}},
        )
    )
