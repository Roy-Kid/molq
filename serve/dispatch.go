package serve

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"path"
	"strings"
	"sync"
	"time"

	"github.com/MolCrafts/molq/protocol"
	"github.com/MolCrafts/molq/scheduler"
	"github.com/MolCrafts/molq/transport"
)

func (s *Service) ensure() {
	if s.obs == nil {
		s.obs = NewObservation(4096)
		s.schedulers = map[string]scheduler.Scheduler{}
		s.locks = map[string]*sync.Mutex{}
	}
}

func (s *Service) cluster(name string) (map[string]any, scheduler.Scheduler, error) {
	s.ensure()
	cluster, err := s.Registry.Get(name)
	if err != nil {
		return nil, nil, err
	}
	id, _ := cluster["id"].(string)
	s.mu.Lock()
	defer s.mu.Unlock()
	item := s.schedulers[id]
	if item == nil {
		target := transport.Create(mapValue(cluster["transport"]))
		item, err = scheduler.Create(cluster, target)
		if err != nil {
			return nil, nil, err
		}
		s.schedulers[id] = item
	}
	if s.locks[id] == nil {
		s.locks[id] = &sync.Mutex{}
	}
	return cluster, item, nil
}

func (s *Service) lock(id string) *sync.Mutex {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.locks[id] == nil {
		s.locks[id] = &sync.Mutex{}
	}
	return s.locks[id]
}

func (s *Service) dispatch(method string, params map[string]any) (any, error) {
	s.ensure()
	ctx, cancel := context.WithTimeout(context.Background(), 120*time.Second)
	defer cancel()
	switch method {
	case "schema.discover":
		var document any
		if err := json.Unmarshal(protocol.Current().Raw(), &document); err != nil {
			return nil, err
		}
		return document, nil
	case "clusters.list":
		return s.Registry.List()
	case "clusters.get":
		return s.Registry.Get(stringField(params["cluster"]))
	case "clusters.register", "clusters.update", "clusters.remove":
		return s.mutateCluster(method, params)
	case "jobs.validate", "jobs.preview", "jobs.submit":
		return s.submit(ctx, method, params)
	case "events.subscribe":
		return s.Since(stringField(params["cursor"])), nil
	case "jobs.get_many":
		refs := make([]map[string]any, 0)
		for _, item := range anySlice(params["refs"]) {
			refs = append(refs, mapValue(item))
		}
		return s.many(ctx, refs, stringField(params["consistency"]), params)
	case "jobs.get":
		result, err := s.many(ctx, []map[string]any{mapValue(params["ref"])}, stringField(params["consistency"]), params)
		if err != nil {
			return nil, err
		}
		errors, _ := mapValue(result["coverage"])["errors"].([]map[string]any)
		if len(errors) > 0 {
			return nil, fromData(errors[0])
		}
		return result, nil
	case "jobs.list":
		_, values, err := s.listCluster(ctx, stringField(params["cluster"]))
		if err != nil {
			return nil, err
		}
		return Collection(filterSnapshots(values, params), nil), nil
	case "jobs.observe", "jobs.history":
		return s.query(ctx, method, params)
	case "jobs.cancel", "jobs.cancel_many":
		return s.cancel(ctx, method, params)
	case "logs.read":
		return s.logs(ctx, params)
	case "files.read", "files.write":
		return s.files(ctx, method, params)
	case "files.transfer":
		return s.transfer(ctx, params)
	case "config.reload", "config.get", "config.set", "presets.list", "presets.get", "presets.set":
		return s.configure(method, params)
	default:
		return nil, protocol.Fail("METHOD_NOT_FOUND", "Method is not implemented", map[string]any{"method": method})
	}
}

