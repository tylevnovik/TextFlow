# TextFlow Studio — 完整技术说明文档

> 自动生成于 2026-04-29

## 一、项目概述

**TextFlow Studio** 是一款**桌面优先的本地文本预处理与基础文本挖掘工具**，面向科研文献分析、舆情分析、内容分析、语料整理等场景。

| 属性 | 值 |
|---|---|
| 项目名称 | `textflow-studio` |
| 当前版本 | `0.1.1` |
| 许可证 | 私有 |
| 仓库地址 | https://github.com/tylevnovik/TextFlow |
| 目标平台 | Windows (主), macOS (可移植, 未正式验证) |
| 一句话定位 | 文本整理与基础分析工具，按项目保存数据、词表和结果 |

---

## 二、技术架构

### 2.1 三层桌面架构

```
┌─────────────────────────────────────────────────────────┐
│                   用户界面层 (Frontend)                    │
│     Tauri 2 Shell (Rust) + React 18 + TypeScript + Vite  │
│     • 8 个页面: 首页/项目/导入/词表/工作流/分析/结果/设置     │
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
│   ├── app/                  #   核心引擎逻辑 (~20 个模块)
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
| CSS | 原生 | 样式 (~58KB, 无 UI 框架) |

无外部 UI 组件库，所有组件 (Panel, StatCard, Table, PaginatedTable 等) 均在 `ui.tsx` 中自建。

### 3.2 页面导航 (8 页)

| 页面 ID | 标题 | 功能描述 |
|---|---|---|
| `home` | 开始 | 项目选择、创建、首页仪表板 |
| `project` | 项目概览 | 项目统计、源文件、运行历史、复核任务、实验 |
| `data` | 导入资料 | 文件导入、字段映射、语料管理、导入规范 |
| `dictionaries` | 词表规则 | 管理 8 类词表: 停用词/自定义/短语/同义/近义/标准/排除/正则 |
| `workflow` | 处理与分析 | **主入口** — 可视化 DAG 工作流编辑器 |
| `analysis` | 分析详情 | 词频表/共现/关键词/主题/聚类/散点图 |
| `results` | 结果导出 | 运行历史/运行对比/工件浏览器/实验矩阵/导出控制 |
| `settings` | 设置 | UI 缩放/语言/主题/项目路径 |

### 3.3 工作流画布

工作流页面采用独立的深色主题布局:
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
| `load_artifact_preview` / `list_run_artifacts` | 工件浏览 |
| `open_path` / `reveal_path` | 系统文件管理器集成 |

---

## 四、共享类型包 (`packages/shared-types/`)

`src/index.ts` 是**前后端共享的唯一类型真相来源**，约 895 行，导出 ~80 个类型/接口。

### 4.1 核心类型分类

| 分类 | 关键类型 | 说明 |
|---|---|---|
| **数据源** | `SourceProfile` (6 种) | generic/literature/wos/patent/incopat/business |
| **工作流** | `BuiltinWorkflowNodeType` (28 种) | 语料输入/词典/清洗/分词/分析/导出/工具 |
| **端口类型** | `WorkflowPortType` (25 种) | CorpusResource/CleanCorpus/FrequencyTable 等 |
| **运行状态** | `RunStatus` | idle/running/completed/failed/cancelled |
| **字典类型** | `DictionaryKind` (8 种) | stopwords/synonym/standard_terms 等 |
| **导出格式** | `ExportFormat` | csv/xlsx/png/html |
| **页面** | `PageId` (9 个) | home/project/data/workflow/dictionaries/analysis/results/report/settings |

### 4.2 核心接口

- **项目模型**: `ProjectManifest` — 根项目结构 (.tfproj)，包含所有子资源
- **语料文档**: `CorpusItem` — 单文档，含 raw_text/clean_text/tokens/filtered_tokens + 元数据
- **词表系统**: `DictionarySet` -> `DictionaryCollection` -> `DictionarySheet` -> `DictionaryEntry`
- **工作流图**: `WorkflowDefinition` -> `WorkflowNodeInstance` + `WorkflowEdge` + `WorkflowGroup`
- **运行记录**: `RunRecord` — 运行 ID、时间戳、状态、日志、工件、节点摘要
- **分析结果**: 11 种行类型 (FrequencyRow/TermDocumentRow/CooccurrenceRow/KeywordRow 等)

### 4.3 预置导入模板

为 6 种数据源预定义了字段映射模板:
- **通用 (generic)**: 自动匹配
- **文献 (literature)**: 标准学术字段
- **WOS**: Web of Science 字段码 (UT/TI/AB/PY/SO/AU/C1/DE/WC)
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
    └── service.py (ThreadingHTTPServer, port 8765)
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

#### 文本操作 (`text_ops.py`, ~510 行)

| 功能 | 函数 | 说明 |
|---|---|---|
| 清洗 | `apply_cleaning()` | HTML/URL/邮箱/电话/表情剥离; 空白/标点/全半角/大小写标准化 |
| 归一化 | `apply_normalization()` | 繁->简中文; 数字/时间标准化; 正则规则; 审计追踪 |
| 短语保护 | `protect_phrases()` | 分词前保护领域短语不被切碎 |
| 分词 | `tokenize_text()` | jieba 中英文混合分词 + 短语保持 |
| 词典应用 | `apply_dictionary()` | 标准词->同义词->近义词->停用词->排除词 流水线 |
| 过滤 | `filter_token_lists()` | 最小长度/数字过滤/词频过滤 |

#### 分析操作 (`analysis_ops.py`, ~923 行)

| 分析类型 | 函数 | 算法/库 |
|---|---|---|
| 词频统计 | `frequency_table()` | TF/DF/ratio/词长/年份 |
| 词-文档关系 | `term_document_table()` | 交叉表 |
| 词-年份关系 | `term_year_table()` | 时间序列交叉表 |
| 共现分析 | `cooccurrence_table()` | 滑动窗口共现 |
| 关键词提取 | `yake_keyword_rows()` | YAKE (并行 ProcessPoolExecutor) |
| TF-IDF 特征词 | `tfidf_feature_bundle()` | sklearn TfidfVectorizer |
| 主题建模 | `nmf_topic_model()` | sklearn NMF |
| 关键词聚类 | `keyword_clusters()` | MiniBatchKMeans |
| 文档聚类 | `document_clusters()` | KMeans + 2D 坐标 |
| 机构-关键词 | `institution_keyword_and_topic()` | 共现分析 |
| 聚类评估 | `cluster_evaluation_rows()` | 轮廓系数 / Davies-Bouldin 指数 |

#### 配置与工作流定义 (`defaults.py`, ~1443 行)

- 8 种字典类型、6 种导入配置文件
- `default_workflow_definition()`: 构建完整 DAG (20+ 节点, 类型化端口连接)
- `workflow_payload_hash()`: SHA256 哈希，忽略 UI-only 变更 (位置/标签/折叠状态)
- `compile_runtime_profile_from_workflow()`: 从 DAG 编译运行时配置
- `default_project_manifest()`: 创建含设置/路径/词表/工作流定义的项目

### 5.4 DAG 执行引擎 (`dag_runtime.py`, ~1434 行)

```
WorkflowExecutionContext (线程安全, RLock)
    │
    ├── _topological_active_node_batches()  ->  拓扑排序 -> 并行执行批次
    │
    ├── 对每个批次:
    │   ├── _prepare_node_execution()       ->  从上游输出解析输入
    │   ├── _execute_prepared_node()        ->  执行函数 / 返回缓存
    │   └── _record_completed_node()        ->  更新状态 / 同步语料
    │
    └── 节点缓存: pickle + SHA256 缓存键
