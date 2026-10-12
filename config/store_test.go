package config

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestSetPreservesClientAndReloads(t *testing.T) {
	path := filepath.Join(t.TempDir(), "config.json")
	if err := os.WriteFile(path, []byte(`{"client":{"executable":"/usr/local/bin/molq"},"settings":{}}`), 0o600); err != nil {
		t.Fatal(err)
	}
	store, err := Open(path)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := store.Set("settings", "cache_max_entries", 12); err != nil {
		t.Fatal(err)
	}
	if err := store.Reload(); err != nil {
		t.Fatal(err)
	}
	got, err := store.Get("settings", "cache_max_entries")
	if err != nil {
		t.Fatal(err)
	}
	value, ok := whole(got["value"])
	if !ok || value != 12 {
		t.Fatalf("entries = %#v", got["value"])
	}
	body, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(body), "/usr/local/bin/molq") {
		t.Fatalf("client section dropped: %s", body)
	}
}

func TestRejectsUnknownSetting(t *testing.T) {
	store, err := Open(filepath.Join(t.TempDir(), "config.json"))
	if err != nil {
		t.Fatal(err)
	}
	if _, err := store.Set("settings", "cadence", 1); err == nil {
		t.Fatal("expected unknown setting")
	}
}
