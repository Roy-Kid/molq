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
import contextlib
import os
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from functools import lru_cache
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


@lru_cache(maxsize=128)
def _host_configures_control_path(host: str, ssh_bin: str = "ssh") -> bool:
    """True when ``~/.ssh/config`` already sets a ControlPath for *host*.

    Asks OpenSSH itself (``ssh -G``) rather than parsing the config, so
    ``Match`` blocks, ``Include``, and the system-wide config are all honoured.
    Cached: this runs once per host, not once per remote operation.

    A failure to ask (no ssh binary, bad flags) is reported as "not
    configured" — molq then falls back to its own socket, which is the same
    behaviour as before the check existed.
    """
    try:
        proc = subprocess.run(
            [ssh_bin, "-G", host],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if proc.returncode != 0:
        return False
    for line in proc.stdout.splitlines():
        key, _, value = line.partition(" ")
        if key.lower() == "controlpath":
            configured = value.strip()
            return bool(configured) and configured.lower() != "none"
    return False


def _auth_failure_hint(stderr: str, host: str) -> str | None:
    """Return a user-facing hint when *stderr* looks like SSH auth failure."""
    text = (stderr or "").lower()
    needles = (
        "permission denied",
        "authentication failed",
        "too many authentication",
        "no more authentication methods",
        "connection closed by",
        "kex_exchange_identification",
        "not allowed at this time",
        "cannot authenticate",
    )
    if not any(n in text for n in needles):
        return None
    return (
        f"SSH to {host!r} needs an interactive login (verification code / 2FA). "
        f"From a terminal run:  ssh {host}   or   molexp connect -ws {host}:/path  "
        f"— or enter the code in the molexp web UI connect dialog. "
        f"ControlMaster reuses the session afterward."
    )


def _write_askpass_helper() -> Path:
    """Create a short-lived executable that prints ``$MOLEXP_SSH_SECRET``.

    OpenSSH invokes ``SSH_ASKPASS`` with the prompt as argv[1] when no TTY
    is available (and ``SSH_ASKPASS_REQUIRE=force``).  The secret is never
    written into the script itself — only read from the environment at
    askpass time, then discarded with the parent process env.
    """
    fd, name = tempfile.mkstemp(prefix="molexp-askpass-", suffix=".sh")
    path = Path(name)
    try:
        os.close(fd)
        path.write_text(
            "#!/bin/sh\n"
            "# molexp ephemeral SSH_ASKPASS helper — do not reuse\n"
            'printf %s "${MOLEXP_SSH_SECRET-}"\n',
            encoding="utf-8",
        )
        path.chmod(stat.S_IRWXU)  # 0o700
    except Exception:
        with contextlib.suppress(OSError):
            path.unlink(missing_ok=True)
        raise
    return path


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
    :mod:`subprocess`.  Routine ops force ``BatchMode=yes`` so a background
    job never blocks on a password / OTP prompt — authentication must
    already succeed via key, agent, GSSAPI/Kerberos, **or a live ControlMaster
    multiplex socket**.

    HPC sites that require a one-time verification code (keyboard-interactive
    2FA / TOTP) cannot authenticate under BatchMode.  Call :meth:`login`
    once from a TTY (or run interactive ``ssh <host>`` with the same
    ``ControlPath``) to open the master; subsequent BatchMode calls ride
    that socket for the duration of ``ControlPersist``.

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

        Three cases, in order:

        1. ``control_path`` set explicitly — use it verbatim.
        2. ``~/.ssh/config`` already defines a ``ControlPath`` for this host —
           inherit it by passing no path at all.  molq then shares the very
           same socket as your own ``ssh``: whichever runs first becomes the
           master and the other rides along.
        3. Nothing configured — supply molq's own ``~/.ssh/molq-%C``.
        """
        if not self.options.control_master:
            return []

        # ControlMaster=auto in every case: reuse a live master, become one
        # otherwise.  Without it a configured ControlPath alone would only
        # *use* a master someone else started.
        opts = ["-o", "ControlMaster=auto"]

        if self.options.control_path:
            return opts + [
                "-o",
                f"ControlPath={self.options.control_path}",
                "-o",
                f"ControlPersist={self.options.control_persist}",
            ]

        if _host_configures_control_path(self.options.host, self._ssh_bin):
            # Inherit path *and* persistence from the user's config — their
            # ControlPersist governs a socket they also use.
            return opts

        control_path = _ssh_control_path()
        if control_path is None:
            return []
        return opts + [
            "-o",
            f"ControlPath={control_path}",
            "-o",
            f"ControlPersist={self.options.control_persist}",
        ]

    def _ssh_argv(self, *, batch_mode: bool = True) -> list[str]:
        """Build the OpenSSH client argv for this transport.

        Args:
            batch_mode: When True (default), force ``BatchMode=yes`` so ops
                never block on password/OTP prompts.  When False, allow
                keyboard-interactive / password so :meth:`login` can collect
                a verification code on a TTY.
        """
        argv: list[str] = [
            self._ssh_bin,
            "-o",
            "BatchMode=yes" if batch_mode else "BatchMode=no",
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

    def is_master_alive(self) -> bool:
        """True when an OpenSSH ControlMaster for this host is accepting clients.

        Uses ``ssh -O check``.  When multiplexing is disabled, always returns
        False (there is no reusable master).
        """
        if not self.options.control_master:
            return False
        argv: list[str] = [self._ssh_bin]
        argv += self._mux_opts()
        if self.options.port is not None:
            argv += ["-p", str(self.options.port)]
        if self.options.identity_file:
            argv += ["-i", self.options.identity_file]
        argv += list(self.options.ssh_opts)
        argv += ["-O", "check", self.options.host]
        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                check=False,
                timeout=max(5, self.options.connect_timeout),
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return proc.returncode == 0

    def login(self, *, force: bool = False, timeout: float | None = None) -> None:
        """Interactively authenticate and open a ControlMaster multiplex socket.

        For hosts that demand a one-time verification code (keyboard-interactive
        2FA / TOTP), this is the TTY path: runs ``ssh`` with ``BatchMode=no``
        on the caller's terminal so the user can type the code.  The master
        stays alive for ``ControlPersist``; subsequent BatchMode ops attach
        without re-prompting.

        When no TTY is available (server / agent), use
        :meth:`login_with_code` instead and supply the code from a UI form.

        No-op when a master is already alive and *force* is False.
        """
        if not force and self.is_master_alive():
            logger.debug(f"ssh master already alive for {self.options.host}")
            return

        if not self.options.control_master:
            raise TransportError(
                f"cannot login with control_master=False for {self.options.host!r}; "
                "enable multiplexing so the interactive session can be reused"
            )

        if not sys.stdin.isatty() or not sys.stdout.isatty():
            raise TransportError(
                f"SSH host {self.options.host!r} needs an interactive login "
                f"(verification code / 2FA) but no TTY is available. "
                f"Use login_with_code(code=…) from the web UI, or run from a "
                f"terminal:  ssh {self.options.host}   "
                f"or  molexp connect -ws {self.options.host}:/path"
            )

        argv = self._ssh_argv(batch_mode=False) + ["--", "true"]
        logger.info(
            f"interactive ssh login to {self.options.host} "
            f"(enter verification code if prompted)"
        )
        try:
            proc = subprocess.run(argv, check=False, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise TransportError(
                f"ssh login timed out on {self.options.host}",
                timeout=timeout,
            ) from exc
        except FileNotFoundError as exc:
            raise TransportError(
                "ssh binary not found — install OpenSSH client",
                ssh_bin=self._ssh_bin,
            ) from exc
        self._finish_login(proc.returncode, stderr="")

    def login_with_code(
        self,
        code: str,
        *,
        force: bool = False,
        timeout: float | None = 90.0,
    ) -> None:
        """Non-TTY login: feed *code* to OpenSSH via ``SSH_ASKPASS``.

        Used by the molexp web UI (and any headless caller) when the host
        requires a keyboard-interactive verification code.  Opens a
        ControlMaster the same way :meth:`login` does, without inheriting a
        terminal.

        *code* is passed only through a short-lived env var read by a private
        askpass helper; it is never written to disk or argv.
        """
        secret = (code or "").strip()
        if not secret:
            raise TransportError("verification code is empty")

        if not force and self.is_master_alive():
            logger.debug(f"ssh master already alive for {self.options.host}")
            return

        if not self.options.control_master:
            raise TransportError(
                f"cannot login with control_master=False for {self.options.host!r}; "
                "enable multiplexing so the interactive session can be reused"
            )

        askpass = _write_askpass_helper()
        env = os.environ.copy()
        env["SSH_ASKPASS"] = str(askpass)
        env["SSH_ASKPASS_REQUIRE"] = "force"
        # Some OpenSSH builds still gate askpass on DISPLAY being set.
        env.setdefault("DISPLAY", env.get("DISPLAY") or ":0")
        env["MOLEXP_SSH_SECRET"] = secret

        argv = self._ssh_argv(batch_mode=False) + ["--", "true"]
        logger.info(f"ssh login_with_code to {self.options.host} via SSH_ASKPASS")
        try:
            proc = subprocess.run(
                argv,
                check=False,
                timeout=timeout,
                # Force askpass: do not attach a controlling terminal.
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                env=env,
                start_new_session=True,
            )
        except subprocess.TimeoutExpired as exc:
            raise TransportError(
                f"ssh login timed out on {self.options.host}",
                timeout=timeout,
            ) from exc
        except FileNotFoundError as exc:
            raise TransportError(
                "ssh binary not found — install OpenSSH client",
                ssh_bin=self._ssh_bin,
            ) from exc
        finally:
            env.pop("MOLEXP_SSH_SECRET", None)
            with contextlib.suppress(OSError):
                askpass.unlink(missing_ok=True)

        self._finish_login(proc.returncode, stderr=proc.stderr or "")

    def _finish_login(self, returncode: int, *, stderr: str) -> None:
        if returncode != 0:
            hint = _auth_failure_hint(stderr, self.options.host) or ""
            detail = (stderr.strip() or f"exit {returncode}") + (
                f"\n{hint}" if hint else ""
            )
            raise TransportError(
                f"ssh login to {self.options.host!r} failed: {detail}",
                returncode=returncode,
                host=self.options.host,
            )
        if not self.is_master_alive():
            logger.warning(
                f"ssh login to {self.options.host} succeeded but no ControlMaster "
                f"socket is live; subsequent BatchMode ops may re-prompt or fail"
            )

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
        stderr = proc.stderr or ""
        if proc.returncode != 0:
            hint = _auth_failure_hint(stderr, self.options.host)
            if hint:
                # Surface the remediation on the result so callers that log
                # stderr (and our own raise paths) can show it.
                stderr = (stderr.rstrip() + "\n" + hint).lstrip("\n")
                logger.warning(hint)
        return CommandResult(
            argv=tuple(argv),
            returncode=proc.returncode,
            stdout=proc.stdout or "",
            stderr=stderr,
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
