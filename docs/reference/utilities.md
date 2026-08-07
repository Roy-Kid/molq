# Supporting APIs

Remote directories, configuration, SSH discovery, lifecycle callbacks, and the
exception hierarchy.

::: molq.workspace.Workspace

::: molq.workspace.Project

::: molq.config.MolqProfile

::: molq.config.MolqConfig

::: molq.config.load_config

::: molq.config.load_profile

::: molq.ssh_config.SshHost

::: molq.ssh_config.list_ssh_hosts

::: molq.ssh_config.ssh_alias_names

::: molq.ssh_config.resolve_ssh_host

::: molq.options.SshTransportOptions

::: molq.callbacks.EventType

::: molq.callbacks.EventPayload

::: molq.callbacks.EventBus

::: molq.plugin.MolqPlugin

::: molq.plugin.PluginContext

::: molq.plugin.PluginManager

::: molq.plugin.available_plugins

`BUILTIN_PLUGIN_FACTORIES` maps each official plugin name to the factory
that builds it. Official names win over third-party entry points of the
same name.

::: molq.plugin.create_plugin

::: molq.config.enabled_plugin_names

::: molq.store.dependency_relation_state

::: molq.errors
    options:
      members:
        - MolqError
        - ConfigError
        - SubmitError
        - CommandError
        - ScriptError
        - SchedulerError
        - JobNotFoundError
        - MolqTimeoutError
        - StoreError

## Dashboard

The full-screen monitor behind `molq monitor`. These names are exported
lazily — importing `molq` does not pull in the terminal UI.

::: molq.dashboard.MolqMonitor

::: molq.dashboard.RunDashboard

::: molq.dashboard.DashboardState

::: molq.dashboard.JobRow
