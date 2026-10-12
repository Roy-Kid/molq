package serve

import (
	"os"
	"os/exec"
	"path/filepath"
	"testing"
)

func TestLocalTransferCopiesFile(t *testing.T) {
	if _, err := exec.LookPath("rsync"); err != nil {
		t.Skip("rsync is not installed")
	}
	root := t.TempDir()
	service, err := Open(filepath.Join(root, "registry.db"))
	if err != nil {
		t.Fatal(err)
	}
	defer service.Close()
	source := filepath.Join(root, "source")
	destination := filepath.Join(root, "destination")
	if err := os.MkdirAll(source, 0o755); err != nil || os.MkdirAll(destination, 0o755) != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(source, "note.txt"), []byte("copied"), 0o600); err != nil {
		t.Fatal(err)
	}
	for _, name := range []string{"from", "to"} {
		dir := source
		if name == "to" {
			dir = destination
		}
		if _, err := service.Call("clusters.register", map[string]any{
			"name": name, "scheduler": "shell", "target_root": dir,
		}); err != nil {
			t.Fatal(err)
		}
	}
	result, err := service.Call("files.transfer", map[string]any{
		"source_cluster": "from", "source_path": "note.txt",
		"destination_cluster": "to", "destination_path": "note.txt",
	})
	if err != nil {
		t.Fatal(err)
	}
	if result.(map[string]any)["outcome"] != "applied" {
		t.Fatalf("result = %#v", result)
	}
	body, err := os.ReadFile(filepath.Join(destination, "note.txt"))
	if err != nil {
		t.Fatal(err)
	}
	if string(body) != "copied" {
		t.Fatalf("body = %q", body)
	}
}
