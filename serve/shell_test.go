package serve

import (
	"path/filepath"
	"testing"
	"time"
)

func TestShellSubmitObserveAndLogs(t *testing.T) {
	root := t.TempDir()
	service, err := Open(filepath.Join(root, "registry.db"))
	if err != nil {
		t.Fatal(err)
	}
	defer service.Close()
	registered, err := service.Call("clusters.register", map[string]any{
		"name": "local", "scheduler": "shell",
	})
	if err != nil {
		t.Fatal(err)
	}
	cluster := registered.(map[string]any)
	submitted, err := service.Call("jobs.submit", map[string]any{
		"cluster": cluster["id"],
		"spec": map[string]any{
			"execution": map[string]any{
				"units": []any{map[string]any{
					"id":      "main",
					"command": map[string]any{"kind": "argv", "argv": []any{"echo", "molq09"}},
				}},
			},
		},
	})
	if err != nil {
		t.Fatal(err)
	}
	ref := submitted.(map[string]any)["ref"]
	deadline := time.Now().Add(5 * time.Second)
	var observed map[string]any
	for time.Now().Before(deadline) {
		result, err := service.Call("jobs.observe", map[string]any{"refs": []any{ref}})
		if err != nil {
			t.Fatal(err)
		}
		observed = result.(map[string]any)
		if observed["completion"].(map[string]any)["all_confirmed_terminal"] == true {
			break
		}
		time.Sleep(50 * time.Millisecond)
	}
	if observed["completion"].(map[string]any)["all_confirmed_terminal"] != true {
		t.Fatalf("not terminal: %#v", observed)
	}
	logs, err := service.Call("logs.read", map[string]any{"ref": ref, "stream": "stdout"})
	if err != nil {
		t.Fatal(err)
	}
	if text, _ := logs.(map[string]any)["text"].(string); text != "molq09\n" && text != "molq09" {
		t.Fatalf("logs = %q", text)
	}
}
