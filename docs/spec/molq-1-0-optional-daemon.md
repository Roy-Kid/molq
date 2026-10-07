# 无 Observer 与短期 runtime 部署

状态：历史入口，2026-10-07 收敛。原设计已由 [单一 runtime 主 spec](molq-1-0-runtime-spec.md)取代，不作为独立实现依据。

Observer关闭仍可正常操作。native可以通过stdio启动同一runtime；网页需要在线网络runtime。不是客户端直调Scheduler的备用路径。

现行约束见 [50 条原则及最新修订](molq-1-0-principles.md)。capability清单/协商已取消；任务schema校验与Scheduler渲染检查保留，实际资源请求交原生调度器接受或拒绝。
