# TextFlow Studio V2 节点工作流规格（迁移版）

> 注：本文件描述的是“从 V1 线性 pipeline 迁移到节点壳层”的过渡规格。  
> 如果目标是完整的 ComfyUI 风格唯一节点编排，请以 [docs/plans/2026-04-18-v2-comfy-node-redesign.md](./plans/2026-04-18-v2-comfy-node-redesign.md) 为新的目标设计基线。

## 1. 文档定位

本文档定义 TextFlow Studio 从 V1 线性 `pipeline` 过渡到 V2 节点式 `workflow` 的首版产品规格。

本版不是直接照搬 ComfyUI，也不是假设当前仓库还没有实现 V1。它以仓库中已经落地的能力为边界，只采纳那些当前数据模型、前端结构和 Python sidecar 能平滑承接的节点化方案。

相关文档：

- 当前线性执行基线：[docs/pipeline-spec.md](./pipeline-spec.md)
- 工作流持久化与兼容结构：[docs/workflow-schema.md](./workflow-schema.md)
- 工作流运行时与编译约束：[docs/node-runtime-spec.md](./node-runtime-spec.md)

## 2. 当前真实基线

截至当前仓库，系统已经具备以下事实基础：

- 项目持久化模型仍以单个 `ProjectManifest.pipeline` 为中心。
- Python 运行器按 `enabled_steps` 和 `execution_order` 线性执行。
- 数据导入、字段映射和主文本构建在“数据”页完成，不属于 `run-pipeline` 的运行链。
- `results` 是项目内最新结果快照，`run_history` 保存 run 级日志和产物摘要。
- `pipeline.nodes`、`pipeline.edges`、`pipeline.node_configs` 仅为预留字段，当前不参与执行。
- `artifacts` 目前是 run 级摘要，不是节点级 artifact registry。
- `cache_hit` 字段已存在，但当前后端没有节点缓存实现，实际恒为 `false`。
- Python sidecar 已经提供内置 `node_definitions` 注册表，工作区快照会把当前可用节点协议一起返回给前端。
- Python sidecar 现已把节点系统拆成 `node_definitions / node_compilers / node_executors / node_plugins / node_registry`，并支持扫描本地纯 Python 插件节点。
- 前端“处理与分析”页已经切到 workflow shell：当前是沉浸式画布壳层，支持自由拖拽、空白区域平移、滚轮缩放、自动整理和位置持久化。
- 当前画布已取消独立 inspector；节点预览、常用参数、深度参数和删除/跳过动作都下沉到节点卡片内。
- 当前画布已支持左侧 rail + dock、dock 收起、右下角 mini-map、顶部浮动运行栏，以及工具箱拖拽投放节点。
- 当前节点卡片编辑已开始从 `screens.tsx` 的硬编码分支迁移到 `node_definitions + workflowNodeRegistry` 驱动；特殊节点保留少量自定义渲染，其余节点优先走统一 schema 表单。
- 当前画布已支持空白画布、推荐 starter graph、节点自由删除，以及输入 / 分析 / 输出节点的独立增删。
- 当前画布已支持端口级连线编辑：可从输出端发起连线、点击兼容输入端接线、选中连线删除、恢复推荐连线。
- 当前 mini-map 已支持点击和拖拽视口框进行实时导航，不再只是一次性跳转。
- 当前 workflow 草稿、视口和基础画布 UI 状态会在页面切换后恢复，不再因为切到别页而回到初始壳层。
- 当前运行时已经按“输出节点回溯活跃子图”的方式编译 workflow；`manual / template` workflow 会走原生 DAG，legacy workflow 才回退到线性 `pipeline`。
- 当前运行时仍未支持局部重跑、并行调度和完整 artifact registry；`merge_corpora` 与节点缓存已接入 native DAG。

V2 规格必须建立在这些事实之上。

## 3. 本次采纳的 V2 核心变化

### 3.1 画布成为主入口

