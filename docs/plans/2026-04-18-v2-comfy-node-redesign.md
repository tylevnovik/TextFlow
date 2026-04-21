# TextFlow Studio V2 节点流重设计（ComfyUI 风格目标版）

## 1. 结论先行

基于当前反馈，V2 的目标不应该是“把线性 pipeline 外面包一层节点壳”，而应该是：

> 工作流画布成为唯一流程编排真相；节点、连线、节点内参数和节点输出共同定义一次文本处理与分析任务。

这意味着：

- 画布允许从空白开始，不预放不可删除的系统节点
- 所有可见节点都可复制、删除、替换、重连
- 用户自己拉线决定流程，不再依赖固定推荐主链
- 配置优先放在节点体内，右侧面板只承接高级参数、调试和输出预览
- 项目中的语料、词表、模板、历史产物作为“资源”存在，工作流通过输入节点引用它们
- 报表输出、图片输出、表格输出都应是独立 sink 节点，而不是一个大一统导出步骤

当前已经实现的“单链迁移壳”不应作为最终 V2 方向继续加码，只能算过渡实现。

---

## 2. 当前方案为什么偏了

这次偏差的根因有五个：

1. 把“当前线性运行器能做什么”直接投影成了“V2 节点应该长什么样”
2. 保留了不可删除的系统节点，导致画布不是真正由用户编排
3. 主要配置仍然围绕页面和右侧表单，而不是节点本体
4. 连线虽然出现了，但语义仍然服从固定主链，而不是服从用户图结构
5. 输入、分析、导出被做成了几个超大聚合节点，难以表达真正的分支、复用和组合

如果继续沿这个方向推进，产品会停在“长得像节点编辑器，但操作心理模型仍然像表单配置器”。

而 ComfyUI 风格真正重要的不是深色画布，也不是方块加连线，而是三件事：

- 图就是唯一真相
- 节点都是局部、可替换、可组合单元
- 结果是由若干输出节点消费上游产物而形成，不靠页面级全局导出开关

---

## 3. 备选方向与取舍

### 方案 A：纯节点优先，资源引用型工作流

这是推荐方案。

特点：

- 项目继续管理语料、词表、模板、历史结果这些资产
- 工作流只负责“引用哪些资产、怎样处理、怎样输出”
- 画布上没有不可删除的系统节点
- 所有配置以节点为中心
- 允许自然分支、汇合、多个输出终点

优点：

- 最接近 ComfyUI 心智
- 真正支持复杂分析分支
- 以后做模板市场、插件节点和局部重跑都顺

代价：

- 需要重做 schema、node registry、运行时和 UI 交互基线
- 不能继续以“固定主链”偷渡设计

### 方案 B：保留固定骨架，只让用户插入可选节点

这是当前实现方向，不推荐继续。

优点：

- 迁移快
- 对现有后端改动小

缺点：

- 本质仍是线性 pipeline
- 复杂流程表达力不够
- 用户会持续感到“这不是节点流”

### 方案 C：双模式，表单和节点长期并存

也不推荐作为长期架构。

优点：

- 迁移压力最小

缺点：

- 维护两套真相
- 设计不断互相牵制
- 最后两边都做不干净

**推荐结论：选择方案 A。**

---

## 4. 新的顶层原则

### 4.1 工作流画布是唯一编排入口

“处理与分析”不再对应线性 pipeline 页面，而是直接对应 workflow canvas。

### 4.2 没有不可删除节点

工作流模板可以生成 starter graph，但模板生成出来的每个节点都可删除。  
空白画布是合法状态，只是“不可运行”而不是“不允许存在”。

### 4.3 项目资源和工作流图分离

项目负责存：

- 语料资源
- 词表资源
- 报告模板
- 图表主题
- 历史运行产物
- 工作流模板

工作流只存：

- 节点
- 连线
- 节点参数
- 节点引用的资源 ID
- 画布布局

### 4.4 配置优先在节点体内完成

节点卡片要能直接编辑常用参数，右侧 inspector 只承接：

