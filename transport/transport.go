// Package transport runs target commands and file I/O. It does not know schedulers.
package transport

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"syscall"
	"time"

	"github.com/MolCrafts/molq/protocol"
)

const outputLimit = 1048576

// Result is one bounded command result.
type Result struct {
	ReturnCode int
	Stdout     []byte
	Stderr     []byte
}

// Text decodes stdout without treating stderr as state.
func (r Result) Text() string { return strings.ToValidUTF8(string(r.Stdout), "\uFFFD") }

// Transport is target I/O with deadlines. input is sent only when hasInput is set.
type Transport interface {
	Run(ctx context.Context, argv []string, timeout time.Duration, input []byte, hasInput bool) (Result, error)
	Read(ctx context.Context, path string, offset, limit int) ([]byte, error)
	Write(ctx context.Context, path string, data []byte, offset *int) error
}

// Local runs commands on this machine without a shell.
type Local struct{}

// SSH invokes system OpenSSH. Connection setup stays in OpenSSH.
type SSH struct{ Alias string }

// Create selects the configured transport.
func Create(definition map[string]any) Transport {
	if definition["kind"] == "ssh" {
		alias, _ := definition["alias"].(string)
		return SSH{Alias: alias}
	}
	return Local{}
}

func (Local) Run(ctx context.Context, argv []string, timeout time.Duration, input []byte, hasInput bool) (Result, error) {
	if len(argv) == 0 {
		return Result{}, protocol.Fail("TRANSPORT_UNAVAILABLE", "Cannot start target command", map[string]any{"command": "", "dispatched": false})
	}
	runCtx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	cmd := exec.CommandContext(runCtx, argv[0], argv[1:]...)
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	cmd.WaitDelay = 2 * time.Second
	cmd.Cancel = func() error {
		if cmd.Process != nil {
			_ = syscall.Kill(-cmd.Process.Pid, syscall.SIGKILL)
		}
		return nil
	}
	var stdout, stderr bytes.Buffer
	cmd.Stdout = limitWriter{&stdout, argv[0]}
	cmd.Stderr = limitWriter{&stderr, argv[0]}
	if hasInput {
		cmd.Stdin = bytes.NewReader(input)
	}
	err := cmd.Run()
	if errors.Is(runCtx.Err(), context.DeadlineExceeded) {
		return Result{}, protocol.Fail("TRANSPORT_UNAVAILABLE", "Target command deadline exceeded", map[string]any{"command": argv[0]})
	}
	var exitErr *exec.ExitError
	if errors.As(err, &exitErr) {
		return Result{ReturnCode: exitErr.ExitCode(), Stdout: stdout.Bytes(), Stderr: stderr.Bytes()}, nil
	}
	if err != nil {
		if _, ok := err.(*protocol.Error); ok {
			return Result{}, err
		}
		if errors.Is(err, exec.ErrNotFound) || errors.Is(err, os.ErrNotExist) {
			return Result{}, protocol.Fail("TRANSPORT_UNAVAILABLE", "Cannot start target command", map[string]any{"command": argv[0], "dispatched": false})
		}
		return Result{}, protocol.Fail("TRANSPORT_UNAVAILABLE", "Cannot start target command", map[string]any{"command": argv[0], "dispatched": false})
	}
	return Result{Stdout: stdout.Bytes(), Stderr: stderr.Bytes()}, nil
}

func (Local) Read(_ context.Context, path string, offset, limit int) ([]byte, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, protocol.Fail("FILE_UNAVAILABLE", "Cannot read target file", map[string]any{"path": path})
	}
	defer file.Close()
	if _, err := file.Seek(int64(offset), io.SeekStart); err != nil {
		return nil, protocol.Fail("FILE_UNAVAILABLE", "Cannot read target file", map[string]any{"path": path})
	}
	buf := make([]byte, limit)
	n, err := file.Read(buf)
	if err != nil && err != io.EOF {
		return nil, protocol.Fail("FILE_UNAVAILABLE", "Cannot read target file", map[string]any{"path": path})
	}
	return buf[:n], nil
}

