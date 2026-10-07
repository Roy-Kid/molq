# 旧 RPC/daemon spec 已合并

状态：历史入口，2026-10-07 收敛。原设计已由 [单一 runtime 主 spec](molq-1-0-runtime-spec.md)取代，不作为独立实现依据。

公共RPC、OOP/CLI、runtime部署、schema与观察语义已集中到新主spec。daemon/Observer不承担runtime业务；不同channel使用同一实现。

现行约束见 [50 条原则及最新修订](molq-1-0-principles.md)。capability清单/协商已取消；任务schema校验与Scheduler渲染检查保留，实际资源请求交原生调度器接受或拒绝。
