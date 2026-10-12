// Package watch periodically asks serve for changes and delivers notifications.
package watch

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/MolCrafts/molq/protocol"
	"github.com/MolCrafts/molq/serve"
)

// Options is one watch pass. Zero interval means five seconds.
type Options struct {
	Interval      time.Duration
	Clusters      []string
	NerveEndpoint string
	Once          bool
	Out           io.Writer
}

// Run calls jobs.observe on the serve process. Notification failure does not
// change submitted work.
func Run(ctx context.Context, service *serve.Service, options Options) error {
	if options.Interval <= 0 {
		options.Interval = 5 * time.Second
	}
	if options.Out == nil {
		options.Out = io.Discard
	}
	backoff := options.Interval
	cursors := map[string]string{}
	reported := map[string]string{}
	seen := map[string]bool{}
	for {
		if err := ctx.Err(); err != nil {
			return err
		}
		names := options.Clusters
		if len(names) == 0 {
			listed, err := service.Call("clusters.list", map[string]any{})
			if err != nil {
				if !sleep(ctx, backoff) {
					return ctx.Err()
				}
				backoff = nextBackoff(backoff, options.Interval)
				continue
			}
			for _, item := range listed.([]map[string]any) {
				names = append(names, stringField(item["name"]))
			}
		}
		failed := false
		for _, name := range names {
			params := map[string]any{"cluster": name}
			if cursor := cursors[name]; cursor != "" {
				params["cursor"] = cursor
			}
			observed, err := service.Call("jobs.observe", params)
			if err != nil {
				failed = true
				reportError(options.Out, reported, name, err)
				continue
			}
			delete(reported, name)
			body := observed.(map[string]any)
			cursors[name] = stringField(body["cursor"])
			for _, change := range mapList(body["changes"]) {
				if ref, ok := change["ref"].(map[string]any); ok {
					seen[serve.RefKey(ref)] = true
				}
				_ = writeEvent(options.Out, change)
				notify(options.NerveEndpoint, change)
			}
			if body["resync"] == true {
				replayTerminal(service, name, seen, options)
			}
		}
		if options.Once {
			return nil
		}
		wait := options.Interval
		if failed {
			wait = backoff
			backoff = nextBackoff(backoff, options.Interval)
		} else {
			backoff = options.Interval
		}
		if !sleep(ctx, wait) {
			return ctx.Err()
		}
	}
}

func mapList(value any) []map[string]any {
	switch items := value.(type) {
	case []map[string]any:
		return items
	case []any:
		out := make([]map[string]any, 0, len(items))
		for _, item := range items {
			if event, ok := item.(map[string]any); ok {
				out = append(out, event)
			}
		}
		return out
	default:
		return nil
	}
}

func writeEvent(out io.Writer, event map[string]any) error {
	encoded, err := json.Marshal(map[string]any{"jsonrpc": "2.0", "method": "events", "params": event})
	if err != nil {
		return err
	}
	_, err = fmt.Fprintln(out, string(encoded))
	return err
}

func reportError(out io.Writer, reported map[string]string, cluster string, err error) {
	signature := errorSignature(err)
	if reported[cluster] == signature {
		return
	}
	reported[cluster] = signature
	_ = writeError(out, err)
}

func errorSignature(err error) string {
	item, ok := err.(*protocol.Error)
	if !ok {
		return err.Error()
	}
	encoded, _ := json.Marshal(item.Data())
	return string(encoded)
}

// replayTerminal reports each finished accounting job from the last 24 hours
// once per process. A history error, including a scheduler with no range
// query, is ignored so it cannot repeat on every resync.
func replayTerminal(service *serve.Service, cluster string, seen map[string]bool, options Options) {
	since := time.Now().UTC().Add(-24 * time.Hour).Format(time.RFC3339Nano)
	result, err := service.Call("jobs.history", map[string]any{
		"cluster": cluster, "since": since, "limit": 1024,
	})
	if err != nil {
		return
	}
	for _, event := range terminalEvents(result, seen) {
		_ = writeEvent(options.Out, event)
		notify(options.NerveEndpoint, event)
	}
}

func terminalEvents(result any, seen map[string]bool) []map[string]any {
	body, ok := result.(map[string]any)
	if !ok {
		return nil
	}
	var events []map[string]any
	for _, snap := range mapList(body["snapshots"]) {
		if snap["terminal"] != true {
			continue
		}
		ref, ok := snap["ref"].(map[string]any)
		if !ok {
			continue
		}
		identity := serve.RefKey(ref)
		if identity == "|||" || seen[identity] {
			continue
		}
		seen[identity] = true
		events = append(events, map[string]any{
			"observed_at": snap["observed_at"], "ref": snap["ref"],
			"previous_state": nil, "state": snap["state"], "terminal": true,
		})
	}
	return events
}

func writeError(out io.Writer, err error) error {
	item, ok := err.(*protocol.Error)
	if !ok {
		item = protocol.Fail("INTERNAL_ERROR", err.Error(), nil)
	}
	encoded, _ := json.Marshal(map[string]any{
		"jsonrpc": "2.0", "id": nil,
		"error": map[string]any{"code": -32000, "message": item.Error(), "data": item.Data()},
	})
	_, writeErr := fmt.Fprintln(out, string(encoded))
	return writeErr
}

func notify(endpoint string, event map[string]any) {
	if endpoint == "" {
		return
	}
	body, err := json.Marshal(event)
	if err != nil {
		return
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	request, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint, bytes.NewReader(body))
	if err != nil {
		return
	}
	request.Header.Set("Content-Type", "application/json")
	response, err := http.DefaultClient.Do(request)
	if err != nil {
		return
	}
	_, _ = io.Copy(io.Discard, io.LimitReader(response.Body, 65536))
	_ = response.Body.Close()
}

func sleep(ctx context.Context, delay time.Duration) bool {
	timer := time.NewTimer(delay)
	defer timer.Stop()
	select {
	case <-ctx.Done():
		return false
	case <-timer.C:
		return true
	}
}

func nextBackoff(current, interval time.Duration) time.Duration {
	next := current * 2
	limit := interval * 8
	if limit < time.Minute {
		limit = time.Minute
	}
	if next > limit {
		return limit
	}
	return next
}

func stringField(value any) string {
	text, _ := value.(string)
	return text
}
