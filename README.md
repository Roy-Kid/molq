# Hamilton-HPC-Orchestra
[WIP] An extension for sf-hamilton to delegate node/task to HPC resource management system

## Proposal
[Hamilton](https://hamilton.dagworks.io/en/latest/) is a general-purpose, extensible workflow framework with high-quality code. The data flow or workflow is constructed using pure Python functions, which are compiled into a DAG (Directed Acyclic Graph) and executed by different executors. To scale up the Python code for parallel and remote execution, several [GraphAdapters](https://hamilton.dagworks.io/en/latest/reference/graph-adapters/) have been implemented. These extensions allow pure Python code to be orchestrated with third-party unified compute frameworks, such as Ray, Dask, Spark, etc.

However, in traditional computational scientific fields, we still rely on classic resource management systems, such as [SLURM](https://slurm.schedmd.com/documentation.html) and [PBS](https://www.pbs.org/). It is sometimes even difficult to use Docker and install your technology stack due to limited storage and file number quotas. Thus, a lightweight "submitter" needs to be implemented to interact with resource management systems. 

Another requirement is that research groups often have more than one cluster. These clusters are distributed across different regions and run on different operating systems. Researchers need to manually balance the load, determining which task should be submitted to which cluster, and they also need to check the status by logging into different clusters. This process becomes quite tedious when the number of tasks surges.

Hereby, after many experiments, we propose a new protocol for fine-grained control task submission in Hamilton workflow:
```python
@submit(system_alias, system_type, [option])
def task_to_submite(upstream: Any) -> to_downstram: Any:
    # before submit
    job_info: JobInfo = yield dict(
        name: str,
        max_cores: str,
        partition: str,
        ... # other config
        dependency: job_info,
        monitor: bool,  # if block until finished
    )
    # after submit
    return result
```
This protocol is non-invasive and can control resources at the node/task level. For example, small or short-time tasks can be assigned to a cluster with few queues but limited runtime, while long-duration tasks can be assigned to machines with long-duration nodes.

These resource management systems are similar; they all use bash scripts with directives. However, the keywords and formats are slightly different. Therefore, we use [a uniform alias/keyword](https://github.com/pyiron/pysqa) for disambiguation.

## Roadmap
[ ] configure register
[ ] system adapter
[ ] script template
[ ] log and panel
--- non-block
  [ ] external query after workflow finish
--- blocking
  [ ] monitoring
[ ] remote login
[ ] upload and retrieve


system support:
[ ] slurm
[ ] PBS

