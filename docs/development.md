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

- 只改前端、样式或文档：通常不需要 Python 引擎测试。
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

截至 `2026-04-28`，本地已验证或纳入最终验证清单：

- `npm run lint` 通过
- `npm run test --workspace apps/desktop` 通过
- `npm run test:engine` 通过
- `npm run test:engine:full` 通过
- `powershell -ExecutionPolicy Bypass -File .\scripts\build-python-sidecar.ps1` 通过
- `npm run build` 通过
- `npm run tauri:build --workspace apps/desktop` 通过，并已产出 NSIS installer

当前 Windows installer 输出位置：

```text
apps/desktop/src-tauri/target/release/bundle/nsis/TextFlow Studio_0.1.1_x64-setup.exe
```

当前测试重点在：

- 项目存储与工作区 CLI
- 导入与 workflow 主链
- workflow 节点目录和前后端 schema 一致性
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
