"""Transport abstraction — where shell commands and file ops actually run.

The two-axis cluster model (Transport × Scheduler) treats *where* commands run
as orthogonal to *how* jobs are dispatched.  ``LocalTransport`` runs commands
on this host via :mod:`subprocess` and uses :mod:`pathlib` for file ops.
``SshTransport`` re-routes the same calls through the system OpenSSH client
(``ssh`` / ``rsync`` / ``scp``).  Schedulers see only a :class:`Transport`,
never the location.

Zero new Python deps: SSH support shells out to whatever ``ssh`` and ``rsync``
the user has installed.  This inherits ``~/.ssh/config``, agents, ProxyJump,
ControlMaster and Kerberos for free.

The module is intentionally narrow.  It exposes only the operations existing
schedulers and the :class:`~molq.submitor.Submitor` actually perform; new
methods should be added as concrete schedulers need them, not speculatively.
"""

from __future__ import annotations

import base64
import os
import shlex
import shutil
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from molq._log import get_logger
from molq.errors import MolqError
from molq.options import SshTransportOptions

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Errors and result type
# ---------------------------------------------------------------------------


class TransportError(MolqError):
    """A transport-level operation failed.

    Wraps the underlying exception (network, rsync, ssh) so callers can catch
    one type regardless of which transport raised it.
    """


@dataclass(frozen=True)
class CommandResult:
    """Result of :meth:`Transport.run`.

    Mirrors the subset of :class:`subprocess.CompletedProcess` schedulers use.
    ``stdout``/``stderr`` are decoded text (always — schedulers are line-based).
    """

    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    def check_returncode(self) -> None:
        """Raise :class:`subprocess.CalledProcessError` if the command failed.

        Provided so callers can opt into the same control flow as
        ``subprocess.run(..., check=True)`` regardless of transport.
        """
        if self.returncode != 0:
            raise subprocess.CalledProcessError(
                self.returncode, list(self.argv), self.stdout, self.stderr
            )


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class Transport(Protocol):
    """Where commands and file ops execute.

    Implementations must be **idempotent** for ``mkdir(parents=True)`` and
    safe to call from multiple threads.  All path arguments are absolute and
    interpreted on the *transport's* filesystem (local for
    :class:`LocalTransport`, remote for :class:`SshTransport`).
    """

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: str | None = None,
        env: Mapping[str, str] | None = None,
        input: str | None = None,
        timeout: float | None = None,
    ) -> CommandResult:
        """Execute *argv* and return its result."""
        ...

    def read_text(self, path: str) -> str: ...
    def read_bytes(self, path: str) -> bytes: ...
    def write_text(self, path: str, data: str, *, mode: int = 0o600) -> None: ...
    def write_bytes(self, path: str, data: bytes, *, mode: int = 0o600) -> None: ...
    def exists(self, path: str) -> bool: ...
    def is_dir(self, path: str) -> bool: ...
    def is_file(self, path: str) -> bool: ...
    def mkdir(
        self, path: str, *, parents: bool = True, exist_ok: bool = True
    ) -> None: ...
    def chmod(self, path: str, mode: int) -> None: ...
    def remove(self, path: str, *, recursive: bool = False) -> None: ...
    def rename(self, src: str, dst: str) -> None: ...
    def copy(self, src: str, dst: str) -> None: ...
    def copytree(self, src: str, dst: str) -> None: ...
    def touch(self, path: str) -> None: ...
    def symlink(self, src: str, dst: str) -> None: ...
    def listdir(self, path: str) -> list[str]: ...
    def stat(self, path: str) -> dict[str, object]: ...
    def getsize(self, path: str) -> int: ...
    def upload(
        self,
        local: str,
        remote: str,
        *,
        recursive: bool = False,
        exclude: Sequence[str] = (),
    ) -> None: ...
    def download(
        self,
        remote: str,
        local: str,
        *,
        recursive: bool = False,
        exclude: Sequence[str] = (),
    ) -> None: ...


# ---------------------------------------------------------------------------
# LocalTransport
# ---------------------------------------------------------------------------


