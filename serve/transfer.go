package serve

import (
	"context"
	"strconv"
	"strings"
	"time"

	"github.com/MolCrafts/molq/protocol"
	"github.com/MolCrafts/molq/transport"
)

func (s *Service) transfer(ctx context.Context, params map[string]any) (any, error) {
	source, _, err := s.cluster(stringField(params["source_cluster"]))
	if err != nil {
		return nil, err
	}
	destination, _, err := s.cluster(stringField(params["destination_cluster"]))
	if err != nil {
		return nil, err
	}
	src, err := targetPath(source, stringField(params["source_path"]))
	if err != nil {
		return nil, err
	}
	dst, err := targetPath(destination, stringField(params["destination_path"]))
	if err != nil {
		return nil, err
	}
	sourceTransport := mapValue(source["transport"])
	destTransport := mapValue(destination["transport"])
	args := []string{"rsync", "-a"}
	runner := transport.Create(sourceTransport)
	if !sameTransport(sourceTransport, destTransport) {
		args = append(args, "-e", "ssh -T -o BatchMode=yes")
		switch {
		case sourceTransport["kind"] == "local" && destTransport["kind"] == "ssh":
			args = append(args, "--", src, stringField(destTransport["alias"])+":"+shellQuote(dst))
		case sourceTransport["kind"] == "ssh" && destTransport["kind"] == "local":
			runner = transport.Create(destTransport)
			args = append(args, "--", stringField(sourceTransport["alias"])+":"+shellQuote(src), dst)
		default:
			return nil, protocol.Fail("TRANSFER_UNSUPPORTED", "Two distinct SSH targets require explicit staging; no remote alias guessing", nil)
		}
	} else {
		if src == dst {
			return nil, protocol.Fail("INVALID_INPUT", "Transfer source and destination are the same file", nil)
		}
		args = append(args, "--", src, dst)
	}
	result, err := runner.Run(ctx, args, 90*time.Second, nil, false)
	if err != nil {
		return nil, err
	}
	if result.ReturnCode != 0 {
		return nil, protocol.FailOutcome("FILE_UNAVAILABLE", "Target rsync transfer failed", "unknown", map[string]any{"returncode": result.ReturnCode})
	}
	size, err := runner.Run(ctx, []string{"wc", "-c", src}, 30*time.Second, nil, false)
	var bytes any
	if err == nil && size.ReturnCode == 0 {
		fields := strings.Fields(size.Text())
		if len(fields) > 0 {
			if number, convErr := strconv.Atoi(fields[0]); convErr == nil {
				bytes = number
			}
		}
	}
	return map[string]any{"outcome": "applied", "bytes": bytes}, nil
}

func sameTransport(left, right map[string]any) bool {
	return left["kind"] == right["kind"] && left["alias"] == right["alias"]
}

func shellQuote(value string) string {
	return "'" + strings.ReplaceAll(value, "'", `'\''`) + "'"
}
