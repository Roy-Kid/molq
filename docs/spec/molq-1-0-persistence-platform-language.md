# Persistence、平台与语言设计已合并

状态：历史入口，2026-10-07 收敛。原设计已由 [单一 runtime 主 spec](molq-1-0-runtime-spec.md)取代，不作为独立实现依据。

SQLite只实现runtime-owned registry/settings/presets；clients无SQL，Job状态不默认持久化。语言和部署位置不冻结架构，不要求Go/Rust或MPSmanager。

现行约束见 [50 条原则及最新修订](molq-1-0-principles.md)。capability清单/协商已取消；任务schema校验与Scheduler渲染检查保留，实际资源请求交原生调度器接受或拒绝。
