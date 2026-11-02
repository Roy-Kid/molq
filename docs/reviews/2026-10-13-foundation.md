# molq 0.9.0 基础审查与修复

日期：2026-10-13。范围：Go serve/RPC/registry/transport、CLI/watch、Python/TypeScript wire、打包与 CI。以 AGENTS.md 的 0.9.0 合同为准；旧技能中的 Python 服务、Submitor、Pydantic 和 capability 规则不适用。

## 修复结果

CODE REVIEW：molq 0.9.0 基础代码。ARCHITECTURE：本轮 RPC 边界问题已修复；PERFORMANCE：本轮已确认热点已优化并测量；DOCUMENTATION：核心合同及公开 Python API docstring 已补全；SYSTEM SAFETY：本轮已复现问题修复并回归；CODE QUALITY：改动源码模块保持 800 行以内；IMMUTABILITY：公共 frozen dataclasses 与生成投影未改变。

SUMMARY：首轮修复 1 CRITICAL、13 HIGH、5 MEDIUM 类问题；下表后续追加收尾项。该数量不代表整个项目不存在其他问题。

| 优先级 | 审查发现 | 已实施修复 |
| --- | --- | --- |
| CRITICAL | CLI、rpc、watch、diagnostics 本地直接打开 registry 并调用 serve；部分路径忽略 endpoint | 客户端通过公共 Go wire 连接 HTTP 或临时 stdio serve；只有 serve 入口组装服务；Go/Python import 守卫防止退化 |
| HIGH | serve 首次并发请求可能重置初始化状态；配置内存读写存在竞争 | serve 使用 sync.Once；配置快照使用 RWMutex；并发回归和 race 检查 |
| HIGH | 损坏 SQLite 缺少 registry_id 时被生成新身份；null cluster definition 导致 panic | 明确返回 STATE_SCHEMA_INCOMPATIBLE，拒绝修复和改写原文件；真实 SQLite 回归 |
| HIGH | bounded 查询忽略 max_age，可能长期返回旧状态 | 使用请求年龄上限或配置默认值；覆盖小数、零值及请求覆盖配置 |
| HIGH | 跨 Cluster 查询/取消串行，等待 Cluster 锁无法取消 | 有限批次 worker；全进程最多 8 个受控目标操作；每 Cluster 串行；等待支持取消；保持结果顺序与单项错误 |
| MEDIUM | Cluster observe 对刚读取的队列再次 QueryMany | 复用 List 的 snapshots，仅补查上一轮基线中已离开队列的 refs |
| HIGH | 任务变化不唤醒订阅；stdio 订阅未随连接释放，注册时可能漏掉事件 | 实际 changes 唤醒；关闭/替换订阅释放 listener；等待前补读 event ring；推送保持帧上限 |
| HIGH | 超限 stdio 帧的尾部会作为下一条请求执行；逐字节读取开销很大 | 整帧排空到 LF；内存有界；缓冲块读取；精确支持 1 MiB JSON 与额外 LF |
| HIGH | WebSocket 默认输入上限不足 1 MiB；TS subscribe 请求 /ws，但服务仅提供 /rpc | 服务采用协议帧上限；TS 使用同一 /rpc；真实网络订阅验收 |
| HIGH | 已启动命令取消/输出超限被当作正常退出；辅助子进程继承管道导致滞留 | 保留 dispatched 证据与错误优先级；输出超限立即取消；WaitDelay 清理自身辅助进程组；已独立启动 allocation 的存活回归 |
| HIGH | mutation 断连和部分目标写入失败可误报未执行 | Go wire 与目标写入/transfer 保留 unknown outcome；不自动重连、重发或换服务；队列中尚未 dispatch 的请求保持 not_applied |
| HIGH | AsyncWire 取消留下响应，污染下一请求；Node 丢弃启动 id:null 错误 | 取消隔离 stdio 会话；保留 CancelledError；显式关闭后重连；Node 保留结构化启动错误并强制回收超时进程 |
| HIGH | POSIX syscall 直接出现在跨平台配置锁/transport 中 | 分离平台文件锁和进程控制；Windows 控制面可编译 |
| MEDIUM | 本地 FIFO/设备路径会阻塞或被原子写替换；取消前仍可能写文件 | 普通文件校验、非阻塞打开、句柄再验证与取消检查；保留普通文件及现有 symlink 语义 |
| MEDIUM | SSH 文件读写 dd bs=1 开销高，父目录计算使用宿主平台规则 | 便携 64 KiB 对齐读取并精确切片；对齐 offset 写入用块大小；POSIX target 路径处理；任意偏移/EOF/引号路径回归 |
| MEDIUM | 慢通知逐条阻塞 watch；resync 客户端自行构造完成事件 | 通知通过 128 项有界队列独立发送；有限关闭排空；watch 仅消费服务 changes，历史显式查询 |
| HIGH | 标准源码包不包含 Go 源码/embedded schema，无法生成 wheel | MANIFEST 包含完整 Go 构建输入和 canonical schema；从 sdist 构建并安装验收 |
| MEDIUM | 不存在的配置文件被入口拒绝，与配置存储的空文档语义不一致 | 缺失默认/显式文件开始为空，首次写入走 RPC；损坏文件仍报错 |
| HIGH | CI 缺少 Go 测试与平台构建；文档仍描述旧实现 | CI 加入 Go、race、平台二进制/Windows 编译；更新架构/API/CLI/观察文档 |

