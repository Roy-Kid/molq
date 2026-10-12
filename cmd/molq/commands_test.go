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
