# TextFlow 三核心工作台 UI 重构计划

> **给执行者:** 实施本计划时请使用 `superpowers:executing-plans`，按任务逐步执行并在每个阶段跑对应测试。

**目标:** 把 TextFlow 前端重构为围绕“语料、词库、节点图”三类项目核心对象组织的桌面工作台，并使用 Fluent UI React v9 承担桌面应用壳、命令栏、面板、表格、树、弹窗和基础控件。

**架构:** 项目不再被 UI 表达成一组互相独立的页面，而是表达成一个本地项目工作台。语料和词库是项目资产，节点图是流程编排真相；运行记录、日志、产物和导出都是节点图执行后的支撑对象。UI 层只负责展示和交互，不把工作流逻辑硬编码进组件；工作流编译、项目存储、引擎调用继续由现有 domain/store/bridge 层承担。

**技术栈:** Tauri 2、React 18、TypeScript、Vite、Fluent UI React v9、Fluent icons、Vitest、React Testing Library。

---

## 先纠正上一版计划的问题

上一版计划的问题不是方向完全错，而是表达重心错了。

它把重点放在了“换成 Fluent UI、做桌面工作台、左中右底布局”，但没有足够明确地回答：TextFlow 的工作台到底围绕什么东西展开。

TextFlow 项目最核心其实就是三样东西：

1. **语料**
   导入进来的文档集合、字段映射、主文本构造、语料视图、文档筛选、文档预览。

2. **词库**
   停用词、自定义词典、短语词典、同义词、近义词、标准词、排除词、正则规则，以及这些词表资源的版本、启用状态、命中和审计。

3. **节点图**
   用节点引用语料和词库，定义清洗、标准化、切词、词表应用、分析、可视化、导出这些处理关系。

所以新 UI 不应该只是“项目页、数据页、词表页、流程页、结果页”换个外壳。它应该让用户始终感到自己在同一个项目里管理三类对象，并用节点图把它们接起来。

## 最终 UI 心智模型

一句话：

> 左边管理项目的三类核心对象，中间操作当前打开的对象，右边检查和编辑选中对象，底部看运行、日志、审计和产物。