func (s *Service) mutateCluster(method string, params map[string]any) (any, error) {
	var definition map[string]any
	if method != "clusters.remove" {
		source := params
		if method == "clusters.update" {
			source = mapValue(params["definition"])
		}
		var err error
		definition, err = cleanDefinition(source)
		if err != nil {
			return nil, err
		}
	}
	var revision *int
	if method != "clusters.register" {
		value, ok := asInt(params["expected_revision"])
		if !ok {
			return nil, protocol.Fail("INVALID_INPUT", "Cluster update requires expected_revision", nil)
		}
		revision = &value
	}
	key := ""
	if method != "clusters.register" {
		key = stringField(params["cluster"])
	}
	result, err := s.Registry.Mutate(definition, key, revision)
	if err != nil {
		return nil, err
	}
	s.ensure()
	s.obs.Clear()
	s.mu.Lock()
	s.schedulers = map[string]scheduler.Scheduler{}
	s.mu.Unlock()
	s.Notify()
	return result, nil
}

func cleanDefinition(source map[string]any) (map[string]any, error) {
	definition := mapValue(deepCopy(source))
	if definition["transport"] == nil {
		definition["transport"] = map[string]any{"kind": "local"}
	}
	if definition["defaults"] == nil {
		definition["defaults"] = map[string]any{}
	}
	root := stringField(definition["target_root"])
	if !strings.HasPrefix(root, "/") || strings.Contains(root, "..") || strings.ContainsAny(root, "\n\r") {
		return nil, protocol.Fail("INVALID_INPUT", "target_root must be an absolute target POSIX path", nil)
	}
	definition["target_root"] = path.Clean(root)
	delete(definition, "id")
	delete(definition, "revision")
	return definition, nil
}

func (s *Service) submit(ctx context.Context, method string, params map[string]any) (any, error) {
	cluster, item, err := s.cluster(stringField(params["cluster"]))
	if err != nil {
		return nil, err
	}
	spec, err := Normalize(mapValue(params["spec"]), mapValue(cluster["defaults"]))
	if err != nil {
		return nil, err
	}
	if err := item.Validate(spec); err != nil {
		return nil, err
	}
	revision, _ := asInt(cluster["revision"])
	if method == "jobs.validate" {
		return map[string]any{"spec": spec, "cluster_revision": revision}, nil
	}
	directory := path.Join(stringField(cluster["target_root"]), newHex())
	if method == "jobs.preview" {
		script, err := item.Render(spec, directory)
		if err != nil {
			return nil, err
		}
		return map[string]any{"spec": spec, "script": script, "cluster_revision": revision}, nil
	}
	id, _ := cluster["id"].(string)
	s.lock(id).Lock()
	defer s.lock(id).Unlock()
	for _, edge := range anySlice(mapValue(spec["scheduling"])["dependencies"]) {
		ref := mapValue(mapValue(edge)["ref"])
		if err := s.checkRef(ref); err != nil {
			return nil, err
		}
		if ref["cluster_id"] != id {
			return nil, protocol.Fail("INVALID_INPUT", "Native dependencies must belong to the same Cluster", nil)
		}
		if _, err := s.identity(ctx, item, ref); err != nil {
			return nil, err
		}
	}
	current, err := s.Registry.Get(id)
	if err != nil {
		return nil, err
	}
	if currentRevision, _ := asInt(current["revision"]); currentRevision != revision {
		return nil, protocol.Fail("CONFLICT", "Cluster changed before native submission", nil)
	}
	job, err := item.Submit(ctx, spec, directory)
	if err != nil {
		return nil, err
	}
	ref, err := s.ref(cluster, job)
	if err != nil {
		return nil, err
	}
	value := Snapshot(ref, &job, nil)
	s.obs.Remember(value)
	return map[string]any{"ref": ref, "snapshot": value, "cluster_revision": revision, "outcome": "accepted"}, nil
}

func (s *Service) ref(cluster map[string]any, job scheduler.Job) (map[string]any, error) {
	if job.Incarnation == "" {
		return nil, protocol.Fail("JOB_IDENTITY_UNVERIFIABLE", "Native submit identity evidence unavailable", map[string]any{"native_id": job.NativeID})
	}
	return map[string]any{
		"registry_id": s.Registry.ID, "cluster_id": cluster["id"],
		"native_id": job.NativeID, "incarnation": job.Incarnation,
	}, nil
}

func (s *Service) checkRef(ref map[string]any) error {
	if ref["registry_id"] != s.Registry.ID {
		return protocol.Fail("REGISTRY_MISMATCH", "JobRef belongs to a different registry", nil)
	}
	return nil
}

