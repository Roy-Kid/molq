package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/MolCrafts/molq/protocol"
	"github.com/MolCrafts/molq/registry"
	"github.com/MolCrafts/molq/serve"
)

type caller struct {
	service  *serve.Service
	endpoint string
	token    string
}

func runCommand(command string, args []string) error {
	flags, positionals := splitArgs(args)
	file, configPath, err := resolveConfig(first(flags["--config"]))
	if err != nil {
		return err
	}
	endpoint := first(flags["--endpoint"])
	if endpoint == "" {
		endpoint = file.Client.Endpoint
	}
	token := first(flags["--token"])
	if token == "" {
		token = file.Client.Token
	}
	client := &caller{endpoint: endpoint, token: token}
	if endpoint == "" {
		path := first(flags["--registry"])
		if path == "" {
			path = file.Client.Registry
		}
		if path == "" {
			path = registry.DefaultPath()
		}
		service, err := serve.Open(path)
		if err != nil {
			return err
		}
		defer service.Close()
		if err := service.UseConfig(configPath); err != nil {
			return err
		}
		client.service = service
	}
	result, err := dispatchCommand(client, command, flags, positionals)
	if err != nil {
		return err
	}
	encoded, err := json.Marshal(map[string]any{"jsonrpc": "2.0", "id": 1, "result": result})
	if err != nil {
		return err
	}
	fmt.Fprintln(os.Stdout, string(encoded))
	if successful, ok := nestedBool(result, "completion", "successful"); ok && !successful {
		os.Exit(9)
	}
	if hasCoverageErrors(result) {
		os.Exit(8)
	}
	return nil
}

func dispatchCommand(client *caller, command string, flags map[string][]string, positionals []string) (any, error) {
	switch command {
	case "discover":
		return client.call("schema.discover", map[string]any{})
	case "clusters":
		return clustersCommand(client, positionals, flags)
	case "submit":
		return submitCommand(client, positionals, flags)
	case "status":
		ref, err := readJSON(required(flags, "--ref"))
		if err != nil {
			return nil, err
		}
		return client.call("jobs.get", map[string]any{"ref": ref, "consistency": orString(first(flags["--consistency"]), "live")})
	case "cancel":
		ref, err := readJSON(required(flags, "--ref"))
		if err != nil {
			return nil, err
		}
		params := map[string]any{"ref": ref}
		if key := first(flags["--request-key"]); key != "" {
			params["request_key"] = key
		}
		return client.call("jobs.cancel", params)
	case "logs":
		ref, err := readJSON(required(flags, "--ref"))
		if err != nil {
			return nil, err
		}
		return client.call("logs.read", map[string]any{
			"ref": ref, "stream": orString(first(flags["--stream"]), "stdout"),
			"offset": numberOr(first(flags["--offset"]), 0), "limit": numberOr(first(flags["--limit"]), 262144),
		})
	case "wait":
		return waitCommand(client, flags)
	case "list":
		if len(positionals) != 1 {
			return nil, protocol.Fail("INVALID_INPUT", "usage: molq list CLUSTER", nil)
		}
		params := map[string]any{"cluster": positionals[0]}
		if states := flags["--state"]; len(states) > 0 {
			params["states"] = anyList(states)
		}
		if name := first(flags["--name"]); name != "" {
			params["name"] = name
		}
		return client.call("jobs.list", params)
	case "observe":
		if len(positionals) != 1 {
			return nil, protocol.Fail("INVALID_INPUT", "usage: molq observe CLUSTER", nil)
		}
		params := map[string]any{"cluster": positionals[0]}
		if cursor := first(flags["--cursor"]); cursor != "" {
			params["cursor"] = cursor
		}
		return client.call("jobs.observe", params)
	case "history":
		return historyCommand(client, positionals, flags)
	default:
		return nil, protocol.Fail("INVALID_INPUT", "usage: molq serve|rpc|watch|discover|clusters|submit|status|cancel|logs|wait|list|observe|history", nil)
	}
}

