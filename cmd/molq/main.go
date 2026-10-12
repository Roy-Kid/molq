package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"net"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/MolCrafts/molq/watch"

	"github.com/MolCrafts/molq/config"
	"github.com/MolCrafts/molq/protocol"
	"github.com/MolCrafts/molq/registry"
	"github.com/MolCrafts/molq/rpc"
	"github.com/MolCrafts/molq/serve"
)

func main() {
	if err := run(os.Args[1:]); err != nil {
		if item, ok := err.(*protocol.Error); ok {
			emit(item)
			os.Exit(exitCode(item.Kind))
		}
		emit(protocol.Fail("INVALID_INPUT", err.Error(), nil))
		os.Exit(2)
	}
}

func run(args []string) error {
	if wantsHelp(args) {
		printHelp(args)
		return nil
	}
	if len(args) > 0 && (args[0] == "--version" || args[0] == "version") {
		fmt.Fprintln(os.Stdout, "0.9.0")
		return nil
	}
	args = peelGlobals(args)
	if len(args) == 0 {
		printHelp(nil)
		return nil
	}
	switch args[0] {
	case "ping":
		return runPing(args[1:])
	case "health":
		return runHealth(args[1:])
	case "doctor":
		return runDoctor(args[1:])
	}
	if args[0] == "rpc" {
		return callRPC(args[1:])
	}
	if args[0] == "watch" {
		return runWatch(args[1:])
	}
	if args[0] != "serve" {
		return runCommand(args[0], args[1:])
	}
	flags := flag.NewFlagSet("serve", flag.ContinueOnError)
	flags.SetOutput(os.Stderr)
	stdio := flags.Bool("stdio", false, "serve RPC on stdin and stdout")
	configPath := flags.String("config", "", "configuration file")
	registryPath := flags.String("registry", "", "registry database")
	host := flags.String("host", "", "listen address for this start")
	port := flags.Int("port", 0, "listen port for this start")
	if err := flags.Parse(args[1:]); err != nil {
		return protocol.Fail("INVALID_INPUT", err.Error(), nil)
	}
	file, resolved, err := resolveConfig(*configPath)
	if err != nil {
		return err
	}
	path := *registryPath
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
	if err := service.UseConfig(resolved); err != nil {
		return err
	}
	if *stdio {
		return rpc.Stdio(service, os.Stdin, os.Stdout)
	}
	listenHost := *host
	if listenHost == "" {
		listenHost = file.Serve.Host
	}
	if listenHost == "" {
		listenHost = "127.0.0.1"
	}
	listenPort := *port
	if listenPort == 0 {
		listenPort = file.Serve.Port
	}
	if listenPort == 0 {
		listenPort = 17891
	}
	handler, err := rpc.Handler(service, file.Serve.Token)
	if err != nil {
		return err
	}
	return http.ListenAndServe(net.JoinHostPort(listenHost, fmt.Sprint(listenPort)), handler)
}

func runWatch(args []string) error {
	flags := flag.NewFlagSet("watch", flag.ContinueOnError)
	flags.SetOutput(os.Stderr)
	configPath := flags.String("config", "", "configuration file")
	registryPath := flags.String("registry", "", "registry database")
	interval := flags.Float64("interval", 0, "seconds between observations")
	once := flags.Bool("once", false, "observe once and exit")
	var clusters stringsFlag
	flags.Var(&clusters, "cluster", "cluster to observe")
	if err := flags.Parse(args); err != nil {
		return protocol.Fail("INVALID_INPUT", err.Error(), nil)
	}
	file, resolved, err := resolveConfig(*configPath)
	if err != nil {
		return err
	}
	path := *registryPath
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
	if err := service.UseConfig(resolved); err != nil {
		return err
	}
	names := file.Client.Watch.Clusters
	if len(clusters) > 0 {
		names = clusters
	}
	every := time.Duration(file.Client.Watch.Interval * float64(time.Second))
	if *interval > 0 {
		every = time.Duration(*interval * float64(time.Second))
	}
	return watch.Run(context.Background(), service, watch.Options{
		Interval: every, Clusters: names, NerveEndpoint: file.Client.Watch.NerveEndpoint,
		Once: *once, Out: os.Stdout,
	})
}

type stringsFlag []string

func (s *stringsFlag) String() string { return strings.Join(*s, ",") }

func (s *stringsFlag) Set(value string) error {
	*s = append(*s, value)
	return nil
}

func peelGlobals(args []string) []string {
	globals := map[string]bool{"--registry": true, "--config": true, "--endpoint": true, "--token": true}
	var flags []string
	var positionals []string
	for i := 0; i < len(args); i++ {
		if globals[args[i]] && i+1 < len(args) {
			flags = append(flags, args[i], args[i+1])
			i++
			continue
		}
		positionals = append(positionals, args[i])
	}
	if len(positionals) == 0 {
		return flags
	}
	return append(append([]string{positionals[0]}, flags...), positionals[1:]...)
}