```

**关键特性**:
- **并行安全调度**: 同一批次内的节点可并行执行
- **节点级缓存**: `.pkl` 文件缓存，SHA256 缓存键，第二次运行显著加速
- **增量处理**: 支持脏节点检测与局部重算
- **进度推送**: 每个节点完成时推送增量进度到前端

### 5.5 节点执行器 (`node_executors.py`, ~1563 行, 35 个执行函数)

| 类别 | 执行器 |
|---|---|
| **输入** | `execute_corpus_input`, `execute_dictionary_input`, `execute_merge_corpora` |
| **处理** | `execute_clean_text`, `execute_normalize_text`, `execute_tokenize`, `execute_apply_dictionary_rules`, `execute_filter_terms` |
| **数据操作** | `execute_filter_by_metadata`, `execute_deduplicate_documents`, `execute_sample_corpus`, `execute_split_corpus`, `execute_bucket_by_time` |
| **控制流** | `execute_conditional_router`, `execute_result_gate`, `execute_manual_review_gate` |
| **字典** | `execute_select_dictionary_tables`, `execute_overlay_dictionary_rules` |
| **分析** | `execute_frequency_statistics`, `execute_term_document_analysis`, `execute_term_year_analysis`, `execute_cooccurrence_analysis`, `execute_group_compare`, `execute_keyness_analysis`, `execute_topic_modeling`, `execute_cluster_evaluation`, `execute_join_results`, `execute_feature_term_selection`, `execute_keyword_extraction`, `execute_keyword_clustering`, `execute_institution_keyword_analysis`, `execute_institution_topic_analysis`, `execute_document_clustering` |
| **导出** | `execute_save_csv`, `execute_save_xlsx`, `execute_save_png`, `execute_save_html_report` |
| **遗留** | `execute_legacy_analyze_corpus`, `execute_legacy_export_results` |

### 5.6 节点定义 (`node_definitions.py`, ~1093 行, 40+ 节点定义)

每个节点定义包含:
- `type`: 节点类型标识 (28 种内置类型)
- `title` / `category`: UI 显示 (input/process/analysis/output/utility/legacy)
- `inputs` / `outputs`: 类型化端口 (25 种端口类型)
- `params`: 参数定义 (boolean/number/string/enum)
- `runtime`: step_id, executor, cacheable, previewable

### 5.7 插件系统 (`node_plugins.py`)

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

### 5.8 支撑模块

| 模块 | 功能 |
|---|---|
| `workflow_runner.py` | 工作流运行入口，委托给 `run_project_workflow_native()` |
| `runtime_support.py` | 运行作用域标准化、文档过滤、运行记录构建 |
| `incremental_runtime.py` | 依赖索引、脏节点检测、增量状态更新 |
| `run_diff.py` | 两次运行的工件计数/文件差异/指标对比 |

---

## 六、数据管理

### 6.1 项目持久化 (`project_store.py`, ~1506 行)

```
{LOCALAPPDATA}/TextFlow Studio/projects/
├── workspace.json                    # 工作区全局状态
└── {project-name}.tfproj/
    ├── project.json                  # 项目清单 (ProjectManifest)
    ├── metadata/corpus.json          # 语料数据
    ├── dictionaries/                 # 词表数据
    ├── runs/                         # 运行历史与工件
    ├── cache/                        # 节点缓存 (.pkl)
    └── exports/                      # 导出文件
