package registry

import (
	"database/sql"
	"os"
	"path/filepath"
	"testing"

	"github.com/MolCrafts/molq/protocol"
	_ "modernc.org/sqlite"
)

func TestOpenPreservesIdentity(t *testing.T) {
	path := filepath.Join(t.TempDir(), "registry.db")
	first, err := Open(path)
	if err != nil {
		t.Fatal(err)
	}
	id := first.ID
	if err := first.Close(); err != nil {
		t.Fatal(err)
	}
	second, err := Open(path)
	if err != nil {
		t.Fatal(err)
	}
	defer second.Close()
	if second.ID != id || id == "" {
		t.Fatalf("registry id = %q then %q", id, second.ID)
	}
	info, err := os.Stat(path)
	if err != nil {
		t.Fatal(err)
	}
	if info.Mode().Perm() != 0o600 {
		t.Fatalf("mode = %o", info.Mode().Perm())
	}
}

func TestOpenRejectsForeignTables(t *testing.T) {
	path := filepath.Join(t.TempDir(), "registry.db")
	db, err := sql.Open("sqlite", path)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := db.Exec("CREATE TABLE jobs(id TEXT)"); err != nil {
		t.Fatal(err)
	}
	_ = db.Close()
	_, err = Open(path)
	item, ok := err.(*protocol.Error)
	if !ok || item.Kind != "STATE_SCHEMA_INCOMPATIBLE" {
		t.Fatalf("err = %#v", err)
	}
}
