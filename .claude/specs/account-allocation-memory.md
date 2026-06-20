# Spec: AllocationMemory —「已用配置记忆」

```yaml
slug: account-allocation-memory
status: code-complete
created: 2026-05-31
scope: local config memory (record-used + select), no cluster query, no admin
```

## 摘要

为 molq 增加一个**纯本地的「已用配置记忆」**：每次提交成功后，把本次实际生效的调度配置（partition / account / qos / reservation）按 cluster 记下来；之后 molexp 等组件能通过只读 API 把「用过的配置」呈现给用户直接复选，免去重复填写 account / partition。

**范围边界（关键）**：

- **不**向集群查询任何东西（无 `sinfo` / `sacctmgr` 发现）。
- **不**向集群校验值是否合法 / 用户是否有权使用。
- **不**做任何 `sacctmgr` 写操作或需要管理员权限的动作。
- 只记**调度身份**（partition/account/qos/reservation），不记资源（cpu/mem/gpu/time）。

保持 molq「零 import 副作用、纯提交客户端」定位不变。

## 现状依据（已确认）

- scheduling（partition/account/qos/reservation）已序列化进 `jobs.request_json`；`jobs` 表按 `cluster_name` + `submitted_at` 组织（`src/molq/store.py:42`）。
- 但清理是**真删行**：`src/molq/store.py:839` `DELETE FROM jobs`，受 retention 控制。→ 故**不**从 job 历史派生记忆，改用独立持久表，避免 retention 清理连带丢失配置记忆。
- molexp 提交路径 `molexp/src/molexp/plugins/submit_molq/submit.py:220` 直接构造 `JobScheduling(partition/account/qos)` 喂给 `submitor.submit_job(...)` → 它需要的就是一个「读出历史配置」的只读 API 来填自己的选择 UI。
- store 归 Submitor 生命周期层；Cluster 是纯目标、无 store。→ `remembered_allocations()` 挂在 **Submitor** 上（molexp 也是拿 Submitor 提交的，正好对齐）。

## 设计

### ① 持久表（`store.py`，schema v7→v8，纯加表迁移）

```sql
CREATE TABLE IF NOT EXISTS allocations (
    cluster_name TEXT NOT NULL,
    alloc_key    TEXT NOT NULL,   -- 归一化身份: f"{partition}|{account}|{qos}|{reservation}"，None→""
    partition    TEXT,
    account      TEXT,
    qos          TEXT,
    reservation  TEXT,
    label        TEXT,
    first_used   REAL NOT NULL,
    last_used    REAL NOT NULL,
    use_count    INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (cluster_name, alloc_key)
);
```

- `alloc_key` 用归一化串作去重键，规避 nullable 字段在唯一约束里的 NULL 歧义（SQLite 中 NULL 互不相等，会导致同一配置重复入表）。
- upsert：
  `INSERT INTO allocations (...) VALUES (...) ON CONFLICT(cluster_name, alloc_key) DO UPDATE SET last_used=excluded.last_used, use_count=use_count+1`。
- 迁移 v7→v8 纯加表：`CREATE TABLE IF NOT EXISTS allocations (...)` + 置 `schema_version=8`，**不**触碰 `jobs` 表数据。沿用现有 `_migrate_*` 框架追加一段 v7→v8。
- 新增 `JobStore.record_allocation(cluster_name, scheduling, *, now)` 与 `JobStore.list_allocations(cluster_name, *, limit=None)`（按 `last_used` 倒序）。
- （第二批可选）`JobStore.label_allocation(cluster_name, alloc_key, label)`。

### ② 公共只读类型（`models.py`，`__init__.py` 导出）

```python
@dataclass(frozen=True)
class RememberedAllocation:
    partition: str | None
    account: str | None
    qos: str | None
    reservation: str | None
    label: str | None
    last_used: float
    use_count: int
```

### ③ 记录（`submitor.py`，自动）

`submit_job` 在**调度器返回成功之后**（已拿到 `scheduler_job_id`），若生效 scheduling 的 partition/account/qos/reservation 至少一项非空，则调用 `store.record_allocation(...)`：