具体布局：

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ 项目标题栏 + 全局命令栏：新建/打开/导入/保存图/运行/停止/导出/搜索            │
├───────────────┬──────────────────────────────────────────────┬───────────────┤
│ 项目对象区     │ 主工作区                                      │ 属性检查器     │
│               │                                              │               │
│ 语料           │ 默认：节点图画布                              │ 当前选中：      │
│  - 全部语料    │ 可打开：语料表、词库表、产物预览、运行对比       │ - 语料视图      │
│  - 语料视图    │                                              │ - 文档          │
│  - 导入规范    │ 节点图中可拖入语料/词库资源生成输入节点          │ - 词库表        │
│               │                                              │ - 词条          │
│ 词库           │                                              │ - 节点          │
│  - 停用词      │                                              │ - 连线          │
│  - 同义词      │                                              │ - 运行/产物     │
│  - 标准词      │                                              │               │
│               │                                              │               │
│ 节点图         │                                              │               │
│  - 默认流程    │                                              │               │
│  - 自定义流程  │                                              │               │
├───────────────┴──────────────────────────────────────────────┴───────────────┤
│ 底部面板：运行进度 / 节点日志 / 校验问题 / 审计记录 / 产物列表               │
└──────────────────────────────────────────────────────────────────────────────┘
```

这不是传统页面导航，而是项目对象导航。

## 三个一级对象应该包括什么

### 1. 语料 Corpus

语料不是一个“导入页面”，而是项目资产。

语料区应包含：

- **原始导入批次**
  例如 `WoS 导入 2026-05-14`、`IncoPat 专利导入`。

- **导入规范**
  source profile、字段映射、主文本构造、跳过空值、字段别名。

- **语料集合**
  全部文档、按来源保存的集合、按年份保存的集合、用户手动保存的 corpus view。

- **文档**
  单篇文档的标题、正文、元数据、清洗后文本、tokens、状态。

语料对象在 UI 中的行为：

- 点击语料集合，在中间打开语料表。
- 点击单篇文档，右侧 inspector 显示文档详情。
- 从左侧拖一个语料集合到节点图，生成或绑定 `Corpus Input` 节点。
- 在节点 inspector 里选择语料资源时，使用同一套语料对象。

### 2. 词库 Lexicon / Dictionary

词库不是一个“词表规则页面”，而是项目资产。

词库区应包含：

- **词库分类**
  停用词、自定义词典、短语词典、正则规则、标准词、同义词、近义词、排除词。

- **资源表**
  内置表、项目自定义表、导入表、复制出来的可编辑表。

- **词条**
  source、target、enabled、hits、tags、notes、来源、版本。

- **绑定关系**
  哪些词库表会被哪些节点引用，哪些节点运行时命中过这些规则。

词库对象在 UI 中的行为：

- 点击词库分类，在中间打开该分类的资源表列表。
- 点击资源表，在中间打开词条表，右侧 inspector 显示表属性。
- 点击词条，右侧 inspector 编辑 source/target/enabled/notes。
- 从左侧拖一个词库资源到节点图，生成 `Dictionary Input` 节点，或绑定到 `Apply Dictionary Rules` 节点。
- 在节点运行结果里能回跳到命中的词库规则。

### 3. 节点图 Workflow Graph

节点图是项目的处理真相，不只是“处理与分析页面”。

节点图区应包含：

- **工作流定义**
  默认流程、自定义流程、模板生成流程、从旧配置迁移的流程。

- **节点**
  输入、清洗、标准化、切词、词表应用、过滤、分析、可视化、报告、导出。

- **连线**
  端口类型、数据流向、兼容校验。

- **节点参数**
  常用参数在节点卡片上快速编辑，高级参数在右侧 inspector。

- **运行态**
  pending、running、completed、cached、failed、dirty。

- **节点产物**
  表格、图表、报告、审计表、中间结果预览。

节点图对象在 UI 中的行为：

- 默认主工作区打开当前节点图。
- 用户从左侧拖入语料和词库，生成输入节点。
- 用户从节点库添加处理、分析、导出节点。
- 选中节点时右侧显示参数、输入输出 schema、最近运行、产物预览和审计。
- 选中连线时右侧显示数据类型、来源节点、目标节点和兼容性。
- 运行时底部显示节点进度、日志、校验问题和产物列表。

## 支撑对象：不再作为一级页面

以下对象重要，但不应该和语料、词库、节点图并列成为主要 UI 心智：

- **运行记录**
  属于节点图执行历史。

- **产物**
  属于某次运行或某个输出节点。

- **日志**
  属于运行过程。

- **导出**
  属于输出节点或运行产物的后续动作。

- **设置**
  属于项目或应用配置。

它们可以出现在左侧资源树的次级区、底部面板、右侧 inspector 或命令栏里，但不应该继续强化成“结果页自己干自己的、设置页自己干自己的”。

## 目标界面长什么样

### 启动或打开项目后

中间显示“项目三核心概览”，不是营销首页：

```text
当前项目：稀土论文与专利分析

语料
- 2 个导入批次
- 4,812 篇文档
- 3 个保存视图
- 最近导入：WoS 论文

词库
- 8 类词库
- 14 张资源表
- 6,230 条启用规则
- 最近命中最高：标准词库

