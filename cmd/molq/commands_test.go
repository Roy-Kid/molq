package main

import (
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

func TestSubmitEcho(t *testing.T) {
	root := t.TempDir()
	binary := filepath.Join(root, "molq")
	command := exec.Command("go", "build", "-o", binary, ".")
	command.Env = append(os.Environ(), "CGO_ENABLED=0")
	command.Dir = "."
	if output, err := command.CombinedOutput(); err != nil {
		t.Fatalf("build: %v\n%s", err, output)
	}
	registry := filepath.Join(root, "registry.db")
	target := filepath.Join(root, "target")
	definition := `{"name":"local","scheduler":"shell","target_root":"` + target + `"}`
	register := exec.Command(binary, "--registry", registry, "clusters", "register", "--definition", definition)
	if output, err := register.CombinedOutput(); err != nil {
		t.Fatalf("register: %v\n%s", err, output)
	}
	submit := exec.Command(binary, "--registry", registry, "submit", "local", "--", "echo", "cli")
	output, err := submit.CombinedOutput()
	if err != nil {
		t.Fatalf("submit: %v\n%s", err, output)
	}
	if !strings.Contains(string(output), `"outcome":"accepted"`) && !strings.Contains(string(output), `"outcome": "accepted"`) {
		t.Fatalf("submit output = %s", output)
	}
}

func TestTransferTakesRsyncSyntax(t *testing.T) {
	if _, err := exec.LookPath("rsync"); err != nil {
		t.Skip("rsync is not installed")
	}
	root := t.TempDir()
	binary := filepath.Join(root, "molq")
	command := exec.Command("go", "build", "-o", binary, ".")
	command.Env = append(os.Environ(), "CGO_ENABLED=0")
	command.Dir = "."
	if output, err := command.CombinedOutput(); err != nil {
		t.Fatalf("build: %v\n%s", err, output)
	}
	registry := filepath.Join(root, "registry.db")
	source := filepath.Join(root, "source")
	destination := filepath.Join(root, "destination")
	if err := os.MkdirAll(source, 0o755); err != nil || os.MkdirAll(destination, 0o755) != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(source, "note.txt"), []byte("copied"), 0o600); err != nil {
		t.Fatal(err)
	}
	for _, name := range []string{"from", "to"} {
		definition := `{"name":"` + name + `","scheduler":"shell","target_root":"` + filepath.Join(root, "jobs", name) + `"}`
		register := exec.Command(binary, "--registry", registry, "clusters", "register", "--definition", definition)
		if output, err := register.CombinedOutput(); err != nil {
			t.Fatalf("register %s: %v\n%s", name, err, output)
		}
	}
	transfer := exec.Command(binary, "transfer", "-a", "--registry", registry, "--exclude", "skip.txt", "note.txt", "skip.txt", "to:"+filepath.Join(destination)+"/")
	transfer.Dir = source
	if err := os.WriteFile(filepath.Join(source, "skip.txt"), []byte("skipped"), 0o600); err != nil {
		t.Fatal(err)
	}
	output, err := transfer.CombinedOutput()
	if err != nil {
		t.Fatalf("transfer: %v\n%s", err, output)
	}
	if !strings.Contains(string(output), `"outcome":"applied"`) && !strings.Contains(string(output), `"outcome": "applied"`) {
		t.Fatalf("transfer output = %s", output)
	}
	body, err := os.ReadFile(filepath.Join(destination, "note.txt"))
	if err != nil || string(body) != "copied" {
		t.Fatalf("body = %q, %v", body, err)
	}
	if _, err := os.Stat(filepath.Join(destination, "skip.txt")); !os.IsNotExist(err) {
		t.Fatalf("excluded skip.txt err = %v", err)
	}
}
