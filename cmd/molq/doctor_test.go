package main

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestPingHealthAndDoctor(t *testing.T) {
	root := t.TempDir()
	registryPath := filepath.Join(root, "registry.db")
	stdout := os.Stdout
	reader, writer, err := os.Pipe()
	if err != nil {
		t.Fatal(err)
	}
	for _, command := range []string{"ping", "health", "doctor"} {
		os.Stdout = writer
		err = run([]string{command, "--registry", registryPath})
		if err != nil {
			writer.Close()
			os.Stdout = stdout
			t.Fatal(command, err)
		}
	}
	writer.Close()
	os.Stdout = stdout
	var output bytes.Buffer
	_, _ = output.ReadFrom(reader)
	lines := bytes.Split(bytes.TrimSpace(output.Bytes()), []byte("\n"))
	if len(lines) != 3 {
		t.Fatalf("output = %s", output.String())
	}
	var ping map[string]any
	if err := json.Unmarshal(lines[0], &ping); err != nil || ping["ok"] != true || ping["checks"] != nil {
		t.Fatalf("ping = %s", lines[0])
	}
	var health map[string]any
	if err := json.Unmarshal(lines[1], &health); err != nil || health["ok"] != true {
		t.Fatalf("health = %s", lines[1])
	}
	if _, ok := health["checks"].([]any)[0].(map[string]any)["error"]; ok {
		t.Fatalf("health should not explain errors: %s", lines[1])
	}
	var doctor map[string]any
	if err := json.Unmarshal(lines[2], &doctor); err != nil || doctor["ok"] != true {
		t.Fatalf("doctor = %s", lines[2])
	}
	first := doctor["checks"].([]any)[0].(map[string]any)
	if first["path"] != registryPath {
		t.Fatalf("doctor path = %#v", first)
	}
}

func TestHelpMentionsDoctor(t *testing.T) {
	stdout := os.Stdout
	reader, writer, err := os.Pipe()
	if err != nil {
		t.Fatal(err)
	}
	os.Stdout = writer
	err = run([]string{"--help"})
	writer.Close()
	os.Stdout = stdout
	var output bytes.Buffer
	_, _ = output.ReadFrom(reader)
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Contains(output.Bytes(), []byte("molq doctor")) || !bytes.Contains(output.Bytes(), []byte("molq submit")) {
		t.Fatalf("help = %s", output.String())
	}
}