class LocalTransport:
    """Run commands and file ops on the current host.

    Direct delegation to :mod:`subprocess` and :mod:`pathlib`.  This is the
    default — installing ``Transport`` infrastructure does not change any
    existing behaviour for callers that don't pass a non-default transport.
    """

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: str | None = None,
        env: Mapping[str, str] | None = None,
        input: str | None = None,
        timeout: float | None = None,
    ) -> CommandResult:
        try:
            proc = subprocess.run(
                list(argv),
                cwd=cwd,
                env=dict(env) if env is not None else None,
                input=input,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise TransportError(
                f"local command timed out: {argv[0] if argv else '<empty>'}",
                argv=list(argv),
                timeout=timeout,
            ) from exc
        except FileNotFoundError as exc:
            raise TransportError(
                f"local command not found: {argv[0] if argv else '<empty>'}",
                argv=list(argv),
            ) from exc
        return CommandResult(
            argv=tuple(argv),
            returncode=proc.returncode,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
        )

    def read_text(self, path: str) -> str:
        return Path(path).read_text()

    def read_bytes(self, path: str) -> bytes:
        return Path(path).read_bytes()

    def write_text(self, path: str, data: str, *, mode: int = 0o600) -> None:
        self.write_bytes(path, data.encode("utf-8"), mode=mode)

    def write_bytes(self, path: str, data: bytes, *, mode: int = 0o600) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Atomic: write tmp + rename, mirroring the workspace's atomic-write idiom.
        fd, tmp = tempfile.mkstemp(
            dir=str(target.parent), prefix=f".{target.name}.", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
            os.chmod(tmp, mode)
            os.replace(tmp, target)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def exists(self, path: str) -> bool:
        return Path(path).exists()

    def mkdir(self, path: str, *, parents: bool = True, exist_ok: bool = True) -> None:
        Path(path).mkdir(parents=parents, exist_ok=exist_ok)

    def chmod(self, path: str, mode: int) -> None:
        os.chmod(path, mode)

    def remove(self, path: str, *, recursive: bool = False) -> None:
        target = Path(path)
        if not target.exists():
            return
        if recursive and target.is_dir():
            shutil.rmtree(target)
        elif target.is_dir():
            target.rmdir()
        else:
            target.unlink()

    def upload(
        self,
        local: str,
        remote: str,
        *,
        recursive: bool = False,
        exclude: Sequence[str] = (),
    ) -> None:
        # For LocalTransport upload == local copy.  Direction is purely conventional.
        _local_copy(local, remote, recursive=recursive, exclude=exclude)

    def download(
        self,
        remote: str,
        local: str,
        *,
        recursive: bool = False,
        exclude: Sequence[str] = (),
    ) -> None:
        _local_copy(remote, local, recursive=recursive, exclude=exclude)

    def is_dir(self, path: str) -> bool:
        return Path(path).is_dir()

    def is_file(self, path: str) -> bool:
        return Path(path).is_file()

    def rename(self, src: str, dst: str) -> None:
        os.rename(src, dst)

    def copy(self, src: str, dst: str) -> None:
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    def copytree(self, src: str, dst: str) -> None:
        shutil.copytree(src, dst)

    def touch(self, path: str) -> None:
        Path(path).touch()

    def symlink(self, src: str, dst: str) -> None:
        Path(dst).symlink_to(src)

    def listdir(self, path: str) -> list[str]:
        return [p.name for p in Path(path).iterdir()]

    def stat(self, path: str) -> dict[str, object]:
        st = os.stat(path)
        return {
            "size": st.st_size,
            "mtime": st.st_mtime,
            "is_dir": Path(path).is_dir(),
            "is_file": Path(path).is_file(),
        }

    def getsize(self, path: str) -> int:
        return os.path.getsize(path)


def _local_copy(src: str, dst: str, *, recursive: bool, exclude: Sequence[str]) -> None:
    src_path = Path(src)
    dst_path = Path(dst)
    if not src_path.exists():
        raise FileNotFoundError(src)
    if src_path.resolve() == dst_path.resolve():
        return
    if src_path.is_dir():
        if not recursive:
            raise IsADirectoryError(f"{src} is a directory; pass recursive=True")
        ignore = shutil.ignore_patterns(*exclude) if exclude else None
        # copytree requires dst not to exist; mirror rsync's "merge into existing" semantics
        # by walking and copying when the destination already exists.
        if dst_path.exists():
            _merge_copy(src_path, dst_path, exclude=set(exclude))
        else:
            shutil.copytree(src_path, dst_path, ignore=ignore, dirs_exist_ok=False)
    else:
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, dst_path)


def _merge_copy(src: Path, dst: Path, *, exclude: set[str]) -> None:
    for root, dirs, files in os.walk(src):
        rel = Path(root).relative_to(src)
        target_dir = dst / rel
        target_dir.mkdir(parents=True, exist_ok=True)
        # Prune excluded dirs in place so os.walk skips them.
        dirs[:] = [d for d in dirs if d not in exclude]
        for name in files:
            if name in exclude:
                continue
            shutil.copy2(Path(root) / name, target_dir / name)


# ---------------------------------------------------------------------------
# SshTransport
# ---------------------------------------------------------------------------

# Unix domain sockets cap out near 104 bytes on macOS / 108 on Linux, and
# OpenSSH expands ``%C`` to a 40-character hash.  Budget for the expansion so
# we silently skip multiplexing rather than making ssh warn on every call.
_SOCKET_PATH_BUDGET = 100
_CONTROL_TOKEN_GROWTH = 38  # len("%C") -> 40

# Exit status a remote helper script uses to report "path does not exist",
# chosen to not collide with the shell's own conventional codes (1, 2, 126-165).
_ENOENT_EXIT = 44


def _ssh_control_path() -> str | None:
    """Return a ControlPath template, or ``None`` if one can't be provided.

    Sockets live directly in ``~/.ssh`` as ``molq-<hash>``, the same flat
    layout other OpenSSH tooling uses — one well-known private directory per
    user rather than a molq-specific subdirectory.  ``%C`` is a hash of the
    connection tuple, so distinct hosts never share a socket.
    """
    uid = getattr(os, "getuid", lambda: 0)()
    ssh_dir = Path.home() / ".ssh"
    template = str(ssh_dir / "molq-%C")
    if len(template) + _CONTROL_TOKEN_GROWTH > _SOCKET_PATH_BUDGET:
        logger.debug(f"ssh ControlPath would exceed socket limit: {template}")
        return None
    try:
        ssh_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        # Refuse a directory we do not own — a socket somewhere another user
        # controls would let them observe or hijack the multiplexed session.
        if ssh_dir.stat().st_uid != uid:
            return None
    except OSError:
        return None
    return template


@dataclass(frozen=True)
class SshTransport:
    """Run commands and file ops on a remote host via OpenSSH and rsync.

    Builds standard ``ssh`` and ``rsync`` argv from
    :class:`~molq.options.SshTransportOptions` and shells out via
    :mod:`subprocess`.  ``BatchMode=yes`` is forced so molq never blocks on a
    password prompt — authentication must succeed via key, agent, or
    GSSAPI/Kerberos.

    Shell-level operations (``cat``, ``test``, ``mkdir``, ``chmod``) are used
    for small file operations to avoid spawning ``rsync`` round-trips for
    things like reading a 1-byte ``.exit_code`` file.
    """

    options: SshTransportOptions
    _ssh_bin: str = field(default="ssh", repr=False)
    _rsync_bin: str = field(default="rsync", repr=False)

    # ── helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _quote_remote_path(path: str) -> str:
        """Shell-quote *path* while preserving ``~`` tilde expansion for the remote shell.

        ``shlex.quote`` wraps everything in single quotes, which prevents the
        remote shell from expanding ``~``.  This helper keeps the tilde prefix
        outside the quoted portion so ``~/work`` expands to the remote home.
        """
        if path.startswith("~/"):
            return "~/" + shlex.quote(path[2:])
        if path == "~":
            return "~"
        return shlex.quote(path)

    def _mux_opts(self) -> list[str]:
        """Connection-multiplexing options, or ``[]`` when unavailable.

        A single molq job performs many small remote operations (write the
        wrapper, mkdir, poll ``.exit_code``, read logs).  Without a shared
        master connection each one is a fresh TCP + auth handshake, which
        dominates wall-clock on any real cluster — and multiplies on hosts
        with Kerberos or hardware-token auth.
        """
        if not self.options.control_master:
            return []
        control_path = _ssh_control_path()
        if control_path is None:
            return []
        return [
            "-o",
            "ControlMaster=auto",
            "-o",
            f"ControlPath={control_path}",
            "-o",
            f"ControlPersist={self.options.control_persist}",
        ]

    def _ssh_argv(self) -> list[str]:
        argv: list[str] = [
            self._ssh_bin,
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-o",
            "RemoteCommand=none",
            "-o",
            "RequestTTY=no",
            "-o",
            f"ConnectTimeout={self.options.connect_timeout}",
        ]
        argv += self._mux_opts()
        if self.options.port is not None:
            argv += ["-p", str(self.options.port)]
        if self.options.identity_file:
            argv += ["-i", self.options.identity_file]
        argv += list(self.options.ssh_opts)
        argv.append(self.options.host)
        return argv

    def _ssh_e_arg(self) -> str:
        """Build the ``-e`` argument for rsync that injects our ssh options."""
        parts: list[str] = [
            self._ssh_bin,
            "-o",
            "BatchMode=yes",
            "-o",
            "RemoteCommand=none",
            "-o",
            "RequestTTY=no",
            "-o",
            f"ConnectTimeout={self.options.connect_timeout}",
        ]
        parts += self._mux_opts()
        if self.options.port is not None:
            parts += ["-p", str(self.options.port)]
        if self.options.identity_file:
            parts += ["-i", self.options.identity_file]
        parts += list(self.options.ssh_opts)
        return " ".join(shlex.quote(p) for p in parts)

    def _remote_target(self, path: str) -> str:
        return f"{self.options.host}:{path}"

    def _shell(
        self, remote_cmd: str, *, input: str | None = None, timeout: float | None = None
    ) -> CommandResult:
        """Run *remote_cmd* (a single shell string) on the remote via ssh."""
        argv = self._ssh_argv() + ["--", remote_cmd]
        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                check=False,
                input=input,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise TransportError(
                f"ssh command timed out on {self.options.host}",
                remote_cmd=remote_cmd,
                timeout=timeout,
            ) from exc
        except FileNotFoundError as exc:
            raise TransportError(
                "ssh binary not found — install OpenSSH client",
                ssh_bin=self._ssh_bin,
            ) from exc
        return CommandResult(
            argv=tuple(argv),
            returncode=proc.returncode,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
        )

    # ── Transport surface ───────────────────────────────────────────────────

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: str | None = None,
        env: Mapping[str, str] | None = None,
        input: str | None = None,
        timeout: float | None = None,
    ) -> CommandResult:
        # Build a quoted shell string to ship over ssh so the remote shell
        # parses the argv consistently regardless of local shell quoting.
        parts: list[str] = []
        if env:
            for k, v in env.items():
                parts.append(f"{shlex.quote(k)}={shlex.quote(v)}")
        if cwd:
            parts += ["cd", self._quote_remote_path(cwd), "&&"]
        parts += [self._quote_remote_path(a) for a in argv]
        remote_cmd = " ".join(parts)
        return self._shell(remote_cmd, input=input, timeout=timeout)

    def read_text(self, path: str) -> str:
        return self.read_bytes(path).decode("utf-8")

    def read_bytes(self, path: str) -> bytes:
        # Use base64 so we don't have to worry about embedded NULs / non-UTF8.
        # Feed it on stdin rather than as an argument: BSD/macOS base64 takes
        # only -i/stdin, so `base64 -- <file>` fails against a macOS host.
        result = self._shell(f"base64 < {self._quote_remote_path(path)}")
        if result.returncode != 0:
            if (
                "No such file" in result.stderr
                or "cannot open" in result.stderr.lower()
            ):
                raise FileNotFoundError(path)
            raise TransportError(
                f"remote read failed: {path}",
                returncode=result.returncode,
                stderr=result.stderr,
            )
        return base64.b64decode(result.stdout)

    def write_text(self, path: str, data: str, *, mode: int = 0o600) -> None:
        self.write_bytes(path, data.encode("utf-8"), mode=mode)

    def write_bytes(self, path: str, data: bytes, *, mode: int = 0o600) -> None:
        # Atomic-ish: write to .tmp and rename.  Use base64 over stdin to
        # carry arbitrary bytes through ssh cleanly.
        encoded = base64.b64encode(data).decode("ascii")
        q_path = self._quote_remote_path(path)
        q_tmp = self._quote_remote_path(f"{path}.tmp")
        remote_cmd = (
            f"base64 -d > {q_tmp} && chmod {mode:o} {q_tmp} && mv {q_tmp} {q_path}"
        )
        result = self._shell(remote_cmd, input=encoded)
        if result.returncode != 0:
            raise TransportError(
                f"remote write failed: {path}",
                returncode=result.returncode,
                stderr=result.stderr,
            )

    def exists(self, path: str) -> bool:
        result = self._shell(f"test -e {self._quote_remote_path(path)}")
        if result.returncode == 0:
            return True
        if result.returncode == 1:
            return False
        raise TransportError(
            f"remote test -e failed: {path}",
            returncode=result.returncode,
            stderr=result.stderr,
        )

    def mkdir(self, path: str, *, parents: bool = True, exist_ok: bool = True) -> None:
        flag = "-p" if parents or exist_ok else ""
        cmd = f"mkdir {flag} {self._quote_remote_path(path)}".strip()
        result = self._shell(cmd)
        if result.returncode != 0:
            raise TransportError(
                f"remote mkdir failed: {path}",
                returncode=result.returncode,
                stderr=result.stderr,
            )

    def chmod(self, path: str, mode: int) -> None:
        result = self._shell(f"chmod {mode:o} {self._quote_remote_path(path)}")
        if result.returncode != 0:
            raise TransportError(
                f"remote chmod failed: {path}",
                returncode=result.returncode,
                stderr=result.stderr,
            )

    def remove(self, path: str, *, recursive: bool = False) -> None:
        flag = "-rf" if recursive else "-f"
        result = self._shell(f"rm {flag} -- {self._quote_remote_path(path)}")
        if result.returncode != 0:
            raise TransportError(
                f"remote remove failed: {path}",
                returncode=result.returncode,
                stderr=result.stderr,
            )

    def upload(
        self,
        local: str,
        remote: str,
        *,
        recursive: bool = False,
        exclude: Sequence[str] = (),
    ) -> None:
        self._rsync(
            local, self._remote_target(remote), recursive=recursive, exclude=exclude
        )

    def download(
        self,
        remote: str,
        local: str,
        *,
        recursive: bool = False,
        exclude: Sequence[str] = (),
    ) -> None:
        # Ensure the local parent exists so rsync doesn't refuse.
        Path(local).parent.mkdir(parents=True, exist_ok=True)
        self._rsync(
            self._remote_target(remote), local, recursive=recursive, exclude=exclude
        )

    def is_dir(self, path: str) -> bool:
        result = self._shell(f"test -d {self._quote_remote_path(path)}")
        return result.returncode == 0

    def is_file(self, path: str) -> bool:
        result = self._shell(f"test -f {self._quote_remote_path(path)}")
        return result.returncode == 0

    def rename(self, src: str, dst: str) -> None:
        result = self._shell(
            f"mv -- {self._quote_remote_path(src)} {self._quote_remote_path(dst)}"
        )
        if result.returncode != 0:
            raise TransportError(f"remote rename failed: {src} -> {dst}")

    def copy(self, src: str, dst: str) -> None:
        result = self._shell(
            f"cp -- {self._quote_remote_path(src)} {self._quote_remote_path(dst)}"
        )
        if result.returncode != 0:
            raise TransportError(f"remote copy failed: {src} -> {dst}")

    def copytree(self, src: str, dst: str) -> None:
        result = self._shell(
            f"cp -r -- {self._quote_remote_path(src)} {self._quote_remote_path(dst)}"
        )
        if result.returncode != 0:
            raise TransportError(f"remote copytree failed: {src} -> {dst}")

    def touch(self, path: str) -> None:
        result = self._shell(f"touch -- {self._quote_remote_path(path)}")
        if result.returncode != 0:
            raise TransportError(f"remote touch failed: {path}")

    def symlink(self, src: str, dst: str) -> None:
        result = self._shell(
            f"ln -s -- {self._quote_remote_path(src)} {self._quote_remote_path(dst)}"
        )
        if result.returncode != 0:
            raise TransportError(f"remote symlink failed: {src} -> {dst}")

    def listdir(self, path: str) -> list[str]:
        result = self._shell(f"ls -1A -- {self._quote_remote_path(path)}")
        if result.returncode != 0:
            return []
        return [line for line in result.stdout.strip().split("\n") if line]

    def stat(self, path: str) -> dict[str, object]:
        q = self._quote_remote_path(path)
        # GNU coreutils first, BSD/macOS second.  Deliberately not python3:
        # HPC login nodes routinely keep Python behind `module load`, so it is
        # not on the default PATH of a non-interactive ssh session.
        remote_cmd = (
            f"test -e {q} || exit {_ENOENT_EXIT}; "
            f"sz=$(stat -c %s {q} 2>/dev/null || stat -f %z {q}); "
            f"mt=$(stat -c %Y {q} 2>/dev/null || stat -f %m {q}); "
            f"d=0; f=0; "
            f"if [ -d {q} ]; then d=1; fi; "
            f"if [ -f {q} ]; then f=1; fi; "
            f'printf "%s %s %s %s\\n" "$sz" "$mt" "$d" "$f"'
        )
        result = self._shell(remote_cmd)
        if result.returncode == _ENOENT_EXIT:
            raise FileNotFoundError(path)
        if result.returncode != 0:
            raise TransportError(
                f"remote stat failed: {path}",
                returncode=result.returncode,
                stderr=result.stderr,
            )
        try:
            size, mtime, is_dir, is_file = result.stdout.split()
            return {
                "size": int(size),
                "mtime": float(mtime),
                "is_dir": is_dir == "1",
                "is_file": is_file == "1",
            }
        except ValueError as exc:
            raise TransportError(
                f"unparseable remote stat output for {path}: {result.stdout!r}"
            ) from exc

    def getsize(self, path: str) -> int:
        q = self._quote_remote_path(path)
        remote_cmd = (
            f"test -e {q} || exit {_ENOENT_EXIT}; "
            f"stat -c %s {q} 2>/dev/null || stat -f %z {q}"
        )
        result = self._shell(remote_cmd)
        if result.returncode == _ENOENT_EXIT:
            raise FileNotFoundError(path)
        if result.returncode != 0:
            raise TransportError(
                f"remote getsize failed: {path}",
                returncode=result.returncode,
                stderr=result.stderr,
            )
        try:
            return int(result.stdout.strip())
        except ValueError as exc:
            raise TransportError(
                f"unparseable remote size for {path}: {result.stdout!r}"
            ) from exc

    def _rsync(
        self, src: str, dst: str, *, recursive: bool, exclude: Sequence[str]
    ) -> None:
        argv: list[str] = [self._rsync_bin]
        argv += list(self.options.rsync_opts)
        if (
            recursive
            and "-a" not in self.options.rsync_opts
            and "-r" not in self.options.rsync_opts
        ):
            argv.append("-r")
        for pattern in exclude:
            argv += ["--exclude", pattern]
        argv += ["-e", self._ssh_e_arg()]
        # rsync directory semantics: trailing slash on source means "contents of"
        # — we want that for recursive copies so the destination is the directory
        # itself, matching shutil.copytree behaviour.
        if recursive and not src.endswith("/") and ":" not in Path(src).name:
            src = src + "/"
        argv += [src, dst]
        try:
            proc = subprocess.run(
                argv, capture_output=True, text=True, check=False, timeout=None
            )
        except FileNotFoundError as exc:
            raise TransportError(
                "rsync binary not found — install rsync",
                rsync_bin=self._rsync_bin,
            ) from exc
        if proc.returncode != 0:
            raise TransportError(
                f"rsync failed: {src} -> {dst}",
                returncode=proc.returncode,
                stderr=proc.stderr or "",
            )


__all__ = [
    "CommandResult",
    "LocalTransport",
    "SshTransport",
    "Transport",
    "TransportError",
]
