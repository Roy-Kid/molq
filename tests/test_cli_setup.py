"""Tests for molq.cli.setup — clusters, workspace, and plugins commands."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from molq.cli.main import app

runner = CliRunner()


@pytest.fixture
def ssh_config(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".ssh").mkdir(parents=True)
    (home / ".ssh" / "config").write_text(
        "Host dardel\n"
        "    HostName dardel.pdc.kth.se\n"
        "    User alice\n"
        "Host gpu-box\n"
        "    HostName gpu.example.org\n"
    )
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("MOLCRAFTS_HOME", str(tmp_path / "molcrafts"))
    return home / ".ssh" / "config"


@pytest.fixture
def profile_config(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "profiles:\n"
        "  gpu:\n"
        "    scheduler: slurm\n"
        "    cluster_name: dardel\n"
        "    host: dardel\n"
        "    jobs_dir: /scratch/alice/jobs\n"
    )
    return cfg


class TestClustersList:
    def test_lists_ssh_aliases(self, ssh_config):
        result = runner.invoke(
            app, ["clusters", "list", "--ssh-config", str(ssh_config)]
        )
        assert result.exit_code == 0
        assert "dardel" in result.output
        assert "gpu-box" in result.output

    def test_lists_profiles_with_their_host(self, ssh_config, profile_config):
        result = runner.invoke(
            app,
            [
                "clusters",
                "list",
                "--config",
                str(profile_config),
                "--ssh-config",
                str(ssh_config),
            ],
        )
        assert result.exit_code == 0
        assert "profile:gpu" in result.output

    def test_reports_when_nothing_is_discovered(self, tmp_path, monkeypatch):
        empty_home = tmp_path / "empty"
        (empty_home / ".ssh").mkdir(parents=True)
        monkeypatch.setenv("HOME", str(empty_home))
        result = runner.invoke(
            app,
            ["clusters", "list", "--ssh-config", str(empty_home / ".ssh" / "missing")],
        )
        assert result.exit_code == 0
        assert "No clusters discovered" in result.output


class TestClustersShow:
    def test_shows_profile_details(self, ssh_config, profile_config):
        result = runner.invoke(
            app, ["clusters", "show", "gpu", "--config", str(profile_config)]
        )
        assert result.exit_code == 0
        assert "Profile:" in result.output
        assert "slurm" in result.output
        assert "dardel" in result.output

    def test_profile_lookup_by_cluster_name(self, ssh_config, profile_config):
        result = runner.invoke(
            app, ["clusters", "show", "dardel", "--config", str(profile_config)]
        )
        assert result.exit_code == 0
        assert "Profile:" in result.output

    def test_falls_back_to_ssh_alias(self, ssh_config):
        result = runner.invoke(
            app, ["clusters", "show", "gpu-box", "--ssh-config", str(ssh_config)]
        )
        assert result.exit_code == 0
        assert "SSH alias:" in result.output


class TestWorkspaceCommands:
    def test_unknown_cluster_alias_is_rejected(self, ssh_config, tmp_path):
        result = runner.invoke(
            app,
            ["workspace", "list", "--cluster", "not-a-host", "--path", "/tmp"],
        )
        assert result.exit_code != 0
        assert "not a Host alias" in result.output

    def test_list_uses_local_cluster_by_default(self, ssh_config, tmp_path):
        target = tmp_path / "ws"
        target.mkdir()
        (target / "a.txt").write_text("a")
        (target / "b.txt").write_text("b")

        result = runner.invoke(app, ["workspace", "list", "--path", str(target)])
        assert result.exit_code == 0
        assert "a.txt" in result.output
        assert "b.txt" in result.output

    def test_list_reports_empty_directory(self, ssh_config, tmp_path):
        target = tmp_path / "empty-ws"
        target.mkdir()
        result = runner.invoke(app, ["workspace", "list", "--path", str(target)])
        assert result.exit_code == 0
        assert "(empty)" in result.output

    def test_sync_push_copies_files(self, ssh_config, tmp_path):
        source = tmp_path / "src"
        source.mkdir()
        (source / "data.txt").write_text("payload")
        dest = tmp_path / "dest"

        result = runner.invoke(
            app, ["workspace", "sync", str(source), "--path", str(dest)]
        )
        assert result.exit_code == 0, result.output
        assert "Pushed" in result.output
        assert (dest / "data.txt").read_text() == "payload"

    def test_sync_dry_run_copies_nothing(self, ssh_config, tmp_path):
        source = tmp_path / "src"
        source.mkdir()
        (source / "data.txt").write_text("payload")
        dest = tmp_path / "dest"

        result = runner.invoke(
            app,
            ["workspace", "sync", str(source), "--path", str(dest), "--dry-run"],
        )
        assert result.exit_code == 0
        assert "Would push" in result.output
        assert not (dest / "data.txt").exists()

    def test_sync_pull_copies_back(self, ssh_config, tmp_path):
        remote = tmp_path / "remote"
        remote.mkdir()
        (remote / "result.txt").write_text("output")
        local = tmp_path / "local"

        result = runner.invoke(
            app,
            ["workspace", "sync", str(local), "--path", str(remote), "--pull"],
        )
        assert result.exit_code == 0, result.output
        assert "Pulled" in result.output
        assert (local / "result.txt").read_text() == "output"


class TestPluginsList:
    def test_lists_builtin_plugins(self, ssh_config, tmp_path):
        missing = tmp_path / "nope.yaml"
        result = runner.invoke(app, ["plugins", "list", "--config", str(missing)])
        assert result.exit_code == 0
        assert "nerve" in result.output

    def test_notes_daemon_default_when_no_plugin_table(self, ssh_config, tmp_path):
        missing = tmp_path / "nope.yaml"
        result = runner.invoke(app, ["plugins", "list", "--config", str(missing)])
        assert result.exit_code == 0
        assert "default" in result.output

    def test_disabled_plugin_shows_as_disabled(self, ssh_config, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text("plugins:\n  nerve:\n    enabled: false\n")
        result = runner.invoke(app, ["plugins", "list", "--config", str(cfg)])
        assert result.exit_code == 0
        assert "disabled" in result.output

    def test_enabled_plugin_shows_as_enabled(self, ssh_config, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text("plugins:\n  nerve:\n    enabled: true\n")
        result = runner.invoke(app, ["plugins", "list", "--config", str(cfg)])
        assert result.exit_code == 0
        assert "enabled" in result.output

    def test_reports_when_no_plugins_available(self, ssh_config, tmp_path):
        with patch("molq.plugin.available_plugins", return_value={}):
            result = runner.invoke(
                app, ["plugins", "list", "--config", str(tmp_path / "none.yaml")]
            )
        assert result.exit_code == 0
        assert "No plugins discovered" in result.output


class TestResolveCluster:
    def test_profile_host_becomes_ssh_transport(self, ssh_config, profile_config):
        from molq.cli.setup import _resolve_cluster
        from molq.transport import SshTransport

        cluster = _resolve_cluster(None, "gpu", str(profile_config))
        assert isinstance(cluster.transport, SshTransport)

    def test_no_cluster_and_no_profile_is_local(self, ssh_config):
        from molq.cli.setup import _resolve_cluster
        from molq.transport import LocalTransport

        cluster = _resolve_cluster(None, None, None)
        assert isinstance(cluster.transport, LocalTransport)

    def test_known_alias_builds_ssh(self, ssh_config):
        from molq.cli.setup import _resolve_cluster
        from molq.transport import SshTransport

        cluster = _resolve_cluster("dardel", None, None)
        assert isinstance(cluster.transport, SshTransport)


class TestProfileDestinations:
    def test_local_profile_is_labelled_local(self, tmp_path):
        from molq.cli.setup import _profile_destinations

        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            "profiles:\n  laptop:\n    scheduler: local\n    cluster_name: laptop\n"
        )
        rows = _profile_destinations(str(cfg))
        assert rows[0]["target"] == "(local)"

    def test_remote_profile_shows_host(self, profile_config):
        from molq.cli.setup import _profile_destinations

        rows = _profile_destinations(str(profile_config))
        assert rows[0]["target"] == "dardel"


class TestSshDestinations:
    def test_returns_alias_rows(self, ssh_config):
        from molq.cli.setup import _ssh_destinations

        rows = _ssh_destinations(str(ssh_config))
        names = {row["name"] for row in rows}
        assert {"dardel", "gpu-box"} <= names
        assert all(row["source"] == "ssh_config" for row in rows)


class TestClustersShowErrors:
    def test_missing_ssh_binary_exits_nonzero(self, ssh_config):
        # The command resolves the name through the molq package namespace.
        with patch("molq.resolve_ssh_host", side_effect=OSError("ssh not found")):
            result = runner.invoke(app, ["clusters", "show", "whatever"])
        assert result.exit_code == 1


class TestWorkspaceSyncWithProfile:
    def test_profile_drives_the_destination(self, ssh_config, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            "profiles:\n  local:\n    scheduler: local\n    cluster_name: laptop\n"
        )
        source = tmp_path / "src"
        source.mkdir()
        (source / "f.txt").write_text("x")
        dest = tmp_path / "dest"

        result = runner.invoke(
            app,
            [
                "workspace",
                "sync",
                str(source),
                "--profile",
                "local",
                "--config",
                str(cfg),
                "--path",
                str(dest),
            ],
        )
        assert result.exit_code == 0, result.output
        assert (dest / "f.txt").exists()