func (Local) Write(_ context.Context, path string, data []byte, offset *int) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return protocol.Fail("FILE_UNAVAILABLE", "Cannot write target file", map[string]any{"path": path})
	}
	if offset == nil {
		var nonce [8]byte
		_, _ = rand.Read(nonce[:])
		temp := path + "." + hex.EncodeToString(nonce[:]) + ".tmp"
		if err := os.WriteFile(temp, data, 0o600); err != nil {
			_ = os.Remove(temp)
			return protocol.Fail("FILE_UNAVAILABLE", "Cannot write target file", map[string]any{"path": path})
		}
		if err := os.Rename(temp, path); err != nil {
			_ = os.Remove(temp)
			return protocol.Fail("FILE_UNAVAILABLE", "Cannot write target file", map[string]any{"path": path})
		}
		return nil
	}
	flags := os.O_RDWR | os.O_CREATE
	file, err := os.OpenFile(path, flags, 0o600)
	if err != nil {
		return protocol.Fail("FILE_UNAVAILABLE", "Cannot write target file", map[string]any{"path": path})
	}
	defer file.Close()
	if _, err := file.Seek(int64(*offset), io.SeekStart); err != nil {
		return protocol.Fail("FILE_UNAVAILABLE", "Cannot write target file", map[string]any{"path": path})
	}
	if _, err := file.Write(data); err != nil {
		return protocol.Fail("FILE_UNAVAILABLE", "Cannot write target file", map[string]any{"path": path})
	}
	return nil
}

func (s SSH) Run(ctx context.Context, argv []string, timeout time.Duration, input []byte, hasInput bool) (Result, error) {
	remote := shellJoin(argv)
	return Local{}.Run(ctx, []string{"ssh", "-T", "-o", "BatchMode=yes", "--", s.Alias, remote}, timeout, input, hasInput)
}

func (s SSH) Read(ctx context.Context, path string, offset, limit int) ([]byte, error) {
	result, err := s.Run(ctx, []string{"dd", "if=" + path, "bs=1", fmt.Sprintf("skip=%d", offset), fmt.Sprintf("count=%d", limit)}, 30*time.Second, nil, false)
	if err != nil {
		return nil, err
	}
	if result.ReturnCode != 0 {
		return nil, protocol.Fail("FILE_UNAVAILABLE", "Cannot read remote target file", map[string]any{"path": path})
	}
	return result.Stdout, nil
}

func (s SSH) Write(ctx context.Context, path string, data []byte, offset *int) error {
	parent := filepath.Dir(path)
	if parent == "." {
		parent = ""
	}
	var nonce [8]byte
	_, _ = rand.Read(nonce[:])
	temp := path + "." + hex.EncodeToString(nonce[:]) + ".tmp"
	q := func(value string) string { return "'" + strings.ReplaceAll(value, "'", `'\''`) + "'" }
	script := fmt.Sprintf("umask 077; mkdir -p -- %s && cat > %s && mv -f -- %s %s", q(parent), q(temp), q(temp), q(path))
	if offset != nil {
		script = fmt.Sprintf("umask 077; mkdir -p -- %s && dd of=%s bs=1 seek=%d conv=notrunc", q(parent), q(path), *offset)
	}
	result, err := s.Run(ctx, []string{"sh", "-c", script}, 30*time.Second, data, true)
	if err != nil {
		return err
	}
	if result.ReturnCode != 0 {
		return protocol.Fail("FILE_UNAVAILABLE", "Cannot write remote target file", map[string]any{"path": path})
	}
	return nil
}

func shellJoin(argv []string) string {
	parts := make([]string, len(argv))
	for i, arg := range argv {
		parts[i] = "'" + strings.ReplaceAll(arg, "'", `'\''`) + "'"
	}
	return strings.Join(parts, " ")
}

type limitWriter struct {
	buf     *bytes.Buffer
	command string
}

func (w limitWriter) Write(p []byte) (int, error) {
	if w.buf.Len()+len(p) > outputLimit {
		return 0, protocol.Fail("PARTIAL_FAILURE", "Command output exceeds bounded frame size", map[string]any{"limit": outputLimit})
	}
	return w.buf.Write(p)
}
