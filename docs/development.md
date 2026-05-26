# 开发与构建说明

## 环境要求

- Node.js `24+`
- npm `11+`
- Python `3.11+`
- Rust / Cargo
- Windows 为当前主要开发和打包目标

## 初始化

### Python 引擎

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap-python.ps1
```

脚本会：

- 创建 `services/python-engine/.venv`
- 升级 `pip`
- 以 editable 模式安装引擎和开发依赖

### 前端依赖

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap-frontend.ps1
```

脚本会把 npm 缓存固定到仓库内的 `.npm-cache`，减少环境漂移。

## 常用命令

### 启动桌面开发模式

```powershell
npm run dev
```

### TypeScript 检查

```powershell
npm run lint
```

注意：当前 `lint` 实际上是 `tsc --noEmit`，不是 ESLint。

### 本地浏览器烟测

涉及前端 UI、视觉、布局、工作台、节点图、语料/词库工作面等改动时，除命令行校验外，应默认做一次本地浏览器烟测。

推荐流程：

```powershell
$port = 5174
$log = Join-Path $env:TEMP "textflow-vite-smoke.log"
$err = Join-Path $env:TEMP "textflow-vite-smoke.err.log"
npm run dev --workspace apps/desktop -- --host 127.0.0.1 --port $port --strictPort
```

如果 `5174` 被占用，可在 `5173..5180` 内换一个空闲端口，或使用其他明确空闲的本地端口。需要后台启动时，可用 `Start-Process`，日志仍写到 `%TEMP%`，不要把临时烟测日志留在仓库里。

启动后，在 Codex 内置 Browser / Browser plugin 打开：

```text
http://127.0.0.1:<port>/
```

不要用系统浏览器启动命令替代 Codex 内置 Browser；后续 agent 应通过内置浏览器做 DOM snapshot、截图和交互确认。

基础检查清单：

- 应用能加载，标题栏、项目对象树、主工作区、右侧检查器和底部运行状态区域没有明显运行时错误。
- 本次改动触达的页面能从外层工作台对象树或主导航直接到达。
- 触达的对象面板、检查器、底部面板能按设计折叠或调整尺寸。
- 画面中没有明显文字重叠、控件溢出、重复命令区、重复状态区或遗留旧控件外观。
- Fluent `Input`、`Select`、`Button`、`Toolbar` 等控件的 focus / hover / active 状态没有旧样式叠边、双重强调圈或过重阴影。

节点图专项检查：

- 从外层对象树进入 `节点图 -> 关键词与主题工作流`，画布和 minimap 正常渲染。
- Workflow 动作应在外层工作台左侧 surface 中，画布内不应再出现旧 `WF / 库 / 图 / 态` 内部 rail、重复工具栏或重复摘要/状态卡片。
- 节点图可拖拽、缩放、适配视图，主要内容不会因为容器高度或滚动限制被遮住。
- 语料集合和词库资源入口仍可通过外层对象树拖放或动作绑定到节点。

视觉或布局类改动至少保留一次可见截图判断；DOM snapshot 可辅助确认重复元素和旧控件是否清除。烟测结束后，可以停止临时 dev server；若保留给用户继续查看，需要在交付说明里报告准确 URL。

### 前后端协同实机测试

这里分两层，不要混用：

- `npm run smoke:desktop:real` 是固定路线的 baseline regression smoke。它会真实拉起浏览器和 Python engine，但只覆盖一条预设 happy path，适合提交前确认主链路没有断。
- `npm run dev:desktop:real` 是给 agent 或人工测试者使用的真实协同栈启动器。它只负责拉起前端、后端和浏览器，并输出 URL、隔离 workspace、CDP 调试地址和首屏截图；后续需要测试者主动浏览、判断、追查问题。

当需要验证 sample project、真实 workflow 运行、Python sidecar HTTP 服务或前端与后端契约的固定基线时，使用：

```powershell
npm run smoke:desktop:real
```

该脚本会自动：

