"""Tests for molq config loading via molcfg."""

from __future__ import annotations

from typing import Any

import pytest
import yaml

from molq.config import MolqConfig, MolqProfile, load_config, load_profile
from molq.errors import ConfigError


def _write_config(tmp_path, data: dict[str, Any]):
    """Write *data* as the molq config file.

    Fixtures are dicts, not config syntax, so these tests assert on loading
    behaviour rather than on the serialization format.
    """
    p = tmp_path / "config.yaml"
    p.write_text(yaml.safe_dump(data), encoding="utf-8")
    return p


def _write_raw(tmp_path, text: str):
    p = tmp_path / "config.yaml"
    p.write_text(text, encoding="utf-8")
    return p


class TestLoadConfig:
    def test_missing_file_returns_empty(self, tmp_path):
        path = tmp_path / "nonexistent.yaml"
        cfg = load_config(path)
        assert cfg == MolqConfig(profiles={})

    def test_empty_file_returns_empty(self, tmp_path):
        path = _write_raw(tmp_path, "")
        cfg = load_config(path)
        assert cfg == MolqConfig(profiles={})

    def test_no_profiles_key_returns_empty(self, tmp_path):
        path = _write_config(tmp_path, {"other": {"key": 1}})
        cfg = load_config(path)
        assert cfg == MolqConfig(profiles={})

    def test_minimal_profile(self, tmp_path):
        path = _write_config(
            tmp_path,
            {"profiles": {"local": {"scheduler": "local", "cluster_name": "dev"}}},
        )
        cfg = load_config(path)
        assert "local" in cfg.profiles
        p = cfg.profiles["local"]
        assert p.scheduler == "local"
        assert p.cluster_name == "dev"

    def test_multiple_profiles(self, tmp_path):
        path = _write_config(
            tmp_path,
            {
                "profiles": {
                    "a": {"scheduler": "local", "cluster_name": "x"},
                    "b": {"scheduler": "slurm", "cluster_name": "y"},
                }
            },
        )
        cfg = load_config(path)
        assert set(cfg.profiles) == {"a", "b"}

    def test_profile_name_stored(self, tmp_path):
        path = _write_config(
            tmp_path,
            {"profiles": {"myjob": {"scheduler": "local", "cluster_name": "c"}}},
        )
        p = load_config(path).profiles["myjob"]
        assert p.name == "myjob"

    def test_jobs_dir_optional(self, tmp_path):
        path = _write_config(
            tmp_path,
            {
                "profiles": {
                    "x": {
                        "scheduler": "local",
                        "cluster_name": "c",
                        "jobs_dir": "/tmp/jobs",
                    }
                }
            },
        )
        p = load_config(path).profiles["x"]
        assert p.jobs_dir == "/tmp/jobs"


class TestSupersededTomlConfig:
    """A leftover config.toml must not be skipped in silence.

    molq reads YAML. Ignoring a TOML file would start molq with no profiles
    at all — every configured cluster gone, and no error saying why.
    """

    def test_stale_toml_beside_a_missing_yaml_is_an_error(self, tmp_path):
        legacy = tmp_path / "config.toml"
        legacy.write_text(
            '[profiles.gpu]\nscheduler = "slurm"\ncluster_name = "hpc"\n',
            encoding="utf-8",
        )
        with pytest.raises(ConfigError, match="TOML"):
            load_config(tmp_path / "config.yaml")

    def test_no_error_once_the_yaml_exists(self, tmp_path):
        (tmp_path / "config.toml").write_text("[profiles.gpu]\n", encoding="utf-8")
        path = _write_config(
            tmp_path,
            {"profiles": {"gpu": {"scheduler": "slurm", "cluster_name": "hpc"}}},
        )
        assert load_config(path).profiles["gpu"].cluster_name == "hpc"

    def test_absent_config_is_still_simply_empty(self, tmp_path):
        assert load_config(tmp_path / "config.yaml") == MolqConfig(profiles={})


class TestValidation:
    def test_missing_scheduler_raises(self, tmp_path):
        path = _write_config(tmp_path, {"profiles": {"bad": {"cluster_name": "c"}}})
        with pytest.raises(ConfigError):
            load_config(path)

    def test_missing_cluster_name_raises(self, tmp_path):
        path = _write_config(tmp_path, {"profiles": {"bad": {"scheduler": "local"}}})
        with pytest.raises(ConfigError):
            load_config(path)

    def test_unknown_scheduler_raises(self, tmp_path):
        path = _write_config(
            tmp_path,
            {"profiles": {"bad": {"scheduler": "bogus", "cluster_name": "c"}}},
        )
        with pytest.raises(ConfigError):
            load_config(path)

    @pytest.mark.parametrize("sched", ["local", "slurm", "pbs", "lsf"])
    def test_all_known_schedulers_accepted(self, tmp_path, sched):
        path = _write_config(
            tmp_path, {"profiles": {"p": {"scheduler": sched, "cluster_name": "c"}}}
        )
        p = load_config(path).profiles["p"]
        assert p.scheduler == sched


