# TextFlow Studio — 完整技术说明文档

> 自动生成于 2026-04-29

## 一、项目概述

**TextFlow Studio** 是一款**桌面优先的本地文本预处理与基础文本挖掘工具**，面向科研文献分析、舆情分析、内容分析、语料整理等场景。

| 属性 | 值 |
|---|---|
| 项目名称 | `textflow-studio` |
| 当前版本 | `0.2.0` |
| 许可证 | 私有 |
| 仓库地址 | https://github.com/tylevnovik/TextFlow |
| 目标平台 | Windows (主), macOS (可移植, 未正式验证) |
| 一句话定位 | 文本整理与基础分析工具，按项目保存语料、词库、节点图和运行产物 |

---

## 二、技术架构

### 2.1 三层桌面架构

```
┌─────────────────────────────────────────────────────────┐
│                   用户界面层 (Frontend)                    │
│     Tauri 2 Shell (Rust) + React 18 + TypeScript + Vite  │
│     • 工作台 activity: 项目/语料/词库/节点图/运行产物/设置     │
│     • 工作流画布: DAG 节点拖拽/连线/缩放/配置               │
│     • 通过 Tauri IPC 调用后端                              │
└───────────────────────┬─────────────────────────────────┘
                        │ Tauri invoke / HTTP bridge
┌───────────────────────┴─────────────────────────────────┐
│                   命令桥接层 (Bridge)                      │
│     desktopBridge.ts — 33 个 Tauri 命令                    │
│     • 双模式: Tauri IPC (生产) / 浏览器模拟数据 (开发)      │
│     • 事件订阅: engine-progress 进度推送                   │
└───────────────────────┬─────────────────────────────────┘
                        │ HTTP localhost:8765
┌───────────────────────┴─────────────────────────────────┐
│                   计算引擎层 (Python Sidecar)              │
│     Python 3.11+ / PyInstaller 打包                      │
│     • FastAPI/Uvicorn 本地 HTTP 任务接口                  │
│     • DAG 运行时: 拓扑排序 → 并行批次执行                   │
│     • 35 个节点执行器 / 40+ 节点定义                        │
│     • jieba 分词 / sklearn 聚类 / YAKE 关键词 / NMF 主题   │
│     • 项目持久化: .tfproj 目录结构                          │
└─────────────────────────────────────────────────────────┘
```

### 2.2 Monorepo 结构

```
TextFlow/
├── package.json              # 根 monorepo (npm workspaces)
├── tsconfig.base.json        # 共享 TS 配置 (ES2022, strict)
├── AGENTS.md                 # AI 代理指令 / 项目规则
├── CHANGELOG.md              # 版本日志
│
├── apps/desktop/             # 桌面前端应用
│   ├── src/                  #   React + TypeScript 源码
│   └── src-tauri/            #   Rust/Tauri 后端
│
├── packages/shared-types/    # 共享类型包 (~895 行, ~80 个类型导出)
│   └── src/index.ts          #   前后端共享的领域类型定义
│
├── services/python-engine/   # Python 计算引擎
│   ├── app/                  #   核心引擎逻辑 (分包化为 analysis/workflow/api/storage/domain/ingestion/reporting/samples 等模块)
│   ├── tests/                #   测试套件 (25 个测试文件)
│   └── dist/                 #   PyInstaller 构建输出
│
├── plugins/nodes/            # Python 节点插件目录
├── scripts/                  # PowerShell 构建/测试脚本
└── docs/                     # 文档 (6 篇活跃文档 + 归档)
```

> **注意**: 不使用 Turborepo，仅通过 npm workspaces + PowerShell 脚本进行编排。

---

## 三、前端应用 (`apps/desktop/`)

### 3.1 技术栈

| 技术 | 版本 | 用途 |
|---|---|---|
| React | 18.3+ | UI 框架 |
| TypeScript | 5.7+ | 类型安全 |
| Vite | 5.4+ | 构建工具 |
| Vitest | 2.1+ | 测试框架 |
| Tauri | 2.0 | 桌面壳 (Rust) |
| Fluent UI React v9 | 9.73+ | 新工作台壳、命令栏、树、面板、Tab 和基础控件 |
| Fluent Icons | 2.0+ | 工作台命令与对象树图标 |
| CSS | 原生 | 工作台布局、旧页面和节点画布定制样式 |