func clustersCommand(client *caller, positionals []string, flags map[string][]string) (any, error) {
	if len(positionals) == 0 {
		return nil, protocol.Fail("INVALID_INPUT", "usage: molq clusters list|get|register|update|remove", nil)
	}
	switch positionals[0] {
	case "list":
		return client.call("clusters.list", map[string]any{})
	case "get":
		if len(positionals) != 2 {
			return nil, protocol.Fail("INVALID_INPUT", "usage: molq clusters get CLUSTER", nil)
		}
		return client.call("clusters.get", map[string]any{"cluster": positionals[1]})
	case "register":
		definition, err := readJSON(required(flags, "--definition"))
		if err != nil {
			return nil, err
		}
		return client.call("clusters.register", definition.(map[string]any))
	case "update":
		if len(positionals) != 2 {
			return nil, protocol.Fail("INVALID_INPUT", "usage: molq clusters update CLUSTER --definition JSON --revision N", nil)
		}
		definition, err := readJSON(required(flags, "--definition"))
		if err != nil {
			return nil, err
		}
		return client.call("clusters.update", map[string]any{
			"cluster": positionals[1], "definition": definition, "expected_revision": numberOr(required(flags, "--revision"), 0),
		})
	case "remove":
		if len(positionals) != 2 {
			return nil, protocol.Fail("INVALID_INPUT", "usage: molq clusters remove CLUSTER --revision N", nil)
		}
		return client.call("clusters.remove", map[string]any{
			"cluster": positionals[1], "expected_revision": numberOr(required(flags, "--revision"), 0),
		})
	default:
		return nil, protocol.Fail("INVALID_INPUT", "usage: molq clusters list|get|register|update|remove", nil)
	}
}

func submitCommand(client *caller, positionals []string, flags map[string][]string) (any, error) {
	if len(positionals) == 0 {
		return nil, protocol.Fail("INVALID_INPUT", "usage: molq submit CLUSTER [--spec JSON | -- ARGV]", nil)
	}
	specText := first(flags["--spec"])
	argv := []string{}
	if len(positionals) > 1 && positionals[1] == "--" {
		argv = positionals[2:]
	}
	if (specText == "") == (len(argv) == 0) {
		return nil, protocol.Fail("INVALID_INPUT", "Provide exactly one of spec or argv", nil)
	}
	name, comment := first(flags["--name"]), first(flags["--comment"])
	if specText != "" && (name != "" || comment != "") {
		return nil, protocol.Fail("INVALID_INPUT", "Name and comment belong in the spec when --spec is set", nil)
	}
	var spec any
	var err error
	if specText != "" {
		spec, err = readJSON(specText)
		if err != nil {
			return nil, err
		}
	} else {
		body := map[string]any{"execution": map[string]any{"units": []any{
			map[string]any{"id": "main", "command": map[string]any{"kind": "argv", "argv": anyList(argv)}},
		}}}
		if name != "" || comment != "" {
			scheduling := map[string]any{}
			if name != "" {
				scheduling["name"] = name
			}
			if comment != "" {
				scheduling["comment"] = comment
			}
			body["scheduling"] = scheduling
		}
		spec = body
	}
	params := map[string]any{"cluster": positionals[0], "spec": spec}
	if key := first(flags["--request-key"]); key != "" {
		params["request_key"] = key
	}
	return client.call("jobs.submit", params)
}

func historyCommand(client *caller, positionals []string, flags map[string][]string) (any, error) {
	if len(positionals) != 1 {
		return nil, protocol.Fail("INVALID_INPUT", "usage: molq history CLUSTER", nil)
	}
	params := map[string]any{"cluster": positionals[0]}
	if refs := first(flags["--refs"]); refs != "" {
		if len(flags["--state"]) > 0 || first(flags["--since"]) != "" || first(flags["--until"]) != "" || first(flags["--name"]) != "" || first(flags["--limit"]) != "" {
			return nil, protocol.Fail("INVALID_INPUT", "History refs are mutually exclusive with range filters", nil)
		}
		value, err := readJSON(refs)
		if err != nil {
			return nil, err
		}
		params["refs"] = value
	}
	if states := flags["--state"]; len(states) > 0 {
		params["states"] = anyList(states)
	}
	for _, name := range []string{"since", "until", "name"} {
		if value := first(flags["--"+name]); value != "" {
			params[name] = value
		}
	}
	if limit := first(flags["--limit"]); limit != "" {
		params["limit"] = numberOr(limit, 100)
	}
	return client.call("jobs.history", params)
}

func waitCommand(client *caller, flags map[string][]string) (any, error) {
	ref, err := readJSON(required(flags, "--ref"))
	if err != nil {
		return nil, err
	}
	timeout := floatOr(first(flags["--timeout"]), 3600)
	interval := floatOr(first(flags["--interval"]), 1)
	if timeout <= 0 || interval <= 0 {
		return nil, protocol.Fail("INVALID_INPUT", "wait timeout/interval must be positive", nil)
	}
	deadline := time.Now().Add(time.Duration(timeout * float64(time.Second)))
	var cursor string
	for {
		if !time.Now().Before(deadline) {
			return nil, protocol.Fail("WAIT_TIMEOUT", "Foreground wait deadline reached", nil)
		}
		params := map[string]any{"refs": []any{ref}}
		if cursor != "" {
			params["cursor"] = cursor
		}
		result, err := client.call("jobs.observe", params)
		if err != nil {
			return nil, err
		}
		body := result.(map[string]any)
		cursor = stringField(body["cursor"])
		if body["completion"].(map[string]any)["all_confirmed_terminal"] == true {
			return body, nil
		}
		delay := time.Duration(interval * float64(time.Second))
		if remaining := time.Until(deadline); remaining < delay {
			delay = remaining
		}
		if delay > 0 {
			time.Sleep(delay)
		}
	}
}

