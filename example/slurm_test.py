"""Generate a SLURM script without submitting it."""

from pathlib import Path
from molq.submitor import SlurmSubmitor

sub = SlurmSubmitor("test")
script = sub.gen_script(
    script_path=Path("run_slurm.sh"),
    cmd=["echo hi"],
    **{"--job-name": "test", "--ntasks": 1}
)
print("Script created at", script)
