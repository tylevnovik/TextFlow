# 当前现状

本文档描述截至 `2026-05-26` 的仓库事实，用来回答“现在项目做到哪一步了”。

## 一句话结论

TextFlow 已经完成了一个可运行的本地桌面应用主链，不再只是 V1 骨架。当前最强的部分是 Python 引擎、项目存储、词库治理、官方场景样例、分析导出和测试基线；最需要继续收敛的部分是以“语料、词库、节点图”为核心的桌面工作台体验、前端/E2E 自动化测试、CI 和持续发版验证。

## 总体状态

| 领域 | 当前状态 | 说明 |
| --- | --- | --- |
| 桌面壳与前后端通信 | 可用 | Tauri 启动常驻 Python sidecar，本地通过任务接口和进度轮询通信；高频 workflow 进度已改成增量节点状态回传。 |
| Fluent 工作台壳 | Phase 5 进行中 | `AppShell` / `ProjectWorkbench` 已用 FluentProvider、命令栏、项目对象树、属性检查器和底部运行面板承载旧 PageView；语料、词库、节点图、运行记录和产物工作面已接入统一 selection、对象 inspector 与支撑面命令壳。 |
| 工作区与项目管理 | 可用 | 已支持创建、打开、复制、删除、导入项目包、导出项目包、最近项目和当前项目持久化；首次启动会恢复 3 个 revised-flow 场景样例项目，缺少打包样例模板时会显式失败。 |
| 语料导入与审查 | 可用，正在工作台化 | 已支持 `txt/csv/xlsx/xls/json` 导入、source profile、字段映射、主文本拼接、文档级预览、编辑、删除；文档选择会驱动右侧属性检查器，语料集合可跳转到节点图入口。 |
| 词库中心 | 可用，正在工作台化 | 已支持 `collections + tables + sheets` 结构、项目自定义表、内置词库快照、导入导出；词库分类和资源表已进入工作台对象树，资源表选择会驱动右侧属性检查器并可跳转绑定节点图。 |
| 工作流处理链 | 可用 | 清洗、标准化、切词、词表规则、过滤、分析、导出均可实际运行。 |
| 分析与导出 | 可用 | 已输出词频、词文档、词年份、共现、相似度、特征词、关键词、NMF/LDA 主题、关键词聚类、机构关键词、机构主题、文档聚类、图分析和技术识别，以及 CSV/XLSX/PNG/HTML。 |
| 运行留痕 | 可用 | `run_history`、`params_snapshot.json`、`logs.json`、`logs.txt`、`corpus_snapshot.json` 已落盘。 |
| workflow 画布 | 可用，正在工作台化 | 当前已经是主流程入口，支持节点、连线、视口恢复、工具箱、mini-map 和节点内配置；固定参数节点会在卡片内完整内联轻量配置控件，只有语料范围、词表分表、元数据条件和复核任务这类会随项目数据增长的节点保留短摘要并在右侧 `WorkflowInspector` 展示完整配置；画布节点/连线选择已同步右侧检查器，语料集合和词库资源表可从对象树拖入画布触发绑定入口。 |
| native DAG 执行 | 已接入主链 | 当前 workflow 运行统一进入 native DAG；旧聚合节点不再发布到 catalog，同层就绪的并行安全节点已支持并发调度。 |
| 节点缓存 | 已接入 | 当前是节点级 `.pkl` 缓存，已在 benchmark 中体现二次运行收益。 |
| 资源、产物、复核和实验 surfaces | 可用，正在工作台化 | 项目模型、bridge/store 和运行产物支撑面已接入语料视图、导入规格、review queue、experiment matrix 和 run diff；底部运行面板可打开 run/artifact 支撑 workspace，artifact preview 也可从已运行 workflow 节点弹窗查看。 |
| 插件节点 | Alpha | 已支持本地纯 Python 节点插件扫描、注册 definition/compiler/executor，并可通过 `artifact_kind` 输出口写入项目 artifact store。 |
| Windows 安装包 | 已通过本地与 CI 打包验证 | Tauri NSIS bundling 已配置，sidecar 会随安装包带上；本地已产出 `TextFlow Studio_0.2.0_x64-setup.exe`，并已配置 GitHub Actions Release 自动构建工作流。 |
| macOS 可移植性 | 保持约束，未完成验证 | 路径、字体、工作区根目录选择都在照顾可移植性，但当前没有成体系的 macOS 构建验证。 |

## 当前已经稳定的主链

- 项目目录采用 `.tfproj` 目录结构，用户工作区默认放在系统本地数据目录，也支持 `TEXTFLOW_WORKSPACE_ROOT` 覆盖。
- 启动空工作区时，系统会优先恢复打包内置的 3 个 revised-flow 场景样例项目；这些项目由 Python sidecar 基于 WoS/IncoPat seed 预构建，语料写入各自的 `project.db`。
- 普通数据导入会把源文件复制到项目的 `corpus/imported/`，并在 `source_files` 中记录来源；打包样例只保留 source audit 元数据，不保留 raw seed 文件。
- 词库已经从“单大表”演进为按分类和表资源管理，项目文件不会再把整包内置词库全量写入。
- Python sidecar 已经承担真实项目动作，而不是只做 CLI 样例。
- 导出能力已经覆盖表格、图表和 HTML 报告，并支持高 DPI、水印和中文字体。
- 高频项目动作已尽量走前端本地 patch，不再每次都整项目 `refresh()`。
- 首次工作区冷启动的示例项目生成热路径已做轻量化，避免重复全量归一化大词表。
- 项目概览不再渲染全量运行日志，只展示最近 3 次运行摘要；完整历史归入运行产物支撑面，artifact preview 可从底部产物列表、运行产物 workspace 或工作流节点按需查看。
- 项目管理页的项目库不再使用内嵌滚动列表，长内容跟随工作台主滚动容器滚动，避免同一页面出现双层纵向滚动条。

