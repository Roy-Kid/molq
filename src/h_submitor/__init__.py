from .base import BaseSubmitor
from .submit import submit
from .monitor import Monitor, JobStatus
from .cmdline import CMDLineExecutionManager
cmdline = submit("_local_cmdline", "local")