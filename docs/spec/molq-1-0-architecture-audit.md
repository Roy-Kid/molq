# 历史审计：此前 24 条原则与 0.8 实现

历史审计：本文描述重构前 0.8.1 的证据与问题；不作为 0.9.0 实现指导。现行实现见 [runtime spec](molq-1-0-runtime-spec.md) 与 [0.9.0 ledger](implementation-0-9-0.md)。


日期：2026-10-07。基线：`6215c15`，包版本 `0.8.1`，加上审计时的工作区。
范围：`src/molq/`、现有测试、包入口、文档及仓库开发约束。
状态：历史基线，仅保留旧编号与已验证证据。本文11/7/4/2计数对应 [旧24条原则快照](molq-1-0-legacy-24-principles.md)，**不是现行50条原则的冲突数量**。
当前约束以 [50条原则及取消capability的最新修订](molq-1-0-principles.md)为准，实现草案集中在 [单一runtime spec](molq-1-0-runtime-spec.md)。下面旧整改建议中的能力清单/native escape/多份部署设计不能覆盖新规范。

## 结论与计数口径

| 分类 | 条数 | 铁律编号 |
|---|---:|---|
| 明确冲突 V | 11 | 1、2、4、8、10、11、15、17、19、20、22 |
| 部分符合，仍需补齐 P | 7 | 3、6、9、12、13、21、24 |
| 当前范围内符合 OK | 4 | 7、14、16、18 |
| 尚无契约或无法从代码验证 M | 2 | 5、23 |
| 合计 | 24 | |

这不是“24 个独立 bug”的计数。多条原则共享同一根因；下文合并为 **13 个可执行整改项**。
V 表示现有代码行为明确偏离 1.0 原则，不表示该行为违反了 0.8 的既有契约。
P 不按明确违反计数；M 也不能据此推断普通 Agent 实际执行过哪些命令。
OK 只覆盖当前检查到的实现，不代表未来能力已经齐备。

## 逐条对照

