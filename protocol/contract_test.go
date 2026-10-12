package protocol

import (
	"os"
	"testing"
)

func TestEmbeddedContractMatchesSource(t *testing.T) {
	source, err := os.ReadFile("../src/molq/protocol/v1.json")
	if err != nil {
		t.Fatal(err)
	}
	if string(source) != string(Current().Raw()) {
		t.Fatal("protocol/v1.json drifted from src/molq/protocol/v1.json")
	}
	if Current().Version()["major"] != 1 {
		t.Fatalf("major = %d", Current().Version()["major"])
	}
	found := false
	for _, name := range Current().Methods() {
		if name == "molq.hello" {
			found = true
		}
	}
	if !found {
		t.Fatal("molq.hello missing")
	}
	if err := Current().Validate("molq.hello", map[string]any{}); err != nil {
		t.Fatal(err)
	}
	if err := Current().Validate("molq.hello", map[string]any{"extra": true}); err == nil {
		t.Fatal("expected schema rejection")
	}
}