V2 将把当前“处理与分析”页升级为工作流画布，采用：

- 左侧节点工具箱
- 中间工作流画布
- 节点体内参数与预览
- 底部运行控制台

但首版画布服务的是“节点化表达现有流程”，不是立即开放无限制图编排。

### 3.2 工作流替代页面状态成为流程主模型

V2 引入 `WorkflowDefinition` 作为新的流程组织单位。用户编辑的是一张节点图，而不是一长串折叠表单。

不过在迁移期内：

- `workflow` 是新的编辑模型
- `pipeline` 仍是当前后端执行的兼容目标
- 运行前需要把节点图编译回线性 `pipeline`
- 当前“处理与分析”页已经只保留 workflow 入口，不再以页面级线性表单作为主编排方式。
- 输出格式、报告选项和一部分分析参数已经下沉到各自节点内配置。

### 3.3 只采纳当前引擎能表达的节点粒度

首版节点粒度不追求“拆得越细越好”，而是优先贴合当前 Python 运行器已经存在的步骤边界。

这意味着 V2 当前 starter graph 已经切成以下节点体系：

- 输入层：`Corpus Input`、`Dictionary Input`
- 处理层：`Merge Corpora`、`Clean Text`、`Normalize Text`、`Tokenize`、`Apply Dictionary Rules`、`Filter Terms`
- 分析层：`Frequency Statistics`、`Term-Year Analysis`、`Cooccurrence Analysis`、`Keyword Extraction`、`Keyword Clustering`、`Institution-Topic Analysis`
- 输出层：`Save CSV`、`Save XLSX`、`Save PNG`、`Save HTML Report`
- 辅助层：`Note`、`Group`

其中最关键的真实边界是：

- 节点已经按输入 / 处理 / 分析 / 输出拆开，不再保留不可删除的系统节点。
- 这些分析节点在运行时仍会共同编译回当前单段式 `analysis` 步骤，因此“节点拆开”先是编排层升级，不是后端已经拥有完全独立的分析执行器。
- `Merge Corpora` 已经进入图模型、节点注册表和原生 DAG 执行链，可用于把多路语料先汇合再进入下游处理。

### 3.4 DAG 原则保留，但首版执行图进一步收紧

V2 仍以 DAG 为上限，不支持循环。

同时，基于当前运行器真实能力，首版可执行图仍有几个约束：

- 多个活跃 `Corpus Input` 需要先经过 `Merge Corpora` 收敛，不能直接并入同一条执行链
- 活跃子图必须能回溯到至少一个输出节点
- 分析分支和多输出已经允许存在，但它们最终会一起编译回线性 `analysis/export` 语义

但当前实现已经开始真正让“图本身”决定运行：

- 编译器会从 `save_*` 输出节点反向追踪活跃子图
- 没有接到任何输出节点的支路只留在画布中，不会进入本次运行
- `Apply Dictionary Rules`、`Save HTML Report` 这类多输入节点只有在必需端口接通时才会进入活跃子图

换句话说，当前阶段已经是“节点化的多分支编排 + 线性执行后端”，而不再只是“把线性表单画成节点样子”。

## 4. 本次明确延后的能力

以下内容保留为方向，但不写入 V2 首版强交付范围：

- 任意导入节点直接在画布内改写项目资源
- 多 workflow 并行编辑、比较和独立结果中心
- 节点级局部执行
- `执行到此为止` / `从此继续执行`
- 节点级缓存
- dirty 传播
- artifact registry
- `Feature Term Selector` 的强交互独立节点
- `Keyword Clustering`、`Institution-Topic Analysis` 等独立可执行节点
- `Reroute`、复杂自动补线
- 第三方二进制依赖插件与签名分发

这些能力并不是不要做，而是当前仓库还没有支撑它们的运行时和持久化基础。

## 5. 首版节点体系

## 5.1 资源节点

### `Load Project Corpus`

