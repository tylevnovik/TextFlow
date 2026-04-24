# 当前现状

本文档描述截至 `2026-04-24` 的仓库事实，用来回答“现在项目做到哪一步了”。

## 一句话结论

TextFlow 已经完成了一个可运行的本地桌面应用主链，不再只是 V1 骨架。当前最强的部分是 Python 引擎、项目存储、词表治理、分析导出和测试基线；最需要继续收敛的部分是工作流画布体验、前端自动化测试、CI 和正式发版验证。

## 总体状态

| 领域 | 当前状态 | 说明 |
| --- | --- | --- |
| 桌面壳与前后端通信 | 可用 | Tauri 启动常驻 Python sidecar，本地通过任务接口和进度轮询通信；高频 workflow 进度已改成增量节点状态回传。 |
| 工作区与项目管理 | 可用 | 已支持创建、打开、复制、删除、导入项目包、导出项目包、最近项目和当前项目持久化。 |
| 语料导入与审查 | 可用 | 已支持 `txt/csv/xlsx/json` 导入、source profile、字段映射、主文本拼接、文档级预览、编辑、删除。 |
| 词表中心 | 可用 | 已支持 `collections + tables + sheets` 结构、项目自定义表、内置词表快照、导入导出。 |
| 工作流处理链 | 可用 | 清洗、标准化、切词、词表规则、过滤、分析、导出均可实际运行。 |
| 分析与导出 | 可用 | 已输出词频、词文档、词年份、共现、特征词、关键词、关键词聚类、机构关键词、机构主题、文档聚类，以及 CSV/XLSX/PNG/HTML。 |
| 运行留痕 | 可用 | `run_history`、`params_snapshot.json`、`logs.json`、`logs.txt`、`corpus_snapshot.json` 已落盘。 |
| workflow 画布 | 可用但仍在打磨 | 当前已经是主流程入口，支持节点、连线、视口恢复、工具箱、mini-map 和节点内配置。 |
| native DAG 执行 | 已接入主链 | 当前 workflow 运行统一进入 native DAG；legacy 聚合节点也在图运行时内兼容执行，同层就绪的并行安全节点已支持并发调度。 |
| 节点缓存 | 已接入 | 当前是节点级 `.pkl` 缓存，已在 benchmark 中体现二次运行收益。 |
| 资源、产物、复核和实验 surfaces | 可用 | 项目模型、bridge/store 和桌面结果页已接入语料视图、导入规格、artifact preview、review queue、experiment matrix 和 run diff。 |
| 插件节点 | Alpha | 已支持本地纯 Python 节点插件扫描、注册 definition/compiler/executor，并可通过 `artifact_kind` 输出口写入 artifact store。 |
| Windows 安装包 | 已通过本地打包验证 | Tauri NSIS bundling 已配置，sidecar 会随安装包带上；本地已产出 `TextFlow Studio_0.1.0_x64-setup.exe`。 |
| macOS 可移植性 | 保持约束，未完成验证 | 路径、字体、工作区根目录选择都在照顾可移植性，但当前没有成体系的 macOS 构建验证。 |

## 当前已经稳定的主链

- 项目目录采用 `.tfproj` 目录结构，用户工作区默认放在系统本地数据目录，也支持 `TEXTFLOW_WORKSPACE_ROOT` 覆盖。
- 启动空工作区时，系统会自动生成 3 个示例项目，并把“示例项目 - 学术摘要机构主题”设为当前项目。
- 数据导入会把源文件复制到项目的 `corpus/imported/`，并在 `source_files` 中记录来源。
- 词表已经从“单大表”演进为按分类和表资源管理，项目文件不会再把整包内置词表全量写入。
- Python sidecar 已经承担真实项目动作，而不是只做 CLI 样例。
- 导出能力已经覆盖表格、图表和 HTML 报告，并支持高 DPI、水印和中文字体。
- 高频项目动作已尽量走前端本地 patch，不再每次都整项目 `refresh()`。
- 首次工作区冷启动的示例项目生成热路径已做轻量化，避免重复全量归一化大词表。

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

### 3. 当前主导航已经收敛为 6 个页面

桌面端当前主导航入口是：

- 开始
- 导入资料
- 词表规则
- 处理与分析
- 结果导出
- 设置

`project / analysis / report` 相关视图仍存在于组件和类型层，但不是当前主导航主路径。

## 质量与验证

截至 `2026-04-24`，本地验证结果如下：

- `npm run lint` 通过
- `npm run test:engine` 通过
- `npm run test --workspace apps/desktop` 通过
- `npm run build` 通过
- `npm run tauri:build --workspace apps/desktop` 通过，并产出 NSIS installer
- 当前测试覆盖重点在 Python 引擎、工作区 CLI、workflow 节点目录一致性和 native DAG 行为

## 当前明显缺口

- 前端缺少系统化单元测试和 E2E 测试。
- 仓库中还没有持续集成配置。
- workflow 画布虽然可用，但仍然偏工程态，距“稳定交付给终端用户”的产品化体验还有差距。
- native DAG 还缺少更细粒度的 ready-queue 调度、面向用户的局部重跑、跨项目 artifact registry 和更完整的 dirty 传播可视化。
- 插件节点没有签名、隔离和安全边界设计，当前只适合开发态本地扩展。
- Windows 安装链路已通过本地打包验证，但仍缺少自动化 release checklist 和持续验证记录。

## 当前最值得继续推进的方向

1. 把 workflow 相关文档、命名和 UI 文案继续统一，减少遗留的旧线性命名。
2. 补齐前端测试与 CI，让当前已经不小的功能面有持续回归保护。
3. 继续优化大语料导出和 snapshot 写盘，避免 benchmark 成绩被后半段 I/O 拖慢。
4. 把安装包、示例项目、插件节点和工作流能力做一轮“面向交付”的整理，而不是继续只面向内部研发迭代。
