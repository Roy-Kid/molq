# 旧 server/clients/Web spec 已合并

状态：历史入口，2026-10-07 收敛。原设计已由 [单一 runtime 主 spec](molq-1-0-runtime-spec.md)取代，不作为独立实现依据。

server仅是runtime的网络入口，Web与Observer都是公共RPCclients。旧文档中的独立server架构、Observer lifecycle diff与RPC lease设计不再有效。

现行约束见 [50 条原则及最新修订](molq-1-0-principles.md)。capability清单/协商已取消；任务schema校验与Scheduler渲染检查保留，实际资源请求交原生调度器接受或拒绝。
