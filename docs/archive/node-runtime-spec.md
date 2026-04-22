# TextFlow Studio Node Runtime Spec（V2 Phase 2）

## 1. 文档定位

本文档定义 V2 节点工作流在 Phase 2 的运行时约束。

当前重点不是描述最终形态的分布式调度器，而是明确：

- 当前 Python sidecar 能执行什么
- 哪些 workflow 已经切到原生 DAG
- 哪些兼容路径仍然保留 bridge

## 2. 当前运行器事实

当前 `run_project_pipeline(...)` 的真实行为已经分成两条路径：

- `manual` / `template` 且不包含 legacy 聚合节点的 workflow：
  - 按输出节点反向追踪活跃子图
  - 对活跃子图做拓扑排序
  - 逐节点执行已注册的 node executor
  - 记录节点级运行摘要与缓存命中
- `system_default` / `migrated_from_pipeline` / legacy workflow：
  - 继续走 `workflow -> pipeline -> 线性执行器` 的兼容路径

当前运行器新增的能力：

- 原生 DAG 子图执行
- 节点级缓存文件
- 节点级运行摘要 `node_runs`
- 大节点中途进度回传
- 从 sink 回溯决定本次真正参与执行的节点
- sidecar 现在已经拆出 `node_definitions`、`node_compilers`、`node_executors`
- sidecar 启动时会扫描本地 `plugins/nodes` 并用 `importlib` 加载纯 Python 节点插件

当前仍然存在的限制：

- 仍然没有真正的并行 DAG 执行
- 仍然没有跨运行的 artifact registry
- 部分分析节点仍依赖运行时共享上下文，而不是完全显式的中间端口
- legacy `analyze_corpus` / `export_results` 仍走兼容 bridge

### 2.1 当前性能结论

截至当前阶段，`20 Newsgroups train` 全量压测已经表明：

- native DAG 初版冷启动约 `313.7s`
- 经第一轮优化后，native DAG 冷启动约 `153.5s`
- 经第二轮优化后，native DAG 冷启动约 `87.6s`
- 已明显超过旧 bridge 的 `151.3s`
- native DAG 二次重跑约 `53.5s`

第一轮优化主要来自：

- 取消节点间大语料 `deepcopy`
- 拆开 `TF-IDF` 与 `YAKE` 的联算
- 词表应用改成运行时查表
- 审计表只记录真实规则命中
- 节点缓存改用更轻的普通 `json`

当前剩余热点集中在：

- 大型 run snapshot / export 写盘
- 大型 CSV / PNG 导出写盘

## 3. 当前总体方案

当前采用混合运行时：

> modern workflow 走原生 DAG，legacy workflow 保留 pipeline bridge

也就是：

1. 用户编辑 `active_workflow`
2. sidecar 做边归一化、活跃子图计算和拓扑排序
3. 原生 DAG 路径按 executor registry 逐节点运行
4. 同时生成兼容的 `PipelineDefinition` 快照，供现有结果中心、导出和审计页面继续消费
5. 若 workflow 含 legacy 聚合节点，则回退到 bridge 运行

## 4. 编译器职责

当前编译器已经不再写死在单个 `defaults.py` 大分支里，而是按“节点类型 -> compiler hook”注册。

当前职责仍然包括把以下节点映射回兼容 `pipeline` 快照：

- `corpus_input -> run_scope`
- `clean_text -> cleaning`
- `normalize_text -> normalization`
- `tokenize -> tokenization`
- `apply_dictionary_rules -> dictionary`
- `filter_terms -> filtering`
- `frequency_statistics` / `term_year_analysis` / `cooccurrence_analysis` / `keyword_extraction` / `keyword_clustering` / `institution_topic_analysis -> analysis`
- `save_csv` / `save_xlsx` / `save_png` / `save_html_report -> export`

同时生成：

- `enabled_steps`
- `execution_order`
- `recipe_id` 或 `template_id` 对应信息
- `output_bundle_id`

并且在当前实现里，编译器已经开始真正使用图信息，而不是只把节点当表单容器：

- 先对边做类型兼容和多输入端口约束下的归一化
- 再计算从资源节点出发的可达节点集合
- 再从输出节点反向追踪本次真正活跃的子图
- 只有活跃子图中的节点才会把自己的配置编译回 `pipeline`
- 多输入节点只有所有必需输入都接通时才会进入活跃子图

### 4.1 当前运行时拆分

当前 Python sidecar 内部结构已经拆成：

- `node_definitions.py`
- `node_compilers.py`
- `node_executors.py`
- `node_plugins.py`
- `node_registry.py`

其中：

- `node_registry.py` 负责组装注册表
- `node_definitions.py` 负责节点 schema
- `node_compilers.py` 负责 workflow -> pipeline 的 compiler hook
- `node_executors.py` 负责 executor id 到真实节点执行函数的注册
- `node_plugins.py` 负责扫描并加载本地纯 Python 插件节点