```

**关键设计**:
- **脏段感知持久化**: `write_project_payload()` 仅写入变更段
- **字典增量存储**: 内置词表仅存储用户覆盖部分，自定义词表全量存储
- **导入/导出**: Zip 格式的 .tfproj 包，支持 ID 冲突处理

### 6.2 文件导入 (`ingestion.py`, ~445 行)

支持格式: **CSV / XLSX / JSON / TXT**

- `map_record_fields()`: 别名感知字段映射 (大小写折叠 + Unicode 归一化)
- `build_raw_text()`: 可配置的多字段文本拼接
- `import_files()`: 完整导入流水线 (MD5 去重、验证、源文件追踪)

### 6.3 其他数据存储

| 模块 | 功能 |
|---|---|
| `artifact_store.py` | Gzip JSON 存储，预览 (前 50 行) / 完整载荷 |
| `experiment_store.py` | 实验矩阵管理 (变体运行) |
| `review_store.py` | 人工复核任务 (5 种类型: keyword_merge/institution_merge/cluster_rename/document_patch/dictionary_patch) |
| `resource_store.py` | 语料视图管理 |
| `ingestion_specs.py` | 导入规范 CRUD |

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

## 八、报告与导出 (`reporting.py`, ~1027 行)

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

### 9.1 9 个内置示例项目

首次空工作区加载时自动注入，基于**真实公开数据** (非模拟)。

| # | 名称 | 数据源 | 核心功能 | 规模 |
|---|---|---|---|---|
| 1 | 基础文本预处理 | Wikipedia | 清洗/归一化/分词/词频 | 20K 行 |
| 2 | 词表治理与词频统计 | UN 并行语料 | 词典覆盖/同义词/停用词 | 10K 行 |
| 3 | 学术摘要关键词与主题 | OpenAlex | 关键词提取/主题建模/文档聚类 | 10K 行 |
| 4 | 机构主题与技术方向 | OpenAlex | 机构-关键词/主题分析 | 10K 行 |
| 5 | 复核实验与增量运行 | UN 并行语料 | 复核任务/实验矩阵/增量运行 | 10K 行 |
| 6 | 多来源语料合并与抽样 | Wiki + OpenAlex | 多格式合并/去重/抽样 | 10K 行 |
| 7 | 分组比较与关键性分析 | OpenAlex | 分组词频比较/显著性分析 | 10K 行 |
| 8 | 切分评估与结果拼接 | Wikipedia | 训练/测试拆分/聚类评估 | 10K 行 |
| 9 | 条件路由与人工门禁 | UN + OpenAlex | 条件路由/指标门禁/人工复核 | 10K 行 |

**数据特性**: 严格 1:1 英中比例，最低 10,000 文档，来源于 Wikimedia/UN/OpenAlex 真实数据。

### 9.2 数据流水线

```
外部 API (Wikipedia/UN/OpenAlex)
    ↓ fetch-public-sample-data.ps1
