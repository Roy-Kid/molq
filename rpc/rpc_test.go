package rpc

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"testing"

	"github.com/MolCrafts/molq/serve"
)

func TestStdioHello(t *testing.T) {
	service := open(t)
	var out bytes.Buffer
	err := Stdio(service, strings.NewReader(`{"jsonrpc":"2.0","id":1,"method":"molq.hello"}`+"\n"), &out)
	if err != nil {
		t.Fatal(err)
	}
	var response map[string]any
	if err := json.Unmarshal(out.Bytes(), &response); err != nil {
		t.Fatal(err)
	}
	result := response["result"].(map[string]any)
	if result["registry_id"] == "" || result["runtime_instance_id"] == "" {
		t.Fatalf("result = %#v", result)
	}
}

func TestHTTPHelloRequiresToken(t *testing.T) {
	service := open(t)
	handler, err := Handler(service, "0123456789abcdef")
	if err != nil {
		t.Fatal(err)
	}
	server := httptest.NewServer(handler)
	defer server.Close()
	request, err := http.NewRequest(http.MethodPost, server.URL+"/rpc", strings.NewReader(`{"jsonrpc":"2.0","id":7,"method":"molq.hello"}`))
	if err != nil {
		t.Fatal(err)
	}
	request.Header.Set("Authorization", "Bearer 0123456789abcdef")
	response, err := http.DefaultClient.Do(request)
	if err != nil {
		t.Fatal(err)
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		t.Fatalf("status = %d", response.StatusCode)
	}
	var body map[string]any
	if err := json.NewDecoder(response.Body).Decode(&body); err != nil {
		t.Fatal(err)
	}
	if body["result"].(map[string]any)["registry_id"] == "" {
		t.Fatalf("body = %#v", body)
	}
}

func open(t *testing.T) *serve.Service {
	t.Helper()
	service, err := serve.Open(filepath.Join(t.TempDir(), "registry.db"))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = service.Close() })
	return service
}
