# TextFlow Studio

TextFlow Studio 是一个面向研究、舆情、内容分析与语料整理场景的桌面优先本地工具。V1 采用 `Tauri + React + TypeScript + Python` 架构，围绕项目化管理、文本预处理、词表治理、基础分析与结果导出构建完整闭环。

## Monorepo 结构

```text
TextFlow/
  apps/
    desktop/              # Tauri + React 桌面端
  services/
    python-engine/        # Python 文本处理与分析引擎
  packages/
    shared-types/         # 前端共享领域类型
  docs/
    plans/
  samples/
```

## 功能概览

- `.tfproj` 项目创建、加载、复制，以及单文件项目包导入/导出
- `txt/csv/xlsx/json` 语料导入与字段映射
- 文本清洗、标准化、分词、词表规则应用与过滤
- 词频、词文档关系、词年份关系、共现、关键词、聚类、机构主题分析
- CSV / XLSX / PNG / HTML 报告导出
- React 响应式界面 + Tauri 桌面壳

## 当前 V1 基础能力

- 工作区会持久化 `current_project` 和 `recent_projects`，不再仅靠“最近修改时间”猜测当前项目
- 工作区默认写入用户本地数据目录，而不是仓库安装目录
- 首页支持真实项目创建、打开、复制
- 首页支持导入和导出单文件 `.tfproj` 项目包
- 数据页支持编辑导入模板：
  - `source profile`
  - 主文本拼接字段
  - 字段连接符
  - 字段映射、别名与必填约束
- 数据页支持按 source profile 一键应用导入模板预设
- 数据页支持桌面文件选择导入
- 导入会自动跳过缺少必填字段或主文本为空的记录
- 数据页支持语料库检索、逐篇预览、原文/清洗后/标准化后/切词/元数据切换查看
- 数据页支持直接修改或删除已导入语料文档
- 首页以“仓库内项目”方式展示工作区项目，支持筛选、复制和删除
- 词表页支持项目内词表编辑、批量追加、JSON 导入导出，并显示每张词表对应的流程步骤和填写说明
- 流程页支持保存主要 pipeline 参数，而不只是只读预览
- Python 后端支持保存/列出项目模板与自定义导入模板，并可由项目模板直接创建新项目
- Python pipeline 会严格按照 `enabled_steps` / `execution_order` 执行
- 关键词提取改为轻量级 `YAKE`，机构主题分析改为 `scikit-learn NMF`，不引入 Java 或大型深度学习运行时
- PNG 图表导出支持高分辨率 `DPI`、可选水印、中文字体处理，并新增关键词词云、项目关键词图、机构主题热力图
- run 目录会稳定写出 `params_snapshot.json`、`logs.json`、`logs.txt`、`corpus_snapshot.json`
- 导入命令会把源文件复制进项目的 `corpus/imported/` 目录，便于迁移和备份
- Python sidecar 提供 `open-project`、`duplicate-project`、`import-project-files`、`run-pipeline`、`export-project` 等动作
- Tauri 会在启动时拉起一个常驻 Python 服务，整个会话内复用同一个后端进程
- 前后端通信改为异步任务轮询，界面会显示阶段性进度，而不是每次点击都弹出黑色命令行窗口
- 处理页采用固定主流程 + 可选步骤，详细参数按步骤分组显示
- 处理页把一次运行明确拆成 `处理对象`、`处理配方`、`输出包` 和 `本次运行摘要`，先确认“处理谁 / 怎么处理 / 产出什么”再开始执行
- 处理页会明确区分 `TF-IDF` 特征词、`YAKE` 关键词、`NMF` 主题和聚类参数，并说明每组参数影响哪个输出
- 结果页支持导出单文件 `.tfproj` 项目包
- 结果页会显示最近一次导出位置，并支持自动打开导出文件夹、手动打开或定位文件
- 首次进入时会自动提供一个可直接体验完整流程的示例项目
- 现有分析链路仍可直接运行，并将运行记录和导出结果写入 `runs/` 和 `exports/`
- Python sidecar 采用目录式打包，安装版不依赖用户自带 Python
- `npm run tauri:build --workspace apps/desktop` 会先自动重建 Python sidecar，再产出 NSIS Windows 安装包

## 开发要求

- Node.js 24+
- npm 11+
- Python 3.11+
- Rust / Cargo

## 快速开始

1. 创建 Python 虚拟环境：`powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap-python.ps1`
2. 安装前端依赖：`powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap-frontend.ps1`
3. 运行桌面开发模式：`npm run dev`
4. 运行 Python 测试：`.\services\python-engine\.venv\Scripts\python.exe -m pytest services/python-engine/tests -q`
5. 构建可分发 Python sidecar：`powershell -ExecutionPolicy Bypass -File .\scripts\build-python-sidecar.ps1`

## 常用脚本

- `npm run dev`
- `npm run build`
- `npm run lint`
- `npm run test:engine`
- `powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap-python.ps1`
- `powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap-frontend.ps1`
- `powershell -ExecutionPolicy Bypass -File .\scripts\build-python-sidecar.ps1`

## 文档

- [PRD](./docs/prd.md)
- [架构说明](./docs/architecture.md)
- [Pipeline 规格](./docs/pipeline-spec.md)
- [V2 节点工作流规格（迁移版）](./docs/workflow-node-spec.md)
- [V2 工作流 Schema](./docs/workflow-schema.md)
- [V2 节点运行时规格](./docs/node-runtime-spec.md)
- [UI 说明](./docs/ui-spec.md)
- [实施计划](./docs/plans/2026-04-16-textflow-v1.md)
- [V1 基础盘实施计划](./docs/plans/2026-04-16-v1-foundation-workspace-import.md)
- [V2 节点工作流设计摘要](./docs/plans/2026-04-18-v2-node-workflow-design.md)