public_sample_cache/ (gzip JSONL)
    ↓ sample_dataset_cache.py
语言均衡采样 -> 短语交错 -> 种子文件 (CSV/XLSX/JSON/TXT)
    ↓ bundled_sample_workspace.py
预构建工作区模板 -> 首次启动时恢复
```

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

# 2. 刷新公共数据缓存 (可选)
scripts/fetch-public-sample-data.ps1 -All

# 3. 构建 Python Sidecar
scripts/build-python-sidecar.ps1    # PyInstaller -> dist/textflow-engine/

# 4. 构建示例工作区模板
scripts/build-bundled-sample-workspace.ps1

# 5. 构建完整安装包
npm run tauri:build                 # -> NSIS 安装程序
```

**输出**: `apps/desktop/src-tauri/target/release/bundle/nsis/TextFlow Studio_0.1.1_x64-setup.exe`

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
| `fetch-public-sample-data.ps1` | 拉取公共数据集 |
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
| `test_sample_projects.py` | 14 | 9 个示例规范/引导元数据/工作流覆盖/运行验证 |
| `test_ingestion.py` | 5 | CSV/JSON/TXT/XLSX 导入/字段映射/IncoPat 模板 |
| `test_modeling_nodes.py` | 3 | 主题建模/聚类评估/结果合并 |
| `test_node_catalog_parity.py` | 4 | **TS<->Python 节点定义一致性校验** |
| `test_control_flow_nodes.py` | 3 | 条件路由/结果门禁/人工复核门禁 |
| `test_comparison_nodes.py` | 4 | 词表选择/覆盖规则/分组比较/关键性分析 |
| `test_incremental_runtime.py` | 3 | 单文档失效/增量作用域/词典覆盖失效 |
| `test_public_sample_data_builder.py` | 5 | OpenAlex/Wikipedia/UN TEI 解析与标准化 |
| `test_sample_dataset_cache.py` | 4 | 缓存读写/语言均衡加载/缺失缓存/奇数拒绝 |
| `test_sample_dataset_sources.py` | 5 | 源注册表/语言支持/行标准化/缺失字段拒绝 |
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
| `@tauri-apps/api` | 2.0.0 | Tauri IPC |
| `@textflow/shared-types` | 0.1.1 | 共享类型 |

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
| `matplotlib` | 图表生成 |
| `wordcloud` | 词云生成 |
| `openpyxl` | XLSX 读写 |
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
- 资源浏览器/工件浏览器/复核队列/实验矩阵/运行对比
- 本地 Python 插件节点
- 9 个预构建示例项目

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
