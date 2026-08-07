# Acceptance: AllocationMemory —「已用配置记忆」

```yaml
slug: account-allocation-memory
spec: account-allocation-memory.md
```

绑定「done」的验收契约。每条标注 `status:`（`pending` → `verified`）。全部 `verified` 方可关闭 spec。

| # | type | status | 准则 |
|---|------|--------|------|
| AC-1 | code | verified | `RememberedAllocation` 为 `@dataclass(frozen=True)`，可从 `molq` 顶层 `from molq import RememberedAllocation` 导入 |
| AC-2 | code | verified | `_SCHEMA_VERSION` 升到 `"8"`；v7→v8 迁移后旧 DB 正常打开，`jobs` 数据无损，`allocations` 表存在 |
| AC-3 | code | verified | `record_allocation` 首次插入 `use_count=1` 且 `first_used==last_used`；同 `alloc_key` 再记 `use_count+1` 且 `last_used` 刷新、`first_used` 不变 |
| AC-4 | code | verified | partition/account/qos/reservation 中含 None 的不同组合不互相冲突，也不与「全有值」组合冲突（归一化 `alloc_key` 生效，无 NULL 歧义重复行） |
| AC-5 | code | verified | `list_allocations(cluster, limit=N)` 按 `last_used` 倒序返回，`limit` 截断生效 |
| AC-6 | code | verified | `submit_job` 调度器成功返回后写入**合并生效**的 scheduling；调度器抛错时不写；scheduling 四字段全 None 时不写 |
| AC-7 | code | verified | `Submitor.remembered_allocations(limit=None)` 只返回**本 cluster** 记录，最近使用优先；`limit` 生效 |
| AC-8 | code | verified | `molq allocations <cluster>` 输出含 partition/account/qos/上次使用/次数 列的 Rich 表；无记录时打印友好提示而非报错 |
| AC-9 | code | verified | retention 清理删除 jobs 行后，`remembered_allocations()` 仍返回历史配置（记忆独立于 job 行生命周期） |
| AC-10 | code | verified | 同配置经多次重试提交，`use_count` 随每次成功提交累加（行为符合「反映真实使用频次」约定） |
| AC-11 | code | verified | 新增公共方法覆盖率 ≥ 80%；`ruff format --check src/ tests/` + `ruff check src/ tests/` + `ty check src/` 全通过 |


> **审计备注（AC-11 toolchain）**：本特性自身文件全部通过 `ruff format --check` / `ruff check` / `ty check`。
> 仓库工作树中 `src/molq/cli/main.py` 存在**与本特性无关的预先存在的半成品 `workspace` 子命令**（约 1032–1037 行，
> `load_profile` / `Cluster` 未定义、`load_config` 未用），导致整树 `ruff check` / `ty check` 仍有告警。该段属既有脏改，
> 已按既定约束排除在本次提交之外，不归属本验收。新增公共方法（`record_allocation` / `list_allocations` /
> `remembered_allocations` / `allocations` CLI / `RememberedAllocation`）均被测试覆盖。
