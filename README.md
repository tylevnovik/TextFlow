# TextFlow Studio

TextFlow Studio 是一个桌面优先的本地文本预处理与基础文本挖掘工具，面向研究、舆情、内容分析和语料整理场景。项目当前采用 `Tauri + React + TypeScript + Python` 架构，目标是提供一个安装即用、项目化、可复跑、可审计的桌面工作台。

当前仓库已经不是空骨架，而是具备可运行的桌面端、Python sidecar、词表中心、workflow 画布、分析导出和自动化测试基线的开发中版本。

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
- 首次启动自动生成 3 个示例项目

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

### workflow 与运行时

- workflow 画布已成为主流程入口
- 节点注册表与 schema 驱动前后端同步
- workflow 到兼容 pipeline 的编译层
- 对符合条件的 `manual/template` workflow 走 native DAG
- 节点级缓存与节点级运行摘要
- 本地纯 Python 插件节点加载

## 当前状态

- 版本：`0.1.0`
- 当前阶段：开发中，已可运行，但仍在持续收敛交付质量
- 已验证：
  - `npm run lint`
  - `npm run test:engine`
  - `npm run tauri:build --workspace apps/desktop`

最近一次对外版本：

- [GitHub Release v0.1.0](https://github.com/tylevnovik/TextFlow/releases/tag/v0.1.0)

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

## 当前文档

- [文档索引](./docs/README.md)
- [当前现状](./docs/current-status.md)
- [产品范围与完成度](./docs/product-scope.md)
- [架构说明](./docs/architecture.md)
- [工作流与运行时](./docs/workflow-runtime.md)
- [开发与构建说明](./docs/development.md)
- [示例项目说明](./docs/sample-projects.md)
- [大规模压测记录](./docs/benchmark.md)
- [插件节点说明](./plugins/nodes/README.md)
- [历史方案与旧文档归档](./docs/archive/README.md)

## 已知仍需继续收敛的部分

- workflow 画布的产品化体验
- 前端自动化测试与 CI
- Windows 发版链路的持续验证
- macOS 构建与运行验证
- native DAG 的并行调度、局部重跑和更完整的 artifact 管理