class TestLoadProfile:
    def test_returns_named_profile(self, tmp_path):
        path = _write_config(
            tmp_path,
            {"profiles": {"gpu": {"scheduler": "slurm", "cluster_name": "hpc"}}},
        )
        p = load_profile("gpu", path)
        assert isinstance(p, MolqProfile)
        assert p.name == "gpu"

    def test_missing_profile_raises(self, tmp_path):
        path = _write_config(
            tmp_path,
            {"profiles": {"gpu": {"scheduler": "slurm", "cluster_name": "hpc"}}},
        )
        with pytest.raises(ConfigError):
            load_profile("cpu", path)


class TestDefaults:
    def test_resources_defaults(self, tmp_path):
        path = _write_config(
            tmp_path,
            {
                "profiles": {
                    "p": {
                        "scheduler": "slurm",
                        "cluster_name": "c",
                        "defaults": {"resources": {"cpu_count": 8}},
                    }
                }
            },
        )
        p = load_config(path).profiles["p"]
        assert p.defaults.resources is not None
        assert p.defaults.resources.cpu_count == 8

    def test_scheduling_defaults(self, tmp_path):
        path = _write_config(
            tmp_path,
            {
                "profiles": {
                    "p": {
                        "scheduler": "slurm",
                        "cluster_name": "c",
                        "defaults": {"scheduling": {"partition": "gpu"}},
                    }
                }
            },
        )
        p = load_config(path).profiles["p"]
        assert p.defaults.scheduling is not None
        assert p.defaults.scheduling.partition == "gpu"

    def test_scheduling_defaults_legacy_queue_key(self, tmp_path):
        # Backward-compat: the legacy "queue" key still loads as partition
        path = _write_config(
            tmp_path,
            {
                "profiles": {
                    "p": {
                        "scheduler": "slurm",
                        "cluster_name": "c",
                        "defaults": {"scheduling": {"queue": "gpu"}},
                    }
                }
            },
        )
        p = load_config(path).profiles["p"]
        assert p.defaults.scheduling is not None
        assert p.defaults.scheduling.partition == "gpu"

    def test_no_defaults_gives_none_fields(self, tmp_path):
        path = _write_config(
            tmp_path,
            {"profiles": {"p": {"scheduler": "local", "cluster_name": "c"}}},
        )
        p = load_config(path).profiles["p"]
        assert p.defaults.resources is None
        assert p.defaults.scheduling is None
        assert p.defaults.execution is None


class TestRetry:
    def test_retry_policy_parsed(self, tmp_path):
        path = _write_config(
            tmp_path,
            {
                "profiles": {
                    "p": {
                        "scheduler": "slurm",
                        "cluster_name": "c",
                        "retry": {"max_attempts": 3},
                    }
                }
            },
        )
        p = load_config(path).profiles["p"]
        assert p.retry is not None
        assert p.retry.max_attempts == 3

    def test_no_retry_gives_none(self, tmp_path):
        path = _write_config(
            tmp_path,
            {"profiles": {"p": {"scheduler": "local", "cluster_name": "c"}}},
        )
        assert load_config(path).profiles["p"].retry is None


class TestRetention:
    def test_retention_defaults_applied(self, tmp_path):
        path = _write_config(
            tmp_path,
            {"profiles": {"p": {"scheduler": "local", "cluster_name": "c"}}},
        )
        p = load_config(path).profiles["p"]
        assert p.retention.keep_job_dirs_for_days == 30

    def test_retention_override(self, tmp_path):
        path = _write_config(
            tmp_path,
            {
                "profiles": {
                    "p": {
                        "scheduler": "local",
                        "cluster_name": "c",
                        "retention": {"keep_job_dirs_for_days": 7},
                    }
                }
            },
        )
        p = load_config(path).profiles["p"]
        assert p.retention.keep_job_dirs_for_days == 7


class TestProfileHost:
    """A profile can name an SSH destination, not just a scheduler."""

    def test_host_is_parsed(self, tmp_path):
        cfg = _write_config(
            tmp_path,
            {
                "profiles": {
                    "gpu": {
                        "scheduler": "slurm",
                        "cluster_name": "dardel",
                        "host": "dardel",
                    }
                }
            },
        )
        profile = load_profile("gpu", cfg)
        assert profile.host == "dardel"

    def test_host_defaults_to_none(self, tmp_path):
        cfg = _write_config(
            tmp_path,
            {"profiles": {"local": {"scheduler": "local", "cluster_name": "laptop"}}},
        )
        assert load_profile("local", cfg).host is None

    def test_cluster_from_profile_builds_ssh_transport(self, tmp_path):
        from molq.cluster import Cluster
        from molq.transport import SshTransport

        cfg = _write_config(
            tmp_path,
            {
                "profiles": {
                    "gpu": {
                        "scheduler": "slurm",
                        "cluster_name": "dardel",
                        "host": "dardel",
                    }
                }
            },
        )
        cluster = Cluster.from_profile("gpu", config_path=cfg)
        assert isinstance(cluster.transport, SshTransport)
        assert cluster.transport.options.host == "dardel"

    def test_cluster_from_profile_without_host_stays_local(self, tmp_path):
        from molq.cluster import Cluster
        from molq.transport import LocalTransport

        cfg = _write_config(
            tmp_path,
            {"profiles": {"local": {"scheduler": "local", "cluster_name": "laptop"}}},
        )
        cluster = Cluster.from_profile("local", config_path=cfg)
        assert isinstance(cluster.transport, LocalTransport)
