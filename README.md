# TextFlow Studio

TextFlow Studio 是一个桌面优先的本地文本预处理与基础文本挖掘工具，面向研究、舆情、内容分析和语料整理场景。项目当前采用 `Tauri + React + TypeScript + Python` 架构，目标是提供一个安装即用、项目化、可复跑、可审计的桌面工作台。

当前仓库已经不是空骨架，而是具备可运行的桌面端、Python sidecar、词表中心、workflow 画布、分析导出、官方场景样例和自动化测试基线的开发中版本。

## 项目目标

- 稳定可交付优先于炫技功能
- 以项目为中心组织语料、词表、流程和输出
- 让文本预处理流程可复跑、可审计、可回看
- 保持 Windows 首发可交付，同时兼顾 macOS 可移植性
- 为后续更强的节点式流程编辑器预留架构空间

## 当前能力

### 项目与数据

- 工作区与 `.tfproj` 项目目录管理
- 项目创建、打开、复制、删除、项目包导入导出
- `txt/csv/xlsx/xls/json` 导入
- `source profile`、字段映射、主文本拼接
- 文档搜索、预览、编辑、删除
- 首次启动从安装包内置模板恢复 3 个后端构建的 revised-flow 示例项目

### 文本处理

- 清洗、标准化、切词、词表规则、过滤
- 自定义词典、短语词典、停用词、同义词、标准词、排除词
- 内置词表快照与项目级自定义词表资源

### 分析与输出

- 词频、词文档、词年份、共现
- TF-IDF 特征词
- YAKE 关键词
- 关键词聚类、文档聚类
- 机构关键词、机构主题
- CSV / XLSX / PNG / HTML 导出
- 运行历史、参数快照、日志、审计表
- 项目概览只展示最近运行摘要，完整运行历史放在结果页；节点产物预览直接从工作流节点弹窗查看

### workflow 与运行时

- workflow 画布已成为主流程入口
- 节点注册表与 schema 驱动前后端同步
- workflow-only native DAG 执行主链
- 同层就绪的 parallel-safe 分析/导出节点会并行执行
- 运行时会从 workflow 派生只读 `runtime_profile`
- 节点级缓存与节点级运行摘要
- 增量进度回传、最终全量状态同步与轻量 `corpus_snapshot`
- 项目保存支持按脏区写盘与 unchanged JSON 跳过写入
- 本地纯 Python 插件节点加载
- 语料资源、语料视图、导入规格、运行产物、复核队列和实验矩阵已进入桌面 UI
- 节点输出可写入 project-local SQLite artifact store，并可从已运行节点按需加载 preview

## 当前状态

- 版本：`0.2.0`
- 当前阶段：开发中，已可运行，但仍在持续收敛交付质量
- 已验证：
  - `npm run test --workspace apps/desktop`
  - `npm run lint`
  - `npm run test:engine`
  - `npm run test:engine:full`
  - `powershell -ExecutionPolicy Bypass -File .\scripts\build-python-sidecar.ps1`
  - `npm run tauri:build --workspace apps/desktop`

最新对外版本：

- [GitHub Release v0.2.0](https://github.com/tylevnovik/TextFlow/releases/tag/v0.2.0)

## 技术栈

- Desktop shell: `Tauri 2`
- Frontend: `React 18 + TypeScript + Vite`
- Engine: `Python 3.11+`
- Analysis libs: `jieba`, `pandas`, `scikit-learn`, `matplotlib`, `wordcloud`, `yake`
- Packaging:
  - Python sidecar via `PyInstaller`
  - Windows installer via `NSIS`

## 仓库结构

```text
TextFlow/
  apps/desktop/              # Tauri + React 桌面端
  services/python-engine/    # Python sidecar、分析引擎、benchmark、测试
  packages/shared-types/     # 前后端共享领域类型
  plugins/nodes/             # 本地纯 Python 节点插件
  docs/                      # 当前有效文档
  docs/archive/              # 历史方案、旧规格、旧计划
  scripts/                   # 引导、测试、打包、词表更新脚本
  sample_seed_sources/       # 本地样例数据种子源（如 wos、incopat 样本数据）
```

## 快速开始

### 环境要求

- Node.js `24+`
- npm `11+`
- Python `3.11+`
- Rust / Cargo

### 初始化

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap-python.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap-frontend.ps1
```

### 本地开发

- **网页端（浏览器模式开发）**：
  ```powershell
  npm run dev
  ```
- **桌面客户端（Tauri 调试模式开发）**：
  ```powershell
  npm run tauri:dev --workspace apps/desktop
  ```

### 常用验证命令

```powershell
npm run lint
npm run test:engine
npm run test:engine:full
```

### 构建 sidecar

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-python-sidecar.ps1
```

### 构建 Windows 安装包

```powershell
npm run tauri:build --workspace apps/desktop
```

`tauri:build` 会自动执行 `beforeBuildCommand` 中配置的 `scripts/build-desktop-release-local-samples.ps1`，该脚本利用本地的样例数据种子（位于 `sample_seed_sources` 目录下）重新构建 Python sidecar 并打入安装包，然后再产出 NSIS 安装包。

## Built-In Scenario Samples

On first launch, TextFlow restores a prebuilt bundled sample workspace that contains three backend-built revised-flow sample projects: WoS paper keyword/topic analysis, IncoPat patent technology graph analysis, and an integrated paper-patent map. Sample corpus rows are stored in each `.tfproj/project.db`, and packaged samples do not retain raw seed files.

See `docs/examples.md`.

## 当前文档

- [文档索引](./docs/README.md)
- [当前现状](./docs/current-status.md)
- [产品范围与完成度](./docs/product-scope.md)
- [架构说明](./docs/architecture.md)
- [工作流与运行时](./docs/workflow-runtime.md)
- [开发与构建说明](./docs/development.md)
- [内置场景样例](./docs/examples.md)
- [大规模压测记录](./docs/benchmark.md)
- [技术全景与架构设计](./docs/technical-overview.md)
- [样例项目内置与管理](./docs/sample-projects.md)
- [节点 Catalog 规范定义](./docs/node-catalog-schema.md)
- [架构决策记录 (ADR)](./docs/adr/)
- [插件节点说明](./plugins/nodes/README.md)
- [发布记录](./CHANGELOG.md)
- [历史方案与旧文档归档](./docs/archive/README.md)

## 已知仍需继续收敛的部分

- **工作台与画布体验**：workflow 画布虽然可用，但仍然偏工程态，距离“稳定交付给终端用户”的产品化体验还有一定差距。
- **质量保障**：虽然已配置 GitHub Actions CI 工作流，但前端仍缺少系统化的 E2E 自动化测试覆盖，需要进一步补齐前端测试用例。
- **native DAG 调度与产物管理**：目前仍缺少更细粒度的 ready-queue 调度、面向用户的局部重跑支持、跨项目 artifact registry，以及更完整的 dirty 传播可视化。
- **插件节点安全性**：本地纯 Python 插件节点尚未进行签名、隔离与安全边界设计，目前仅适合开发态本地扩展。
- **多平台验证**：虽然 Windows 安装链路已通过本地手动打包及 GitHub Actions Release 自动构建流配置，但依然缺少成体系的 macOS 构建与运行验证。
- **大项目性能表现**：超大项目的冷启动、大语料导出、结果页首屏以及大文件 snapshot 写盘 I/O 仍有较大的持续优化空间。
