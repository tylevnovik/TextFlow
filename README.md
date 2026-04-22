# TextFlow Studio

TextFlow Studio 是一个桌面优先的本地文本预处理与基础文本挖掘工具，面向研究、舆情、内容分析和语料整理场景。当前仓库已经不是“空骨架”，而是具备可运行的 Tauri 桌面端、Python sidecar、项目化数据存储、词表中心、工作流画布、分析导出和自动化测试的开发中版本。

## 当前阶段

- 版本号：`0.1.0`
- 代码阶段：开发中，尚未形成正式发行版
- 当前文档基线：截至 `2026-04-23`
- 当前目标：把现有能力收敛为稳定可交付的 Windows 桌面版，并保留 macOS 可移植性

## 当前已落地能力

- `Tauri + React + TypeScript + Python` 的本地桌面架构
- 工作区与 `.tfproj` 项目目录管理
- `txt/csv/xlsx/json` 导入、source profile、字段映射、主文本拼接
- 文档级预览、搜索、编辑、删除
- 词表中心，支持内置词表快照和项目级自定义词表
- 文本清洗、标准化、切词、词表规则、过滤
- 词频、词文档、词年份、共现、特征词、关键词、关键词聚类、机构关键词、机构主题、文档聚类
- CSV / XLSX / PNG / HTML 导出
- 运行历史、参数快照、日志、审计表
- 工作流画布、节点注册表、兼容 pipeline 编译层
- 对符合条件的 manual/template workflow 走原生 DAG 执行
- 本地纯 Python 插件节点加载
- 首次启动自动生成 3 个示例项目

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

### 开发环境

- Node.js `24+`
- npm `11+`
- Python `3.11+`
- Rust / Cargo

### 初始化

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap-python.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap-frontend.ps1
```

### 日常开发

```powershell
npm run dev
npm run lint
npm run test:engine
```

### 打包

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-python-sidecar.ps1
npm run tauri:build --workspace apps/desktop
```

`tauri:build` 会先执行 `scripts/build-desktop-release.ps1`，再产出 Windows NSIS 安装包。

## 当前验证快照

以下结果在 `2026-04-23` 本地执行得到：

- `npm run lint`：通过
- `npm run test:engine`：`48 passed`，耗时约 `7m58s`
- Python 测试当前有 `3` 条 `scikit-learn` 收敛类 warning，但不影响测试通过

## 文档入口

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
