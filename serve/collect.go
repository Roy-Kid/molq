package serve

import (
	"context"
	"fmt"
	"os"
	"path"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	"github.com/MolCrafts/molq/protocol"
	"github.com/MolCrafts/molq/scheduler"
	"github.com/MolCrafts/molq/transport"
)

// jobIdentity is the name submit gives each job directory under JobRoot.
var jobIdentity = regexp.MustCompile(`^[0-9a-f]{32}$`)

// removeEmptyTree removes only empty directories, so it cannot destroy data;
// it succeeds when nothing is left at the path.
const removeEmptyTree = `find "$1" -depth -type d -exec rmdir -- {} \; 2>/dev/null; [ ! -e "$1" ]`

// archive is the serve-host directory that receives an SSH Cluster's job
// directories. Local targets already live on the serve host and have none.
func (s *Service) archive(cluster map[string]any) string {
	if clusterTransport(cluster)["kind"] != "ssh" {
		return ""
	}
	return filepath.Join(filepath.Dir(s.Registry.Path), "collected", stringField(cluster["id"]))
}

// collectable names the job directory submit created for a confirmed terminal
// job, on the target or already in archive. Jobs placed elsewhere, such as ones
// submitted outside molq, have none.
func collectable(job scheduler.Job, archive string) string {
	if !scheduler.Terminal(job.State) || job.Workdir == nil {
		return ""
	}
	dir := path.Clean(*job.Workdir)
	identity, parent := path.Base(dir), path.Dir(dir)
	onTarget := strings.HasSuffix(parent, "/"+scheduler.JobRoot)
	if !jobIdentity.MatchString(identity) || !(onTarget || (archive != "" && parent == filepath.ToSlash(archive))) {
		return ""
	}
	return identity
}

// collectTerminal collects every terminal job in one observation. Callers must
// not hold the Cluster's native slot.
func (s *Service) collectTerminal(ctx context.Context, cluster map[string]any, jobs []scheduler.Job) {
	for _, job := range jobs {
		s.collect(ctx, cluster, job)
	}
}

// collect moves a terminal job's directory from an SSH target to the serve
// host and returns the local copy, or "" when the job has none yet. rsync
// deletes each source file only after copying it, so an interrupted move
// leaves every file on one side and the next observation resumes it. A failure
// keeps the remote files and never changes the observation itself.
func (s *Service) collect(ctx context.Context, cluster map[string]any, job scheduler.Job) string {
	archive := s.archive(cluster)
	identity := collectable(job, archive)
	if identity == "" || archive == "" {
		return ""
	}
	final := filepath.Join(archive, identity)
	if isDirectory(final) {
		return final
	}
	s.mu.Lock()
	if s.collections == nil {
		s.collections = map[string]chan struct{}{}
	}
	if running := s.collections[final]; running != nil {
		s.mu.Unlock()
		select {
		case <-running:
		case <-ctx.Done():
		}
		if isDirectory(final) {
			return final
		}
		return ""
	}
	done := make(chan struct{})
	s.collections[final] = done
	s.mu.Unlock()
	defer func() {
		s.mu.Lock()
		delete(s.collections, final)
		s.mu.Unlock()
		close(done)
	}()
	if err := s.moveJobDirectory(ctx, cluster, path.Clean(*job.Workdir), final); err != nil {
		fmt.Fprintf(os.Stderr, "molq serve: job directory %s stays on Cluster %s: %s\n", identity, stringField(cluster["name"]), mustJSON(asData(err)))
		return ""
	}
	return final
}

func (s *Service) moveJobDirectory(ctx context.Context, cluster map[string]any, remote, final string) error {
	partial := filepath.Join(filepath.Dir(final), "."+filepath.Base(final)+".partial")
	if err := os.MkdirAll(partial, 0o700); err != nil {
		return protocol.Fail("FILE_UNAVAILABLE", "Cannot create the local job directory", map[string]any{"path": partial})
	}
	release, err := s.acquire(ctx, stringField(cluster["id"]))
	if err != nil {
		return err
	}
	defer release()
	binding := clusterTransport(cluster)
	source := location{transport: binding, path: remote + "/"}
	destination := location{transport: map[string]any{"kind": "local"}, path: filepath.ToSlash(partial) + "/"}
	runner, rsh, operands, err := transferRoute([]location{source}, destination)
	if err != nil {
		return err
	}
	args := append(append([]string{"rsync", "-a", "--remove-source-files"}, rsh...), "--")
	// A failed copy is not final: an earlier attempt may already have moved
	// everything, which the cleanup below confirms.
	copied, err := runner.Run(ctx, append(args, operands...), transferTimeout, nil, false)
	if err != nil {
		return err
	}
	cleaned, err := transport.Create(binding).Run(ctx, []string{"sh", "-c", removeEmptyTree, "sh", remote}, 30*time.Second, nil, false)
	if err != nil {
		return err
	}
	if cleaned.ReturnCode != 0 {
		return protocol.Fail("FILE_UNAVAILABLE", "Remote job directory is not empty after collection", map[string]any{
			"path": remote, "rsync_returncode": copied.ReturnCode,
			"stderr": strings.ToValidUTF8(string(copied.Stderr), "\uFFFD"),
		})
	}
	if err := os.Rename(partial, final); err != nil {
		return protocol.Fail("FILE_UNAVAILABLE", "Cannot finish the local job directory", map[string]any{"path": final})
	}
	return nil
}

// collectedPath maps a path inside the job's observed directory to the
// serve-host copy of that directory.
func collectedPath(local string, workdir *string, target string) (string, bool) {
	if local == "" || workdir == nil {
		return "", false
	}
	relative, ok := strings.CutPrefix(path.Clean(target), path.Clean(*workdir)+"/")
	if !ok {
		return "", false
	}
	return filepath.Join(local, filepath.FromSlash(relative)), true
}

func isDirectory(name string) bool {
	info, err := os.Stat(name)
	return err == nil && info.IsDir()
}
