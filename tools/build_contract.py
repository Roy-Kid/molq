"""Build the versioned protocol from one declarative source."""

import json
from pathlib import Path


def obj(properties, required=()):
    return {
        "type": "object",
        "properties": properties,
        "required": list(required),
        "additionalProperties": False,
    }


def ref(name):
    return {"$ref": f"#/$defs/{name}"}


string = {"type": "string", "minLength": 1, "maxLength": 4096}
identifier = {"type": "string", "pattern": "^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$"}
positive = {"type": "integer", "minimum": 1, "maximum": 1000000}
strings = {"type": "array", "items": string, "minItems": 1, "maxItems": 4096}
env = {
    "type": "object",
    "propertyNames": {"pattern": "^[A-Za-z_][A-Za-z0-9_]*$"},
    "additionalProperties": {"type": "string"},
}
command = {
    "oneOf": [
        obj(
            {
                "kind": {"const": "argv"},
                "argv": {**strings, "items": {**string, "minLength": 0}},
            },
            ["kind", "argv"],
        ),
        obj({"kind": {"const": "shell"}, "command": string}, ["kind", "command"]),
        obj(
            {
                "kind": {"const": "script"},
                "text": {"type": "string", "minLength": 1, "maxLength": 524288},
            },
            ["kind", "text"],
        ),
    ]
}
defs = {
    "Command": command,
    "Accelerator": obj(
        {
            "kind": {"enum": ["gpu", "nvidia_mps"]},
            "quantity": positive,
            "scope": {"enum": ["per_node", "total"]},
            "model": identifier,
        },
        ["kind", "quantity", "scope"],
    ),
    "Resources": obj(
        {
            "nodes": positive,
            "tasks": positive,
            "cpus_per_task": positive,
            "memory_bytes": {"type": "string", "pattern": "^[1-9][0-9]{0,19}$"},
            "time_limit_seconds": positive,
            "accelerators": {
                "type": "array",
                "items": ref("Accelerator"),
                "maxItems": 16,
            },
        }
    ),
    "JobRef": obj(
        {
            "registry_id": string,
            "cluster_id": string,
            "native_id": {
                "type": "string",
                "pattern": "^[A-Za-z0-9][A-Za-z0-9_.;-]{0,255}$",
            },
            "incarnation": string,
        },
        ["registry_id", "cluster_id", "native_id", "incarnation"],
    ),
    "Dependency": obj(
        {
            "ref": ref("JobRef"),
            "condition": {
                "enum": ["after", "after_success", "after_failure", "after_started"]
            },
        },
        ["ref", "condition"],
    ),
    "Scheduling": obj(
        {
            "name": identifier,
            "partition": identifier,
            "account": identifier,
            "qos": identifier,
            "reservation": identifier,
            "priority": {"type": "integer", "minimum": 0, "maximum": 1000000},
            "exclusive": {"type": "boolean"},
            "dependencies": {
                "type": "array",
                "items": ref("Dependency"),
                "maxItems": 256,
            },
        }
    ),
    "Launch": obj(
        {"kind": {"enum": ["direct", "mpi"]}, "ranks": positive, "threads": positive},
        ["kind"],
    ),
    "Placement": obj({"tasks": positive, "cpus_per_task": positive}),
    "ExecutionUnit": obj(
        {
            "id": identifier,
            "command": ref("Command"),
            "env": env,
            "cwd": string,
            "stdout": string,
            "stderr": string,
            "launch": ref("Launch"),
            "placement": ref("Placement"),
        },
        ["id", "command"],
    ),
    "Plan": {
        "oneOf": [
            obj({"kind": {"const": "unit"}, "ref": identifier}, ["kind", "ref"]),
            obj(
                {
                    "kind": {"enum": ["sequence", "parallel"]},
                    "children": {
                        "type": "array",
                        "items": ref("Plan"),
                        "minItems": 1,
                        "maxItems": 256,
                    },
                },
                ["kind", "children"],
            ),
        ]
    },
    "Execution": obj(
        {
            "units": {
                "type": "array",
                "items": ref("ExecutionUnit"),
                "minItems": 1,
                "maxItems": 256,
            },
            "plan": ref("Plan"),
            "env": env,
            "cwd": string,
        },
        ["units"],
    ),
    "JobSpec": obj(
        {
            "resources": ref("Resources"),
            "scheduling": ref("Scheduling"),
            "execution": ref("Execution"),
        },
        ["execution"],
    ),
    "Defaults": obj(
        {
            "resources": ref("Resources"),
            "scheduling": ref("Scheduling"),
            "env": env,
            "cwd": string,
        }
    ),
    "TransportDefinition": {
        "oneOf": [
            obj({"kind": {"const": "local"}}, ["kind"]),
            obj({"kind": {"const": "ssh"}, "alias": identifier}, ["kind", "alias"]),
        ]
    },
    "ClusterDefinition": obj(
        {
            "name": identifier,
            "scheduler": {"enum": ["shell", "slurm", "pbs", "lsf"]},
            "transport": ref("TransportDefinition"),
            "target_root": string,
            "defaults": ref("Defaults"),
            "launcher": {"enum": ["srun", "mpirun", "mpiexec"]},
            "pbs_dialect": {"enum": ["openpbs"]},
        },
        ["name", "scheduler", "target_root"],
    ),
}
defs.update(
    {
        "ErrorData": obj(
            {
                "kind": string,
                "message": {"type": "string"},
                "outcome": {"enum": ["not_applied", "applied", "unknown"]},
                "context": {"type": "object"},
            },
            ["kind", "message", "outcome", "context"],
        ),
        "Freshness": obj(
            {
                "status": {"enum": ["live", "cached", "stale", "unavailable"]},
                "age_seconds": {"type": "number", "minimum": 0},
            },
            ["status", "age_seconds"],
        ),
        "Completion": obj(
            {
                "all_confirmed_terminal": {"type": "boolean"},
                "successful": {"type": ["boolean", "null"]},
            },
            ["all_confirmed_terminal", "successful"],
        ),
        "JobSnapshot": obj(
            {
                "ref": ref("JobRef"),
                "state": {
                    "enum": [
                        "queued",
                        "running",
                        "succeeded",
                        "failed",
                        "cancelled",
                        "timed_out",
                        "unknown",
                    ]
                },
                "terminal": {"type": "boolean"},
                "observed_at": string,
                "freshness": ref("Freshness"),
                "source": {
                    "enum": [
                        "queue",
                        "accounting",
                        "shell_receipt",
                        "absent",
                        "unavailable",
                    ]
                },
                "raw_state": {"type": "string"},
                "exit_code": {"type": ["integer", "null"]},
                "error": ref("ErrorData"),
                "last_known": ref("JobSnapshot"),
            },
            [
                "ref",
                "state",
                "terminal",
                "observed_at",
                "freshness",
                "source",
                "raw_state",
                "exit_code",
            ],
        ),
        "Coverage": obj(
            {
                "complete": {"type": "boolean"},
                "errors": {"type": "array", "items": ref("ErrorData")},
            },
            ["complete", "errors"],
        ),
        "ObservedChange": obj(
            {
                "cursor": string,
                "observed_at": string,
                "ref": ref("JobRef"),
                "previous_state": {"type": ["string", "null"]},
                "state": string,
                "terminal": {"type": "boolean"},
            },
            ["cursor", "observed_at", "ref", "previous_state", "state", "terminal"],
        ),
        "ObservationResult": obj(
            {
                "snapshots": {"type": "array", "items": ref("JobSnapshot")},
                "coverage": ref("Coverage"),
                "completion": ref("Completion"),
                "changes": {"type": "array", "items": ref("ObservedChange")},
                "cursor": string,
                "resync": {"type": "boolean"},
            },
            ["snapshots", "coverage", "completion"],
        ),
        "ClusterRecord": obj(
            {
                **defs["ClusterDefinition"]["properties"],
                "id": string,
                "revision": positive,
            },
            ["name", "scheduler", "target_root", "id", "revision"],
        ),
    }
)
defs["Resources"]["properties"]["memory_bytes"]["description"] = (
    "Minimum memory per allocated node, decimal bytes; Scheduler rounds upward to its native granularity."
)