Fluent UI React v9 已先接入 `AppShell` 和 `ProjectWorkbench`，承担应用壳、命令栏、对象树、底部 Tab、属性检查器和基础按钮。旧 `PageId` 和 `ui.tsx` 组件仍保留，用于承载现有页面内容；语料工作面已拆到 `features/corpus/`，词库工作面已拆到 `features/lexicon/`，节点图工作面已拆到 `features/workflow/`，运行产物支撑面已拆到 `features/runs/`。

### 3.2 工作台 activity 与旧 PageId 映射

| 旧 PageId | UI activity | 角色 | 功能描述 |
|---|---|---|---|
| `home` | 开始 | 系统入口 | 项目选择、创建、首页仪表板 |
| `project` | 项目 | 核心对象 | 项目统计、三核心概览、源文件、最近运行、复核任务、实验 |
| `data` | 语料 | 核心对象 | 文件导入、字段映射、主文本构造、语料管理、导入规范 |
| `dictionaries` | 词库 | 核心对象 | 管理 8 类词库: 停用词/自定义/短语/同义/近义/标准/排除/正则 |
| `workflow` | 节点图 | 核心对象 | **主工作区** — 可视化 DAG 工作流编辑器，引用语料和词库资源 |
| `results` | 运行产物 | 支撑面 | 运行历史/运行对比/导出控制；产物预览可从底部面板、运行产物 workspace 或工作流节点弹窗进入 |
| `report` | 报告预览 | 支撑面 | 预览 HTML 报告结构和摘要，不作为一级核心对象入口 |
| `settings` | 设置 | 系统入口 | UI 缩放/语言/主题/项目路径 |

`results` 和 `report` 是节点图执行后的支撑 surface，不再作为和语料、词库、节点图并列的核心对象来描述。

语料工作面当前由 `CorpusWorkspace` 提供命令栏和摘要，`CorpusInspector` 提供集合/导入规范/文档属性检查器。文档点击会通过统一 `WorkbenchSelection` 更新为 `corpus_document`，右侧检查器显示正文、元数据、清洗文本和 tokens。

词库工作面当前由 `LexiconWorkspace` 提供命令栏和摘要，`LexiconInspector` 提供分类/资源表/条目属性检查器。资源表点击会通过统一 `WorkbenchSelection` 更新为 `lexicon_table`，右侧检查器显示资源类型、条目数、启用条目、命中次数和绑定入口。

节点图工作面当前由 `WorkflowWorkspace` 提供命令栏、摘要和状态面板，`WorkflowInspector` 提供节点图/节点/连线属性检查器。画布点击节点或连线会通过统一 `WorkbenchSelection` 更新为 `workflow_node` 或 `workflow_edge`，右侧检查器显示节点参数、端口、运行状态、产物摘要或连线端口兼容性。项目对象树里的语料集合和词库资源表支持以 selection payload 拖入画布，作为 `Corpus Input` 与 `Dictionary Input` 的资源绑定入口。

运行产物支撑面当前由 `RunStatusPane`、`RunHistoryWorkspace`、`ArtifactWorkspace` 和 `RunInspector` 承担。底部面板显示当前运行进度、节点日志、校验问题与产物列表；点击 run 或 artifact 会更新统一 `WorkbenchSelection`，中间打开相应支撑 workspace，右侧检查器显示运行、节点、参数快照、文件路径和导出动作。

### 3.3 节点图画布

节点图工作面采用独立的深色主题布局:
- **左侧工具栏** (64px): 操作按钮
- **停靠面板** (330px): 节点工具箱与配置面板
- **画布区域**: 支持缩放/平移、节点拖拽、连线、小地图
- **浮动顶栏**: 工作流标题、状态指示器、运行控制
- **检查器抽屉**: 节点属性详情

### 3.4 前后端通信

```
┌──────────────────┐     invoke()      ┌──────────────────┐
│   React 组件     │ ────────────────→ │   Tauri Rust     │
│                  │                    │   (IPC Bridge)   │
│  useReducer      │ ←──────────────── │                  │
│  startTransition │   engine-progress  │                  │
│  Context API     │   (实时进度事件)    │                  │
└──────────────────┘                    └──────────────────┘
```

- **Tauri IPC (生产)**: `invoke<T>(command, payload)` 调用 33 个 Tauri 命令
- **浏览器回退 (开发)**: `isTauri()` 为 false 时返回模拟数据，支持纯前端开发
- **进度订阅**: `listen("engine-progress", ...)` 接收实时工作流进度 (节点级状态)
- **状态管理**: `WorkspaceProvider` — useReducer + Context，乐观本地补丁模式

### 3.5 Tauri 命令清单