| # | 原则 | 判断 | 代码证据与解释 | 整改 |
|---|---|---|---|---|
| 1 | 三个 client 平权 | V | `cli/_helpers.py:68` 构造 Python `Submitor`；`cli/jobs.py:175` 调用其提交 API。仓库没有 TS SDK。CLI 已包装 Python SDK | A01 |
| 2 | RPC 是一级公共接口 | V | `cluster.py:100` 在 SDK 中构造 backend，`:140` 直接查询 scheduler；`submitor.py:669` 直接提交。没有 RPC 服务、wire schema 或协议版本 | A01 |
| 3 | Python OOP 领域对象 | P | 已有 Cluster / Submitor / JobHandle；`__init__.py:94` 的公共导出缺少 Molq、JobCollection。现有对象同时持有服务端职责，需重塑而非否认已有 OOP | A02 |
| 4 | Agent-first CLI | V | `cli/jobs.py:189` 文本输出，`:229` Rich 表，`:200` 多种错误合并 exit 1；缺全局结构化输出、稳定 schema、错误分类和机器发现 | A03 |
| 5 | Agent 默认经 molq 管理任务 | M | CLI 已提供常规操作，但没有 Agent 工作流契约。backend 调用 sbatch 等是正常实现，不能据此判违反 | A03 |
| 6 | daemon 是可选自动化 client | P | `submitor.py:452` 已有定时观察，不把显式前台 wait/follow 判违规；但 daemon 与 SDK 内 backend/store 耦合，缺通过公共 server API 的多 Cluster 自动化观察。常驻 server 不属于此条禁止对象；RPC 缺失另列第 2 条 | A04 |
| 7 | 不造庞大 engine/controller/core | OK | 当前已有普通 scheduler、transport、配置、monitor 等模块，没有额外巨型 core 抽象。单文件职责过多另列治理问题 | 保留 |
| 8 | 语言无关的原生异步与有界并发 | V | `submitor.py:465` 的持续后台循环串行 sleep/poll，`transport.py:169` 阻塞 subprocess，`plugins/nerve/__init__.py:138` threading.Timer；未形成可取消、有界的多 Cluster runtime。Python 或同步前台 facade 本身不违规 | A04 |
| 9 | cluster / batch 为并发单位 | P | `reconciler.py:87` 已批量 poll；但 `monitor.py:59` 每个 wait 自行 reconcile_one，`reconciler.py:233` 逐个 terminal 查询。当前没有一 job 一个永久 coroutine，不能夸大为该问题 | A11 |
| 10 | scheduler 是 Job 真相 | V | `submitor.py:268` 读 DB；`:361` 主动写 CANCELLED；`reconciler.py:148` 已存终态不再询问 scheduler。失联后可永久写 LOST | A07 |
| 11 | 默认不持久化 Job 状态/历史 | V | `submitor.py:128` 默认开 jobs.db；`:645` 插入所有任务；`store/schema.py:36` Job 全记录，`:63` transition 历史 | A08 |
| 12 | SQLite 由 molq-owned durable state 决定 | P | `store/schema.py:109` 的 allocation 使用统计确有 molq-owned 数据；ShellScheduler 也有自有执行凭据。不能仅因用了 SQLite 判违反。但目前无存储必要性决策，且与 Job 镜像强耦合 | A08 |
| 13 | Cluster 必须持久化 | P | `config.py:33` profiles 保存 scheduler/host/defaults；但 `cluster.py:57` 动态创建目标无需注册，缺公共 server 的权威 registry/API 和监控开关 | A05 |
| 14 | registry 只保存计算语义 | OK | 当前 `MolqProfile` 保存名称、scheduler、host/defaults/options；没有把解析出的 IdentityFile/ProxyJump 存进 profiles。完整 registry 尚待实现 | 保留/A05 |
| 15 | OpenSSH 管 SSH 配置/复用 | V | `cluster.py:211` ssh -G 后将 port/identity 再写入 options；`transport.py:528` 即使已有用户 ControlPath 仍强制 ControlMaster=auto；`:567` 覆盖主机密钥策略 | A09 |
| 16 | 不重造 SSH connection pool | OK | `transport.py:463` 调用系统 ssh/rsync，复用由 OpenSSH ControlPath 完成；没有 Python 长期 socket/session pool | 保留 |
| 17 | SSH alias 与 Cluster 分开 | V | `cli/setup.py:80` 将 profiles 和裸 SSH aliases 合列为 clusters；`cli/_helpers.py:55` 按名称猜 SSH，未知名字在 `:64` 落到 local | A06 |
| 18 | Transport / Scheduler 正交 | OK | `cluster.py:100` 显式组合；`scheduler/shell.py:51` 与各 batch backend 都使用注入的 Transport | 保留 |
| 19 | scheduler 语义留在 backend | V | `types.py:80`、`:177` 公开 Memory/Duration 的 to_slurm/to_pbs/to_lsf 格式；`reconciler.py:209` 对 Shell 专有 terminal 方法 duck typing。resource/dependency 主映射已有正确归属 | A10 |
| 20 | cache 可丢弃、有 freshness | V | `handle.py:29` 仅返回 `_state`，无 freshness；`submitor.py:275` 返回永久 DB 记录，`reconciler.py:73` 以 DB active 集决定观察对象。last_polled 列存在不等于公共 freshness 契约 | A07 |
| 21 | notification 是观察层 | P | `plugin.py:35` 只读上下文；`callbacks.py:90` 捕获异常，Nerve HTTP 有 timeout。可是任意 handler 仍在提交/观察路径同步执行，慢 observer 可阻塞操作 | A12 |
| 22 | Retry 移出 1.0 核心 | V | `models.py:98` RetryPolicy；`submitor.py:757` terminal 回调自动重提并 sleep；`store/schema.py:41` attempt/lineage/retry_group；CLI 也有 retry 参数 | A13 |
| 23 | 实现语言不是公共契约 | M | 当前契约是 Python 导出、实例和私有 Store 访问，没有独立于实现语言的契约。Go/Rust 可替换性需通过 wire 合约测试证明 | A01 |
| 24 | 不重复成熟设施 | P | scheduler/SSH 基础设施已有正确复用；但永久任务镜像、SSH 策略覆盖重复承担职责；前台观察本身不是重复基础设施 | A04/A07/A09 |

表中相对路径均位于 `src/molq/`。下面给出主要源码链接。

## 13 个整改项

### A01 — 公共边界改为 RPC（P0）