节点图
- 默认流程：稀土主题分析
- 38 个节点
- 最近运行：成功，12 分钟前
- 产物：22 个表格/图表/报告
```

用户最自然的下一步是打开节点图，而不是在多个页面之间猜路线。

### 打开节点图后

主工作区是画布：

- 左侧对象区仍然显示语料、词库、节点图三大组。
- 左侧可以切换到“节点库”，但语料和词库资源仍可拖入画布。
- 中间是深色或中性节点画布。
- 顶部命令栏显示：保存图、运行、停止、自动布局、适配视图、校验、导出。
- 右侧 inspector 显示选中节点或连线。
- 底部显示运行进度、日志、校验问题、产物。

### 打开语料对象后

中间不是一个孤立“导入资料页面”，而是语料工作面：

- 左侧仍能看到当前项目的语料/词库/节点图。
- 中间是 corpus grid。
- 右侧是选中文档或导入规范 inspector。
- 顶部命令栏显示：导入文件、保存导入规范、创建语料视图、发送到节点图。
- 如果用户点“发送到节点图”，可以生成 `Corpus Input` 节点或绑定当前选中的 `Corpus Input` 节点。

### 打开词库对象后

中间是词库工作面：

- 左侧选中某类词库或资源表。
- 中间显示资源表列表或词条 grid。
- 右侧编辑资源表/词条属性。
- 顶部命令栏显示：导入词库、导出词库、新增词条、复制内置表、绑定到节点。
- 如果用户点“绑定到节点”，可选择当前图里的 `Dictionary Input` 或 `Apply Dictionary Rules` 节点。

### 查看结果后

结果不再是一个独立目的地，而是从节点图自然进入：

- 点击输出节点的产物，在中间打开 artifact preview tab。
- 点击底部产物列表，在中间打开表格、图表或报告预览。
- 点击运行记录，在中间打开 run detail 或 run diff。
- 右侧 inspector 显示产物来源、节点、参数快照、文件路径、导出动作。

## 导航结构

推荐主导航只保留这些稳定入口：

1. **项目**
   项目概览、最近项目、新建/打开/复制/删除。

2. **语料**
   当前项目的语料资产和导入规范。

3. **词库**
   当前项目的词库资产。

4. **节点图**
   当前项目的工作流图和节点库。

5. **运行**
   最近运行、队列、日志、产物。它是支撑入口，不是核心对象入口。

6. **设置**
   项目设置和应用设置。

如果要更极简，可以把“运行”并入底部面板和节点图，只在左侧保留：项目、语料、词库、节点图、设置。

## 关键交互流程

### 流程 1：从空项目开始

1. 用户创建项目。
2. 中间显示三核心概览，语料/词库/节点图都为空。
3. 用户点击“导入语料”。
4. 导入完成后，左侧语料区出现导入批次和“全部语料”。
5. 用户点击“创建默认节点图”。
6. 系统生成一个 starter graph，其中 `Corpus Input` 引用刚导入的语料。
7. 用户运行节点图。
8. 底部显示进度，输出节点产生表格、图表和报告产物。

### 流程 2：把词库接入节点图

1. 用户在词库区导入或编辑同义词表。
2. 左侧词库区出现新的资源表。
3. 用户把该资源表拖入画布。
4. 如果画布上已有 `Apply Dictionary Rules` 节点，系统提示“绑定到现有节点”或“创建 Dictionary Input 节点”。
5. 运行后，节点 inspector 显示命中的规则数量。
6. 点击命中规则可回跳到词库条目。

### 流程 3：从结果回溯规则

1. 用户打开关键词或词频产物。
2. 右侧 inspector 显示产物来源节点和参数快照。
3. 用户点击某个词项。
4. inspector 显示该词项来自哪些文档、被哪些词库规则影响、在哪些节点产物中出现。
5. 用户可以直接跳到对应词库条目或文档。

这个流程很重要，因为 TextFlow 的产品优先级里有“规则审计”和“运行历史”。新 UI 应该让回溯变自然，而不是让用户在多个页面之间来回找。

## 推荐文件结构

```text
apps/desktop/src/
  app/
    AppShell.tsx                 # 顶层 FluentProvider + 工作台壳
    ProjectWorkbench.tsx         # 三核心工作台布局
    workbenchNavigation.ts       # 项目/语料/词库/节点图/设置导航
    workbenchSelection.ts        # 跨对象选中模型
    workbenchCommands.ts         # 顶部命令栏聚合
    workbenchLayoutState.ts      # 左/右/底面板折叠与尺寸
    fluentTheme.ts               # Fluent 主题与密度 token

  ui/fluent/
    AppToolbar.tsx
    AppPanel.tsx
    AppDataGrid.tsx
    AppTree.tsx
    AppInspector.tsx
    AppEmptyState.tsx
    AppMetric.tsx
    index.ts

  features/corpus/
    CorpusExplorer.tsx           # 左侧语料树
    CorpusWorkspace.tsx          # 中间语料表/导入规范工作面
    CorpusInspector.tsx          # 右侧文档/语料视图/导入规范属性
    corpusCommands.ts

  features/lexicon/
    LexiconExplorer.tsx          # 左侧词库树
    LexiconWorkspace.tsx         # 中间词库表/词条表
    LexiconInspector.tsx         # 右侧词库表/词条属性
    lexiconCommands.ts

  features/workflow/
    WorkflowExplorer.tsx         # 左侧流程树/节点库
    WorkflowWorkspace.tsx        # 中间节点图画布
    WorkflowCanvas.tsx
    WorkflowNodeCard.tsx
    WorkflowInspector.tsx
    WorkflowStatusPane.tsx
    workflowCommands.ts
    workflowEditorState.ts

  features/runs/
    RunStatusPane.tsx            # 底部运行/日志/校验/产物
    RunHistoryWorkspace.tsx
    ArtifactWorkspace.tsx
    RunInspector.tsx
    runCommands.ts

  features/project/
    ProjectOverviewWorkspace.tsx
    ProjectExplorer.tsx
    ProjectInspector.tsx
    projectCommands.ts

  features/settings/
    SettingsWorkspace.tsx