| 命令 | 功能 |
|---|---|
| `load_workspace` | 加载工作区状态 |
| `create_project` / `open_project` / `delete_project` | 项目 CRUD |
| `import_project_files` | 导入语料文件 |
| `run_workflow` | 执行完整 NLP 流水线 |
| `save_project` | 持久化项目清单 |
| `export_project` / `export_project_backup` | 生成输出文件 |
| `create_corpus_view` / `update_corpus_view` / `delete_corpus_view` | 语料视图管理 |
| `save_ingestion_spec` | 保存导入规范 |
| `import_dictionary_sheet` / `export_dictionary_sheet` | 词表导入/导出 |
| `create_review_task` / `list_review_tasks` / `resolve_review_task` | 人工复核工作流 |
| `save_experiment_spec` / `run_experiment_matrix` | 实验管理 |
| `compare_runs` | 运行对比 |
| `load_artifact_preview` / `list_run_artifacts` | 节点产物预览 |
| `open_path` / `reveal_path` | 系统文件管理器集成 |

---

## 四、共享类型包 (`packages/shared-types/`)

`src/index.ts` 是**前后端共享的唯一类型真相来源**，约 895 行，导出 ~80 个类型/接口。

### 4.1 核心类型分类

| 分类 | 关键类型 | 说明 |
|---|---|---|
| **数据源** | `SourceProfile` (7 种) | generic/literature/wos/scopus/patent/incopat/business_reserved |
| **工作流** | `BuiltinWorkflowNodeType` | 语料输入/词典/清洗/分词/分析/图分析/技术识别/导出/工具 |
| **端口类型** | `WorkflowPortType` | CorpusResource/CleanCorpus/FrequencyTable/GraphMetricTable 等 |
| **运行状态** | `RunStatus` | idle/running/completed/failed/cancelled |
| **字典类型** | `DictionaryKind` (8 种) | stopwords/synonym/standard_terms 等 |
| **导出格式** | `ExportFormat` | csv/xlsx/png/html |
| **页面/工作台** | `PageId` + 前端 activity 元数据 | 旧 ID 保持 home/project/data/workflow/dictionaries/results/report/settings；UI 文案映射为项目/语料/词库/节点图/运行产物/设置 |

### 4.2 核心接口

- **项目模型**: `ProjectManifest` — 根项目结构 (.tfproj)，包含所有子资源
- **语料文档**: `CorpusItem` — 单文档，含 raw_text/clean_text/tokens/filtered_tokens + 元数据
- **词表系统**: `DictionarySet` -> `DictionaryCollection` -> `DictionarySheet` -> `DictionaryEntry`
- **工作流图**: `WorkflowDefinition` -> `WorkflowNodeInstance` + `WorkflowEdge` + `WorkflowGroup`
- **运行记录**: `RunRecord` — 运行 ID、时间戳、状态、日志、工件、节点摘要
- **分析结果**: 11 种行类型 (FrequencyRow/TermDocumentRow/CooccurrenceRow/KeywordRow 等)

### 4.3 预置导入模板

为 7 种数据源预定义了字段映射模板:
- **通用 (generic)**: 自动匹配
- **文献 (literature)**: 标准学术字段
- **WOS**: Web of Science 字段码 (UT/TI/AB/PY/SO/AU/C1/DE/WC)
- **Scopus**: 常见 Scopus 导出字段 (EID/Title/Abstract/Authors/Affiliations)
- **专利 (patent)**: 标准专利字段
- **IncoPat**: 中文专利字段 (含大量别名)
- **商业 (business_reserved)**: 预留

### 4.4 参数接口

| 接口 | 说明 |
|---|---|
| `CleaningParameters` | 10 个布尔开关 (HTML/URL/邮箱/电话剥离、空白/标点标准化等) |
| `NormalizationParameters` | 繁→简、数字/时间标准化、正则规则、优先级 |
| `TokenizationParameters` | 语言模式、后端、自定义词典、短语保持、最小词长 |
| `DictionaryParameters` | 应用哪些词表类型、冲突解决策略 |
| `FilteringParameters` | 最小词长、数字过滤、最小词频、词性过滤 |
| `AnalysisParameters` | top_n、共现窗口、特征词数、聚类 K 值、各分析类型开关 |
| `ExportParameters` | 格式开关、审计包含、图表 DPI、水印设置 |
| `RunScopeDefinition` | 作用域模式 (all/filtered/selected)、过滤条件 |

---

## 五、Python 计算引擎 (`services/python-engine/`)

### 5.1 服务架构

