# 事件驱动诊断 Agent v0.3

本目录是已实现版本的契约与验收材料。原公共图谱、学生档案、评价快照、正式建议包保留v2格式；新增四类运行记录使用schema_version=3.0.0。

- [四类契约与执行方案](四类契约与执行方案.md)：先定义规则与实施顺序，再执行。
- [运行协议与接口](运行协议与接口.md)：失效、读写、版本和模型配置。
- [验收记录](验收记录.md)：实际通过的检查与未验证边界。
- contracts/：四类运行Schema和模型终答Schema；作者源为agent/contracts.py。
- examples/：隔离临时数据库导出的四类合法记录及有界上下文，均为规则演示结果。

生成示例与机器Schema：在仓库根目录运行 `python tools/export_agent_examples.py`。此操作不更改原始预置数据、不调用模型、不写默认运行数据库。

`evaluation_changed`描述事实发生了什么变化；`diagnostic_artifact`描述解释依据什么生成、在哪一版仍有效；`agent_run`描述执行过程与预算；`conversation_turn`保存用户问题和固定评价版本。它们通过对象、场景、节点和snapshot_ref关联原v2数据，不替代原数据契约。
