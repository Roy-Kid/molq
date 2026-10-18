package transport

import (
	"context"
	"github.com/MolCrafts/molq/protocol"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestAuthenticateUsesPrivateHelperAndSharedConnection(t *testing.T) {
	requirePOSIX(t)
	dir := t.TempDir()
	t.Setenv("TMPDIR", dir)
	bin := filepath.Join(dir, "bin")
	if err := os.Mkdir(bin, 0o700); err != nil {
		t.Fatal(err)
	}
	log := filepath.Join(dir, "arguments")
	script := "#!/bin/sh\nprintf '%s\\n' \"$@\" >> '" + log + "'\nif [ -n \"$SSH_ASKPASS\" ]; then [ \"$(\"$SSH_ASKPASS\")\" = 123456 ] || { echo 'Permission denied (keyboard-interactive)' >&2; exit 255; }; fi\n"
	if err := os.WriteFile(filepath.Join(bin, "ssh"), []byte(script), 0o700); err != nil {
		t.Fatal(err)
	}
	t.Setenv("PATH", bin+string(os.PathListSeparator)+os.Getenv("PATH"))
	ssh := SSH{Alias: "fixture"}
	if err := ssh.Authenticate(context.Background(), "123456"); err != nil {
		t.Fatal(err)
	}
	if _, err := ssh.Run(context.Background(), []string{"true"}, fileHelperTimeout, nil, false); err != nil {
		t.Fatal(err)
	}
	args, err := os.ReadFile(log)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(args), "123456") {
		t.Fatal("response leaked into argv")
	}
	paths := []string{}
	for _, line := range strings.Split(string(args), "\n") {
		if strings.HasPrefix(line, "ControlPath=") {
			paths = append(paths, line)
		}
	}
	if len(paths) != 2 || paths[0] != paths[1] {
		t.Fatalf("different control paths: %v", paths)
	}
	matches, _ := filepath.Glob(filepath.Join(dir, "molq-auth-*"))
	if len(matches) != 0 {
		t.Fatalf("authentication resources leaked: %v", matches)
	}
	if err := ssh.Authenticate(context.Background(), "bad"); err == nil {
		t.Fatal("rejected response reported success")
	}
}

func TestAuthenticationTimeoutAndDisconnectedWrite(t *testing.T) {
	requirePOSIX(t)
	dir := t.TempDir()
	t.Setenv("TMPDIR", dir)
	binary := filepath.Join(dir, "ssh")
	if err := os.WriteFile(binary, []byte("#!/bin/sh\nsleep 5\n"), 0700); err != nil {
		t.Fatal(err)
	}
	t.Setenv("PATH", dir+string(os.PathListSeparator)+os.Getenv("PATH"))
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Millisecond)
	defer cancel()
	err := (SSH{Alias: "fixture"}).Authenticate(ctx, "123456")
	failure, ok := err.(*protocol.Error)
	if !ok || failure.Kind != "CONNECTION_TIMEOUT" {
		t.Fatalf("timeout was conflated: %v", err)
	}
	matches, _ := filepath.Glob(filepath.Join(dir, "molq-auth-*"))
	if len(matches) != 0 {
		t.Fatalf("helpers leaked: %v", matches)
	}
	if err := os.WriteFile(binary, []byte("#!/bin/sh\necho 'connection reset' >&2\nexit 255\n"), 0700); err != nil {
		t.Fatal(err)
	}
	err = (SSH{Alias: "fixture"}).Write(context.Background(), "/tmp/file", []byte("payload"), nil)
	failure, ok = err.(*protocol.Error)
	if !ok || failure.Outcome != "unknown" {
		t.Fatalf("write uncertainty lost: %v", err)
	}
}

func TestAuthenticationPreservesBoundedDiagnosticWithoutResponse(t *testing.T) {

	requirePOSIX(t)
	dir := t.TempDir()
	t.Setenv("TMPDIR", dir)
	script := "#!/bin/sh\nresponse=$(\"$SSH_ASKPASS\")\nprintf 'unix_listener failed: %s\\n' \"$response\" >&2\nhead -c 4096 /dev/zero | tr '\\000' x >&2\nexit 255\n"
	if err := os.WriteFile(filepath.Join(dir, "ssh"), []byte(script), 0700); err != nil {
		t.Fatal(err)
	}
	t.Setenv("PATH", dir+string(os.PathListSeparator)+os.Getenv("PATH"))
	err := (SSH{Alias: "fixture"}).Authenticate(context.Background(), "sensitive-response")
	failure, ok := err.(*protocol.Error)
	if !ok || failure.Kind != "TRANSPORT_UNAVAILABLE" {
		t.Fatalf("unexpected error: %v", err)
	}
	diagnostic, ok := failure.Context["diagnostic"].(string)
	if !ok || !strings.Contains(diagnostic, "unix_listener failed") {
		t.Fatal("connection diagnostic was discarded")
	}
	if len(diagnostic) > 2048 || strings.Contains(diagnostic, "sensitive-response") {
		t.Fatal("diagnostic exceeded its bound or exposed the response")
	}
}
