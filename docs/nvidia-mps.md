# NVIDIA MPS

Choose the mode using your knowledge of the target cluster. molq does not probe MPS configuration or negotiate support. Both modes use ordinary Cluster.submit, Job.wait and Job.logs over public RPC.

## Native scheduler resource

`Accelerator("nvidia_mps", 20, "per_node")` requests 20 native MPS resource units per node. Slurm renders `--gres=mps:20`; `--gps:mps` is not the flag. The quantity is a positive integer in the site's native resource units, not a portable physical-GPU percentage. Slurm supports only `per_node` for this request in molq, with no GPU model or combined GPU/MPS request.

The user determines whether the site supports this resource. Schema/layout validation does not establish resource availability or permission. Slurm decides acceptance. A definite native rejection returns `SUBMISSION_REJECTED`; a disconnected mutation can return `OUTCOME_UNKNOWN`. molq never automatically resends, substitutes a whole GPU, or launches MPS in response. Schedulers without an exact mapping return `SCHEDULER_UNSUPPORTED`.

## User-managed execution

When the site does not expose native MPS resources, calculate your GPU/CPU/memory budget and request ordinary resources. Start and stop MPS using your payload script and environment. These commands are ordinary Execution content; molq adds no MPS resource or isolation guarantee and does not manage the daemon lifecycle.

The example below uses one node and one allocated GPU. Change its budget, target working directory and program for your workload. It preserves scheduler-assigned device visibility, creates private pipe/log directories and attempts cleanup on ordinary script exit. The user remains responsible for site permissions and cleanup after forced termination. The active-thread percentage is a user-selected execution setting, independent of native resource quantity.

## Python

The complete runnable example is [examples/10_nvidia_mps.py](../examples/10_nvidia_mps.py). Register a Slurm cluster named `hpc`, place `train.py` and its dependencies in `/scratch/user/project` on the target, and adapt that directory and resource budget first.

```sh
# Native MPS: no user daemon startup is added.
python examples/10_nvidia_mps.py native
# Ordinary GPU allocation with explicit user-owned MPS startup/cleanup.
python examples/10_nvidia_mps.py manual
```

Both modes construct frozen Python request values and use the same submit/wait/logs flow.

## TypeScript

The equivalent requests use the generated `JobSpec` type. This example targets the same registered Slurm cluster and target program; choose `mode` explicitly before submission.

```typescript
import {Molq, type JobSpec} from "@molcrafts/molq";

const mode: "native" | "manual" = process.argv[2] === "manual" ? "manual" : "native";
const script = `set -euo pipefail
mps_root=$(mktemp -d "\${TMPDIR:-/tmp}/molq-mps.XXXXXX")
export CUDA_MPS_PIPE_DIRECTORY="$mps_root/pipe"
export CUDA_MPS_LOG_DIRECTORY="$mps_root/log"
mkdir -p "$CUDA_MPS_PIPE_DIRECTORY" "$CUDA_MPS_LOG_DIRECTORY"
cleanup() {
    printf 'quit\\n' | nvidia-cuda-mps-control || true
    rm -rf "$mps_root"
}
trap cleanup EXIT
nvidia-cuda-mps-control -d
python train.py
`;
const spec: JobSpec = {
  resources: {
    nodes: 1, tasks: 1, cpus_per_task: 4,
    memory_bytes: "8589934592", time_limit_seconds: 3600,
    accelerators: [{
      kind: mode === "native" ? "nvidia_mps" : "gpu",
      quantity: mode === "native" ? 20 : 1, scope: "per_node"
    }]
  },
  execution: {
    cwd: "/scratch/user/project",
    units: [mode === "native"
      ? {id: "main", command: {kind: "argv", argv: ["python", "train.py"]}}
      : {id: "main", command: {kind: "script", text: script},
         env: {CUDA_MPS_ACTIVE_THREAD_PERCENTAGE: "50"}}]
  }
};
const mq = Molq.http("http://127.0.0.1:17891", "your-long-token");
try {
  const job = await mq.cluster("hpc").submit(spec);
  console.log(await job.wait());
  console.log(await job.logs());
} finally {
  await mq.close();
}
```

The native mapping follows [Slurm GRES/MPS documentation](https://slurm.schedmd.com/gres.html); user-managed commands and environment follow [NVIDIA MPS documentation](https://docs.nvidia.com/deploy/mps/latest/index.html). Fixture and local Shell tests verify molq mapping/execution, not live HPC resource support.
