// Package serve is the only molq business process.
package serve

import (
	"sync"

	"github.com/MolCrafts/molq/config"
	"github.com/MolCrafts/molq/protocol"
	"github.com/MolCrafts/molq/registry"
	"github.com/MolCrafts/molq/scheduler"
)

// Service answers public RPC methods for one registry.
type Service struct {
	Registry   *registry.Registry
	ID         string
	mu         sync.Mutex
	obs        *Observation
	schedulers map[string]scheduler.Scheduler
	locks      map[string]*sync.Mutex
	listeners  map[chan struct{}]struct{}
	config     *config.Store
	operations map[string]*remembered
}

// UseConfig loads the serve-owned settings file. An empty path leaves settings unset.
func (s *Service) UseConfig(path string) error {
	if path == "" {
		return nil
	}
	store, err := config.Open(path)
	if err != nil {
		return err
	}
	s.config = store
	s.ensure()
	s.obs.SetMaxEntries(store.Entries(4096))
	return nil
}

// Open prepares a serve process for a registry path.
func Open(registryPath string) (*Service, error) {
	reg, err := registry.Open(registryPath)
	if err != nil {
		return nil, err
	}
	id, err := registry.NewHex()
	if err != nil {
		_ = reg.Close()
		return nil, err
	}
	return &Service{Registry: reg, ID: id}, nil
}

// Notify wakes every event subscriber.
func (s *Service) Notify() {
	s.ensure()
	s.mu.Lock()
	defer s.mu.Unlock()
	for listener := range s.listeners {
		select {
		case listener <- struct{}{}:
		default:
		}
	}
}

// Listen returns a private wakeup channel. The returned function removes it.
func (s *Service) Listen() (<-chan struct{}, func()) {
	s.ensure()
	listener := make(chan struct{}, 8)
	s.mu.Lock()
	if s.listeners == nil {
		s.listeners = map[chan struct{}]struct{}{}
	}
	s.listeners[listener] = struct{}{}
	s.mu.Unlock()
	return listener, func() {
		s.mu.Lock()
		if _, ok := s.listeners[listener]; ok {
			delete(s.listeners, listener)
			close(listener)
		}
		s.mu.Unlock()
	}
}

// Since reads the event ring.
func (s *Service) Since(cursor string) map[string]any {
	s.ensure()
	return s.obs.Since(cursor)
}

// Close releases resources owned by this process.
func (s *Service) Close() error { return s.Registry.Close() }

// Call validates and executes one public method.
func (s *Service) Call(method string, params map[string]any) (any, error) {
	contract := protocol.Current()
	if err := contract.Validate(method, params); err != nil {
		return nil, err
	}
	return s.callDeduped(method, params)
}

func (s *Service) invoke(method string, params map[string]any) (any, error) {
	contract := protocol.Current()
	if method == "molq.hello" {
		return hello{
			Version:       version{Major: contract.Version()["major"], Minor: contract.Version()["minor"]},
			Release:       contract.Release(),
			SchemaVersion: 2,
			RegistryID:    s.Registry.ID,
			InstanceID:    s.ID,
			Methods:       contract.Methods(),
			Limits:        limits{MaxFrameBytes: 1048576, BatchSize: 128},
		}, nil
	}
	return s.dispatch(method, params)
}

type version struct {
	Major int `json:"major"`
	Minor int `json:"minor"`
}

type limits struct {
	MaxFrameBytes int `json:"max_frame_bytes"`
	BatchSize     int `json:"batch_size"`
}

type hello struct {
	Version       version  `json:"version"`
	Release       string   `json:"release"`
	SchemaVersion int      `json:"schema_version"`
	RegistryID    string   `json:"registry_id"`
	InstanceID    string   `json:"runtime_instance_id"`
	Methods       []string `json:"methods"`
	Limits        limits   `json:"limits"`
}