```
main.py
├── CLI 模式: python main.py <action> [json-payload]
└── HTTP 模式: python main.py serve [host port]
    └── service.py (FastAPI + Uvicorn, port 8765)
        ├── GET  /health           -> {"status": "ok"}
        ├── GET  /tasks/{task_id}  -> 任务快照
        ├── POST /tasks/start      -> {"action": "...", "payload": {...}}
        └── POST /shutdown         -> 优雅关闭
```

- **TaskManager**: 单线程执行器 (max_workers=1)，支持异步任务提交与进度回调
- **33 个已注册 Action**: 涵盖工作区/项目CRUD/导入导出/词典/复核/实验/工件等

### 5.2 CLI Action 清单 (33 个)

| 类别 | Actions |
|---|---|
| **工作区** | `load-workspace` |
| **项目 CRUD** | `create-project`, `create-project-from-template`, `open-project`, `duplicate-project`, `delete-project` |
| **导入/导出** | `import-project-files`, `run-workflow`, `export-project`, `export-project-backup`, `import-project-package` |
| **模板** | `save-project-template`, `list-project-templates`, `save-import-template`, `list-import-templates`, `load-import-template` |
| **语料** | `save-project`, `update-corpus-document`, `delete-corpus-document` |
| **词典** | `import-dictionary-sheet`, `export-dictionary-sheet` |
| **复核** | `create-review-task`, `list-review-tasks`, `resolve-review-task`, `apply-review-resolution` |
| **实验** | `save-experiment-spec`, `list-experiment-specs`, `run-experiment-matrix` |
| **对比** | `compare-runs` |
| **导入规范** | `save-ingestion-spec`, `list-ingestion-specs` |
| **视图** | `create-corpus-view`, `update-corpus-view`, `delete-corpus-view` |
| **工件** | `load-artifact-preview`, `load-artifact-payload`, `list-run-artifacts` |

### 5.3 核心处理模块

#### 文本操作与预处理 (`app/analysis/text.py`, ~532 行)

| 功能 | 函数 | 说明 |
|---|---|---|
| 清洗 | `apply_cleaning()` | HTML/URL/邮箱/电话/表情剥离; 空白/标点/全半角/大小写标准化 |
| 归一化 | `apply_normalization()` | 繁->简中文; 数字/时间标准化; 正则规则; 审计追踪 |
| 短语保护 | `protect_phrases()` | 分词前保护领域短语不被切碎 |
| 分词 | `tokenize_text()` | jieba 中英文混合分词 + 短语保持 |
| 词典应用 | `apply_dictionary()` | 标准词->同义词->近义词->停用词->排除词 流水线 |
| 过滤 | `filter_token_lists()` | 最小长度/数字过滤/词频过滤 |

#### 分析与聚类操作 (`app/analysis/` 目录下多模块)

分析算法与统计计算逻辑已重构分包，文件总规模 ~1200 行：
- **`app/analysis/statistics.py`**：词频统计（`frequency_table()`）、词-文档关系（`term_document_table()`）、词-年份关系（`term_year_table()`）及共现分析（`cooccurrence_table()`）。
- **`app/analysis/keywords.py`**：关键词提取（YAKE 算法，含 `yake_keyword_rows()` 等）、TF-IDF 特征词（`tfidf_feature_bundle()`）。
- **`app/analysis/topics.py`**：主题建模（NMF 算法，`nmf_topic_model()`）、聚类与坐标评估（`keyword_clusters()`、`document_clusters()`、`cluster_evaluation_rows()` 等）。
- **`app/analysis/technology.py`**：技术识别、分类以及主路径等分析。
- **`app/analysis/graph.py`**：网络/图计算相关共现矩阵与图指标计算。

#### 配置、默认值与编译逻辑 (`app/domain/defaults.py`, `app/workflow/` 目录下多模块)

- **`app/domain/defaults.py`**：定义 8 种字典类型、6 种导入配置文件和默认项目骨架（`default_project_manifest()`）。
- **`app/workflow/compilers.py`**：包含从 DAG 编译运行时配置（`compile_runtime_profile_from_workflow()`）。
- **`app/workflow/registry.py`**：提供工作流定义和节点注册服务，包括构建完整默认 DAG（`default_workflow_definition()`）。
- **`app/workflow/runner.py`**：计算工作流哈希（`workflow_payload_hash()`）。

### 5.4 DAG 执行引擎 (`app/workflow/runtime/` 子包)