- 作用：从项目现有语料库加载文档集合
- 输入：无
- 输出：`ProjectCorpus`
- 说明：它引用项目中的 `corpus.json`，不负责导入文件

### `Project Dictionary Set`

- 作用：引用项目当前词表集
- 输入：无
- 输出：`DictionarySet`
- 说明：它引用项目内 `dictionary_set`，不是工作流私有副本

## 5.2 可执行处理节点

### `Filter Corpus`

- 作用：表达当前 `run_scope`
- 输入：`ProjectCorpus`
- 输出：`ScopedCorpus`
- 配置对应：来源、机构、标签、年份、手动选文档
- 编译目标：`pipeline.run_scope`

### `Clean Text`

- 编译目标：`pipeline.cleaning`

### `Normalize Text`

- 编译目标：`pipeline.normalization`

### `Tokenize`

- 编译目标：`pipeline.tokenization`

### `Apply Dictionary Rules`

- 输入需同时依赖 `TokenCorpus` 和 `DictionarySet`
- 编译目标：`pipeline.dictionary`

### `Filter Terms`

- 编译目标：`pipeline.filtering`

### `Analyze Corpus`

- 编译目标：`pipeline.analysis`
- 输出：`AnalysisBundle`、`AuditTable`
- 说明：当前后端一次性产出：
  - `frequency_table`
  - `term_document_table`
  - `term_year_table`
  - `cooccurrence_table`
  - `selected_feature_terms`
  - `keyword_result`
  - `keyword_cluster_result`
  - `institution_keyword_cooccurrence`
  - `institution_topic_cooccurrence`
  - `clustering_result`

### `Export Results`

- 编译目标：`pipeline.export`
- 输出：`ExportBundle`
- 说明：当前仍由 run 统一写出 CSV/XLSX/PNG/HTML 和运行快照

## 5.3 辅助节点

### `Note`

- 仅用于画布注释
- 不参与执行编译

### `Group`

- 仅用于分组和折叠
- 不参与执行编译

### `Bypass`

- 表现为节点的 `bypassed` 状态
- 编译后映射到：
  - 从 `enabled_steps` 中移除对应步骤
  - 或沿用上一步输出

## 6. 首版端口类型

首版端口类型只定义当前运行器真正在意的类型：

- `ProjectCorpus`
- `ScopedCorpus`
- `DictionarySet`
- `CleanCorpus`
- `NormalizedCorpus`
- `TokenCorpus`
- `FilteredTokenCorpus`
- `AnalysisBundle`
- `AuditTable`
- `ExportBundle`

连接规则：

- `ProjectCorpus -> Filter Corpus`
- `ScopedCorpus -> Clean Text | Normalize Text | Tokenize`
- `DictionarySet -> Apply Dictionary Rules`
- `FilteredTokenCorpus -> Analyze Corpus`
- `AnalysisBundle -> Export Results`
- `AuditTable -> Export Results`

首版不支持复杂的自动转换节点，也不支持真正的任意多路合流，但会基于端口类型做兼容校验，并在画布中高亮可连接输入端。

## 7. 工作流编辑器规格

## 7.1 页面结构

- 左侧：窄 rail + dock，负责节点分类、节点列表、工作流状态与模板入口
- 中间：沉浸式无限画布，为主工作区
- 顶部：浮动运行栏、缩放与聚焦操作
- 右侧：不再保留独立 inspector，参数和预览全部进入节点卡片
- 右下：mini-map 导航
- 底部：首版不再强制固定日志栏，运行摘要先收敛到 dock 和节点内预览

## 7.2 首版必须支持的交互

- 拖入节点
- 从输出端发起连线
- 点击兼容输入端完成接线
- 选中连线并删除
- 恢复推荐连线
- 框选与移动
- 选中节点查看参数
- 节点体内快捷编辑常用参数
- 选中连线查看数据流摘要
- 节点启用 / 绕过
- 保存工作流
- 运行当前工作流
- 从线性 pipeline 自动生成默认图
- mini-map 导航

