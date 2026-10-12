package watch

import (
	"bytes"
	"context"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/MolCrafts/molq/protocol"
	"github.com/MolCrafts/molq/serve"
)

func TestOnceOnEmptyRegistryPrintsNothing(t *testing.T) {
	service, err := serve.Open(filepath.Join(t.TempDir(), "registry.db"))
	if err != nil {
		t.Fatal(err)
	}
	defer service.Close()
	var out bytes.Buffer
	err = Run(context.Background(), service, Options{Interval: time.Second, Once: true, Out: &out})
	if err != nil {
		t.Fatal(err)
	}
	if out.Len() != 0 {
		t.Fatalf("output = %s", out.String())
	}
}

func TestReportErrorPrintsARepeatedFailureOnce(t *testing.T) {
	var out bytes.Buffer
	reported := map[string]string{}
	err := protocol.Fail("SCHEDULER_UNAVAILABLE", "ssh failed", nil)
	reportError(&out, reported, "Arrhenius", err)
	reportError(&out, reported, "Arrhenius", err)
	if strings.Count(out.String(), "SCHEDULER_UNAVAILABLE") != 1 {
		t.Fatalf("output = %s", out.String())
	}
	delete(reported, "Arrhenius")
	reportError(&out, reported, "Arrhenius", err)
	if strings.Count(out.String(), "SCHEDULER_UNAVAILABLE") != 2 {
		t.Fatalf("output = %s", out.String())
	}
}

func TestMissingClusterErrorIsNotRepeated(t *testing.T) {
	service, err := serve.Open(filepath.Join(t.TempDir(), "registry.db"))
	if err != nil {
		t.Fatal(err)
	}
	defer service.Close()
	ctx, cancel := context.WithTimeout(context.Background(), 200*time.Millisecond)
	defer cancel()
	var out bytes.Buffer
	err = Run(ctx, service, Options{Interval: time.Millisecond, Clusters: []string{"missing"}, Out: &out})
	if err != context.DeadlineExceeded {
		t.Fatal(err)
	}
	if strings.Count(out.String(), "CLUSTER_NOT_FOUND") != 1 {
		t.Fatalf("output = %s", out.String())
	}
}

func TestShellWatchOnceIgnoresUnsupportedHistory(t *testing.T) {
	root := t.TempDir()
	service, err := serve.Open(filepath.Join(root, "registry.db"))
	if err != nil {
		t.Fatal(err)
	}
	defer service.Close()
	if _, err := service.Call("clusters.register", map[string]any{
		"name": "local", "scheduler": "shell", "target_root": filepath.Join(root, "target"),
	}); err != nil {
		t.Fatal(err)
	}
	var out bytes.Buffer
	err = Run(context.Background(), service, Options{Once: true, Clusters: []string{"local"}, Out: &out})
	if err != nil {
		t.Fatal(err)
	}
	if out.Len() != 0 {
		t.Fatalf("output = %s", out.String())
	}
}

func TestTerminalCatchUpSkipsSeenRefs(t *testing.T) {
	ref := map[string]any{"registry_id": "r", "cluster_id": "c", "native_id": "3711469", "incarnation": "t"}
	result := map[string]any{"snapshots": []map[string]any{{
		"ref": ref, "state": "failed", "terminal": true, "observed_at": "2026-10-12T12:00:00Z",
	}}}
	seen := map[string]bool{}
	first := terminalEvents(result, seen)
	second := terminalEvents(result, seen)
	if len(first) != 1 || first[0]["previous_state"] != nil || first[0]["state"] != "failed" || len(second) != 0 {
		t.Fatalf("first=%#v second=%#v", first, second)
	}
}