- 高级参数
- I/O schema
- 预览
- 调试信息

### 4.5 输出必须节点化

CSV、XLSX、PNG、HTML 报告、结果打包都应该是独立输出节点。  
“导出什么”由图上的 sink 节点决定，而不是页面全局勾选。

---

## 5. 项目资源模型

V2 目标版里，画布不直接承担资源导入中心的职责，但可以引用资源。

### 5.1 资源类别

- `CorpusResource`
  - 一个已导入语料表、一个保存过的子集、或一次历史产物中的语料对象
- `DictionaryResource`
  - 一个词表集，或词表集中的某个 sheet 组合
- `ReportTemplateResource`
  - HTML 报告模板、栏目布局模板
- `ChartThemeResource`
  - 图表主题、配色和字号方案
- `ArtifactResource`
  - 历史 run 的表格、图表、报告或中间产物

### 5.2 资源进入工作流的方式

左侧除了“节点”外，还应该有“资产/资源”面板。  
把一个资源拖到画布上时，系统直接创建对应输入节点：

- 拖一个语料资源，创建 `Corpus Input`
- 拖一个词表资源，创建 `Dictionary Input`
- 拖一个历史结果表，创建 `Artifact Input`
- 拖一个报告模板，创建 `Report Template Input`

这样用户感知会更像 ComfyUI 的“模型/素材 -> 节点引用”。

---

## 6. 节点体系重构

下面是推荐的节点族，不要求一次全做完，但架构必须按这个方向设计。

### 6.1 输入节点（Input / Resource）

这些节点都应该是普通节点，且都可删除。

- `Corpus Input`
  - 选择一个语料资源
  - 可带基础筛选条件或保存选择器 ID
- `Dictionary Input`
  - 选择一个词表资源
- `Artifact Input`
  - 引用历史 run 的某个 artifact
- `Report Template Input`
  - 选择报告模板
- `Chart Theme Input`
  - 选择图表主题
- `Constant / Text Input`
  - 提供文字常量、文件名前缀、注释、标题等

### 6.2 结构化与文本构建节点（Build）

如果未来允许把导入也节点化，可以补这些；如果首版先不做导入上图，它们也应在架构中留位。

- `Import Files`
- `Source Profile`
- `Field Mapper`
- `Text Builder`
- `Metadata Normalizer`
- `Deduplicate Documents`
- `Merge Tables`

### 6.3 语料操作节点（Corpus Ops）

这是文本工作流里最关键的一层，因为真正的分析分支通常不是“分词后分支”，而是“语料先被切成几路”。

- `Filter Documents`
- `Select Fields`
- `Sample Documents`
- `Split Corpus By Metadata`
- `Merge Corpora`
- `Intersect Corpora`
- `Union Corpora`
- `Join Metadata`

说明：

- 不需要单独的 `Branch Corpus` 节点，因为一对多输出天然就是分支
- `Merge Corpora`、`Union Corpora` 这类节点要支持可变数量输入端

### 6.4 预处理节点（Preprocess）

- `Clean Text`
- `Normalize Text`
- `Regex Replace`
- `Tokenize`
- `Phrase Detect`
- `Apply Dictionary Rules`
- `Filter Terms`
- `Feature Term Selector`

这里的关键变化是：

- `Feature Term Selector` 不能继续藏在 `Analyze Corpus` 里
- 它是文本挖掘流程里的关键分叉点，应该成为一等节点

### 6.5 分析节点（Analysis）

这里必须从“大分析节点”拆开。

- `Frequency Statistics`
- `Term-Document Analysis`
- `Term-Year Analysis`
- `Cooccurrence Analysis`
- `Keyword Extraction`
- `Keyword Clustering`
- `Institution-Keyword Analysis`
- `Institution-Topic Analysis`
- `Document Vectorization`
- `Document Clustering`
- `Topic Modeling`

为什么要拆开：

- 用户天然会从同一份 token 结果分出多条分析支线
- 不同分析节点的输入要求不同
- 输出结果也应作为独立 artifact 被后续图表或报告节点消费