func (c *caller) call(method string, params map[string]any) (any, error) {
	if c.endpoint == "" {
		return c.service.Call(method, params)
	}
	payload, err := json.Marshal(map[string]any{"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
	if err != nil {
		return nil, err
	}
	request, err := http.NewRequest(http.MethodPost, strings.TrimRight(c.endpoint, "/")+"/rpc", bytes.NewReader(payload))
	if err != nil {
		return nil, err
	}
	request.Header.Set("Authorization", "Bearer "+c.token)
	request.Header.Set("Content-Type", "application/json")
	response, err := http.DefaultClient.Do(request)
	if err != nil {
		return nil, protocol.Fail("RUNTIME_UNAVAILABLE", "RPC connection failed", nil)
	}
	defer response.Body.Close()
	body, err := io.ReadAll(io.LimitReader(response.Body, 1048577))
	if err != nil {
		return nil, protocol.Fail("RUNTIME_UNAVAILABLE", "RPC connection failed", nil)
	}
	var envelope map[string]any
	if err := json.Unmarshal(body, &envelope); err != nil {
		return nil, protocol.Fail("RUNTIME_UNAVAILABLE", "RPC connection failed", nil)
	}
	if failure, ok := envelope["error"].(map[string]any); ok {
		data, _ := failure["data"].(map[string]any)
		return nil, protocol.FailOutcome(stringField(data["kind"]), stringField(data["message"]), stringField(data["outcome"]), mapValue(data["context"]))
	}
	return envelope["result"], nil
}

func splitArgs(args []string) (map[string][]string, []string) {
	flags := map[string][]string{}
	var positionals []string
	for i := 0; i < len(args); i++ {
		if args[i] == "--" {
			positionals = append(positionals, args[i:]...)
			break
		}
		if strings.HasPrefix(args[i], "--") {
			if i+1 < len(args) && !strings.HasPrefix(args[i+1], "--") {
				flags[args[i]] = append(flags[args[i]], args[i+1])
				i++
				continue
			}
			flags[args[i]] = append(flags[args[i]], "true")
			continue
		}
		positionals = append(positionals, args[i])
	}
	return flags, positionals
}

func readJSON(value string) (any, error) {
	var text string
	switch {
	case value == "@-":
		body, err := io.ReadAll(os.Stdin)
		if err != nil {
			return nil, protocol.Fail("INVALID_INPUT", "Cannot read JSON input", nil)
		}
		text = string(body)
	case strings.HasPrefix(value, "@"):
		body, err := os.ReadFile(value[1:])
		if err != nil {
			return nil, protocol.Fail("INVALID_INPUT", "Cannot read JSON input", nil)
		}
		text = string(body)
	default:
		text = value
	}
	var parsed any
	if err := json.Unmarshal([]byte(text), &parsed); err != nil {
		return nil, protocol.Fail("INVALID_INPUT", "Cannot read JSON input", nil)
	}
	return parsed, nil
}

func first(values []string) string {
	if len(values) == 0 {
		return ""
	}
	return values[0]
}

func required(flags map[string][]string, name string) string {
	return first(flags[name])
}

func orString(value, fallback string) string {
	if value == "" {
		return fallback
	}
	return value
}

func numberOr(value string, fallback int) int {
	if value == "" {
		return fallback
	}
	var number int
	if _, err := fmt.Sscan(value, &number); err != nil {
		return fallback
	}
	return number
}

func floatOr(value string, fallback float64) float64 {
	if value == "" {
		return fallback
	}
	var number float64
	if _, err := fmt.Sscan(value, &number); err != nil {
		return fallback
	}
	return number
}

func anyList(values []string) []any {
	out := make([]any, len(values))
	for i, value := range values {
		out[i] = value
	}
	return out
}

func stringField(value any) string {
	text, _ := value.(string)
	return text
}

func mapValue(value any) map[string]any {
	item, _ := value.(map[string]any)
	if item == nil {
		return map[string]any{}
	}
	return item
}

func nestedBool(value any, key, child string) (bool, bool) {
	body, ok := value.(map[string]any)
	if !ok {
		return false, false
	}
	parent, ok := body[key].(map[string]any)
	if !ok {
		return false, false
	}
	boolean, ok := parent[child].(bool)
	return boolean, ok
}