- 在 `%TEMP%` 下创建隔离工作区，不污染本地默认工作区。
- 使用 `services/python-engine/.venv` 启动 Python engine HTTP service。
- 设置 `TEXTFLOW_WORKSPACE_ROOT` 和 `TEXTFLOW_BUNDLED_SAMPLE_WORKSPACE_ROOT`，让 engine 加载官方 sample workspace。
- 使用 `VITE_TEXTFLOW_ENGINE_URL` 启动 Vite 前端，使普通浏览器模式不再走 demo fallback，而是通过 HTTP 调用真实 engine。
- 启动 headless Chrome，按常规桌面尺寸打开工作台，依次点击 `项目`、`语料`、`词库`、`节点图`、`运行`、`系统`，并触发一次 `运行节点图`。
- 把截图和隔离工作区路径写入脚本输出，截图位于 `%TEMP%\textflow-real-smoke-*\screenshots\`。

当需要做主动探索式实机测试时，使用：

```powershell
npm run dev:desktop:real
```

启动后根据脚本输出的 `appUrl` 打开真实前端，确认 `engineUrl` 指向本次临时 Python engine，并按实际观察做测试决策。测试者应至少检查：

- 页面是否真正加载官方 sample，而不是 browser demo fallback。
- 项目、语料、词库、节点图、运行、系统等主要 surface 的可达性、状态文案、空/加载/失败态和明显布局问题。
- 当前页面可见按钮、输入框、表格、折叠区、对象树节点、底部状态面板和右侧检查器是否行为一致。
- console/runtime/network 是否出现真实错误；遇到错误应回到代码或 engine 响应追查，而不是只记录截图。
- 对高风险功能区采用隔离 workspace 做真实操作，例如运行节点图、查看产物、打开运行历史、切换 sample project。

可选环境变量：

```powershell
$env:TEXTFLOW_SMOKE_WIDTH = "1440"
$env:TEXTFLOW_SMOKE_HEIGHT = "900"
$env:TEXTFLOW_SMOKE_VITE_PORT = "5174"
$env:TEXTFLOW_SMOKE_CHROME = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$env:TEXTFLOW_SMOKE_WORKFLOW_TIMEOUT_MS = "480000"
$env:TEXTFLOW_REAL_STACK_HEADLESS = "0"
```

使用前应先完成 Python 和前端依赖初始化。若没有找到 Chrome/Edge，可用 `TEXTFLOW_SMOKE_CHROME` 指定兼容浏览器路径。默认使用 headless Chrome；需要可见窗口时设置 `TEXTFLOW_REAL_STACK_HEADLESS=0`。

### 前端工作台命名

当前前端为了降低迁移风险，仍保留旧 `PageId`：`data`、`dictionaries`、`workflow`、`results` 等。面向用户和新代码的 UI activity 命名应使用：

- `data` -> 语料 / corpus
- `dictionaries` -> 词库 / lexicon
- `workflow` -> 节点图 / workflow graph
- `results` -> 运行产物 / run artifacts

`results` 是节点图执行后的支撑 surface，不应在新文档或新 UI 文案里继续被描述成和语料、词库、节点图并列的核心对象。

运行和产物相关 UI 应优先落在 `features/runs/`：底部状态面板使用 `RunStatusPane`，运行历史使用 `RunHistoryWorkspace`，产物预览使用 `ArtifactWorkspace`，右侧追溯信息使用 `RunInspector`。旧 `features/results/RunHistoryPanel` 和 `features/artifacts/ArtifactBrowser` 仍可作为内部子组件复用，但不应再作为新的一级页面心智扩张。

### 前端视觉 token

桌面端视觉统一以 Fluent 中性工作台为基准。全局颜色、圆角和阴影优先使用 `apps/desktop/src/app/fluentTheme.ts` 里导出的 `tfColorTokens`、`tfRadiusTokens`、`tfShadowTokens`，并通过 `textFlowCssVariables` 注入 `FluentProvider`。CSS 中使用 `--tf-color-*`、`--tf-radius-*`、`--tf-shadow-*`，旧的 `--bg`、`--panel`、`--ink`、`--line` 等变量只作为兼容别名保留。

新增页面或组件应优先使用 Fluent `Toolbar`、`Button`、`Input`、`DataGrid` 等桌面控件。除 workflow 画布内部节点图的专用交互外，不应新增或继续扩张旧 `toolbar-button`、`tab-button`、`Panel` 这类自绘控件外观；必须保留的旧内容也要通过全局 token 呈现为中性、低阴影、低动画的同一桌面应用风格。

语料相关新 UI 应优先放在 `apps/desktop/src/features/corpus/`：

- `CorpusWorkspace.tsx`：语料工作面命令栏、摘要和旧导入/审查内容容器。
- `CorpusInspector.tsx`：语料集合、导入规范、单篇文档的右侧属性检查器。
- `CorpusExplorer.tsx`：语料对象树节点模型，当前供工作台对象树复用。
- `corpusCommands.ts`：导入、保存导入规范、创建视图、发送到节点图等命令元数据。

当语料表内选择文档时，应更新 `WorkbenchSelection` 为 `corpus_document`，不要只维护页面内局部选中态。

词库相关新 UI 应优先放在 `apps/desktop/src/features/lexicon/`：

- `LexiconWorkspace.tsx`：词库工作面命令栏、摘要和旧资源表/条目编辑内容容器。
- `LexiconInspector.tsx`：词库分类、资源表、单条词库条目的右侧属性检查器。
- `LexiconExplorer.tsx`：8 类词库和每类资源表的对象树节点模型，当前供工作台对象树复用。
- `lexiconCommands.ts`：导入、导出、新增、复制、绑定到节点等命令元数据。

当词库页内选择分类、资源表或条目时，应更新 `WorkbenchSelection` 为 `lexicon_kind`、`lexicon_table` 或 `lexicon_entry`。节点图里的 `Dictionary Input` / `Select Dictionary Tables` 相关入口应复用同一套词库资源概念。

节点图相关新 UI 应优先放在 `apps/desktop/src/features/workflow/`：

- `WorkflowWorkspace.tsx`：节点图画布工作面容器；节点图动作、摘要和状态信息应优先接入外层 workbench 左侧对象树、右侧检查器和底部状态面板。
- `WorkflowInspector.tsx`：节点图、单个节点、单条连线的右侧属性检查器。
- `WorkflowExplorer.tsx`：当前画布节点和节点库对象模型，当前供工作台对象树复用。
- `WorkflowStatusPane.tsx`：节点图校验、运行状态和最近运行摘要。
- `workflowCommands.ts`：保存图、运行、自动布局、适配视图、校验等命令元数据。

当画布内选择节点或连线时，应更新 `WorkbenchSelection` 为 `workflow_node` 或 `workflow_edge`，不要只维护画布局部选中态。对象树里的语料集合和词库资源表可通过 `WORKBENCH_SELECTION_MIME` 拖放到画布，节点图负责解析 selection 并绑定到 `Corpus Input` 或 `Dictionary Input`。

### 新增或修改 workflow 节点

节点定义只改 Python 节点模块，不要在前端新增内置节点 schema、尺寸、默认位置、默认配置或属性编辑器分支。完整 schema 见 [节点 Catalog Schema](./node-catalog-schema.md)。

推荐流程：

1. 在 `services/python-engine/app/workflow/nodes/<node>.py` 定义或修改 `node_definition()`。
2. 在同一模块注册 compiler 和 executor，复用 `_common.py` 中的 `port()`、`graph()`、`ui()`、`field()`、`slot()` helper。
3. 在 `params` 写默认值，在 `graph` 写画布尺寸/默认位置，在 `ui.layout` 写动态属性面板。
4. 复杂属性交互只声明白名单 `slot(component_id)`，不要让后端下发 UI 代码。
5. 运行 `npm run test:engine:fast`。
6. 如果改默认样例、模板图、导出/import 流或 bootstrap 路径，补跑 `npm run test:engine:full`。
7. 触及前端动态解释器、工具箱、连线或属性面板时，补跑相关 Vitest，例如 `workflowNodeCatalog.test.ts`、`DynamicNodeEditor.test.tsx`、`pluginNodeCatalog.test.tsx`、`workflow.test.ts`。

### Python 测试

```powershell
npm run test:engine
npm run test:engine:full
```

或直接：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\test-engine.ps1 -Suite fast
powershell -ExecutionPolicy Bypass -File .\scripts\test-engine.ps1 -Suite full
```