func (s *Service) identity(ctx context.Context, item scheduler.Scheduler, ref map[string]any) (scheduler.Job, error) {
	jobs, err := item.QueryMany(ctx, []string{stringField(ref["native_id"])})
	if err != nil {
		return scheduler.Job{}, err
	}
	job, ok := jobs[stringField(ref["native_id"])]
	if !ok || job.Incarnation == "" {
		return scheduler.Job{}, protocol.Fail("JOB_IDENTITY_UNVERIFIABLE", "Cannot confirm native allocation identity", nil)
	}
	if job.Incarnation != ref["incarnation"] {
		return scheduler.Job{}, protocol.Fail("JOB_IDENTITY_MISMATCH", "Native ID has been reused", nil)
	}
	return job, nil
}

func (s *Service) many(ctx context.Context, refs []map[string]any, consistency string, params map[string]any) (map[string]any, error) {
	if consistency == "" {
		consistency = "live"
	}
	found := map[string]map[string]any{}
	var failures []map[string]any
	groups := map[string][]map[string]any{}
	for _, ref := range refs {
		if err := s.checkRef(ref); err != nil {
			return nil, err
		}
		if consistency != "live" {
			if cached := s.obs.Cached(ref, nil); cached != nil {
				found[RefKey(ref)] = cached
				continue
			}
		}
		if consistency == "cached" {
			failure := protocol.Fail("CACHE_MISS", "No cached observation", nil).Data()
			failures = append(failures, failure)
			found[RefKey(ref)] = Snapshot(ref, nil, failure)
			continue
		}
		groups[stringField(ref["cluster_id"])] = append(groups[stringField(ref["cluster_id"])], ref)
	}
	for id, batch := range groups {
		_, item, err := s.cluster(id)
		if err != nil {
			failure := asData(err)
			failures = append(failures, failure)
			for _, ref := range batch {
				found[RefKey(ref)] = Snapshot(ref, nil, failure)
			}
			continue
		}
		s.lock(id).Lock()
		jobs, err := item.QueryMany(ctx, nativeIDs(batch))
		s.lock(id).Unlock()
		if err != nil {
			failure := asData(err)
			failures = append(failures, failure)
			for _, ref := range batch {
				found[RefKey(ref)] = Snapshot(ref, nil, failure)
			}
			continue
		}
		for _, ref := range batch {
			job, ok := jobs[stringField(ref["native_id"])]
			if ok && job.Incarnation != ref["incarnation"] {
				failure := protocol.Fail("JOB_IDENTITY_MISMATCH", "Native identity no longer matches", nil).Data()
				failures = append(failures, failure)
				found[RefKey(ref)] = Snapshot(ref, nil, failure)
				continue
			}
			var observed *scheduler.Job
			if ok {
				observed = &job
			}
			value := Snapshot(ref, observed, nil)
			found[RefKey(ref)] = value
			s.obs.Remember(value)
		}
	}
	ordered := make([]map[string]any, 0, len(refs))
	for _, ref := range refs {
		ordered = append(ordered, found[RefKey(ref)])
	}
	return Collection(ordered, failures), nil
}

func (s *Service) listCluster(ctx context.Context, name string) (map[string]any, []map[string]any, error) {
	cluster, item, err := s.cluster(name)
	if err != nil {
		return nil, nil, err
	}
	id, _ := cluster["id"].(string)
	s.lock(id).Lock()
	jobs, err := item.List(ctx)
	s.lock(id).Unlock()
	if err != nil {
		return nil, nil, err
	}
	values := make([]map[string]any, 0, len(jobs))
	for _, job := range jobs {
		if job.Incarnation == "" {
			return nil, nil, protocol.Fail("JOB_IDENTITY_UNVERIFIABLE", "Queue entry lacks stable native submit identity", nil)
		}
		ref, err := s.ref(cluster, job)
		if err != nil {
			return nil, nil, err
		}
		value := Snapshot(ref, &job, nil)
		s.obs.Remember(value)
		values = append(values, value)
	}
	return cluster, values, nil
}