原 `dag_runtime.py` 的 DAG 执行逻辑已被重构并拆分为以下子模块：
- **`native.py`**：工作流执行的主入口与装配器，驱动整体运行生命周期（`run_project_workflow_native()`）。
- **`context.py`**：提供线程安全的执行上下文管理（`WorkflowExecutionContext`，含 `RLock`）。
- **`scheduler.py`**：处理节点的拓扑排序与并行批次调度（`_topological_active_node_batches()`）。
- **`cache.py`**：节点级缓存管理（基于 Pickle + SHA256 缓存键）。
- **`artifacts.py`**：管理节点运行中产生的临时与持久化工件。
- **`previews.py`**：负责节点执行结果的预览快照生成。
- **`incremental.py`**：支持脏节点检测与局部增量重算。
- **`support.py`**：其他辅助与支持函数。

### 5.5 节点执行器 (`app/workflow/executors/` 子包)

节点执行逻辑已按照功能类别拆分为 `app/workflow/executors/` 子包，并在 `__init__.py` 中统一对外注册：
- **`corpus.py`**：语料相关输入与合并（如 `execute_corpus_input`、`execute_merge_corpora` 等）。
- **`preprocessing.py`**：文本清洗、归一化、分词和词典过滤（如 `execute_clean_text`、`execute_normalize_text` 等）。
- **`analysis.py`**：各种统计与挖掘算法分析（如 `execute_frequency_statistics`、`execute_topic_modeling`、`execute_document_clustering` 等）。
- **`export.py`**：数据与报告导出（如 `execute_save_csv`、`execute_save_xlsx` 等）。
- **`technology.py`**：技术识别分析。
- **`support.py`**：辅助性节点执行器。

### 5.6 节点定义 (`app/workflow/definitions/` 子包)

节点定义被组织在 `app/workflow/definitions/` 下，包括内置节点与工作流定制节点：
- **`builtin.py`**：定义了所有系统内置节点（如语料输入、清洗、分词、分析等）。
- **`new_flow.py`**：定义了新流（Revised-flow）的节点规范。

每个节点定义均包含：
- `type`: 节点类型标识 (28 种内置类型)
- `title` / `category`: UI 显示 (input/process/analysis/output/utility)
- `inputs` / `outputs`: 类型化端口 (25 种端口类型)
- `params`: 参数定义 (boolean/number/string/enum)
- `runtime`: step_id, executor, cacheable, previewable

### 5.7 插件系统 (`app/workflow/plugins.py`)

插件扫描路径:
1. `plugins/nodes/` (项目根)
2. sidecar 同级 `plugins/nodes/`
3. `TEXTFLOW_NODE_PLUGIN_DIR` 环境变量

```python
def register_nodes(builder):
    builder.register_definition(...)
    builder.register_executor(...)
    builder.register_compiler(...)
```

> 当前状态: Alpha — 本地 Python 插件扫描与注册已实现，无安全隔离。

### 5.8 支撑模块与辅助逻辑

| 模块 | 功能 |
|---|---|
| `app/workflow/runner.py` | 工作流运行入口，委托给 `run_project_workflow_native()` |
| `app/workflow/runtime/support.py` | 运行作用域标准化、文档过滤、运行记录构建 |
| `app/workflow/runtime/incremental.py` | 依赖索引、脏节点检测、增量状态更新 |
| `app/storage/run_diff.py` | 两次运行的工件计数/文件差异/指标对比 |

---

## 六、数据管理

### 6.1 项目持久化 (`app/storage/projects.py`, ~1500 行)

```
{LOCALAPPDATA}/TextFlow Studio/projects/
├── workspace.json                    # 工作区全局状态
└── {project-name}.tfproj/
    ├── project.json                  # 项目清单 (ProjectManifest)
    ├── project.db                    # 语料与较大运行产物
    ├── dictionaries/                 # 词表数据
    ├── runs/                         # 运行历史与工件
    ├── cache/                        # 节点缓存 (.pkl)
    └── exports/                      # 导出文件
```

**关键设计**:
- **脏段感知持久化**: `write_project_payload()` 仅写入变更段
- **SQLite 项目存储**: 新项目将 corpus rows 和 artifact payload 写入 `project.db`；旧 `metadata/corpus.json` 会在加载时迁移
- **字典增量存储**: 内置词表仅存储用户覆盖部分，自定义词表全量存储
- **导入/导出**: Zip 格式 of .tfproj 包，支持 ID 冲突处理

### 6.2 文件导入 (`app/ingestion/importers.py` 与 `app/ingestion/specs.py`)

支持格式: **CSV / XLSX / XLS / JSON / TXT**