证据：[CLI 打开 Submitor](https://github.com/Roy-Kid/molq/blob/6215c15/src/molq/cli/_helpers.py#L68)、[SDK 构造 backend](https://github.com/Roy-Kid/molq/blob/6215c15/src/molq/cluster.py#L100)。
所有业务 client 使用同一版本化协议；CLI 不 import Python OOP client，SDK 不 import scheduler/transport/store/daemon。短期 stdio server 与常驻 HTTP/WS server 共用 services；自动观察 daemon 和网页都作为公共 RPC clients。
TS SDK 与 Python SDK、CLI 一起通过同一套 contract fixtures，1.0 GA 不允许缺席。

### A02 — 完整 OOP projection（P1）

证据：[公共导出](https://github.com/Roy-Kid/molq/blob/6215c15/src/molq/__init__.py#L94)、[JobHandle](https://github.com/Roy-Kid/molq/blob/6215c15/src/molq/handle.py#L15)。
提供 Molq / Cluster(Target alias) / Job / JobCollection；对象只持有 client 与引用。
status 返回带来源和 freshness 的 snapshot；wait 有 observer 时使用 server 共享观察，无 observer 时 foreground client 经公共 live batch RPC 查询。

### A03 — Agent-first CLI 和使用契约（P0）

证据：[提交输出与错误](https://github.com/Roy-Kid/molq/blob/6215c15/src/molq/cli/jobs.py#L175)、[Rich list](https://github.com/Roy-Kid/molq/blob/6215c15/src/molq/cli/jobs.py#L229)。
制定 JSON/NDJSON envelope、稳定 exit code、schema/discover 命令、非交互默认。
记录 Agent 常规任务流程和明确的 backend escape hatch；Rich 作为显式 human projection。
CLI 的输入解析失败、server 不可达也必须结构化表达；observer 不可用不应令普通业务失败。

### A04 — 公共 server 与独立自动化 client（P0）

证据：[现有 daemon](https://github.com/Roy-Kid/molq/blob/6215c15/src/molq/submitor.py#L452)、[现有等待循环](https://github.com/Roy-Kid/molq/blob/6215c15/src/molq/monitor.py#L55)、[CLI 日志轮询](https://github.com/Roy-Kid/molq/blob/6215c15/src/molq/cli/_helpers.py#L230)。
server（stdio/HTTP/WS）提供 submit/query/cancel/config update、registry/cache/event fan-out与backend；daemon是独立自动化client，定时经公共RPC查询/通知，不打开DB/SSH。网页经同源HTTP/WS API，不依赖observer存活。
原生异步 I/O、有界并发与取消/deadline 不绑定 Python；不以无界线程包装阻塞监控作为长期架构。
允许显式前台 wait/watch/follow，经公共RPC按session/Cluster批量查询，退出即停。server listener可常驻，但不自主扫描scheduler；周期观察属于daemon自动化client。

### A05 — 权威 Cluster registry（P0）

证据：[profiles](https://github.com/Roy-Kid/molq/blob/6215c15/src/molq/config.py#L33)、[Cluster 构造](https://github.com/Roy-Kid/molq/blob/6215c15/src/molq/cluster.py#L57)。
保存 stable cluster ID/name、scheduler、transport.kind、ssh_alias、defaults/options、monitor.enabled。
增删改经 RPC、server 原子持久化；server 重启恢复 registry，daemon 经 API 加载观察配置。profile 是可迁移来源，不是多个目标定义的隐式合并。

### A06 — 停止猜测目标（P0）

证据：[目标判断及 local 回退](https://github.com/Roy-Kid/molq/blob/6215c15/src/molq/cli/_helpers.py#L41)、[混合 discovery](https://github.com/Roy-Kid/molq/blob/6215c15/src/molq/cli/setup.py#L80)。
`--cluster` 只解析 registry；不存在就是 CLUSTER_NOT_FOUND。
SSH aliases 只出现在独立 discovery 接口，注册时显式指定 scheduler；不可自动成为计算目标。

### A07 — 状态来源、错误和 cache 分离（P0）

证据：[空结果隐藏 transport 失败](https://github.com/Roy-Kid/molq/blob/6215c15/src/molq/scheduler/slurm.py#L128)、[永久 LOST](https://github.com/Roy-Kid/molq/blob/6215c15/src/molq/reconciler.py#L238)、[终态跳过查询](https://github.com/Roy-Kid/molq/blob/6215c15/src/molq/reconciler.py#L148)、[取消后本地终态](https://github.com/Roy-Kid/molq/blob/6215c15/src/molq/submitor.py#L351)。
查询区分 found / absent / unavailable；连接失败不产生 Job 终态。
cancel 返回控制请求是否被 backend 接受，终态来自后续确认。
SDK snapshot 公布 observed_at/freshness/source；丢弃 cache 后从 queue/accounting 重新查询。

### A08 — 删除默认 Job 镜像，逐项审定 durable state（P0）

证据：[默认 DB](https://github.com/Roy-Kid/molq/blob/6215c15/src/molq/submitor.py#L128)、[所有 Job 入库](https://github.com/Roy-Kid/molq/blob/6215c15/src/molq/submitor.py#L645)、[allocation 统计](https://github.com/Roy-Kid/molq/blob/6215c15/src/molq/store/schema.py#L109)、[Shell exit receipt](https://github.com/Roy-Kid/molq/blob/6215c15/src/molq/scheduler/shell.py#L100)。
分别评估 registry、Shell launch receipts、artifact manifests、allocation presets/使用统计。
HPC Job 状态、transition、retry family 不保留默认 DB；真实 owned state 允许使用 SQLite，并用表/字段白名单、独立 repositories 和恢复契约约束范围。
不能把 launch receipt 当作重复的 HPC accounting，也不能为了无 DB 而丢失 Shell 的唯一退出证据。

### A09 — SSH 配置单一归属（P1）

证据：[配置快照再注入](https://github.com/Roy-Kid/molq/blob/6215c15/src/molq/cluster.py#L211)、[强制 ControlMaster](https://github.com/Roy-Kid/molq/blob/6215c15/src/molq/transport.py#L528)、[host-key policy](https://github.com/Roy-Kid/molq/blob/6215c15/src/molq/transport.py#L567)。
registry 只存 alias。ssh -G 的解析值仅诊断展示，不重新注入常规连接参数。
默认继承用户 multiplexing 和信任策略；molq-managed master 若保留，必须显式 opt-in 并仍由 OpenSSH 管理。
BatchMode 与禁用 TTY 属于后台操作要求，可以保留；不能据此覆盖 IdentityFile、ProxyJump、ControlMaster 等。

### A10 — backend 语义收口（P1）

证据：[Memory 转译](https://github.com/Roy-Kid/molq/blob/6215c15/src/molq/types.py#L78)、[Duration 转译](https://github.com/Roy-Kid/molq/blob/6215c15/src/molq/types.py#L175)、[Shell 专用探测](https://github.com/Roy-Kid/molq/blob/6215c15/src/molq/reconciler.py#L207)。
公用值类型只保留 bytes/seconds 与通用解析；格式和资源语义移入各 backend。
以统一 async query_many/history/cancel_many 接口覆盖 local 与 HPC，service 不再探测 Shell 私有扩展。
raw dependency 字符串迁到显式 backend_options escape hatch；正常依赖为 typed JobRef/condition。

### A11 — 全链路批处理（P1）

证据：[批量 active 查询](https://github.com/Roy-Kid/molq/blob/6215c15/src/molq/reconciler.py#L86)、[逐 Job accounting](https://github.com/Roy-Kid/molq/blob/6215c15/src/molq/reconciler.py#L232)。
复用 poll_many 的思路，终态/accounting、cancel、wait watchers 也按 cluster 聚合。
受 backend 能力限制的逐项调用必须有限并发；不承诺每个 scheduler 都有真正原生 batch cancel/history。

### A12 — observer 不能阻塞操作（P1）

证据：[inline handlers](https://github.com/Roy-Kid/molq/blob/6215c15/src/molq/callbacks.py#L90)、[Nerve debounce](https://github.com/Roy-Kid/molq/blob/6215c15/src/molq/plugins/nerve/__init__.py#L134)。
daemon 使用有界队列、独立有界 observer、超时与溢出 resync。
插件获得不可变 observation 和 health 信息，不能决定 Job 状态，不能进入 scheduler 操作提交路径。

### A13 — 移除核心 Retry（P0）

证据：[终态自动重提](https://github.com/Roy-Kid/molq/blob/6215c15/src/molq/submitor.py#L757)、[持久化 attempt](https://github.com/Roy-Kid/molq/blob/6215c15/src/molq/store/schema.py#L41)。
1.0 wire/SDK/CLI 不暴露自动 Job RetryPolicy；删除 terminal→resubmit 和 lineage 状态机。
网络连接恢复 backoff 不属于任务重试，可以保留。外部 workflow 可显式再次 submit，每次都有独立 JobRef。

## 已验证的具体行为

使用 `.venv/bin/python`、内存 SQLite 和模拟失联 Transport，未连接真实 HPC、未取消真实任务：

1. Slurm poll_many 的 transport 异常返回 `{}`；reconciler 将 RUNNING 写为 LOST。
2. scheduler 恢复后 reconcile_one 直接返回已存 LOST，不再 poll。
3. Slurm cancel 的 transport 异常被吞掉；Submitor 仍写 CANCELLED。
4. 显式指定不存在的 SSH/Cluster 名称，resolve_target 构造 LocalTransport。
5. 已有用户 ControlPath 时 `_mux_opts()` 仍返回 `ControlMaster=auto` 覆盖参数。

这些是本地复现实测；其他判断来自源码与测试阅读。
现有 `tests/test_reconciler.py:107`、`:151` 和 `tests/test_cli.py:389` 已把部分旧行为固化为测试，迁移时必须重写预期；现有测试通过不等于符合 1.0。

额外运行当前 reconciler、monitor、CLI、plugin 四组测试：**61 passed，2 skipped**（两条 allocation CLI 测试因当前未接线而跳过）。这验证现状基线，不验证尚未实现的 1.0 spec。

## 约束文件的额外问题（不计入 24 条）

- AGENTS.md 的 0.8 架构段以 Store 为中心，声明 Cluster 是纯 config，但实际对象会构造 backend；还写 config.toml，代码 `config.py:77` 已使用 config.yaml。本轮加 1.0 方向提示，旧段仍仅描述现状。
- `.agents/skills/molq-spec/SKILL.md`、`molq-arch/SKILL.md` 仍要求早期 SchedulerAdapter / Pydantic 架构，与当前冻结 dataclass 架构及本次原则不一致。
- `transport.py` 1098 行，超过 AGENTS.md 的 800 行上限。改造时拆为 package，不新造巨型 core 文件。
- 指令引用的 RTK.md 在仓库与搜索到的技能位置未找到；本次未能应用其未知内容。

## 下一步设计

见 [单一 Runtime 主 spec](molq-1-0-runtime-spec.md)。该 spec 给出 wire、OOP、registry、cache、Scheduler、owned state、错误、迁移阶段和验收要求。
本审计只修改文档，不修改运行时代码，也不宣称迁移已经实现。现行职责划分以主 spec 为准；历史审计不改写为新架构已经实现。

## 现行原则的新重点（源码复核，不计入旧条数）

| 当前原则 | 当前代码证据 | 新设计要求 |
|---|---|---|
| 1–4、7–11 | CLI仍通过Submitor，SDK直接backend；无统一RPC contract | 提取唯一runtime，各client只投影，stdio/HTTP/WS同代码 |
| 12–14 | `reconciler.py`依赖store计算变化，现有daemon绑定Submitor | observation/diff/events在runtime单一实现，Observer只采样/通知 |
| 最新取消capability | `scheduler/base.py:117`的SchedulerCapabilities、`validation.py:100`全True fallback | 删除公共capability层/Cluster清单，不迁入1.0；Scheduler 直接校验渲染 |
| 33–39 | `models.py:171` JobSpec只有一个command；`types.py:288` JobExecution只有env/path；`scheduler/script.py:51`只渲染一个payload | allocation+units/sequence/parallel原生schema，保持单unit简单 |
| 40、45–47 | `types.py:264` JobScheduling保留rawdependency；`scheduler/slurm.py:276`已有backend内GPU映射 | 公共schema删除native syntax，不以rawflags替代领域模型；native 渲染归 Scheduler |
| 41–44 | `types.py:253`只有gpu_count/type，Slurm渲染目前无MPSresource路径 | typed scheduler-managed MPS request；未实现明确报错，实际存在交原生调度器判断，无自动MPS代理 |

尚未实现新的runtime、多unit schema或Observer；这些是静态源码差距，不是新增功能测试结果。现有61passed/2skipped仍仅是旧实现基线。
