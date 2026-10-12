package main

import (
	"encoding/json"
	"fmt"
	"os"

	"github.com/MolCrafts/molq/config"
	"github.com/MolCrafts/molq/protocol"
	"github.com/MolCrafts/molq/registry"
	"github.com/MolCrafts/molq/serve"
)

// runPing asks the selected serve process for molq.hello and reports only whether it answered.
func runPing(args []string) error {
	probe, err := newProbe(args, "ping")
	if err != nil {
		return err
	}
	defer probe.close()
	_, err = probe.hello()
	if err != nil {
		return err
	}
	return printJSON(map[string]any{"ok": true})
}

// runHealth reports whether the selected installation is ready. It does not explain failures.
func runHealth(args []string) error {
	return runChecks(args, "health", false)
}

// runDoctor reports each check with its path and, on failure, the error.
func runDoctor(args []string) error {
	return runChecks(args, "doctor", true)
}

func runChecks(args []string, command string, diagnose bool) error {
	probe, err := newProbe(args, command)
	if err != nil {
		return err
	}
	defer probe.close()
	checks := []map[string]any{}
	if probe.endpoint == "" {
		registryCheck := map[string]any{"name": "registry", "ok": probe.registryErr == nil}
		if diagnose {
			registryCheck["path"] = probe.registryPath
			attachError(registryCheck, probe.registryErr)
		}
		checks = append(checks, registryCheck)
	}
	if probe.configChecked {
		configCheck := map[string]any{"name": "config", "ok": probe.configErr == nil}
		if diagnose {
			configCheck["path"] = probe.configPath
			attachError(configCheck, probe.configErr)
		}
		checks = append(checks, configCheck)
	}
	_, helloErr := probe.hello()
	helloCheck := map[string]any{"name": "hello", "ok": helloErr == nil}
	if diagnose {
		attachError(helloCheck, helloErr)
	}
	checks = append(checks, helloCheck)
	ok := true
	for _, check := range checks {
		if check["ok"] != true {
			ok = false
		}
	}
	if err := printJSON(map[string]any{"ok": ok, "checks": checks}); err != nil {
		return err
	}
	if !ok {
		probe.close()
		os.Exit(1)
	}
	return nil
}

type probe struct {
	service       *serve.Service
	endpoint      string
	token         string
	registryPath  string
	configPath    string
	configChecked bool
	registryErr   error
	configErr     error
}

func newProbe(args []string, command string) (*probe, error) {
	flags, positionals := splitArgs(args)
	if len(positionals) > 0 {
		return nil, protocol.Fail("INVALID_INPUT", "usage: molq "+command, nil)
	}
	item := &probe{
		endpoint:   first(flags["--endpoint"]),
		token:      first(flags["--token"]),
		configPath: first(flags["--config"]),
	}
	file, resolved, err := resolveConfig(item.configPath)
	if resolved != "" {
		item.configPath = resolved
		item.configChecked = true
	}
	item.configErr = err
	if err != nil {
		file = config.File{}
	}
	if item.endpoint == "" {
		item.endpoint = file.Client.Endpoint
	}
	if item.token == "" {
		item.token = file.Client.Token
	}
	if item.endpoint != "" {
		item.registryPath = "endpoint"
		return item, nil
	}
	item.registryPath = first(flags["--registry"])
	if item.registryPath == "" {
		item.registryPath = file.Client.Registry
	}
	if item.registryPath == "" {
		item.registryPath = registry.DefaultPath()
	}
	service, err := serve.Open(item.registryPath)
	item.registryErr = err
	if err != nil {
		return item, nil
	}
	item.service = service
	if item.configErr == nil && item.configPath != "" {
		item.configErr = service.UseConfig(item.configPath)
	}
	return item, nil
}

func (p *probe) hello() (any, error) {
	if p.registryErr != nil {
		return nil, p.registryErr
	}
	if p.endpoint != "" && p.service == nil {
		return (&caller{endpoint: p.endpoint, token: p.token}).call("molq.hello", map[string]any{})
	}
	if p.service == nil {
		return nil, protocol.Fail("RUNTIME_UNAVAILABLE", "Serve process is not available", nil)
	}
	return p.service.Call("molq.hello", map[string]any{})
}

func (p *probe) close() {
	if p.service != nil {
		_ = p.service.Close()
		p.service = nil
	}
}

func attachError(check map[string]any, err error) {
	if err == nil {
		return
	}
	item, ok := err.(*protocol.Error)
	if !ok {
		check["error"] = map[string]any{"kind": "INTERNAL_ERROR", "message": err.Error()}
		return
	}
	check["error"] = map[string]any{"kind": item.Kind, "message": item.Message}
}

func printJSON(value any) error {
	encoded, err := json.Marshal(value)
	if err != nil {
		return err
	}
	fmt.Fprintln(os.Stdout, string(encoded))
	return nil
}