```

命名上建议用 `corpus` 和 `lexicon`，不要继续让 UI 到处叫 `data` / `dictionaries` / `results`。用户可以看到中文“语料/词库/节点图”，代码里也尽量贴近领域对象。

## 跨对象选中模型

需要一个全局的 workbench selection，而不是每个页面自己维护自己的 selected state。

建议类型：

```ts
export type WorkbenchSelection =
  | { kind: "project"; projectId: string }
  | { kind: "corpus_collection"; projectId: string; collectionId: string }
  | { kind: "corpus_document"; projectId: string; docId: string }
  | { kind: "ingestion_spec"; projectId: string; specId: string }
  | { kind: "lexicon_kind"; projectId: string; dictionaryKind: DictionaryKind }
  | { kind: "lexicon_table"; projectId: string; dictionaryKind: DictionaryKind; tableId: string }
  | { kind: "lexicon_entry"; projectId: string; dictionaryKind: DictionaryKind; tableId: string; entryId: string }
  | { kind: "workflow"; projectId: string; workflowId: string }
  | { kind: "workflow_node"; projectId: string; workflowId: string; nodeId: string }
  | { kind: "workflow_edge"; projectId: string; workflowId: string; edgeId: string }
  | { kind: "run"; projectId: string; runId: string }
  | { kind: "artifact"; projectId: string; artifactId: string };