### 6.6 可视化节点（Visualization）

图表本身也不应该混在导出里。

- `Table View`
- `Document Preview`
- `Trend Chart`
- `Bar Chart`
- `Word Cloud`
- `Cooccurrence Graph`
- `Cluster Scatter Plot`
- `Topic Summary View`
- `Audit View`

这些节点主要产出 `ChartSpec` 或 `ViewArtifact`。  
是否写文件，交给后续输出节点决定。

### 6.7 输出节点（Output）

这些是整个图的终点节点。

- `Save CSV`
- `Save XLSX`
- `Save PNG`
- `Save HTML Report`
- `Package Result Bundle`
- `Save Artifact`

特别是：

- `Save PNG` 应接收图像或图表渲染结果
- `Save HTML Report` 不应该直接吃一个“大分析包”，而应该吃一个报告组合结果

### 6.8 报告组合节点（Report Composition）

这是当前方案里缺失但很重要的一层。

- `Report Section`
  - 把标题、描述、图表、表格、注释拼成一个章节对象
- `Compose Report`
  - 接多个 `ReportSection`
  - 可接 `Report Template Input`
  - 输出 `ReportDocument`

这样报告生成才能真正像节点图，而不是页面级导出选项。

### 6.9 工具节点（Utility）

- `Note`
- `Reroute`
- `Group`
- `Rename Artifact`
- `Merge Tables`
- `Merge Charts`

---

## 7. 推荐端口类型

V2 目标版不要只围绕当前线性 pipeline 的几个步骤定义端口，而要围绕领域对象定义端口。

### 7.1 资源引用类

- `CorpusResource`
- `DictionaryResource`
- `ArtifactResource`
- `ReportTemplateResource`
- `ChartThemeResource`

### 7.2 数据类

- `StructuredTable`
- `CorpusTable`
- `DocumentSubset`
- `MetadataSchema`
- `TokenCorpus`
- `FilteredTokenCorpus`
- `FeatureTermSet`

### 7.3 分析结果类

- `FrequencyTable`
- `TermDocumentTable`
- `TermYearTable`
- `CooccurrenceTable`
- `KeywordTable`
- `KeywordClusterTable`
- `InstitutionKeywordTable`
- `InstitutionTopicTable`
- `DocumentClusterTable`
- `TopicTable`
- `AuditTable`

### 7.4 展示与输出类

- `ChartSpec`
- `RenderedImage`
- `ReportSection`
- `ReportDocument`
- `ExportArtifact`

### 7.5 连接规则

- 一对多分发天然允许
- 多输入节点必须支持显式多口
- `Merge Corpora`、`Compose Report` 这类节点要支持动态增减输入端
- 兼容关系由类型系统控制，而不是由固定链路控制

---

## 8. 交互模型应该怎样像 ComfyUI

### 8.1 空白画布优先

新建 workflow 时提供三种入口：

- 空白画布
- 从模板创建
- 从旧 pipeline 导入为 starter graph

### 8.2 节点体内直接配置

节点上直接展示最常用的 3 到 6 个参数，例如：

- `Corpus Input`
  - 资源下拉
  - 子集筛选器
- `Tokenize`
  - 分词器
  - 语言模式
  - 自定义词典开关
- `Save PNG`
  - 文件名前缀
  - 分辨率

右侧 inspector 再承接：

- 高级参数
- 输入输出 schema
- 调试信息
- 最近一次运行预览

### 8.3 手动拉线是默认，不是补充

画布应支持：

- 从输出端拉线到输入端
- 删除任意连线
- 插入节点到连线上
- 拖资源到画布直接生成输入节点
- 选中输出节点后执行“运行到这个输出”

“恢复推荐连线”只能是辅助命令，不能成为主操作。

### 8.4 节点删除规则

所有节点都可删除。  
删除之后只是可能让 workflow 变为“暂不可运行”，而不是 UI 上不允许删。

### 8.5 运行方式

推荐仿照 ComfyUI 的思路：

