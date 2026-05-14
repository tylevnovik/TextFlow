# 工作流与运行时

本文档只描述当前仓库已经实现并被代码验证的 workflow 运行模型。

## 当前结论

TextFlow 现在采用的是：

> workflow graph 是唯一真相、唯一执行入口、唯一项目持久化模型。

当前不再保留任何独立流程快照作为项目文件中的中心结构，也不再保留 bridge / native DAG 双轨执行。

## 当前模型

- 项目持久化保存 `workflow_definitions` 与 `active_workflow_id`
- 运行时始终从 active workflow 直接进入 native DAG
- 运行过程中会生成只读的 `runtime_profile`，用于导出、日志和运行快照
- 当前代码不会再从历史快照字段恢复项目真相；任何残留字段都只会被忽略

## 项目中的 workflow

当前项目真相层关键字段是：

- `workflow_definitions`
- `active_workflow_id`
- `run_history`
- `results`

其中：

- `workflow_definitions` 负责保存画布节点、边、节点配置和 meta
- `active_workflow_id` 指向当前工作流
- `run_history` 保存实际运行记录
- `results` 保存最近一次项目级结果快照

新保存的项目不再写独立默认流程配置文件，`project.json` 里只保留 workflow 真相层字段。

## 节点体系

当前内置节点分为五类：

- 输入节点：`corpus_input`、`dictionary_input`
- 处理节点：`merge_corpora`、`clean_text`、`normalize_text`、`tokenize`、`apply_dictionary_rules`、`filter_terms`
- 分析节点：`frequency_statistics`、`term_document_analysis`、`term_year_analysis`、`cooccurrence_analysis`、`similarity_analysis`、`feature_term_selection`、`keyword_extraction`、`keyword_clustering`、`topic_modeling`、`institution_keyword_analysis`、`institution_topic_analysis`、`document_clustering`
- 输出节点：`save_csv`、`save_xlsx`、`save_png`、`save_html_report`
- 辅助节点：`note`、`group`

旧的聚合节点 `analyze_corpus`、`export_results` 仍可被读取并在 native DAG 中执行，但它们只是 legacy workflow 兼容节点，不再是默认 starter graph 的一部分。

## 执行方式

当前只有一条执行路径：

1. 读取 active workflow
2. 归一化节点和边
3. 从输出节点回溯活跃子图
4. 按拓扑层分批执行节点；同层就绪且 `parallel-safe` 的节点可并行运行
5. 写回结果 bundle、run history、导出产物和运行快照

当前 native DAG 已支持：

- 活跃子图裁剪
- 同层就绪节点的保守并行调度
- 节点级缓存
- 节点级运行摘要 `node_runs`
- 中途进度回传
- 节点状态增量同步与完成时全量状态对齐
- result bundle 与显式 `artifact_kind` 输出口写入 run artifact store
- `artifact_records` 索引和 preview/payload 懒加载
- legacy 聚合节点在图运行时内兜底

当前 revised-flow 主图额外覆盖：

- `tokenize` 可按节点配置生成 2-5 gram，n-gram 追加在基础 token 后，仍进入后续词表和过滤链路。
- `similarity_analysis` 基于 TF-IDF 特征矩阵计算文档对 cosine 相似度，输出 `similarity_table`，可导出到 CSV/XLSX/HTML。
- `topic_modeling` 支持 NMF 与 LDA 两种本地 scikit-learn 算法；BerTopic 尚未作为内置 sidecar 依赖打包。

## Artifact Store

运行时会在每次 run 结束时把可表格化或对象化的结果写入项目 artifact store：

- 内置分析节点通过 `result_bundle_key` 绑定到结果 bundle，再生成 artifact record。
- 插件或自定义节点可以在输出口声明 `artifact_kind`，executor 返回该输出口的普通 JSON payload 后，native DAG 会生成 artifact payload、preview 和 handle。
- `run_record.artifacts` 保存本次 run 的 handle 摘要，`manifest.artifact_records` 保存项目级索引，前端节点产物弹窗只在用户点击时加载 preview。