func (s *Service) query(ctx context.Context, method string, params map[string]any) (any, error) {
	if method == "jobs.history" && params["refs"] == nil {
		since, until, err := historyWindow(params)
		if err != nil {
			return nil, err
		}
		cluster, item, err := s.cluster(stringField(params["cluster"]))
		if err != nil {
			return nil, err
		}
		id, _ := cluster["id"].(string)
		s.lock(id).Lock()
		jobs, err := item.HistoryRange(ctx, since, until)
		s.lock(id).Unlock()
		if err != nil {
			return nil, err
		}
		return historyResult(jobs, func(job scheduler.Job) (map[string]any, error) {
			return s.ref(cluster, job)
		}, params, since, until), nil
	}
	var refs []map[string]any
	if raw, ok := params["refs"].([]any); ok {
		for _, item := range raw {
			refs = append(refs, mapValue(item))
		}
	}
	var cluster map[string]any
	if name := stringField(params["cluster"]); name != "" && method == "jobs.observe" {
		var err error
		cluster, err = s.Registry.Get(name)
		if err != nil {
			return nil, err
		}
	}
	scope := mustJSON(map[string]any{"cluster": clusterID(cluster), "refs": refKeys(refs)})
	if refs == nil {
		if cluster == nil {
			return nil, protocol.Fail("INVALID_INPUT", "observe requires explicit refs or Cluster", nil)
		}
		_, values, err := s.listCluster(ctx, stringField(cluster["id"]))
		if err != nil {
			return nil, err
		}
		for _, value := range values {
			refs = append(refs, mapValue(value["ref"]))
		}
		if cursor := stringField(params["cursor"]); cursor != "" {
			if baselineScope, items, ok := s.obs.Baseline(cursor); ok && baselineScope == string(scope) {
				known := map[string]bool{}
				for _, ref := range refs {
					known[RefKey(ref)] = true
				}
				for identity, value := range items {
					if !known[identity] {
						refs = append(refs, mapValue(value["ref"]))
					}
				}
			}
		}
	}
	result, err := s.many(ctx, refs, stringField(params["consistency"]), params)
	if err != nil {
		return nil, err
	}
	if method != "jobs.observe" {
		return result, nil
	}
	observed := s.obs.Observe(result, string(scope), stringField(params["cursor"]))
	return observed, nil
}

func (s *Service) cancel(ctx context.Context, method string, params map[string]any) (any, error) {
	refs := []map[string]any{}
	if method == "jobs.cancel_many" {
		for _, item := range anySlice(params["refs"]) {
			refs = append(refs, mapValue(item))
		}
	} else {
		refs = append(refs, mapValue(params["ref"]))
	}
	results := make([]map[string]any, 0, len(refs))
	for _, ref := range refs {
		outcome, err := s.cancelOne(ctx, ref)
		if err != nil {
			if len(refs) == 1 {
				return nil, err
			}
			results = append(results, map[string]any{"ref": ref, "error": asData(err)})
			continue
		}
		outcome["ref"] = ref
		results = append(results, outcome)
	}
	if method == "jobs.cancel" {
		return results[0], nil
	}
	partial := false
	for _, result := range results {
		if result["error"] != nil {
			partial = true
		}
	}
	return map[string]any{"results": results, "partial_failure": partial}, nil
}

func (s *Service) cancelOne(ctx context.Context, ref map[string]any) (map[string]any, error) {
	if err := s.checkRef(ref); err != nil {
		return nil, err
	}
	_, item, err := s.cluster(stringField(ref["cluster_id"]))
	if err != nil {
		return nil, err
	}
	id := stringField(ref["cluster_id"])
	s.lock(id).Lock()
	defer s.lock(id).Unlock()
	job, err := s.identity(ctx, item, ref)
	if err != nil {
		return nil, err
	}
	return item.Cancel(ctx, job)
}

