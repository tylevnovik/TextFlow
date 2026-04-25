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
```

或直接：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\test-engine.ps1
```

### 缩小官方样例规模用于测试

如果你只是在本地验证样例项目创建或 workflow smoke test，可以临时设置：

```powershell
$env:TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT = "120"
```

注意：

- 这个值必须是偶数。
- 样例创建会强制保持英中 `1:1`，所以奇数会直接报错。
- 测试结束后可以执行 `Remove-Item Env:TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT` 清理当前终端环境变量。

## 构建

### 刷新官方样例公开数据缓存

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\fetch-public-sample-data.ps1 -All
```

说明：

- 脚本会优先复用 `services/python-engine/app/public_sample_cache/` 中已经满足条件的真实公开数据缓存。
- 如果 `services/python-engine/.cache/public-source-raw/` 下已经放好了官方原始文件，builder 会优先从这些本地文件生成缓存，避免重复联网下载。
- 如果缓存缺失、版本过旧，或不满足每种语言至少 `10,000` 行的要求，脚本会从官方 Wikimedia、UN 和 OpenAlex 源重新抓取并规范化数据。
- 产出的 `manifest.json` 会记录缓存版本、数据来源、每种语言的行数和打包用校验摘要。

### 仅重建 Python sidecar

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-python-sidecar.ps1
```

产物目录：

```text
services/python-engine/dist/textflow-engine/
```

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

截至 `2026-04-25`，本地已验证或纳入最终验证清单：

- `npm run lint` 通过
- `npm run test --workspace apps/desktop` 通过
- `npm run test:engine` 通过
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
- Python 测试耗时约 3 分钟，适合在较完整改动后执行。
- sidecar 打包依赖 `PyInstaller`，首次构建会慢一些。
- 大语料性能当前主要受关键词提取和导出写盘影响。

## 建议的开发节奏

1. 先跑 `bootstrap-python.ps1` 和 `bootstrap-frontend.ps1`
2. 日常修改时用 `npm run dev`
3. 提交前至少跑 `npm run lint`
4. 涉及引擎、workflow、存储或导出的改动再跑 `npm run test:engine`
5. 涉及打包时补跑 `build-python-sidecar.ps1` 或 `tauri:build`