这让“新增节点”从改大分支，变成“注册 definition + compiler + executor”。

另外，内置节点的输出端口现在还会在 definition 层显式声明导出语义，而不是继续写死在运行时：

- `outputs[*].result_bundle_key`：该输出应回写到哪个 `result_bundle` 键
- `outputs[*].png_chart_ids`：该输出默认可以派生哪些 PNG 图表
- `outputs[*].include_in_html_audit`：该输出接入 `Save HTML Report` 时是否应走审计摘要通道

这意味着更新某个分析节点的结果落点、补充默认图表，或者新增一个可导出的分析节点时，通常只需要改 node definition，不需要再同步修改 `dag_runtime.py` 里的节点类型映射表。

## 5. 当前图校验与活跃子图规则

当前原生 DAG 仍不会支持以下能力：

- 不经 `merge_corpora` 直接并入同一执行链的多条语料支路
- 节点级并行执行
- 并行调度
- 手动选择某个中间节点局部重跑
- 完整 artifact lineage registry

当前实现对“图不完整”的处理方式是：

- 前端把缺线显示为 graph validation 问题
- 原生运行时只执行活跃子图中的节点
- 因缺线而不属于活跃子图的步骤会自动从 `enabled_steps` 中消失
- 例如 `Save HTML Report` 缺少上游分析结果时，导出步骤不会进入本次运行

当前推荐的 starter graph 应当类似：

```text
corpus_input
  -> clean_text
  -> normalize_text
  -> tokenize
  -> apply_dictionary_rules
  -> filter_terms
  -> frequency_statistics -> save_csv/save_xlsx/save_png/save_html_report
  -> term_year_analysis -> save_csv/save_xlsx/save_png/save_html_report
  -> cooccurrence_analysis -> save_csv/save_xlsx/save_png/save_html_report
  -> keyword_extraction -> keyword_clustering -> save_csv/save_xlsx/save_png/save_html_report
  -> institution_topic_analysis -> save_csv/save_xlsx/save_png/save_html_report
```

其中：

- `clean_text`
- `normalize_text`
- `apply_dictionary_rules`
- `filter_terms`
- `merge_corpora`
- 各类 `save_*` 输出节点

可以被 bypass、移除或断开；是否参与运行由“能否连到输出节点”决定。

## 6. 节点状态如何产生

当前节点状态来源分成两类：

- native DAG workflow：
  - 来自本次 `node_runs`
  - 可看到 `completed` / `cached` / `failed`
- legacy bridge workflow：
  - 仍然来自 run 结果映射

当前尚未承诺：

- 真实 `dirty`
- 真实 `partial_success`
- 并行 `running` 进度

## 7. 运行输出归属

Phase 1 继续沿用当前输出机制：

- `runs/<run_id>/params_snapshot.json`
- `runs/<run_id>/logs.json`
- `runs/<run_id>/logs.txt`
- `runs/<run_id>/corpus_snapshot.json`
- `runs/<run_id>/outputs/*`
- `runs/<run_id>/charts/*`
- `runs/<run_id>/report/report.html`

对应 UI 规则：

- 节点 Debug 面板显示这些已有 run 文件的映射信息
- 结果中心继续基于 `results` 和 `run_history`
- 不额外引入节点级 artifact 存储目录

## 8. 插件与局部执行的正式结论

当前已支持：

- 本地 `plugins/nodes` 目录下的纯 Python 节点插件
- 插件节点随 workspace snapshot 一起暴露给前端
- 插件节点通过 compiler hook 影响兼容 `pipeline`
- modern workflow 中的内置节点通过 executor registry 原生执行

当前仍不支持：

- `执行到此为止`
- `从此继续执行`
- 面向用户的局部执行按钮
- 完整 dirty 传播 UI
- artifact registry

UI 要求：

- 不显示可点击但无效的局部执行按钮
- 可以在 spec 中保留能力方向
- 但首版实现不得承诺“节点重跑”

## 9. 后续演进边界

只有在以下条件满足后，才能进入真正的图运行时：

- 更多分析节点把隐式共享上下文改成显式端口
- sink 导出完全按连接关系决定输出文件，而不再借现有报告层的全局 bundle 逻辑
- artifact registry 有真实落盘逻辑
- 支持局部重跑与 dirty 传播

在那之前，V2 的正确策略是：

- 先用 hybrid runtime 把主要节点链路切到原生 DAG
- 再逐步把 bridge 范围缩小到 legacy 节点

## 10. Phase 1 结论

V2 Phase 1 的运行时不是“节点执行器”，而是：

> 以工作流图作为新的流程编辑模型，以编译器作为兼容层，以当前线性 Python pipeline 作为真实执行引擎。

这让我们可以先升级流程组织方式，同时不破坏现有测试、导出和 run history 体系。
