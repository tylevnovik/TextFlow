# 架构说明

## 架构总览

TextFlow 当前采用典型的桌面端三层结构：

- 桌面壳：`Tauri 2`
- 前端：`React + TypeScript + Vite`
- 本地引擎：`Python sidecar/service`

前端不直接承担文本处理逻辑，所有项目持久化、语料导入、规则应用、分析和导出都由 Python sidecar 负责。Tauri 负责 sidecar 生命周期、本地命令桥接、文件选择与进度事件转发。

## 仓库布局

```text
apps/desktop/
  src/                       # React 页面、workflow 画布、状态层
  src-tauri/                 # Tauri 命令、sidecar 启动与 bundling

services/python-engine/
  app/                       # Python sidecar app package
  app/analysis/              # 文本处理、统计、关键词、主题、图和技术指标算法
  app/api/                   # FastAPI sidecar service 与 action dispatcher
  app/domain/                # project/dictionary/workflow/result 领域 helper
  app/ingestion/             # 语料导入器与导入规范
  app/reporting/             # HTML、图表和运行输出报告
  app/samples/               # 内置样例、seed 发现和打包样例工作区
  app/storage/               # workspace、project、SQLite、artifact、resource、review、experiment 存储
  app/workflow/              # workflow definitions、registry、compiler、executors、runtime、plugin boundary
  app/workflow/nodes/        # 可扫描的内置节点模块
  tests/                     # Python 测试
  benchmarks/                # 大语料 benchmark

packages/shared-types/
  src/index.ts               # 共享领域模型

plugins/nodes/
  *.py                       # 本地纯 Python 插件节点

textflow.config.json         # 产品名、identifier、发布版本等仓库级配置入口
```

Python engine 当前仍处在从平铺模块向分层包结构迁移的阶段。2026-05-24 起，`domain/defaults.py` 已收敛为兼容聚合入口，领域实现分散到 `domain/common.py`、`domain/dictionary.py`、`domain/import_profiles.py`、`domain/runtime_profile.py`、`domain/workflow.py`、`domain/results.py` 和 `domain/project.py`；`storage/projects.py` 也开始把 workspace、template、dictionary serialization 和 project package 职责外移。最终模块边界、迁移顺序和性能评估见 [Python Engine 模块边界 ADR](./adr/2026-05-23-python-engine-module-boundaries.md)，本轮执行计划见 [2026-05-24 Python Engine Boundary Refactor](./plans/2026-05-24-python-engine-boundary-refactor.md)。

## 仓库级配置入口

`textflow.config.json` 是产品发布元数据的唯一人工修改入口。当前包含：

- `product.name`
- `product.identifier`
- `product.version`
- `engine.serviceTitle`

由于 npm、Tauri、Cargo 和 Python packaging 都要求各自的 manifest 中存在版本字段，仓库用 `scripts/sync-project-config.mjs` 将根配置同步到这些 manifest，并用 `npm run config:check` 做漂移校验。桌面 release 脚本会先运行该校验；开发者修改版本时应先改 `textflow.config.json`，再运行 `npm run config:sync`。

## 运行时数据流

### 1. 桌面端启动

- Tauri 启动时尝试拉起 Python sidecar。
- 开发环境优先使用虚拟环境或本地 `dist/textflow-engine`。
- 打包环境使用随资源一起分发的 sidecar 目录。

### 2. 前端发起动作

前端通过 `desktopBridge` 调用 Tauri command，常见动作包括：

- `load_workspace`
- `create_project`
- `open_project`
- `import_project_files`
- `run_workflow`
- `export_project`

### 3. Tauri 与 sidecar 通信

Tauri 不直接嵌入 Python 逻辑，而是通过 sidecar 暴露的本地 FastAPI 任务接口通信：

- `GET /health`
- `POST /tasks/start`
- `GET /tasks/<task_id>`
- `POST /shutdown`

### 4. 任务与进度

- sidecar 由 FastAPI/Uvicorn 提供本地 HTTP 外壳，任务管理器当前使用单 worker 顺序执行。
- 单次 workflow run 内部已支持同层就绪、parallel-safe 节点的并发执行。
- Tauri 轮询任务状态并向前端发出 `engine-progress` 事件。
- 前端会把 stage、当前节点、完成度和摘要映射到顶部进度条。

## 用户工作区与项目存储

### 工作区根目录

默认情况下：

- Windows：`%LOCALAPPDATA%/TextFlow Studio`
- macOS：`~/Library/Application Support/TextFlow Studio`
- Linux：`$XDG_DATA_HOME/textflow-studio` 或 `~/.local/share/textflow-studio`

开发和 benchmark 场景下可通过 `TEXTFLOW_WORKSPACE_ROOT` 覆盖。

### 工作区结构

```text
<workspace-root>/
  projects/
    workspace.json
    <project>.tfproj/
  templates/
    project_templates/
    import_templates/
  data/
```

`workspace.json` 负责记录：

- `current_project_id`
- `recent_project_ids`
- `bootstrap_completed`

### 项目目录结构

