# 历史快照：此前 24 条原则

仅用于解释旧审计编号，已由现行 50 条原则替代，不作为新实现约束。

# molq 1.0 架构铁律

用户讨论确定的约束，更新于 2026-10-07。具体字段、默认值和语言另见实现草案。
本轮重新划分 server/daemon：server 提供公共操作接口；daemon 位于 client 层，负责自动化观察。第 6 条不再宣称所有常驻进程只能是 daemon；第 8 条仍不绑定 Python。

1. **CLI、Python SDK、TypeScript SDK 地位完全平等。** 都是 molq client，谁也不包装谁，稳定业务能力尽量一一对应。网页与自动化 daemon 也使用公共 client 契约。
2. **RPC 是一级公共接口，molq-server 是公共操作边界。** 所有 clients，包括 daemon，都通过同一语言无关协议操作；server 可短期 stdio 或常驻 HTTP/WS，不要求 observer daemon 存活。
3. **Python SDK 必须是 OOP API。** 用户面对 Molq / Cluster(Target) / Job / JobCollection 等领域对象。
4. **CLI 必须 Agent-first。** 结构化输出、稳定 schema/exit code、非交互运行、良好 discoverability；Agent 不解析 Rich table。
5. **普通 Agent 默认通过 molq 管理任务。** sbatch/squeue/scancel/qsub 等是 escape hatch，不是常规生命周期接口。
6. **daemon 是可选的自动化 client，负责自主后台观察与通知。** 定时经公共 RPC 按 Cluster/batch 查询，管理 cadence/backoff 与通知；server 可常驻提供 API，但不自主轮询 Cluster。显式前台 wait/watch 可以经 RPC 查询，退出即停止。
7. **server/backend 与 daemon 分责。** domain、scheduler、transport、services/persistence 在 server 侧；daemon 不构造 backend、不直接读写 SQL/SSH。保持普通模块，不造庞大 engine/controller/core。
8. **原生异步 I/O 与有界并发是长期模型，不绑定实现语言/runtime。** Python asyncio、Go 的可取消 I/O/受控 goroutine、Rust async runtime 均可选择；支持取消、deadline、backpressure，不采用先阻塞监控以后再改的过渡架构。
9. **并发单位主要是 Cluster / batch operation。** server 合并并发查询、限制外部 I/O；observer/前台 client 按批调用 RPC，不为每 Job 建立永久 coroutine/thread/SSH/timer。跨 client 共享数据经同一 server。
10. **Scheduler 是任务运行状态的事实来源。** queue/accounting 优先；Shell backend 自产执行凭据是其原始证据。daemon 观察结果不能取代 scheduler。
11. **默认不持久化具体 HPC Job 状态和历史。** 不复制 scheduler 的永久镜像；SQLite 不作为 Job 状态机中心。
12. **允许 SQLite，但 persistence 有 owned-state 白名单。** Cluster/config/presets 等可保存；client/daemon 只经 RPC 更新，不因已有 jobs.db 恢复全任务镜像。
13. **Cluster 信息必须持久化，由 server registry 管理。** server 重启恢复目标，daemon 经 API 读取，不维护第二份 registry。
14. **Cluster registry 只保存 molq 计算语义。** stable name/id、scheduler、SSH alias、defaults/options、monitor 开关；不复制 OpenSSH 配置。alias 由 server host 解析。
15. **OpenSSH 管理 SSH 配置和连接复用。** Host/ProxyJump/IdentityFile/ControlMaster/ControlPath/ControlPersist 等归系统 OpenSSH。
16. **molq 不重造 SSH connection pool。** server transport 使用系统 ssh/rsync；已有 master 按用户配置复用；显式 managed master 仍由 OpenSSH multiplexing 实现。
17. **SSH host、Cluster、公共 server endpoint 是不同概念。** alias 描述连接，Cluster 描述计算目标，endpoint 描述操作入口；未知 Cluster 不猜成 alias 或本机。
18. **Transport 与 Scheduler 正交。** SSH 不理解 Slurm，Slurm 不实现 SSH；组合由 server 两层装配。
19. **Scheduler-specific 语义只在 backend。** resource translation、submit、queue parsing、cancel、accounting、dependency syntax 不泄漏到 clients/daemon/services。
20. **server cache 永远只是 cache。** 有 freshness，可丢弃并从 scheduler 重建；按授权 scope 隔离。observer baseline 和 event ring 也不持久化为第二事实来源。
21. **notification 是观察层，不参与任务正确性。** daemon/Nerve/UI/subscriber 故障不影响公共操作；无 observer 时不承诺 client 退出后的持续通知。
22. **Retry 不属于 1.0 核心。** 不引入自动 Job retry、attempt lineage 或对应持久化状态机；连接恢复 backoff 单独处理。
23. **内部实现语言不是公共契约。** server/backend 与自动化 client 可独立选 Python/Go/Rust；RPC 和 client 领域 API 不随之重设计。
24. **不重复成熟基础设施。** SSH 交给 OpenSSH，调度交给 scheduler；网页部署复用成熟 HTTP/TLS/身份设施，molq 专注统一控制、抽象、观察与接口。

> Client 平权，RPC 为界。
> Server 管操作，daemon 管自动观察，backend 管语义。
> Scheduler 管任务真相。
> Cluster 持久化，Job 尽量不持久化。
> SSH 交给 OpenSSH。
> 网页、Agent、daemon 都通过 molq。

新架构见 [公共 server、clients 与网页](molq-1-0-server-clients-web.md)；无 daemon 运行见 [部署与生命周期](molq-1-0-optional-daemon.md)。
