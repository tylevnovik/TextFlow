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
  app/                       # 项目存储、导入、pipeline、DAG、导出、插件
  tests/                     # Python 测试
  benchmarks/                # 大语料 benchmark

packages/shared-types/
  src/index.ts               # 共享领域模型

plugins/nodes/
  *.py                       # 本地纯 Python 插件节点
```

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
- `run_pipeline`
- `export_project`

### 3. Tauri 与 sidecar 通信

Tauri 不直接嵌入 Python 逻辑，而是通过 sidecar 暴露的本地 HTTP 任务接口通信：

- `GET /health`
- `POST /tasks/start`
- `GET /tasks/<task_id>`

### 4. 任务与进度

- sidecar 任务管理器当前使用单 worker 顺序执行。
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
  corpus/
    imported/
  dictionaries/
  pipelines/
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

## 核心领域模型

### ProjectManifest

当前项目模型的关键字段包括：

- `source_files`
- `import_template`
- `dictionary_set`
- `pipeline`
- `workflow_definitions`
- `active_workflow_id`
- `run_history`
- `results`

其中：

- `workflow_definitions` 是当前编辑层的主模型
- `pipeline` 是兼容快照和 bridge 执行输入
- `run_history` 是运行记录真相
- `results` 是项目级最新结果快照

### DictionarySet

词表当前采用双视图结构：

- `collections`
  面向 UI 的分类与资源表结构
- `sheets`
  面向运行时的扁平可执行视图

项目文件不会完整保存所有内置词表条目，而是以“内置快照 + 稀疏覆盖”方式落盘，减小项目体积。

## 导入与分析引擎

### 导入层

- 支持 `txt/csv/xlsx/json`
- 基于 source profile 和 import template 做字段映射
- 支持多字段拼接主文本
- 会把导入源文件复制进项目目录

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

## workflow 与兼容层

当前 architecture 的关键决定不是“用不用 workflow”，而是：

> workflow 已经进入项目真相层，但执行层同时保留 native DAG 和兼容 pipeline 两条路径。

详细规则见 [工作流与运行时](./workflow-runtime.md)。

## 插件节点架构

sidecar 启动时会扫描：

- 仓库根目录 `plugins/nodes`
- 打包 sidecar 同级 `plugins/nodes`
- `TEXTFLOW_NODE_PLUGIN_DIR`

插件可以注册：

- node definition
- compiler hook
- executor hook

前端当前优先读取 sidecar 返回的 `node_definitions`，因此插件节点可以进入工具箱和 schema 驱动表单。

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
- native DAG 已进入主链，但并没有完全替换掉兼容 pipeline。
- 当前还没有 artifact registry、完整的局部重跑和多项目协同设计。

这些边界并不阻碍当前主链可用，但决定了后续收敛工作的重点。