```

这个模型的作用：

- 左侧树点击对象，更新 selection。
- 中间工作区根据 selection 打开或聚焦对应 surface。
- 右侧 inspector 根据 selection 渲染。
- 命令栏根据 selection 决定启用哪些命令。
- 节点图、语料表、词库表、产物预览之间可以互相跳转。

这一步是让 UI 不再“各页面各干各的”的关键。

## 顶部命令栏设计

命令栏不应该是每个页面自己写一排按钮。应由当前 selection + active workspace 推导。

命令分组：

- **项目**
  新建、打开、复制、删除、导入项目包、导出项目包。

- **语料**
  导入文件、保存导入规范、创建语料视图、编辑文档、删除文档、发送到节点图。

- **词库**
  新建资源表、导入词库、导出词库、新增词条、复制内置表、绑定到节点。

- **节点图**
  新建图、保存图、运行、停止、自动布局、适配视图、校验、清空画布。

- **运行/产物**
  打开产物、定位文件、比较运行、导出表格、导出报告。

命令描述建议：

```ts
export interface WorkbenchCommand {
  id: string;
  label: string;
  icon: React.ReactNode;
  group: "project" | "corpus" | "lexicon" | "workflow" | "run" | "view";
  enabled: boolean;
  visible: boolean;
  tooltip?: string;
  run: () => void | Promise<void>;
}
```

## Fluent UI 使用边界

Fluent 应该负责：

- `FluentProvider`
- 主题 token
- Button / Toolbar / Menu / Tooltip
- Tree
- DataGrid
- Dialog / Drawer
- Field / Input / Textarea / Select / Switch
- Badge / ProgressBar / Spinner
- TabList

继续自定义：

- 节点画布
- 节点卡片布局
- 连线层
- mini-map
- 图表/canvas 预览
- 需要特殊交互的词云、网络图、聚类图

不要为了“全都 Fluent”牺牲节点图原生感。Fluent 是桌面壳和控件系统，节点图仍应保持 TextFlow 自己的产品性格。

## 分阶段实施计划

### Phase 0：统一术语和计划

**目标:** 先把 UI 目标统一成“语料、词库、节点图”三核心模型。

**文件:**

- 修改：`docs/current-status.md`
- 修改：`docs/technical-overview.md`
- 修改：`docs/development.md`
- 修改：`apps/desktop/src/screens.tsx`
- 修改：`apps/desktop/src/App.tsx`

**步骤:**

1. 更新文档中的 UI 说明，把“数据/词表/结果页面”表述调整为“语料/词库/节点图/运行产物工作台”。
2. 在代码里先保留旧 page id，但新增面向 UI 的 activity 命名。
3. 明确 `results` 是运行/产物支撑 surface，不是核心对象。
4. 跑 `npm run lint`。

**验收:**

- 文档和计划不再把 UI 描述成多个孤立页面。
- 代码暂不大改，但命名迁移方向明确。

### Phase 1：建立三核心工作台壳

**目标:** 替换当前 `App.tsx` 的 sidebar/topbar/progress strip，建立项目对象区 + 主工作区 + inspector + 底部面板。

**文件:**

- 创建：`apps/desktop/src/app/AppShell.tsx`
- 创建：`apps/desktop/src/app/ProjectWorkbench.tsx`
- 创建：`apps/desktop/src/app/workbenchNavigation.ts`
- 创建：`apps/desktop/src/app/workbenchSelection.ts`
- 创建：`apps/desktop/src/app/workbenchLayoutState.ts`
- 创建：`apps/desktop/src/app/fluentTheme.ts`
- 修改：`apps/desktop/src/App.tsx`
- 修改：`apps/desktop/src/styles.css`
- 测试：`apps/desktop/src/app/ProjectWorkbench.test.tsx`

**步骤:**

1. 安装 Fluent UI 依赖。
2. 用 `FluentProvider` 包住应用。
3. 新建 `WorkbenchSelection` 类型和 reducer。
4. 新建左侧三核心对象区，先用现有 snapshot 数据渲染语料、词库、节点图。
5. 中间暂时继续挂载现有 `PageView`，但默认进入 workflow/project overview。
6. 右侧新建 inspector host，先支持 empty/project/workflow/corpus/lexicon/artifact 的基础状态。
7. 底部移动当前 progress strip，增加日志/校验/产物 tab 壳。
8. 保留 `uiScale`、loading、statusLine、taskProgress 行为。
9. 跑 `npm run lint`、`npm run test --workspace apps/desktop`、`npm run build`。

**验收:**

- 打开项目后能看到语料、词库、节点图三个对象区。
- 当前 workflow 可以作为主工作区打开。
- 右侧 inspector 和底部面板始终存在，可折叠。
- 旧功能仍可进入和使用。

### Phase 2：把语料变成对象工作面

**目标:** 把原 `DataPage` 迁移为语料工作面，而不是独立导入页。

**文件:**

- 创建：`apps/desktop/src/features/corpus/CorpusExplorer.tsx`
- 创建：`apps/desktop/src/features/corpus/CorpusWorkspace.tsx`
- 创建：`apps/desktop/src/features/corpus/CorpusInspector.tsx`
- 创建：`apps/desktop/src/features/corpus/corpusCommands.ts`
- 修改：`apps/desktop/src/screens.tsx`
- 测试：`apps/desktop/src/features/corpus/CorpusWorkspace.test.tsx`

**步骤:**

1. 把导入批次、导入规范、全部语料、语料视图建模成左侧语料树节点。
2. 点击语料集合时，中间打开 corpus grid。
3. 点击文档时，更新 `WorkbenchSelection` 为 `corpus_document`。
4. 右侧 inspector 显示文档正文、元数据、清洗文本、tokens。
5. 顶部命令栏显示导入文件、保存导入规范、创建视图、发送到节点图。
6. “发送到节点图”先实现为：打开 workflow，并选中或创建 `Corpus Input` 的入口动作。
7. 保留现有导入字段映射功能。
8. 跑前端测试。

**验收:**

- 语料不再只存在于导入页。
- 文档选择能驱动右侧 inspector。
- 语料集合能和节点图发生关系。

### Phase 3：把词库变成对象工作面

**目标:** 把原 `DictionariesPage` 迁移为词库工作面，并和节点图绑定。

**文件:**

- 创建：`apps/desktop/src/features/lexicon/LexiconExplorer.tsx`
- 创建：`apps/desktop/src/features/lexicon/LexiconWorkspace.tsx`
- 创建：`apps/desktop/src/features/lexicon/LexiconInspector.tsx`
- 创建：`apps/desktop/src/features/lexicon/lexiconCommands.ts`
- 修改：`apps/desktop/src/workflowNodeRegistry.tsx`
- 测试：`apps/desktop/src/features/lexicon/LexiconWorkspace.test.tsx`

**步骤:**

1. 左侧词库树显示 8 类词库和每类资源表。
2. 点击词库分类，中间显示资源表列表。
3. 点击资源表，中间显示词条 grid。
4. 点击词条，右侧 inspector 编辑条目。
5. 顶部命令栏显示导入、导出、新增、复制内置表、绑定到节点。
6. 在 `Apply Dictionary Rules` 或 `Dictionary Input` 节点 inspector 里使用同一套词库资源选择。
7. 从节点运行审计命中回跳到词库条目。
8. 跑前端测试。

**验收:**

- 词库是项目资源，不是孤立页面。
- 词库和节点绑定关系可见。
- 规则命中能回溯到词条。

### Phase 4：节点图成为默认主工作区

**目标:** 工作流画布成为项目默认工作面，语料和词库以资源方式进入图。

**文件:**

- 创建/修改：`apps/desktop/src/features/workflow/WorkflowWorkspace.tsx`
- 创建/修改：`apps/desktop/src/features/workflow/WorkflowExplorer.tsx`
- 创建/修改：`apps/desktop/src/features/workflow/WorkflowInspector.tsx`
- 创建/修改：`apps/desktop/src/features/workflow/WorkflowStatusPane.tsx`
- 创建：`apps/desktop/src/features/workflow/workflowCommands.ts`
- 修改：`apps/desktop/src/workflow.ts`
- 修改：`apps/desktop/src/workflowNodeRegistry.tsx`
- 测试：`apps/desktop/src/features/workflow/WorkflowWorkspace.test.tsx`

**步骤:**

1. 保留现有拖拽、连线、缩放、预览、保存、运行能力。
2. 把节点库放进 workflow explorer。
3. 允许从语料树拖资源到画布生成 `Corpus Input`。
4. 允许从词库树拖资源到画布生成 `Dictionary Input` 或绑定词库应用节点。
5. 选中节点时，右侧 inspector 显示参数、schema、运行状态、产物、审计。
6. 选中连线时，右侧 inspector 显示端口类型和兼容性。
7. 运行态统一进入底部状态面板。
8. 跑前端测试和 `npm run build`。

**验收:**

- 用户能从“语料 + 词库”自然构造节点图。
- 节点图不是单独页面，而是项目主工作区。
- inspector 和底部面板成为工作流日常操作的一部分。

### Phase 5：运行和产物降级为支撑面板

**目标:** 把结果页能力拆成运行历史、产物预览、导出命令，挂到节点图和底部面板上。

**文件:**

- 创建：`apps/desktop/src/features/runs/RunStatusPane.tsx`
- 创建：`apps/desktop/src/features/runs/RunHistoryWorkspace.tsx`
- 创建：`apps/desktop/src/features/runs/ArtifactWorkspace.tsx`
- 创建：`apps/desktop/src/features/runs/RunInspector.tsx`
- 创建：`apps/desktop/src/features/runs/runCommands.ts`
- 修改：`apps/desktop/src/features/results/RunHistoryPanel.tsx`
- 修改：`apps/desktop/src/features/artifacts/ArtifactBrowser.tsx`

**步骤:**

1. 底部面板显示当前运行进度、节点日志、校验问题、产物列表。
2. 点击产物，在中间打开 artifact workspace tab。
3. 点击运行记录，在中间打开 run history/detail workspace。
4. 输出节点 inspector 显示其产物和导出动作。
5. 导出 CSV/XLSX/PNG/HTML 从命令栏或输出节点触发。
6. 保留现有结果页作为过渡入口，后续可以隐藏。
7. 跑前端测试。

**验收:**

- 用户从节点图和运行过程进入结果，而不是先切到孤立结果页。
- 产物可追溯到节点、运行和参数快照。

### Phase 6：拆分 `screens.tsx` 和清理旧 CSS

**目标:** 移除旧页面式实现的维护负担。

**文件:**

- 修改：`apps/desktop/src/screens.tsx`
- 修改：`apps/desktop/src/ui.tsx`
- 修改：`apps/desktop/src/styles.css`
- 修改：各 feature 目录

**步骤:**

1. 把 `screens.tsx` 缩减为过渡路由，或完全替换为 workbench surfaces。
2. 把旧 `Panel`、`Table`、`StatCard` 等迁移到 Fluent/app wrapper。
3. 删除不再使用的旧 sidebar/topbar/content-grid CSS。
4. 检查小窗口和中等桌面窗口。
5. 跑 `npm run lint`、`npm run test --workspace apps/desktop`、`npm run build`。

**验收:**

- UI 结构不再由旧 page list 主导。
- CSS 不再同时维护两套应用壳。
- 工作台对象模型清晰可维护。

## 测试策略

前端默认验证：

```powershell
npm run lint
npm run test --workspace apps/desktop
npm run build
```

需要新增测试：

- 三核心对象区能渲染语料、词库、节点图。
- 点击语料对象会更新 selection 和 inspector。
- 点击词库对象会更新 selection 和 inspector。
- 点击节点会更新 selection 和 inspector。
- 命令栏会根据 selection 启用/禁用命令。
- 底部运行面板能显示 progress 和节点状态。
- artifact 能从输出节点或底部产物列表打开。
- 语料/词库资源能触发“发送到节点图”或“绑定到节点”的动作。

前端 UI 重构一般不需要跑 engine 测试。只有当修改了 Python-facing contract、workflow/project manifest、导出/导入模板或样例 bootstrap 相关行为时，才跑：

```powershell
npm run test:engine:fast
```

触及样例生成、sidecar 打包、seeded sample 或导出导入模板联动时，再跑：

```powershell
npm run test:engine:full
```

## 关键风险

| 风险 | 处理 |
| --- | --- |
| 只换 Fluent，心智仍是旧页面 | 先做 WorkbenchSelection 和三核心对象区，再迁移具体页面。 |
| 节点图被普通表单 UI 稀释 | 节点画布保持自定义，Fluent 只做壳、命令、面板和基础控件。 |
| 语料/词库/节点图互相跳转混乱 | 用统一 selection 模型，不让每个页面各自维护选中状态。 |
| 右侧 inspector 变成另一个大表单 | 只显示当前选中对象的属性、参数、审计和预览；复杂编辑仍可在中间工作区完成。 |
| 运行产物找不到来源 | artifact inspector 必须显示 run、node、参数快照和文件路径。 |
| 项目文件被 UI 状态污染 | 面板折叠、tab、选择、宽度等 transient UI state 不写入 `.tfproj`。 |

## 最终判断

这次 UI 重构的主线不应该是“Fluent 化”，而应该是：

> 把 TextFlow 项目表达为语料、词库、节点图三类核心对象；节点图引用语料和词库完成处理；运行记录、日志、审计、产物围绕节点图自然出现。

Fluent UI React v9 只是帮助我们把这个模型做成稳定、密集、像桌面软件的工作台。