- 失败 / 被拒的提交**不记**（避免记住坏配置）。
- scheduling 全为 None 时**不记**（无意义的空配置）。
- 重试沿用同一配置会累加 `use_count`，可接受（反映真实使用频次）。
- 记录的是**合并后生效**的 scheduling（显式字段 + profile defaults 合并结果），不是用户原始入参。

### ④ 读取（`Submitor` 上，molexp / CLI 消费）

```python
def remembered_allocations(self, *, limit: int | None = None) -> list[RememberedAllocation]:
    """本 cluster 用过的调度配置，last_used 倒序。"""
```

molexp 拿到列表渲染成「之前的配置」供选；用户选中后把字段回填进 `submit_job(scheduling=JobScheduling(...))`。molq 不替 molexp 做 UI；契约就是这个只读 API。

### ⑤ CLI（`cli/main.py`，挂现有 Typer app）

- `molq allocations <cluster>` → Rich 表格：partition / account / qos / 上次使用 / 次数 / label。`<cluster>` 解析复用 `history` 命令现有路径（profile / ssh-alias）。无记录时给友好提示。
- （第二批可选）`molq allocations <cluster> --label <name> <alloc_key>` 给某条配置命名。

## 涉及文件

| 文件 | 改动 |
|------|------|
| `src/molq/store.py` | `allocations` 建表；v7→v8 加表迁移；`record_allocation` / `list_allocations`（+ 可选 `label_allocation`） |
| `src/molq/models.py` | `RememberedAllocation` frozen dataclass |
| `src/molq/__init__.py` | 导出 `RememberedAllocation` |
| `src/molq/submitor.py` | 提交成功后 `record_allocation`；新增 `remembered_allocations` |
| `src/molq/cli/main.py` | `allocations` 命令 + Rich 表格 |
| `tests/test_store.py` | 建表 / upsert 去重 / nullable key / 排序 / v7→v8 迁移 |
| `tests/test_submitor.py` | 成功记录 / 失败不记 / 全 None 不记 / 重试累加 / `remembered_allocations` |
| `tests/test_cli.py` | `allocations` 表格输出 + 空提示 |

## 任务

1. ✅ Add `allocations` table + v7→v8 additive migration in `store.py`.
2. ✅ Add `JobStore.record_allocation` (upsert by normalized `alloc_key`) + `list_allocations` (recency-ordered, `limit`).
3. ✅ Add `RememberedAllocation` frozen dataclass in `models.py`; export from `__init__.py`.
4. ✅ Record effective scheduling after successful submit in `submit_job` (skip on failure / all-None).
5. ✅ Add `Submitor.remembered_allocations(limit=None)`.
6. ✅ Add `molq allocations <cluster>` CLI command with Rich table + empty-state hint.
7. ⏸ (deferred / 第二批) `--label` 命名 + `JobStore.label_allocation`.

## 测试策略

- **store**：upsert 去重（同身份 `use_count+1`、`last_used` 刷新）；含 None 的不同组合不互相冲突（归一化 key 生效）；`list_allocations` 按 `last_used` 倒序 + `limit` 生效；v7→v8 迁移后老 DB 可正常打开、`jobs` 数据无损、`allocations` 表存在。
- **submitor**：成功提交后写入生效 scheduling；调度器报错时不写；全 None scheduling 不写；同配置重复提交累加 `use_count`；`remembered_allocations()` 返回本 cluster 记录、最近优先。
- **retention 独立性**：清理删除 jobs 行后，`remembered_allocations()` 仍返回历史配置。
- **cli**：表格行列正确；无记录时友好提示。
- 测试用 `:memory:` 或 `tmp_path` SQLite（不 mock SQLite）；覆盖率沿用 80%+；`ruff format --check` + `ruff check` + `ty check src/` 通过。

## Out of scope（明确不做）

- `sinfo` / `sacctmgr` 向集群发现 partition/account/qos。
- 向集群校验所选 partition/account 是否合法 / 有权使用。
- 任何 `sacctmgr` 写操作（建/改 account、加用户、改 limit/fairshare）或需管理员权限的动作。
- 记录资源维度（cpu/memory/gpu/time_limit）——仅记调度身份。
- 跨机器 / 云端同步配置记忆。
- 自动「推荐/挑选最优配置」策略。