```text
<project>.tfproj/
  project.json
  project.db
  corpus/
    imported/
  dictionaries/
  metadata/
    corpus.json
  runs/
    <run-id>/
      params_snapshot.json
      logs.json
      logs.txt
      corpus_snapshot.json
      outputs/
      charts/
      report/
  cache/
    nodes/
  exports/
```

`project.json` 保存项目元数据、词表、workflow、运行历史和轻量索引。`project.db` 保存导入后的语料行和较大的 run artifact payload；`metadata/corpus.json` 仅作为旧项目迁移入口保留，加载旧项目时会迁移到 SQLite。

## 核心领域模型

### ProjectManifest

当前项目模型的关键字段包括：

- `source_files`
- `corpus_resources`
- `corpus_views`
- `ingestion_specs`
- `artifact_records`
- `review_tasks`
- `experiment_specs`
- `import_template`
- `dictionary_set`
- `workflow_definitions`
- `active_workflow_id`
- `run_history`
- `results`

其中：

- `workflow_definitions` 是当前编辑与持久化真相
- `run_history` 是运行记录真相
- `results` 是项目级最新结果快照
- `artifact_records` 是 project-local SQLite artifact store 的可懒加载索引
- `corpus_views / ingestion_specs / review_tasks / experiment_specs` 是产品 surface 的可复现状态，不属于临时 UI 状态

### DictionarySet

词表当前采用双视图结构：

- `collections`
  面向 UI 的分类与资源表结构
- `sheets`
  面向运行时的扁平可执行视图

项目文件不会完整保存所有内置词表条目，而是以“内置快照 + 稀疏覆盖”方式落盘，减小项目体积。

## 导入与分析引擎

### 导入层

- 支持 `txt/csv/xlsx/xls/json`
- 基于 source profile 和 import template 做字段映射
- 支持多字段拼接主文本
- 普通用户导入会把源文件复制进项目目录；打包内置样例只保留 source audit 元数据，不保留 raw seed 文件

### 分析层

当前主链包括：

- 清洗
- 标准化
- 切词
- 词表规则应用
- 过滤
- 统计分析与挖掘
- 导出

当前分析算法/组件：

- `jieba`
- `TF-IDF`
- `YAKE`
- `KMeans`
- `NMF`
- `matplotlib`
- `wordcloud`

## workflow 与运行层

当前 architecture 的关键决定是：

> workflow graph 是唯一真相，执行层统一走 native DAG。

详细规则见 [工作流与运行时](./workflow-runtime.md)。

## 插件节点架构

节点注册分为两层，但入口形状保持一致：

- 内置节点：`services/python-engine/app/workflow/nodes/*.py`
- 外部插件节点：仓库根目录 `plugins/nodes`、打包 sidecar 同级 `plugins/nodes`、`TEXTFLOW_NODE_PLUGIN_DIR`

内置节点模块可以暴露：

- `node_definition(runtime_profile?)`
- `node_definitions(runtime_profile?)`
- `register_nodes(builder, runtime_profile?)`
- `register(builder, runtime_profile?)`

每个内置节点文件应同时拥有节点级 definition、compiler、executor 和注册函数。节点可以调用 `analysis`、`storage`、`reporting` 或 `workflow/executors/support.py` 里的共享算法/工具，但不应再要求开发者为了修改同一个节点而同时改 `definitions/builtin.py`、`compilers.py` 和 `executors/__init__.py`。

外部插件节点继续使用同样的 `register_nodes` / `register` 入口。registry 会先扫描内置节点目录，再加载外部插件；旧的 `workflow/definitions/builtin.py` 仅作为 catalog 兼容入口保留，其内容来自这些目录模块。所有内置节点都已经迁移到 `app/workflow/nodes`，旧的全局 compiler/executor map 不再参与节点注册。

节点可以注册：

- node definition
- compiler hook
- executor hook
- artifact output port declaration

前端当前优先读取 sidecar 返回的 `node_definitions`，因此插件节点可以进入工具箱和 schema 驱动表单。插件输出口若声明 `artifact_kind`，native DAG 会把该输出写入项目 artifact store，并把 handle 写回 `run_record.artifacts` 和 `manifest.artifact_records`。

## 打包策略

### Python sidecar

- 通过 `PyInstaller --onedir` 打包
- 随安装包一起分发
- 不依赖用户自装 Python
- 同时把内置词表源文件一并打进 sidecar 资源

### Desktop installer

- Tauri bundling 目标当前为 `NSIS`
- `beforeBuildCommand` 会先执行 `scripts/build-desktop-release.ps1`
- 安装包资源中会带上 `services/python-engine/dist/textflow-engine`

## 当前架构边界

- front-end 仍偏单仓库组件式组织，页面与复杂 workflow UI 代码还比较集中。
- sidecar 当前仍是单任务 worker，不支持多任务并行。
- native DAG 已成为唯一运行主链，并支持同层就绪节点的保守并行调度。
- 当前已有项目内 artifact record 索引和懒加载 preview，但还没有跨项目 artifact registry、面向用户的完整局部重跑和多项目协同设计。

这些边界并不阻碍当前主链可用，但决定了后续收敛工作的重点。