- `map_record_fields()`: 别名感知字段映射 (大小写折叠 + Unicode 归一化)
- `build_raw_text()`: 可配置的多字段文本拼接
- `import_files()`: 完整导入流水线 (MD5 去重、验证、源文件追踪)

### 6.3 其他数据存储

| 模块 | 功能 |
|---|---|
| `app/storage/artifacts.py` | Gzip JSON 存储，预览 (前 50 行) / 完整载荷 |
| `app/storage/experiments.py` | 实验矩阵管理 (变体运行) |
| `app/storage/reviews.py` | 人工复核任务 (5 种类型: keyword_merge/institution_merge/cluster_rename/document_patch/dictionary_patch) |
| `app/storage/resources.py` | 语料视图管理 |
| `app/ingestion/specs.py` | 导入规范 CRUD |

---

## 七、字典系统

### 7.1 内置词表 (`builtin_dictionary_data.py`)

| 词表类型 | 来源 | 规模 | 默认状态 |
|---|---|---|---|
| 中文停用词 | stopwords-iso | 700+ | 启用 |
| 英文停用词 | stopwords-iso | 1200+ | 启用 |
| IT 术语 | THUOCL | 15K+ | 启用 |
| 金融术语 | THUOCL | - | 启用 |
| 医学术语 | THUOCL | 18K+ | 启用 |
| 成语短语 | THUOCL | - | 禁用 |
| 繁->简同义词 | OpenCC | - | 启用 |
| 拼写纠错 | misspell | 25K+ | 启用 |
| 历史人物 | THUOCL | - | 禁用 |
| 地名 | THUOCL | 40K+ | 禁用 |

### 7.2 词表结构

```
DictionarySet (项目级)
├── DictionaryCollection (按 kind 分组)
│   ├── DictionaryTableResource (命名/版本/可编辑)
│   │   └── DictionarySheet (行集合)
│   │       └── DictionaryEntry (source/target/tags/enabled/hit_count)
│   └── ...
└── 8 种 kind: stopwords / custom_lexicon / phrase_lexicon /
    synonym_map / near_synonym_map / standard_terms /
    exclusion_terms / regex_rules
```

---

## 八、报告与导出 (`app/reporting/core.py`, ~1000 行)

### 8.1 图表生成 (matplotlib/PNG)

| 图表 | 函数 | 说明 |
|---|---|---|
| 高频词柱状图 | `save_frequency_chart()` | Top N 词频 |
| 关键词柱状图 | `save_keyword_chart()` | 关键词排名 |
| 词云 | `save_wordcloud()` | matplotlib wordcloud |
| 机构-主题热力图 | `save_institution_topic_heatmap()` | 机构x主题矩阵 |
| 文档聚类散点图 | `save_cluster_chart()` | KMeans 聚类可视化 |

### 8.2 导出格式

- **CSV / XLSX**: 表格数据 (支持中文)
- **PNG**: 高 DPI 图表 (中文字体自适应)
- **HTML**: 自包含报告 (元数据卡片 + 结果表 + 嵌入图表 + 审计追踪)

---

## 九、示例项目系统

### 9.1 3 个内置 revised-flow 示例项目

首次空工作区加载时自动注入。样例从 WoS/IncoPat seed 预构建为已经导入的 `.tfproj` 项目，语料位于 `project.db`，打包模板不保留 raw seed。

| # | 名称 | Source profile | 核心功能 |
|---|---|---|---|
| 1 | WoS论文关键词与主题流程 | `wos` | 字段映射、主文本拼接、元数据标准化、关键词、主题、年份趋势、共现、导出 |
| 2 | IncoPat专利技术识别与图分析 | `incopat` | 专利元数据、claims 文本、图指标、社区、主路径、链接预测、技术识别 |
| 3 | 论文专利融合分析流程 | `wos + incopat` | 多来源融合、机构关键词/主题、跨来源统计、图谱与技术输出 |

### 9.2 Seed 与数据流水线

```
WoS/IncoPat seed (local/private or approved)
    ↓ sample_seed_sources.py 授权 gate
    ↓ bundled_sample_workspace.py
source profile 导入 -> project.db -> 预构建工作区模板
    ↓ 首次启动时恢复
```

Scopus 已有导入 profile 和测试夹具，但没有内置样例。

---

## 十、构建与部署

### 10.1 环境要求

| 工具 | 版本 | 用途 |
|---|---|---|
| Node.js | 24+ | 前端构建 |
| npm | 11+ | 包管理 |
| Python | 3.11+ | 引擎运行 |
| Rust/Cargo | 最新 | Tauri 编译 |