说明：

- `npm run test:engine` 等价于 `test:engine:fast`，是默认的日常引擎回归集。
- `npm run test:engine:full` 会额外跑官方样例生成、样例刷新、导出触发运行、打包期样例模板等重覆盖测试。
- 未来 AI 在没有额外对话提示时，应默认按改动范围自动选择测试层级，而不是一律跑最慢的全量集。

### 引擎测试分层规则

- 只改前端、样式或文档：通常不需要 Python 引擎测试；至少按改动范围跑 `npm run lint`，触及组件行为时补跑 `npm run test --workspace apps/desktop`。
- 改普通引擎逻辑但不涉及官方样例打包/引导：跑 `npm run test:engine`。
- 改工作区首次启动、官方样例、样例 seed gate、sidecar 打包脚本、导出会触发样例运行的链路：跑 `npm run test:engine:full`。
- 如果改动同时碰到 `services/python-engine/app/sample_projects.py`、`services/python-engine/app/bundled_sample_workspace.py`、`services/python-engine/app/cli.py` 的 bootstrap 路径、`scripts/build-bundled-sample-workspace.ps1` 或 `scripts/build-python-sidecar.ps1`，直接视为 `full`。
- 发布前或对测试层级有疑问时，补跑 `npm run test:engine:full`。

### 缩小官方样例规模用于测试

如果你只是在本地验证样例项目创建或 workflow smoke test，可以临时设置：

```powershell
$env:TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT = "120"
```

注意：

- 当前 3 个样例基于 WoS/IncoPat seed，不再要求英中配比或偶数行数。
- 测试结束后可以执行 `Remove-Item Env:TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT` 清理当前终端环境变量。

## 构建

### 配置官方样例 seed