- 顶部是队列/运行控制
- 运行整个图，或运行到选定的 sink 节点
- 仅重新执行 dirty 上游

---

## 9. 文本处理全流程推荐拆法

下面给一条更符合文本分析实际的标准图，不是强制骨架，只是一个常见模板：

```text
Corpus Input (全部语料)
  -> Filter Documents (仅 2023 以后)
  -> Clean Text
  -> Normalize Text
  -> Tokenize
  -> Apply Dictionary Rules <- Dictionary Input (学术词表)
  -> Filter Terms
  -> Feature Term Selector
      -> Frequency Statistics -> Bar Chart -> Save PNG
      -> Term-Year Analysis -> Trend Chart -> Save PNG
      -> Cooccurrence Analysis -> Cooccurrence Graph -> Save PNG
      -> Keyword Clustering -> Topic Summary View
      -> Institution-Topic Analysis

Bar Chart ------------\
Trend Chart -----------> Report Section -> Compose Report <- Report Template Input
Cooccurrence Graph ----/
Institution-Topic Table -> Report Section -> Compose Report -> Save HTML Report
Frequency Table -------------------------------------------> Save XLSX
Term-Year Table -------------------------------------------> Save CSV
```

这个模板体现的不是“固定顺序”，而是：

- 先做语料选择
- 再做预处理
- 再从可复用的中间产物分出多条分析支路
- 图表、表格、报告分别作为独立输出终点

---

## 10. 对当前实现的直接修正方向

基于这个目标版，当前代码实现后续应该做的不是继续补固定主链，而是反过来做这些修正：

### 10.1 去掉不可删除节点机制

- 不再保留固定 mandatory node 列表
- 模板生成的节点全部可删
- `normalizeWorkflowGraph` 不再自动补系统节点

### 10.2 把输入改成资源选择节点

- 用 `Corpus Input` 代替 `Load Project Corpus + Filter Corpus` 的固定组合
- 用 `Dictionary Input` 代替固定 `Project Dictionary Set`
- 资源选择节点直接引用项目资产 ID

### 10.3 把页面级 recipe / output bundle 继续拆散

- `Analyze Corpus` 不再承接整个 recipe
- recipe 应退化为“模板图”
- 输出 bundle 退化为“输出节点模板组合”

### 10.4 把大节点继续拆细

优先拆分：

- `Analyze Corpus`
- `Export Results`

次优先拆分：

- `Filter Corpus`

### 10.5 让图结构成为唯一真相

- 编译器不能再依赖固定 execution order 推断主链
- 必须从 sink 节点回溯依赖图执行
- 无输出节点的图不可运行，但依然可编辑和保存

---

## 11. 迁移实施建议

### Phase A：编辑器真相迁移

- 空白画布
- 所有节点可删
- 资源拖放生成输入节点
- 节点体内快速配置
- 手动拉线为主

### Phase B：节点类型重构

先落最关键的新节点：

- `Corpus Input`
- `Dictionary Input`
- `Merge Corpora`
- `Feature Term Selector`
- `Frequency Statistics`
- `Term-Year Analysis`
- `Cooccurrence Analysis`
- `Save CSV`
- `Save XLSX`
- `Save PNG`
- `Compose Report`
- `Save HTML Report`

### Phase C：运行时重构

- 引入 artifact registry
- 以 sink 为目标执行图
- 节点缓存
- dirty 传播
- 局部重跑

### Phase D：移除线性真相

- `pipeline` 降级为 legacy import/export 兼容层
- workflow 成为唯一执行输入

---

## 12. 最终判断

真正像 ComfyUI 的 V2，不是“节点版 pipeline 配置页”，而是：

> 资产在项目里，引用在输入节点里；处理、分析、可视化、报告、导出全部以节点表达；用户自己拉线定义流程；所有节点都可删；运行从输出目标回溯依赖执行。

如果按这个目标推进，TextFlow 的节点流才会真正成立。  
如果继续围绕固定主链和不可删除节点修补，最后只会得到一个操作起来仍像表单的伪节点系统。
