from .base import BaseSubmitor
from .submit import submit
from .monitor import Monitor, JobStatus
cmdline = submit("_local_cmdline", "local")