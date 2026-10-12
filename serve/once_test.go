package serve

import (
	"path/filepath"
	"sync"
	"testing"
)

func TestRequestKeyRepeatsTheSameSubmission(t *testing.T) {
	root := t.TempDir()
	service, err := Open(filepath.Join(root, "registry.db"))
	if err != nil {
		t.Fatal(err)
	}
	defer service.Close()
	registered, err := service.Call("clusters.register", map[string]any{
		"name": "local", "scheduler": "shell", "target_root": filepath.Join(root, "target"),
	})
	if err != nil {
		t.Fatal(err)
	}
	params := map[string]any{
		"cluster":     registered.(map[string]any)["id"],
		"request_key": "once",
		"spec": map[string]any{"execution": map[string]any{"units": []any{
			map[string]any{"id": "main", "command": map[string]any{"kind": "argv", "argv": []any{"echo", "once"}}},
		}}},
	}
	first, err := service.Call("jobs.submit", params)
	if err != nil {
		t.Fatal(err)
	}
	second, err := service.Call("jobs.submit", params)
	if err != nil {
		t.Fatal(err)
	}
	if first.(map[string]any)["ref"].(map[string]any)["native_id"] != second.(map[string]any)["ref"].(map[string]any)["native_id"] {
		t.Fatalf("repeated key created another job: %#v %#v", first, second)
	}
	params["spec"].(map[string]any)["execution"].(map[string]any)["units"].([]any)[0].(map[string]any)["command"].(map[string]any)["argv"] = []any{"echo", "other"}
	if _, err := service.Call("jobs.submit", params); err == nil {
		t.Fatal("expected conflict")
	}
}

func TestRequestKeyWaitsForTheInflightCall(t *testing.T) {
	root := t.TempDir()
	service, err := Open(filepath.Join(root, "registry.db"))
	if err != nil {
		t.Fatal(err)
	}
	defer service.Close()
	registered, err := service.Call("clusters.register", map[string]any{
		"name": "local", "scheduler": "shell", "target_root": filepath.Join(root, "target"),
	})
	if err != nil {
		t.Fatal(err)
	}
	params := map[string]any{
		"cluster": registered.(map[string]any)["id"], "request_key": "parallel",
		"spec": map[string]any{"execution": map[string]any{"units": []any{
			map[string]any{"id": "main", "command": map[string]any{"kind": "argv", "argv": []any{"echo", "parallel"}}},
		}}},
	}
	var group sync.WaitGroup
	results := make([]any, 2)
	for i := range results {
		group.Add(1)
		go func(i int) {
			defer group.Done()
			value, err := service.Call("jobs.submit", params)
			if err != nil {
				t.Error(err)
				return
			}
			results[i] = value
		}(i)
	}
	group.Wait()
	if results[0] == nil || results[1] == nil {
		t.Fatal(results)
	}
	left := results[0].(map[string]any)["ref"].(map[string]any)["native_id"]
	right := results[1].(map[string]any)["ref"].(map[string]any)["native_id"]
	if left != right {
		t.Fatalf("ids = %v %v", left, right)
	}
}
