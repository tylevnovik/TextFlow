# 2026-04-18 V2 节点工作流设计摘要

## 背景

V1 已经完成并推送 GitHub。当前仓库不是空白原型，而是已经具备：

- 项目化持久化
- 数据导入与字段映射
- 词表治理
- 线性 pipeline 执行
- run history 与结果导出
- Python sidecar 常驻服务

因此 V2 的核心不是重新定义产品边界，而是把“流程组织方式”从线性表单升级为节点工作流，同时不脱离现有运行器。

## 本次确定的设计结论

- 节点工作流采用“迁移版”路线，而不是一步到位的完全自由图执行。
- 首版工作流画布以单条主执行链为约束，真实执行前仍编译回当前线性 `pipeline`。
- `Analyze Corpus` 在首版保持为聚合分析节点，不拆成多个独立后端节点。
- `results`、`run_history`、项目词表与导出目录体系继续沿用。
- `workflow_definitions` 和 `active_workflow_id` 作为新的持久化入口引入。
- `artifact_registry`、节点缓存、局部执行、多 workflow 独立结果中心全部延期。

## 已落文档

- [docs/workflow-node-spec.md](../workflow-node-spec.md)
- [docs/workflow-schema.md](../workflow-schema.md)
- [docs/node-runtime-spec.md](../node-runtime-spec.md)

## 设计取向

这次 V2 规格的判断标准不是“看起来够不够像 ComfyUI”，而是：

- 能否复用当前真实能力
- 能否保证旧项目平滑迁移
- 能否为后续真正的图执行器留下干净的演进接口

结论是：先把流程表达切换到工作流图，再逐步拆运行时，而不是反过来。
