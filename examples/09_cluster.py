"""Register an explicit SSH computing destination; OpenSSH owns the alias."""

from molq import Molq

with Molq() as mq:
    destination = mq.clusters.register(
        name="research",
        scheduler="slurm",
        transport={"kind": "ssh", "alias": "hpc"},
        target_root="/scratch/user/molq",
        launcher="srun",
    )
    print(destination.definition())