### 10.2 构建流水线

```powershell
# 1. 初始化环境
scripts/bootstrap-frontend.ps1      # npm install
scripts/bootstrap-python.ps1        # 创建 .venv, 安装引擎

# 2. 配置样例 seed (本地/私有构建)
$env:TEXTFLOW_SAMPLE_WOS_SOURCE = "C:\path\to\wos.xls"
$env:TEXTFLOW_SAMPLE_INCOPAT_SOURCE = "C:\path\to\incopat.xlsx"
$env:TEXTFLOW_ALLOW_RESTRICTED_SAMPLE_DATA = "1"

# 3. 构建 Python Sidecar
scripts/build-python-sidecar.ps1    # PyInstaller -> dist/textflow-engine/

# 4. 构建示例工作区模板
scripts/build-bundled-sample-workspace.ps1

# 5. 构建完整安装包
npm run tauri:build                 # -> NSIS 安装程序
```

**输出**: `apps/desktop/src-tauri/target/release/bundle/nsis/TextFlow Studio_0.2.0_x64-setup.exe`

### 10.3 测试分层

| 变更类型 | 测试命令 | 说明 |
|---|---|---|
| 前端/样式/文档 | `npm run test` | Vitest 前端测试 |
| 引擎逻辑 (非示例) | `npm run test:engine` | 快速 Python 引擎测试 |
| 示例项目/工作区/打包 | `npm run test:engine:full` | 完整测试套件 (含 `@pytest.mark.engine_full`) |
| 类型检查 | `npm run lint` | `tsc --noEmit` |

### 10.4 PowerShell 脚本一览

| 脚本 | 功能 |
|---|---|
| `bootstrap-frontend.ps1` | 初始化前端 (npm install) |
| `bootstrap-python.ps1` | 初始化 Python 环境 (.venv) |
| `build-python-sidecar.ps1` | PyInstaller 构建 sidecar |
| `build-bundled-sample-workspace.ps1` | 构建示例工作区模板 |
| `build-desktop-release.ps1` | 构建完整桌面发布包 |
| `test-engine.ps1` | 运行引擎测试 (fast/full) |
| `update-builtin-dictionaries.ps1` | 更新内置词表快照 |
| `run-large-benchmark.ps1` | 大规模基准测试 |

---

## 十一、测试覆盖

### 11.1 测试套件概览

- **25 个测试文件**, 覆盖引擎所有核心模块
- **两种标记**: 常规测试 + `@pytest.mark.engine_full` (重量级集成测试)
- **隔离工作区**: 每个测试通过 `monkeypatch` 获得临时工作区目录
- **会话级 fixture**: 公共数据缓存和预构建工作区仅构建一次

### 11.2 关键测试覆盖

| 测试文件 | 测试数 | 覆盖范围 |
|---|---|---|
| `test_workflow_runner.py` | 22 | 端到端工作流/导出/缓存/作用域/增量/并行 |
| `test_workspace_cli.py` | 23 | 项目 CRUD/工作区快照/导入导出/插件加载 |
| `test_sample_projects.py` | 14 | 3 个 revised-flow 示例规范/引导元数据/工作流覆盖/运行验证 |
| `test_ingestion.py` | 5 | CSV/JSON/TXT/XLSX 导入/字段映射/IncoPat 模板 |
| `test_modeling_nodes.py` | 3 | 主题建模/聚类评估/结果合并 |
| `test_node_catalog_parity.py` | 4 | **TS<->Python 节点定义一致性校验** |
| `test_control_flow_nodes.py` | 3 | 条件路由/结果门禁/人工复核门禁 |
| `test_comparison_nodes.py` | 4 | 词表选择/覆盖规则/分组比较/关键性分析 |
| `test_incremental_runtime.py` | 3 | 单文档失效/增量作用域/词典覆盖失效 |
| `test_sample_seed_sources.py` | 2 | WoS/IncoPat seed 授权 gate 与 restricted override |
| `test_review_store.py` | 3 | 关键词合并/词表回写/文档补丁 |
| `test_artifact_store.py` | 1 | 工件预览 (前 50 行) |
| `test_bundled_sample_workspace.py` | 3 | 元数据匹配/行限制拒绝/引导状态 |
| `test_experiment_store.py` | 1 | 实验矩阵变体运行 |
| `test_ingestion_specs.py` | 1 | 导入规范哈希持久化 |
| `test_main.py` | 2 | UTF-8 stdio/JSON 解析 |
| `test_project_resources.py` | 2 | 资源集合默认值/遗留项目回填 |
| `test_resource_store.py` | 1 | 语料视图过滤规范 |
| `test_run_diff.py` | 1 | 运行对比 |
| `test_service.py` | 1 | TaskManager 进度追踪 |