```powershell
$env:TEXTFLOW_SAMPLE_WOS_SOURCE = "C:\path\to\wos.xls"
$env:TEXTFLOW_SAMPLE_INCOPAT_SOURCE = "C:\path\to\incopat.xlsx"
$env:TEXTFLOW_ALLOW_RESTRICTED_SAMPLE_DATA = "1"
```

说明：

- WoS/IncoPat/Scopus 导出通常受订阅协议限制，默认不能公开再分发。
- `TEXTFLOW_ALLOW_RESTRICTED_SAMPLE_DATA=1` 只用于本地或私有构建。
- `sample_seed_sources/private/` 已被 git 忽略，可放本地 seed。
- 公开发布构建必须使用已明确可再分发的 seed，或者不要开启 restricted override。

### 仅重建 Python sidecar

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-python-sidecar.ps1 `
  -WosSeed "C:\path\to\wos.xls" `
  -IncopatSeed "C:\path\to\incopat.xlsx" `
  -AllowRestrictedSampleData
```

产物目录：

```text
services/python-engine/dist/textflow-engine/
```

### 预构建官方样例工作区

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-bundled-sample-workspace.ps1 `
  -WosSeed "C:\path\to\wos.xls" `
  -IncopatSeed "C:\path\to\incopat.xlsx" `
  -AllowRestrictedSampleData `
  -RowLimit 120
```

说明：

- 该脚本会导入 WoS/IncoPat seed，生成 3 个 revised-flow 官方样例工作区模板。
- 样例语料写入各项目的 `project.db`，打包模板不保留 raw seed 文件。
- `build-python-sidecar.ps1` 会自动调用它，并把生成出的 `app/bundled_sample_workspace/` 一并打进 sidecar。
- 安装包里的首次启动会优先恢复这份预构建模板，而不是现场重建样例项目。
- 如果你修改了官方样例定义，重新打包后新安装包会自动带上新的样例工作区。
- `-RowLimit` 只建议用于开发或测试模板。

### 构建安装包

```powershell
npm run tauri:build --workspace apps/desktop
```

当前配置行为：

- Tauri 在 build 前会先执行 `scripts/build-desktop-release.ps1`
- `build-desktop-release.ps1` 会先重建 Python sidecar，再构建前端
- bundling 目标当前为 `NSIS`
- 发版前应确认 `apps/desktop/src-tauri/target/release/bundle/nsis/` 下生成 Windows installer

## 词表快照更新

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\update-builtin-dictionaries.ps1
```

当前内置来源包括：

- `stopwords-iso`
- `THUOCL`
- `OpenCC`
- `client9/misspell`

## benchmark

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-large-benchmark.ps1
```

可选参数示例：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-large-benchmark.ps1 --limit 2000
```

## 当前测试与验证情况

截至 `2026-05-14`，前端工作台本地验证：

- `npm run lint` 通过
- `npm run test --workspace apps/desktop` 通过
- `npm run build` 通过
- Codex 内置 Browser 已用于 `http://127.0.0.1:5174/` 本地烟测；后续视觉/布局/工作台改动默认按“本地浏览器烟测”流程复核

截至 `2026-04-28`，引擎与安装包链路已验证或纳入最终验证清单：

- `npm run test:engine` 通过
- `npm run test:engine:full` 通过
- `powershell -ExecutionPolicy Bypass -File .\scripts\build-python-sidecar.ps1` 通过
- `npm run tauri:build --workspace apps/desktop` 通过，并已产出 NSIS installer

当前 Windows installer 输出位置：

```text
apps/desktop/src-tauri/target/release/bundle/nsis/TextFlow Studio_0.2.0_x64-setup.exe
```

当前测试重点在：

- 项目存储与工作区 CLI
- 导入与 workflow 主链
- 后端 node catalog 契约、插件节点、端口兼容和前端动态脚手架
- native DAG 的关键路径

## 当前开发注意事项

- 目前已有少量前端组件/store 测试，但还没有系统化前端测试矩阵和 E2E 测试。
- 仓库中没有 CI 配置，回归主要依赖本地命令。
- `test:engine:fast` 应保持适合日常迭代；`test:engine:full` 会明显更慢，因为它覆盖样例生成、刷新和打包期模板校验。
- sidecar 打包依赖 `PyInstaller`，首次构建会慢一些。
- 大语料性能当前主要受关键词提取和导出写盘影响。

## 建议的开发节奏

1. 先跑 `bootstrap-python.ps1` 和 `bootstrap-frontend.ps1`
2. 日常修改时用 `npm run dev`
3. 提交前至少跑 `npm run lint`
4. 涉及引擎、workflow、存储或导出的改动先跑 `npm run test:engine`
5. 涉及官方样例、首次启动、sidecar 打包或样例导出链路的改动补跑 `npm run test:engine:full`
6. 涉及打包时补跑 `build-python-sidecar.ps1` 或 `tauri:build`