新项目默认使用 `.tfproj/project.db` 中的 `artifacts` 表保存 payload 和 preview，artifact record 的 `path`/`preview_path` 使用 `project.db:artifacts/<artifact_id>/...` 逻辑路径。旧项目如果只有 `runs/*/artifacts/*.json.gz`，读取层仍会兼容。

桌面端不再提供独立 artifact 检视页面。用户在工作流运行完成后，直接在已完成且有产物的节点上点击“产物”按钮，打开该节点的产物预览弹窗。

## 活跃子图规则

运行时不是“画布上所有节点都执行”，而是：

1. 先归一化边和端口连接
2. 计算可达节点
3. 从输出 sink 节点反向追踪活跃子图
4. 只执行真正参与当前输出的节点

因此：

- 没连到输出节点的分支不会进入本次执行
- 缺少必需输入的多输入节点不会进入活跃子图
- 输出节点决定了本次真正写出哪些结果

## runtime_profile

虽然项目不再保存独立流程快照，但运行时仍会从 workflow 派生一个只读 `runtime_profile`，用于：

- 汇总 `run_scope / cleaning / normalization / tokenization / dictionary / filtering / analysis / export`
- 生成 `enabled_steps`
- 生成 `recipe_id` 与 `output_bundle_id`
- 写入 `params_snapshot.json`

它的作用只是运行时视图，不是项目真相，也不会写回项目持久化结构。

## 运行快照与输出

每次运行仍会写出：

- `runs/<run_id>/params_snapshot.json`
- `runs/<run_id>/logs.json`
- `runs/<run_id>/logs.txt`
- `runs/<run_id>/corpus_snapshot.json`

其中 `params_snapshot.json` 现在保存的是：

- `workflow_definition`
- `workflow_hash`
- `runtime_profile`

而不是旧的独立流程快照。

其中 `corpus_snapshot.json` 当前已经做了轻量化：

- 小语料仍保留完整文本快照，方便审计与复现
- 大语料默认只保存预览文本、计数与元数据，避免运行结束时的大块写盘拖慢 UI

## 进度事件

当前 workflow 运行中的进度 detail 采用两种模式：

- 高频中途事件只回传 `node_state_delta`
- 运行完成时再做一次 `full_node_state_sync`

这样可以让桌面端持续拿到节点级状态变化，同时避免每个轮询周期都重复发送整张节点状态表。

## 节点缓存

当前 native DAG 会把节点缓存写到：

```text
cache/nodes/<node_id>/<cache_key>.pkl
```

缓存 key 会综合：

- `project_id`
- `workflow_id`
- `workflow_hash`
- `dictionary_version`
- 节点配置
- 输入 hash

其中 `workflow_hash` 只覆盖执行相关 payload；画布 viewport、节点位置、分组、折叠等 UI 状态不会触发缓存失效。

## 兼容策略

当前已经没有“历史流程快照读取迁移”这一层：

- 项目真相只认 `workflow_definitions` 与 `active_workflow_id`
- 残留的旧运行快照字段不再参与恢复、迁移或回填
- legacy workflow 聚合节点是否执行，属于图节点兼容问题，不再属于项目模型兼容问题

## 当前限制

以下能力仍未完成：

- 更细粒度的 ready-queue / 动态并行调度
- 面向用户的局部重跑
- 更细粒度的 dirty 传播可视化
- 跨项目 artifact registry 和 artifact 生命周期治理
- 更细粒度的中间结果浏览器
- 安全隔离和签名分发级别的插件生态

## 当前最重要的判断

当前仓库已经不应再描述成“workflow + 兼容旧流程快照 + bridge/native 混合运行”。

更准确的描述是：

> 当前仓库采用 workflow-only 持久化 + workflow-only native DAG 执行；历史流程快照已不再参与项目模型恢复。