func callRPC(args []string) error {
	flags, positionals := splitArgs(args)
	if len(positionals) != 1 {
		return protocol.Fail("INVALID_INPUT", "usage: molq rpc METHOD", nil)
	}
	method := positionals[0]
	known := false
	for _, name := range protocol.Current().Methods() {
		if name == method {
			known = true
		}
	}
	if !known {
		return protocol.Fail("METHOD_NOT_FOUND", "Unknown RPC method", map[string]any{"method": method})
	}
	paramsText := first(flags["--params"])
	if paramsText == "" {
		paramsText = "{}"
	}
	parsed, err := readJSON(paramsText)
	if err != nil {
		return err
	}
	body, ok := parsed.(map[string]any)
	if !ok {
		return protocol.Fail("INVALID_INPUT", "Named RPC params must be an object", nil)
	}
	file, resolved, err := resolveConfig(first(flags["--config"]))
	if err != nil {
		return err
	}
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
	if err := service.UseConfig(resolved); err != nil {
		return err
	}
	result, err := service.Call(method, body)
	if err != nil {
		return err
	}
	encoded, err := json.Marshal(map[string]any{"jsonrpc": "2.0", "id": 1, "result": result})
	if err != nil {
		return err
	}
	fmt.Fprintln(os.Stdout, string(encoded))
	if hasCoverageErrors(result) {
		os.Exit(8)
	}
	return nil
}

func hasCoverageErrors(result any) bool {
	body, ok := result.(map[string]any)
	if !ok {
		return false
	}
	if body["partial_failure"] == true {
		return true
	}
	coverage, ok := body["coverage"].(map[string]any)
	if !ok {
		return false
	}
	switch errors := coverage["errors"].(type) {
	case []any:
		return len(errors) > 0
	case []map[string]any:
		return len(errors) > 0
	default:
		return false
	}
}

// resolveConfig loads --config, or ~/.molcrafts/molq/config.json when that
// file exists. A missing default is an empty configuration. An invalid file
// is an error. The returned path is what serve should validate.
func resolveConfig(explicit string) (config.File, string, error) {
	path := explicit
	if path == "" {
		candidate := config.DefaultPath()
		info, err := os.Stat(candidate)
		if err == nil && !info.IsDir() {
			path = candidate
		} else if err != nil && !os.IsNotExist(err) {
			return config.File{}, "", protocol.Fail("INVALID_INPUT", "Cannot read configuration file", map[string]any{"path": candidate})
		}
	}
	file, err := config.Load(path)
	if err != nil {
		return config.File{}, path, err
	}
	return file, path, nil
}

func emit(err *protocol.Error) {
	payload := map[string]any{
		"jsonrpc": "2.0",
		"id":      nil,
		"error":   map[string]any{"code": -32000, "message": err.Error(), "data": err.Data()},
	}
	encoded, _ := json.Marshal(payload)
	fmt.Fprintln(os.Stdout, string(encoded))
}

func exitCode(kind string) int {
	codes := map[string]int{
		"INVALID_INPUT": 2, "METHOD_NOT_FOUND": 2,
		"CLUSTER_NOT_FOUND": 3, "CACHE_MISS": 3, "FILE_UNAVAILABLE": 3,
		"RUNTIME_UNAVAILABLE": 4, "SCHEDULER_UNAVAILABLE": 4, "TRANSPORT_UNAVAILABLE": 4,
		"SCHEDULER_UNSUPPORTED": 5, "TRANSFER_UNSUPPORTED": 5, "RESOURCE_REQUEST_INVALID": 5,
		"EXECUTION_RESOURCE_CONFLICT": 5, "RPC_CHANNEL_UNSUPPORTED": 5, "PROTOCOL_MISMATCH": 5,
		"STATE_SCHEMA_INCOMPATIBLE": 5, "WAIT_TIMEOUT": 6,
		"AUTH_REQUIRED": 7, "PERMISSION_DENIED": 7, "SUBMISSION_REJECTED": 7, "CANCEL_REJECTED": 7,
		"PARTIAL_FAILURE": 8, "CONFLICT": 10, "STATE_BUSY": 10, "OUTCOME_UNKNOWN": 10,
		"REGISTRY_MISMATCH": 10, "JOB_IDENTITY_MISMATCH": 10, "JOB_IDENTITY_UNVERIFIABLE": 10,
	}
	if code, ok := codes[kind]; ok {
		return code
	}
	return 1
}