func (s *Service) logs(ctx context.Context, params map[string]any) (any, error) {
	ref := mapValue(params["ref"])
	if err := s.checkRef(ref); err != nil {
		return nil, err
	}
	cluster, item, err := s.cluster(stringField(ref["cluster_id"]))
	if err != nil {
		return nil, err
	}
	job, err := s.identity(ctx, item, ref)
	if err != nil {
		return nil, err
	}
	stream := stringField(params["stream"])
	if stream == "" {
		stream = "stdout"
	}
	var location string
	if stream == "stdout" && job.StdoutPath != nil {
		location = *job.StdoutPath
	}
	if stream == "stderr" && job.StderrPath != nil {
		location = *job.StderrPath
	}
	if location == "" {
		if job.Workdir == nil {
			return nil, protocol.Fail("FILE_UNAVAILABLE", "Native log location unavailable", nil)
		}
		location = path.Join(*job.Workdir, stream)
	}
	offset, _ := asInt(params["offset"])
	limit, ok := asInt(params["limit"])
	if !ok {
		limit = 262144
	}
	target, ok := item.(interface {
		Transport() transport.Transport
	})
	_ = target
	_ = ok
	data, err := transport.Create(mapValue(cluster["transport"])).Read(ctx, location, offset, limit)
	if err != nil {
		return nil, err
	}
	return map[string]any{"text": string(data), "next_offset": offset + len(data), "bytes_read": len(data)}, nil
}

func (s *Service) files(ctx context.Context, method string, params map[string]any) (any, error) {
	cluster, _, err := s.cluster(stringField(params["cluster"]))
	if err != nil {
		return nil, err
	}
	location, err := targetPath(cluster, stringField(params["path"]))
	if err != nil {
		return nil, err
	}
	target := transport.Create(mapValue(cluster["transport"]))
	if method == "files.read" {
		offset, _ := asInt(params["offset"])
		limit, ok := asInt(params["limit"])
		if !ok {
			limit = 262144
		}
		data, err := target.Read(ctx, location, offset, limit)
		if err != nil {
			return nil, err
		}
		return map[string]any{"data": base64.StdEncoding.EncodeToString(data), "next_offset": offset + len(data)}, nil
	}
	decoded, err := base64.StdEncoding.DecodeString(stringField(params["data"]))
	if err != nil {
		return nil, protocol.Fail("INVALID_INPUT", "File content must be base64", nil)
	}
	if len(decoded) > 262144 {
		return nil, protocol.Fail("INVALID_INPUT", "File chunk too large", nil)
	}
	var offset *int
	if value, ok := asInt(params["offset"]); ok {
		offset = &value
	}
	if err := target.Write(ctx, location, decoded, offset); err != nil {
		return nil, err
	}
	start := 0
	if offset != nil {
		start = *offset
	}
	return map[string]any{"outcome": "applied", "next_offset": start + len(decoded)}, nil
}

func targetPath(cluster map[string]any, requested string) (string, error) {
	root := stringField(cluster["target_root"])
	result := requested
	if !strings.HasPrefix(result, "/") {
		result = path.Join(root, result)
	}
	cleanRoot := path.Clean(root)
	clean := path.Clean(result)
	if clean != cleanRoot && !strings.HasPrefix(clean, cleanRoot+"/") {
		return "", protocol.Fail("PERMISSION_DENIED", "File operations are scoped to Cluster target_root", nil)
	}
	return clean, nil
}

func nativeIDs(refs []map[string]any) []string {
	ids := make([]string, len(refs))
	for i, ref := range refs {
		ids[i] = stringField(ref["native_id"])
	}
	return ids
}

func clusterID(cluster map[string]any) any {
	if cluster == nil {
		return nil
	}
	return cluster["id"]
}

func refKeys(refs []map[string]any) any {
	if refs == nil {
		return nil
	}
	keys := make([]string, len(refs))
	for i, ref := range refs {
		keys[i] = RefKey(ref)
	}
	return keys
}

func fromData(data map[string]any) error {
	context, _ := data["context"].(map[string]any)
	outcome, _ := data["outcome"].(string)
	return protocol.FailOutcome(stringField(data["kind"]), stringField(data["message"]), outcome, context)
}

func anySlice(value any) []any {
	items, _ := value.([]any)
	return items
}