| HIGH | 相同 live 查询串行重复访问原生 Scheduler | 相同 Cluster revision 与完整身份集合共享进行中的查询；128 组上限、独立取消、最后等待者取消原生请求；完成后重新查询 |
| HIGH | Cluster 更新与 Scheduler 缓存替换之间可混用定义版本 | 定义读取、Registry mutation 和 Scheduler 缓存替换在同一临界区；并发切换 launcher 验证绑定一致性 |
| HIGH | Baseline/Since/Observe 暴露内部可变 map；缓存大量编码与深复制占据锁 | 输入和输出隔离，内部值不可变；记录一次字节预算，大型编码和复制移至锁外；身份键用 JSON 元组避免分隔符碰撞 |
| HIGH | 本地普通文件/NFS 系统调用阻塞请求，context 无法强制返回 | 每个 chunk 使用显式私有辅助进程；父请求按 deadline 返回，最多 8 个进程，回收前保留额度；已尝试写入断连为 unknown |
| HIGH | Slurm/PBS 将 20 位 decimal memory_bytes 转为 int，可能溢出或向下请求资源 | math/big 精确向上取整并输出十进制 MiB；完整 schema 范围边界回归 |
| MEDIUM | 公共 Python API 缺少参数、返回值、错误和不确定结果说明 | 源投影与请求值补齐 Google 风格文档，重新生成 async 投影；行为保持不变 |

| HIGH | Slurm 正常空队列 warning 被当成 partial failure，结束后的 status 失败 | 只接受实测确切空队列提示；正常查 accounting；异常响应保持拒绝；真实任务终态重验通过 |
| MEDIUM | 共享大环境值按单元重复生成，可把 1 MiB 请求放大到约 128 MiB 脚本 | 公共环境函数只生成一次，单元切换目录后调用并应用覆盖；256 单元/500 KiB 环境脚本约 532 KiB；真实 Bash 验证优先级、隔离和退出码 |

## 验证

- 合同和客户端生成、generated drift 检查通过；未手改生成文件。
- Go 全量 CGO_ENABLED=0 测试、全量 race 检查与 go vet 通过。
- Python 15 项测试通过，覆盖率 82.74%；Ruff、格式检查与 ty 通过。
- TypeScript 7 项测试通过，包含实际 stdio、HTTP 和 WebSocket 订阅。
- Windows amd64 serve 与所有 Go 测试包交叉编译通过；本地没有执行 Windows 二进制。
- 标准 sdist → 当前平台 wheel 构建通过；独立环境安装后在仓库外通过模块、公开导出、资源、本地 Shell 和 console 验收。
- 1 MiB stdio 帧读取由约一百万次底层单字节读取改成最多 300 次缓冲读取；回归测试检查读次数。
- Cluster observe 回归检查首次采样 1 次 List、0 次 QueryMany；任务离开队列后才补查 accounting。

## 性能测量

最终复测将 HEAD 与最终 Observation 实现分别放入隔离临时 module，复用同一基准和辅助函数，顺序运行 `-benchmem -count 3 -benchtime 300ms`（Apple M4、Go 1.26、10 个逻辑线程）。并发缓存 Remember + Cached 从 16.7–16.9 µs/op、269 allocations 降至 1.63–1.72 µs/op、72 allocations，约 10 倍；1,024 snapshots Observe 从 8.73–8.80 ms/op、约 174k allocations 降至 4.17–4.22 ms/op、约 69.7k allocations，约 2.1 倍。基准位于 serve/observation_bench_test.go；结果只描述本机内存热点，不代表 HPC 任务吞吐提升。

[修改前测量](evidence/2026-10-13-arrhenius/benchmark-before.txt)、[最终测量](evidence/2026-10-13-arrhenius/benchmark-after.txt)。

## 边界与后续债务

Arrhenius 真实 Slurm CPU 验收：Atomiverse 420c2e46d91bf116a94ed8b9d62e0b12feee7238，任务 3777168，账户 naiss2026-1-53-cpu。六组基础单元测试全部通过，CTest 0.13 秒，构建和测试 allocation 运行 64 秒，退出码 0。watch 观察 queued → running → succeeded。详见 [Arrhenius 实测记录](2026-10-13-arrhenius.md)。PBS/LSF 仍为 fixtures；本次不证明 GPU、MPI、MPS 或完整科学方法回归通过。

本地文件的内核 I/O 仍可能推迟进程终止，但不会继续占用已截止的服务请求。辅助进程回收前保留额度，防止无限积累；强制结束可能留下本次写入的私有 .tmp 文件，目标文件或已发出写入的结果以 unknown 表达，不自动重发。

观察事件入环时仍有一次小对象编码，用于精确字节预算。大范围原生 accounting 输出仍受 1 MiB 目标输出上限约束；超限返回明确错误，应由调用者选择较窄时间窗口，不隐式重试。

通知是 fail-open：接收端过慢时队列满的通知可能丢弃；stdout 中的观察变化仍保留。独立 serve 实例不共享 cache/events/cursors，request_key 不提供跨重启 exactly-once。
