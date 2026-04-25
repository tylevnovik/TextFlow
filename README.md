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
- `txt/csv/xlsx/json` 导入
- `source profile`、字段映射、主文本拼接
- 文档搜索、预览、编辑、删除
- 首次启动自动生成 9 个后端构建的真实公开数据场景示例项目

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
- 项目概览只展示最近运行摘要，完整运行历史与产物预览放在结果页按需查看

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
- 节点输出可写入 artifact store，结果页支持按需加载 artifact preview

## 当前状态

- 版本：`0.1.1`
- 当前阶段：开发中，已可运行，但仍在持续收敛交付质量
- 已验证：
  - `npm run test --workspace apps/desktop`
  - `npm run lint`
  - `npm run test:engine`
  - `npm run tauri:build --workspace apps/desktop`

最新对外版本：

- [GitHub Release v0.1.1](https://github.com/tylevnovik/TextFlow/releases/tag/v0.1.1)

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
  samples/                   # 样例数据与旧示例项目
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

```powershell
npm run dev
```

### 常用验证命令

```powershell
npm run lint
npm run test:engine
```

### 构建 sidecar

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-python-sidecar.ps1
```

### 构建 Windows 安装包

```powershell
npm run tauri:build --workspace apps/desktop
```

`tauri:build` 会先执行 `scripts/build-desktop-release.ps1`，自动重建 Python sidecar，然后再产出 NSIS 安装包。

## Built-In Scenario Samples

On first launch, TextFlow creates nine backend-built sample projects from real public datasets. Each official sample has at least 10,000 public-source documents, split exactly 1:1 between English and Chinese rows, and demonstrates a real workflow scenario from preprocessing to advanced gates.

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
- [插件节点说明](./plugins/nodes/README.md)
- [发布记录](./CHANGELOG.md)
- [历史方案与旧文档归档](./docs/archive/README.md)

## 已知仍需继续收敛的部分

- workflow 画布的产品化体验
- 更系统的前端自动化测试、E2E 与 CI
- Windows 发版链路的持续自动化验证
- macOS 构建与运行验证
- native DAG 更细粒度的 ready-queue 调度、局部重跑和更完整的 artifact 管理
- 超大项目的冷启动、结果页首屏和导出阶段 I/O 仍有继续优化空间