## 7.3 首版不要求支持的交互

- 无限复杂分组布局
- 自动补全转换节点
- 节点右键的局部执行
- 独立 viewer 节点预览

## 8. 工作流模板策略

模板仍然重要，但首版只保留两层：

### 8.1 工作流模板

等价于当前 `recipe + output_bundle + optional steps` 的升级版。

但在当前实现里：

- `recipe` 由 `Analyze Corpus` 节点负责承接和切换
- `output bundle` 由 `Export Results` 节点负责承接和切换
- 模板元信息仍保留在 workflow 级字段中，用于迁移和回显

首批内置模板建议直接复用现有运行意图：

- `Standard Analysis Workflow`
- `Keyword + Topic Workflow`
- `Trend Scan Workflow`

### 8.2 节点预设

用于快速填充单节点参数，例如：

- `Clean Text / Academic`
- `Tokenize / Mixed Language`
- `Export Results / Full Report`

首版不做子流程模板市场。

不过当前仓库已经支持一层更轻量的本地插件能力：

- 后端会扫描 `plugins/nodes`
- 插件可注册自己的 schema、compiler hook、executor id
- 前端工具箱会优先读取后端返回的 `node_definitions`
- 插件节点当前主要走泛型表单渲染，少量内置节点保留 custom renderer

## 9. 与当前 V1 的兼容策略

## 9.1 V1 pipeline 继续存在

迁移期内，`pipeline` 不是废弃字段，而是：

- 当前执行器的真实输入
- 工作流编译结果
- 兼容旧项目与旧测试的落地格式

## 9.2 自动迁移规则

当前 V1 的默认执行链：

`Ingestion -> Cleaning -> Normalization -> Tokenization -> Dictionary Application -> Filtering -> Analysis -> Export`

迁移到 V2 首版时，转换为：

`Load Project Corpus -> Filter Corpus -> Clean Text -> Normalize Text -> Tokenize -> Apply Dictionary Rules -> Filter Terms -> Analyze Corpus -> Export Results`

对应规则：

- `enabled_steps` 决定节点是否默认启用或 bypass
- `execution_order` 决定默认推荐连线顺序
- `run_scope` 编译到 `Filter Corpus`
- `recipe_id` 记录为工作流模板来源，并由 `Analyze Corpus` 节点配置驱动
- `output_bundle_id` 记录为 `Export Results` 的预设来源
- 当用户手动改线后，真正进入执行的步骤由“可达节点 + 必需输入是否接通”共同决定

### 9.3 经典模式保留

V2 初期仍应保留“经典线性流程入口”，但它本质上是：

- 打开默认工作流的受限编辑视图
- 或根据工作流图回填线性参数面板

这样可以降低迁移门槛，并复用当前前端结构。

## 10. 首版执行与调试要求

首版执行目标不是局部调试，而是可追溯迁移：

- 一次点击执行当前工作流
- 执行前将图编译为线性 `pipeline`
- 执行后仍写入当前 `runs/<run_id>/`
- 继续生成：
  - `params_snapshot.json`
  - `logs.json`
  - `logs.txt`
  - `corpus_snapshot.json`
  - `outputs/`
  - `charts/`
  - `report/`

Debug 面板首版展示：

- 节点参数
- 上次运行摘要
- 相关日志片段
- 是否 bypass
- 对应的线性步骤 ID

它不是节点级真实执行日志，只是 run 结果的映射视图。

## 11. 首版结论

V2 首版的正确定位不是“完整 ComfyUI 化”，而是：

> 在保留现有项目、词表、导入、run history、结果导出和 Python 线性执行器的前提下，引入工作流图作为新的流程编辑壳层，并通过“图到线性 pipeline 的编译层”完成兼容迁移。

这版规格的价值在于：

- 让工作流组织方式先升级
- 不和当前后端能力脱节
- 为后续真正的分支执行、节点缓存、artifact registry 和多 workflow 项目结构预留稳定入口