## 当前最重要的技术事实

### 1. 项目模型已经切到 workflow-only

当前 `ProjectManifest` 保存：

- `workflow_definitions`
- `active_workflow_id`
- `run_history`
- `results`

项目模型现在只认 workflow 真相层字段，任何历史遗留快照都不会再参与恢复或写回。

### 2. workflow 已不是“只画不跑”的壳层

当前工作流系统已经具备：

- 节点注册表
- 节点 schema 到前端表单的同步
- 输出节点回溯活跃子图
- workflow-only native DAG 执行
- 同层就绪节点的保守并行执行
- 节点级运行摘要与缓存

它仍然不是完整的图运行时，但已经不只是“把线性表单换个外观”。

### 3. UI 心智正在从页面导航迁移到工作台对象

桌面端仍保留旧 `PageId`，以避免一次性重写 store、测试和现有页面实现；但面向 UI 的 activity 命名和工作台壳已经先对齐为：

- 开始
- 项目
- 语料（旧 `data`）
- 词库（旧 `dictionaries`）
- 节点图（旧 `workflow`）
- 运行产物（旧 `results`，支撑面而非核心对象）
- 设置

`report` 相关视图仍存在于组件和类型层，定位为产物预览支撑面。`results` 不再被描述成和语料、词库、节点图并列的核心对象。

Phase 2 已开始把旧 `DataPage` 迁移为语料对象工作面：新增 `apps/desktop/src/features/corpus/`，其中 `CorpusWorkspace` 承接语料命令栏和摘要，`CorpusInspector` 承接语料集合、导入规范和单篇文档属性，`CorpusExplorer` 建模导入批次、导入规范、全部语料和语料视图节点。

Phase 3 已开始把旧 `DictionariesPage` 迁移为词库对象工作面：新增 `apps/desktop/src/features/lexicon/`，其中 `LexiconWorkspace` 承接词库命令栏和摘要，`LexiconInspector` 承接词库分类、资源表和条目属性，`LexiconExplorer` 建模 8 类词库及其资源表节点。

Phase 4 已开始把旧 `WorkflowEditorPage` 迁移为节点图默认主工作面：新增 `apps/desktop/src/features/workflow/`，其中 `WorkflowWorkspace` 承接节点图命令栏、摘要和状态面板，`WorkflowInspector` 承接节点图、节点和连线属性检查器，`WorkflowExplorer` 建模当前画布节点和节点库。画布点击节点或连线会更新统一 `WorkbenchSelection`，右侧检查器显示节点参数、端口、运行状态和产物摘要；对象树中的语料集合和词库资源表支持拖放到节点图画布，作为资源绑定入口。

## 质量与验证

截至 `2026-05-26`，本地与 CI 验证结果如下：

- `npm run lint` 通过
- `npm run test --workspace apps/desktop` 通过
- `npm run build` 通过
- `npm run test:engine` (或 `test:engine:fast`) 通过
- `npm run test:engine:full` 通过
- `powershell -ExecutionPolicy Bypass -File .\scripts\build-python-sidecar.ps1` 通过
- `npm run tauri:build --workspace apps/desktop` 通过，且 GitHub Actions 自动化 CI 和 Release 打包工作流正常运行
- 当前测试覆盖重点在 Python 引擎、工作区 CLI、workflow 节点目录一致性和 native DAG 行为

## 当前明显缺口

- 前端已有基础组件/store 测试，但仍缺少系统化的 E2E 自动化测试覆盖。
- workflow 画布虽然可用，但仍然偏工程态，距“稳定交付给终端用户”的产品化体验还有差距。
- native DAG 还缺少更细粒度的 ready-queue 调度、面向用户的局部重跑、跨项目 artifact registry 和更完整的 dirty 传播可视化。
- 插件节点没有签名、隔离和安全边界设计，当前只适合开发态本地扩展。
- Windows 安装与发布链路虽然在 GitHub Actions 中配置了自动 Release 工作流，但多平台的自动化集成机制仍需持续演进。
- 缺少成体系的 macOS 构建与运行验证。

## 当前最值得继续推进的方向

1. 把工作台相关文档、命名和 UI 文案继续统一，减少“数据页/词表页/结果页”等旧页面式表达。
2. 补齐前端 E2E 测试，让当前已经不小的功能面有持续回归保护。
3. 继续优化大语料导出和 snapshot 写盘，避免 benchmark 成绩被后半段 I/O 拖慢。
4. 把安装包、示例项目、插件节点和工作流能力做一轮“面向交付”的整理，而不是继续只面向内部研发迭代。
