# 工作流与运行时

本文档只描述当前仓库已经实现的 workflow 和运行时关系，不再把历史迁移草图当作当前规格。

## 当前模型

TextFlow 现在不是“只有线性 pipeline”，也不是“完全图原生执行”，而是混合模型：

- workflow 负责编辑和组织
- pipeline 负责兼容快照和 legacy 执行
- native DAG 负责一部分 modern workflow 的真实执行

## workflow 在项目中的位置

当前项目里同时保留：

- `workflow_definitions`
- `active_workflow_id`
- `pipeline`

实际含义是：

- 用户在前端编辑的是 `active_workflow`
- sidecar 会根据 workflow 生成兼容 `pipeline`
- 结果中心、run history 和部分执行链仍消费这份 pipeline 快照

## 节点体系

当前内置节点大致分为五类：

- 输入节点：`corpus_input`、`dictionary_input`
- 处理节点：`merge_corpora`、`clean_text`、`normalize_text`、`tokenize`、`apply_dictionary_rules`、`filter_terms`
- 分析节点：`frequency_statistics`、`term_document_analysis`、`term_year_analysis`、`cooccurrence_analysis`、`feature_term_selection`、`keyword_extraction`、`keyword_clustering`、`institution_keyword_analysis`、`institution_topic_analysis`、`document_clustering`
- 输出节点：`save_csv`、`save_xlsx`、`save_png`、`save_html_report`
- 辅助节点：`note`、`group`

旧的聚合节点 `analyze_corpus`、`export_results` 已不再是默认 starter graph 的中心，但仍作为 legacy 兼容节点保留。

## 当前 workflow 画布能力

前端当前已经支持：

- 节点工具箱
- 节点拖入与删除
- 端口级连线
- 连线删除
- 自动整理
- 视口缩放、平移、恢复
- mini-map 导航
- 节点内参数编辑
- workflow 草稿与视口持久化

这意味着 workflow 已经是主流程入口，而不是单纯的展示壳层。

## 两种执行路径

### 1. 兼容 bridge 路径

以下情况会回退到兼容路径：

- `workflow.source` 属于 `system_default` 或 `migrated_from_pipeline`
- workflow 中仍含 legacy 聚合节点
- 图里有节点没有 executor，无法满足原生执行条件

这条路径的过程是：

1. `workflow -> pipeline`
2. 使用既有线性执行器
3. 生成 run 目录、结果 bundle 和 run history

### 2. native DAG 路径

当 workflow 满足以下条件时，会走原生 DAG：

- `workflow.source` 为 `manual` 或 `template`
- 图中不含 legacy 聚合节点
- 所有活跃节点都能在 executor registry 中找到实现

这条路径已经支持：

- 从输出节点回溯活跃子图
- 边归一化和拓扑排序
- 节点级执行
- 节点级运行摘要 `node_runs`
- 节点级缓存
- 中途进度回传

## 活跃子图规则

当前运行时不是“画布上所有节点都执行”，而是：

1. 先归一化边和端口连接
2. 计算可达节点
3. 从输出 sink 节点反向追踪活跃子图
4. 只执行真正参与当前输出的节点

因此：

- 没连到输出节点的分支不会进入本次执行
- 缺少必需输入的多输入节点不会进入活跃子图
- 输出节点决定了本次真正写出哪些结果

## workflow 到 pipeline 的编译

编译器当前按“节点类型 -> compiler hook”注册，而不是硬编码在单个大分支里。

编译阶段主要做三件事：

- 把节点配置映射回 `cleaning / normalization / tokenization / dictionary / filtering / analysis / export`
- 生成 `enabled_steps` 和 `execution_order`
- 根据输出节点推导 `output_bundle_id` 和实际导出开关

因此 pipeline 现在更像：

> workflow 的兼容快照，而不是唯一真相。

## 节点缓存

当前 native DAG 已经写出节点缓存，路径大致为：

```text
cache/nodes/<node_id>/<cache_key>.json
```

缓存 key 会综合：

- `project_id`
- `workflow_id`
- `workflow_hash`
- `dictionary_version`
- 节点配置
- 输入 hash

当前缓存已经在 benchmark 中证明能显著降低二次运行成本。

## 输出选择

输出节点不只是开关，它们还会借由 node definition 中的元信息决定：

- 结果 bundle 的回写位置
- 可派生的 PNG 图表
- 是否进入 HTML 报告或审计摘要

这让当前导出已经从“全局导出开关”转向“由 sink 节点消费上游结果”。

## 插件节点

本地纯 Python 插件节点当前可以注册：

- definition
- compiler
- executor

当前行为是：

- 前端会把插件 definition 放进工具箱
- compiler hook 可以影响兼容 pipeline
- 如果插件节点提供 executor，且 workflow 满足原生执行条件，它也可以进入 native DAG

## 当前限制

以下能力目前仍未完成：

- DAG 并行调度
- 面向用户的局部重跑
- 完整 dirty 传播
- 完整 artifact registry
- 更细粒度的中间结果浏览器
- 安全隔离和签名分发级别的插件生态

## 当前最重要的判断

TextFlow 现在的 workflow 系统已经足够被视为正式架构的一部分，但还不应该被描述成“完整的图原生运行时”。更准确的说法是：

> 当前仓库采用 workflow 编辑层 + 兼容 pipeline 快照 + 部分 native DAG 执行的混合方案。
