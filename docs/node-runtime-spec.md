# TextFlow Studio Node Runtime Spec（V2 Phase 1）

## 1. 文档定位

本文档定义 V2 节点工作流在 Phase 1 的运行时约束。

重点不是描述理想中的完整图执行器，而是明确：

- 当前 Python sidecar 能执行什么
- 节点工作流首版如何复用它
- 哪些运行时能力必须延后

## 2. 当前运行器事实

当前 `run_project_pipeline(...)` 的真实行为是：

- 读取项目语料
- 基于 `run_scope` 过滤文档
- 按线性步骤执行
- 把结果写入项目级 `results`
- 把 run 记录追加到 `run_history`
- 把文件写到 `runs/<run_id>/`

当前执行器的关键限制：

- 只有线性步骤，没有节点依赖图
- 没有节点级缓存
- 没有 dirty 传播
- 没有局部执行
- `analysis` 是聚合步骤，不是独立子图

V2 Phase 1 必须显式承认这些限制。

## 3. Phase 1 运行时总体方案

V2 Phase 1 采用：

> 工作流图编辑 + 运行前编译为兼容 `pipeline` + 继续调用现有线性执行器

也就是：

1. 用户编辑 `active_workflow`
2. 前端或 sidecar 对 workflow 做结构校验
3. 编译器把 workflow 变成兼容当前引擎的 `PipelineDefinition`
4. 调用当前 `run_project_pipeline`
5. 运行结果再映射回节点 UI

## 4. 编译器职责

编译器当前负责把以下节点映射回线性配置：

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

## 5. 首版可执行图校验规则

由于当前运行时只能跑线性步骤，Phase 1 仍不会支持以下能力：

- 多个 `Corpus Input` 在运行时同时生效
- `merge_corpora` 的真实语义执行
- 节点级并行执行
- 节点级缓存与 dirty 传播
- `从某节点继续执行` / `执行到此为止`

当前实现对“图不完整”的处理方式不是报错终止，而是：

- 前端把缺线显示为 graph validation 问题，并阻止直接运行
- 编译器只编译活跃子图中的节点
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
- 各类 `save_*` 输出节点

可以被 bypass、移除或断开；是否参与运行由“能否连到输出节点”决定。

## 6. 节点状态如何产生

Phase 1 的节点状态不是节点原生执行状态，而是 run 结果映射状态。

建议状态来源：

- `idle`：还没有 run
- `configured`：节点存在且参数合法，但未运行
- `bypassed`：节点被显式跳过
- `success`：对应线性步骤成功执行
- `warning`：对应步骤日志包含 warning
- `error`：run 失败且错误归属于该步骤

### 6.1 不能伪装的状态

以下状态在 Phase 1 不应伪造：

- 真实 `cached`
- 真实 `partial_success`
- 真实 `dirty`
- 真实 `running` 的节点级进度

原因是当前运行器只提供 run 级进度，没有节点级执行事件。

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

## 8. 缓存与局部执行的正式结论

Phase 1 明确不支持：

- `执行到此为止`
- `从此继续执行`
- 节点级缓存
- dirty 传播
- artifact registry

UI 要求：

- 不显示可点击但无效的局部执行按钮
- 可以在 spec 中保留能力方向
- 但首版实现不得承诺“节点重跑”

## 9. 后续演进边界

只有在以下条件满足后，才能进入真正的图运行时：

- `analysis` 被拆分成多个独立可执行节点
- 中间产物有稳定 schema 和文件写出约定
- run 记录能跟踪节点级执行
- cache key 有明确组成
- artifact registry 有真实落盘逻辑

在那之前，V2 的正确策略是：

- 先把流程编辑体验节点化
- 再逐步把运行时从线性执行迁移到图执行

## 10. Phase 1 结论

V2 Phase 1 的运行时不是“节点执行器”，而是：

> 以工作流图作为新的流程编辑模型，以编译器作为兼容层，以当前线性 Python pipeline 作为真实执行引擎。

这让我们可以先升级流程组织方式，同时不破坏现有测试、导出和 run history 体系。
