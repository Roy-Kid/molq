package serve

import (
	"path/filepath"
	"testing"
)

func TestHello(t *testing.T) {
	service, err := Open(filepath.Join(t.TempDir(), "registry.db"))
	if err != nil {
		t.Fatal(err)
	}
	defer service.Close()
	result, err := service.Call("molq.hello", map[string]any{})
	if err != nil {
		t.Fatal(err)
	}
	body, ok := result.(hello)
	if !ok {
		t.Fatalf("result = %#v", result)
	}
	if body.Version.Major != 1 || body.RegistryID == "" || body.InstanceID == "" {
		t.Fatalf("hello = %#v", body)
	}
	if body.Limits.MaxFrameBytes != 1048576 || body.Limits.BatchSize != 128 {
		t.Fatalf("limits = %#v", body.Limits)
	}
}
