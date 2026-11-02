# Arrhenius 实测验收

日期：2026-10-13。通过 molq 的公开 RPC、CLI 和 Python SDK 操作；原生调度器仍是任务事实来源。任务使用现有 Cluster Arrhenius，未改变 Cluster 定义、用户默认配置或已有任务。

## Atomiverse 测试

- 两端源码版本相同：`420c2e46d91bf116a94ed8b9d62e0b12feee7238`。
- 原有 CPU 构建未完成、未注册测试；本次在 `/home/jicli594/work/molq-acceptance-20261013/build-core` 独立构建。
- 复用已有依赖的源码目录，所有新构建产物位于本次测试目录。
- 账户：`naiss2026-1-53-cpu`，来自已有 CPU allocation；用户授权任取一个项目账户。
- 资源：1 node、1 task、8 CPU、16,000,000,000 bytes/node、15 分钟上限，cpu partition。
- 任务号：**3777168**。提交 13:00:27 UTC；运行 13:01:20 UTC；结束 13:02:24 UTC。
- 原生 accounting：COMPLETED、exit_code 0、elapsed 64 秒。
- `test_mat3`、`test_vec3`、`test_real_harmonics`、`test_units`、`test_cpu_box`、`test_cpu_chunked_range` 六组全部通过；CTest 0.13 秒。
- 任务自身打印 `ATOMIVERSE_ACCEPTANCE=PASS`，stderr 为空。

[执行脚本](evidence/2026-10-13-arrhenius/atomiverse-core.sh)、[JobSpec](evidence/2026-10-13-arrhenius/spec.json)、[完整构建与测试输出](evidence/2026-10-13-arrhenius/stdout.log)、[原生终态经 RPC 返回](evidence/2026-10-13-arrhenius/terminal.json)。

## molq 控制面

- files.write 上传脚本；files.read 验证非对齐偏移和完整输出下载。
- jobs.preview、jobs.submit 成功；首次缺少 account 的原生拒绝明确为 not_applied，没有接受任务；指定账户后仅提交一次。
- watch 使用同一个临时本地 HTTP serve（认证配置只保存在权限 0600 的临时文件），实测 queued → running → succeeded；订阅通知接收端未设置。
- 结束后 live status 通过 sacct 返回确认成功；cached status 标示缓存年龄。
- Python SDK 8 个并发 HTTP 查询全部成功，随后 wait 确认成功；本次合计约 0.34 秒。原生查询调用合并数量由可计数的并发回归测试验证，此延迟不单独证明减少了多少次 SSH。
- logs.read 正常返回 allocation 默认 stdout；该文件为空，因为 ExecutionUnit 的 stdout 显式重定向到测试日志，完整日志另经 files.read 下载。
- 对已结束任务 cancel 返回 already_terminal，没有重新发送 native cancellation。

[提交响应](evidence/2026-10-13-arrhenius/submit.json)、[Python SDK 验收](evidence/2026-10-13-arrhenius/python-http.json)、[终态取消语义](evidence/2026-10-13-arrhenius/terminal-cancel.json)。

## 实测发现与修复

squeue 在已结束任务离开队列后，返回 exit 0、jobs=[] 和 `Zero jobs to dump` 提示；旧解析器将所有 warning 当成 partial failure，导致后续 status 错误。现仅接受实际捕获的确切空队列提示，正常查询 accounting；其他 warning、非空队列携带该提示及错误响应仍拒绝。新增回归测试覆盖终态查询、空队列列表和异常响应；重建后真实任务终态查询通过。

本次验收覆盖 Slurm CPU 的实际提交、队列、accounting、观察和文件路径；不代表 Atomiverse 全部科学方法、GPU、MPI、MPS 或 PBS/LSF 已实测通过。测试输出和原生 allocation 收据保留。