consistency = {"enum": ["live", "bounded", "cached"]}
query = {
    "refs": {"type": "array", "items": ref("JobRef"), "minItems": 1, "maxItems": 1024},
    "consistency": consistency,
    "max_age": {"type": "number", "minimum": 0, "maximum": 86400},
}
params = {
    "molq.hello": obj({}),
    "schema.discover": obj({}),
    "clusters.list": obj({}),
    "clusters.get": obj({"cluster": string}, ["cluster"]),
    "clusters.register": ref("ClusterDefinition"),
    "clusters.update": obj(
        {
            "cluster": string,
            "definition": ref("ClusterDefinition"),
            "expected_revision": positive,
        },
        ["cluster", "definition", "expected_revision"],
    ),
    "clusters.remove": obj(
        {"cluster": string, "expected_revision": positive},
        ["cluster", "expected_revision"],
    ),
    "jobs.validate": obj(
        {"cluster": string, "spec": ref("JobSpec")}, ["cluster", "spec"]
    ),
    "jobs.preview": obj(
        {"cluster": string, "spec": ref("JobSpec")}, ["cluster", "spec"]
    ),
    "jobs.submit": obj(
        {"cluster": string, "spec": ref("JobSpec"), "request_key": identifier},
        ["cluster", "spec"],
    ),
    "jobs.get": obj(
        {
            "ref": ref("JobRef"),
            "consistency": consistency,
            "max_age": {"type": "number", "minimum": 0, "maximum": 86400},
        },
        ["ref"],
    ),
    "jobs.get_many": obj(query, ["refs"]),
    "jobs.observe": obj({**query, "cluster": string, "cursor": string}),
    "jobs.list": obj({"cluster": string}, ["cluster"]),
    "jobs.history": obj(
        {"cluster": string, "refs": query["refs"]}, ["cluster", "refs"]
    ),
    "jobs.cancel": obj({"ref": ref("JobRef"), "request_key": identifier}, ["ref"]),
    "jobs.cancel_many": obj({"refs": query["refs"]}, ["refs"]),
    "logs.read": obj(
        {
            "ref": ref("JobRef"),
            "stream": {"enum": ["stdout", "stderr"]},
            "offset": {"type": "integer", "minimum": 0},
            "limit": {"type": "integer", "minimum": 1, "maximum": 262144},
        },
        ["ref"],
    ),
    "files.read": obj(
        {
            "cluster": string,
            "path": string,
            "offset": {"type": "integer", "minimum": 0},
            "limit": {"type": "integer", "minimum": 1, "maximum": 262144},
        },
        ["cluster", "path"],
    ),
    "files.write": obj(
        {
            "cluster": string,
            "path": string,
            "offset": {"type": "integer", "minimum": 0},
            "data": {"type": "string", "maxLength": 350000},
        },
        ["cluster", "path", "data"],
    ),
    "files.transfer": obj(
        {
            "source_cluster": string,
            "source_path": string,
            "destination_cluster": string,
            "destination_path": string,
        },
        ["source_cluster", "source_path", "destination_cluster", "destination_path"],
    ),
    "config.get": obj({"key": identifier}, ["key"]),
    "config.set": obj({"key": identifier, "value": {}}, ["key", "value"]),
    "presets.list": obj({}),
    "presets.get": obj({"key": identifier}, ["key"]),
    "presets.set": obj({"key": identifier, "value": ref("Defaults")}, ["key", "value"]),
    "events.subscribe": obj({"cursor": string}),
}
contract = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://molcrafts.org/molq/protocol/v1",
    "$defs": defs,
    "methods": params,
    "protocol_version": {"major": 1, "minor": 0},
    "release": "0.9.0",
}
p = Path(__file__).resolve().parents[1] / "src/molq/protocol/v1.json"
p.write_text(json.dumps(contract, indent=2) + "\n")
