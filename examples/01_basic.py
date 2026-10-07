"""Submit and wait without a long-lived Runtime."""

import tempfile
from pathlib import Path

from molq import Molq

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    with Molq(registry=root / "registry.db") as mq:
        mq.clusters.register(
            name="local", scheduler="shell", target_root=str(root / "jobs")
        )
        job = mq.cluster("local").submit(argv=["echo", "molq 0.9.0"])
        print(job.wait(timeout=10))
        print(job.logs()["text"])