---

## 十二、依赖清单

### 12.1 前端依赖

| 包 | 版本 | 用途 |
|---|---|---|
| `react` | ^18.3.1 | UI 框架 |
| `react-dom` | ^18.3.1 | DOM 渲染 |
| `@fluentui/react-components` | ^9.73.8 | Fluent UI React v9 组件 |
| `@fluentui/react-icons` | ^2.0.326 | Fluent 图标 |
| `@tauri-apps/api` | 2.0.0 | Tauri IPC |
| `@textflow/shared-types` | 0.2.0 | 共享类型 |

### 12.2 前端开发依赖

| 包 | 版本 | 用途 |
|---|---|---|
| `vite` | ^5.4.11 | 构建工具 |
| `typescript` | ^5.7.2 | 类型系统 |
| `vitest` | ^2.1.8 | 测试框架 |
| `@testing-library/react` | - | 组件测试 |
| `@testing-library/jest-dom` | - | DOM 断言 |
| `@vitejs/plugin-react` | - | Vite React 插件 |
| `@tauri-apps/cli` | 2.0.0 | Tauri CLI |
| `jsdom` | - | 测试 DOM 环境 |

### 12.3 Python 引擎依赖

| 包 | 用途 |
|---|---|
| `jieba` | 中文分词 |
| `pandas` | 数据处理 |
| `numpy` | 数值计算 |
| `scikit-learn` | TF-IDF/KMeans/NMF |
| `yake` | 关键词提取 |
| `fastapi` | sidecar 本地 HTTP API |
| `uvicorn` | ASGI 服务运行时 |
| `matplotlib` | 图表生成 |
| `wordcloud` | 词云生成 |
| `openpyxl` | XLSX 读写 |
| `httpx` | FastAPI TestClient 支撑 (dev) |
| `pytest` | 测试框架 (dev) |
| `pyinstaller` | 打包工具 (build) |

---

## 十三、当前状态与已知差距

### 13.1 V1 完成度

**V1 全部 16 项必需功能已完成**:
项目管理 / 多格式导入 / 元数据映射 / 文本构建 / 清洗归一化 / 短语分词 / 词典中心 / 停用词同义词标准词排除处理 / 词频统计 / 词-文档/年关系 / 共现分析 / 基础聚类 / TF-IDF 特征词 / YAKE 关键词 / 关键词聚类 / 机构-关键词主题分析 / CSV/XLSX/PNG/HTML 导出 / 运行记录与日志

### 13.2 超出 V1 已交付的功能

- 工作流画布作为主入口
- 工作流定义纳入项目模型
- 原生 DAG 执行 + 并行调度
- 节点级缓存 (.pkl)
- 语料视图/工件记录/复核任务/实验规格
- 资源浏览器/节点产物弹窗/复核队列/实验矩阵/运行对比
- 本地 Python 插件节点
- 3 个 revised-flow 预构建示例项目

### 13.3 已知差距

| 差距 | 影响 |
|---|---|
| 无 CI/CD 流水线 | 回归依赖本地手动测试 |
| 前端测试不足 | 仅少量组件测试，无 E2E 测试 |
| 工作流画布 UX 待打磨 | 可用但不精致 |
| macOS 未验证 | 可移植性保留但未正式构建验证 |
| 插件节点无安全隔离 | 恶意插件可访问全进程 |
| 无自动化发布清单 | 发布流程依赖人工 |

---

## 十四、关键设计决策总结

| 决策 | 原因 |
|---|---|
| **仅工作流持久化** (无线性流水线) | 简化模型，为未来 DAG 编辑器铺路 |
| **Python Sidecar 处理所有计算** | 充分利用 jieba/sklearn/numpy 生态 |
| **节点级 .pkl 缓存** | 第二次运行显著加速，避免重复计算 |
| **字典增量存储** | 内置词表快照 + 仅存用户覆盖 = 小项目文件 |
| **预构建示例工作区** | 打包时构建，首次启动无生成开销 |
| **TS 类型直接源码导入** | 无编译步骤，path alias 直接引用 |
| **双模式桥接** (Tauri/浏览器) | 支持纯前端开发，无需后端 |
| **Windows 优先** | 主要目标平台，macOS 可移植性保留 |
| **无外部 UI 库** | 完全自定义控件，保持轻量与一致性 |
